"""Build a non-rigged, model-template-first handoff for licensed Cubism PRO.

Cubism Editor performs template application, CMO3 authoring, and MOC3 export.
This tool neither reverse-engineers CMO3 nor claims to automate the editor.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import shutil
import zipfile

FRAMES = {"bust_up", "upper", "full"}
PART_TEMPLATES = (
    {"name": "face", "required": True, "use": "Face shape, eye whites/irises/lashes, brows and mouth"},
    {"name": "head_hair", "required": True, "use": "Front, side, back and twin-tail hair; separate roots and tips"},
    {"name": "body_outfit", "required": True, "use": "Neck, shoulders, collar, floating sleeves and arms"},
    {"name": "dna_accessories", "required": False, "use": "Distinct rigid capsule, DNA helix and flexible cables"},
)
PARAMETERS = (
    "ParamAngleX", "ParamAngleY", "ParamAngleZ",
    "ParamBodyAngleX", "ParamBodyAngleY", "ParamBodyAngleZ",
    "ParamEyeLOpen", "ParamEyeROpen", "ParamEyeBallX", "ParamEyeBallY",
    "ParamMouthOpenY", "ParamMouthForm", "ParamBreath",
)
EDITOR_GUIDE = """# Cubism PRO — template-first handoff

이 ZIP은 **리깅된 모델이 아닙니다.** 원본 PSD와 Cubism PRO 작업 계획입니다.

1. 데스크톱 Cubism Editor PRO 5.3 정식판에서 avatar.psd를 열어 파츠를 확인합니다.
   눈 흰자·홍채·속눈썹, 입안·윗입술·아랫입술, 얼굴·목, 머리카락의
   앞/옆/뒤/트윈테일, 의상, DNA 장식이 실제 독립 레이어여야 합니다.
   누락된 파츠는 원화 단계에서 수정합니다. AI 추론으로 성공을 선언하지 않습니다.
2. 모델링 > 자동 메시 생성(Automatic Mesh generator)에서 아트메시를 만듭니다.
   템플릿이 이미 유효한 메시를 가지고 있다면 재생성으로 기존 변형을 손상시키지 마세요.
3. 모델링 > 모델 템플릿 > 템플릿 적용(Apply template)을 선택합니다.
   에디터에 있는 공식 템플릿이나 사용 권한이 있는 CMO3를 선택하세요.
   ZIP 내 templates/source.cmo3가 있으면 'CMO3 파일에서 선택'으로 열 수 있습니다.
4. Layout에서 기준 얼굴/목/어깨를 먼저 정렬하고 Preview에서 아트메시를 수동 대응시킵니다.
   얼굴→몸→헤어→장식 순서로 부분 적용해 불필요한 전신 매핑을 피합니다.
   동일 ID 파라미터는 필요 시 '같은 ID 덮어쓰기'를 설정하고 중복 물리 그룹을 확인하세요.
5. 가려진 피부/두피의 빈 공간, 좌우 눈 깜빡임, 입 개폐·발음,
   ±30도~±45도 얼굴 회전, 목/어깨 연결, 헤어 물리 충돌을 실제로 검사합니다.
   DNA 캡슐 본체는 강체처럼, 헬릭스 링/전선은 각기 다른 디포머로 조정합니다.
   템플릿에 없는 헬릭스는 **추가 아트메시 및 수동 리깅이 필요**합니다.
6. 결과를 새로운 .cmo3로 저장하고 에디터의 공식 MOC3(.model3.json,
   텍스처, 필요한 physics3.json)로 내보냅니다. 출력 파일과 앱 동작을 검사합니다.
   PRO의 텍스처 아틀라스 구성은 실제 크기/개수/가독성에 따라 선택합니다.

**불합격 조건:** 레이어 오염/누락, 빈 공간, 목 분리, 눈·입 미작동,
헤어/캡슐 물리 깨짐, 템플릿 이름만 있고 리깅 미적용, 실물 MOC3 미검증.
원본 PSD와 원본 템플릿은 변경하지 마세요.

2026-10-23 참고: Cubism 5.4 alpha 편집 API의 사용 기한은
2026-10-18에 종료되었습니다. 5.3 정식판에서 외부 편집 API가
자동 리깅을 지원한다고 가정하거나 그 API에 의존하지 마세요.
"""


def _psd_header(archive: zipfile.ZipFile, member: zipfile.ZipInfo) -> dict:
    with archive.open(member, "r") as stream:
        header = stream.read(26)
    if len(header) != 26 or header[:4] != b"8BPS" or int.from_bytes(header[4:6], "big") != 1:
        raise ValueError("CUBISM_PRO_PSD_HEADER_INVALID: expected Photoshop PSD v1")
    height = int.from_bytes(header[14:18], "big")
    width = int.from_bytes(header[18:22], "big")
    channels = int.from_bytes(header[12:14], "big")
    depth = int.from_bytes(header[22:24], "big")
    if not (1 <= width <= 30000 and 1 <= height <= 30000
            and 1 <= channels <= 56 and depth in (8, 16, 32)):
        raise ValueError("CUBISM_PRO_PSD_DIMENSIONS_INVALID")
    # Header inspection does not prove PSD layer quality or Photoshop import.
    return {"width": width, "height": height, "channels": channels,
            "depth": depth, "layer_structure_verified": False}


def _unique_member(archive: zipfile.ZipFile) -> zipfile.ZipInfo:
    entries = [m for m in archive.infolist() if not m.is_dir()]
    names = [m.filename for m in entries]
    if len(names) != len(set(names)):
        raise ValueError("CUBISM_PRO_DUPLICATE_ZIP_MEMBERS")
    if any(name.startswith("/") or "\\" in name or ".." in Path(name).parts for name in names):
        raise ValueError("CUBISM_PRO_UNSAFE_ZIP_MEMBER")
    psds = [m for m in entries if m.filename.lower().endswith(".psd")]
    if len(psds) != 1:
        raise ValueError("CUBISM_PRO_EXPECTS_ONE_PSD: artwork ZIP must contain one PSD")
    if psds[0].file_size < 26:
        raise ValueError("CUBISM_PRO_PSD_TOO_SMALL")
    return psds[0]


def build_cubism_pro_handoff(artwork_zip: Path, output_zip: Path, *,
                            frame: str = "upper",
                            template_cmo3: Path | None = None) -> dict:
    """Create a portable PSD + template work order; never emit fictional CMO3/MOC3."""
    if frame not in FRAMES:
        raise ValueError("CUBISM_PRO_FRAME_INVALID")
    artwork_zip = Path(artwork_zip).expanduser().resolve(strict=True)
    output_zip = Path(output_zip).expanduser().resolve()
    if artwork_zip == output_zip:
        raise ValueError("CUBISM_PRO_INPUT_OUTPUT_COLLISION")
    if not zipfile.is_zipfile(artwork_zip):
        raise ValueError("CUBISM_PRO_ARTWORK_ZIP_INVALID")
    template = None
    if template_cmo3 is not None:
        template = Path(template_cmo3).expanduser().resolve(strict=True)
        if template.suffix.lower() != ".cmo3" or template.stat().st_size < 16:
            raise ValueError("CUBISM_PRO_TEMPLATE_MUST_BE_CMO3")
    if output_zip.exists():
        raise FileExistsError("CUBISM_PRO_OUTPUT_ALREADY_EXISTS: " + str(output_zip))
    output_zip.parent.mkdir(parents=True, exist_ok=True)
    try:
        with zipfile.ZipFile(artwork_zip, "r") as source:
            member = _unique_member(source)
            psd = _psd_header(source, member)
            if source.testzip() is not None:
                raise ValueError("CUBISM_PRO_CORRUPT_INPUT_ZIP")
            plan = {
                "schema": "vtuber/cubism-pro-template-handoff-v1",
                "state": "awaiting_cubism_pro_editor_template_application",
                "source_psd_member": member.filename,
                "frame": frame,
                "psd_header": psd,
                "template_strategy": "official_model_template_reuse",
                "template_included": template is not None,
                "part_templates": list(PART_TEMPLATES),
                "target_parameters": list(PARAMETERS),
                "editor_required": True,
                "template_applied": False,
                "cmo3_generated": False,
                "moc3_generated": False,
                "native_runtime_verified": False,
                "artwork_layer_structure_verified": False,
                "studio_tracking_verified": False,
            }
            with zipfile.ZipFile(output_zip, "w", zipfile.ZIP_DEFLATED,
                                 allowZip64=True) as dest:
                with source.open(member) as src, dest.open("avatar.psd", "w", force_zip64=True) as dst:
                    shutil.copyfileobj(src, dst, length=1024 * 1024)
                if template is not None:
                    dest.write(template, "templates/source.cmo3")
                dest.writestr("cubism_pro/rig_transfer_plan.json",
                              json.dumps(plan, ensure_ascii=False, indent=2))
                dest.writestr("cubism_pro/START_HERE.md", EDITOR_GUIDE)
    except BaseException:
        output_zip.unlink(missing_ok=True)
        raise
    if not zipfile.is_zipfile(output_zip):
        raise RuntimeError("CUBISM_PRO_OUTPUT_NOT_ZIP")
    return {"state": "awaiting_cubism_pro_editor_template_application",
            "package": str(output_zip), "editor_required": True,
            "psd_header_verified": True,
            "layer_structure_verified": False,
            "template_included": template is not None,
            "moc3_generated": False, "native_runtime_verified": False}


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Prepare a Cubism PRO template-first PSD ZIP")
    parser.add_argument("--artwork-zip", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--frame", choices=sorted(FRAMES), default="upper")
    parser.add_argument("--template-cmo3", type=Path, default=None)
    options = parser.parse_args(argv)
    result = build_cubism_pro_handoff(options.artwork_zip, options.output,
                                      frame=options.frame,
                                      template_cmo3=options.template_cmo3)
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
