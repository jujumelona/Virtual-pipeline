"""Colab-native, finite lifetime VTuber generation. No Gradio or HTTP server.

Usage from a notebook cell:
    from tools.colab_native import generate
    RESULT_FILE = generate("live2d", "corporation")

Colab's file picker is the only interactive input. The notebook cell waits
for the isolated AI subprocess and returns or raises. Interrupting the cell
kills its process group (including spawned GPU model workers).
"""
from __future__ import annotations

from pathlib import Path
import re
import time
import uuid

WORK = Path("/content/vtuber_builder")
OUTPUT = WORK / "output"
MODES = ("inochi2d", "live2d", "3d", "accessory")
USAGES = ("corporation", "personalProfit", "personalNonProfit")
ANCHORS = (
    "HEAD_TOP", "FACE", "LEFT_EAR", "RIGHT_EAR", "NECK", "CHEST",
    "BACK", "LEFT_SHOULDER", "RIGHT_SHOULDER", "LEFT_HAND",
    "RIGHT_HAND", "LEFT_FOOT", "RIGHT_FOOT", "HIPS",
)
ACCESSORY_ANCHOR_OPTIONS = ("AUTO", "ALL", *ANCHORS)
# Classification is intentionally filename-based, not a claim that a vision
# model understood an uploaded accessory. Ambiguous names fail before CUDA.
ACCESSORY_ANCHOR_HINTS = (
    (("hat", "cap", "crown", "tiara", "hairpin", "ribbon", "모자", "왕관", "머리핀"), ("HEAD_TOP",)),
    (("glasses", "goggle", "eyewear", "안경", "고글"), ("FACE",)),
    (("earring", "귀걸이"), ("LEFT_EAR", "RIGHT_EAR")),
    (("necklace", "choker", "collar", "목걸이"), ("NECK",)),
    (("brooch", "badge", "브로치", "뱃지"), ("CHEST",)),
    (("backpack", "cape", "배낭", "망토"), ("BACK",)),
    (("shoulder", "어깨"), ("LEFT_SHOULDER", "RIGHT_SHOULDER")),
    (("glove", "bracelet", "장갑", "팔찌"), ("LEFT_HAND", "RIGHT_HAND")),
    (("shoe", "boot", "sock", "신발", "부츠"), ("LEFT_FOOT", "RIGHT_FOOT")),
    (("belt", "skirt", "허리띠", "벨트"), ("HIPS",)),
)


def _resolve_accessory_anchors(image_path: str, selected: str) -> tuple[str, ...]:
    """ALL expands positions; AUTO only resolves unambiguous filename hints."""
    if selected == "ALL":
        return ANCHORS
    if selected in ANCHORS:
        return (selected,)
    if selected != "AUTO":
        raise ValueError("지원하지 않는 액세서리 부착 범위: " + str(selected))
    filename = Path(image_path).stem.casefold()
    matches = [
        placements for keywords, placements in ACCESSORY_ANCHOR_HINTS
        if any(key in filename for key in keywords)
    ]
    unique = tuple(dict.fromkeys(anchor for group in matches for anchor in group))
    if len(matches) != 1 or not unique:
        raise ValueError(
            "자동 위치 판정 불가: " + Path(image_path).name
            + " — 파일명에 hat/glasses/earring/necklace/shoe 등 종류를 명시하거나 "
              "액세서리 위치를 직접 선택하세요."
        )
    return unique
IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".webp"}
MAX_IMAGE_BYTES = 32 * 1024 * 1024


def stop_legacy_server() -> None:
    """Retire only the previous notebook's Gradio process if still running."""
    import os
    import signal

    pid_file = WORK / "ui_server.pid"
    if not pid_file.is_file():
        return
    try:
        pid = int(pid_file.read_text(encoding="utf-8").strip())
        command = Path(f"/proc/{pid}/cmdline").read_bytes()
        if pid > 1 and b"/tools/colab_app.py" in command:
            try:
                os.killpg(pid, signal.SIGTERM)
            except (ProcessLookupError, PermissionError):
                os.kill(pid, signal.SIGTERM)
            print("이전 웹 UI 서버를 종료했습니다.", flush=True)
    except (ValueError, OSError):
        pass
    finally:
        pid_file.unlink(missing_ok=True)


def _stored_uploads(upload, folder: Path, *, images: bool, multiple: bool) -> list[str]:
    """Store bytes returned by the Colab uploader in one job-specific folder."""
    selected = upload()
    if not isinstance(selected, dict) or not selected:
        raise ValueError("파일 업로드가 취소되었습니다. 생성 작업은 시작하지 않았습니다.")
    if not multiple and len(selected) != 1:
        raise ValueError("캐릭터 생성에는 원본 이미지 한 장만 업로드하세요.")
    folder.mkdir(parents=True, exist_ok=True)
    paths = []
    for index, (name, payload) in enumerate(selected.items()):
        extension = Path(name).suffix.casefold()
        if images and extension not in IMAGE_EXTENSIONS:
            raise ValueError("지원하는 이미지: PNG/JPG/WEBP")
        if not images and extension != ".vrm":
            raise ValueError("기준 캐릭터 파일은 VRM이어야 합니다.")
        if not isinstance(payload, bytes) or not payload:
            raise ValueError(f"업로드 데이터가 비어 있습니다: {name}")
        if len(payload) > (MAX_IMAGE_BYTES if images else 1024 * 1024 * 1024):
            raise ValueError("업로드 파일 크기 제한 초과: " + name)
        # Retain a safe basename so AUTO can infer position per accessory;
        # never use user-controlled path separators inside output directories.
        stem = re.sub(r"[^0-9a-zA-Z가-힣_-]", "_", Path(name).stem)[:70]
        path = folder / f"input_{index:02d}_{stem}{extension}"
        path.write_bytes(payload)
        paths.append(str(path))
    return paths


def _existing_image(path: str, *, description: str) -> str:
    file = Path(path).expanduser().resolve()
    if not file.is_file() or file.suffix.casefold() not in IMAGE_EXTENSIONS:
        raise ValueError(f"{description} 파일이 없거나 이미지가 아닙니다: {path}")
    return str(file)


def _has_vrm_container(path: Path) -> bool:
    """Reject stale/truncated GLBs before selecting an accessory base.

    This is a cheap header/JSON preflight, NOT the product validator that
    checks humanoid bones, expressions, materials and skinning downstream.
    """
    import json
    import struct

    try:
        length = path.stat().st_size
        if length < 28 or length > 1024 * 1024 * 1024:
            return False
        with path.open("rb") as handle:
            header = handle.read(12)
            if len(header) != 12:
                return False
            magic, version, total = struct.unpack("<4sII", header)
            if magic != b"glTF" or version != 2 or total != length:
                return False
            chunk_header = handle.read(8)
            if len(chunk_header) != 8:
                return False
            chunk_length, chunk_type = struct.unpack("<II", chunk_header)
            if chunk_type != 0x4E4F534A or chunk_length < 4 or chunk_length > length - 20:
                return False
            payload = json.loads(handle.read(chunk_length).rstrip(b" \t\r\n\x00"))
        if not isinstance(payload, dict):
            return False
        extensions = payload.get("extensions")
        used = payload.get("extensionsUsed")
        vrm = extensions.get("VRMC_vrm") if isinstance(extensions, dict) else None
        return (
            isinstance(vrm, dict)
            and vrm.get("specVersion") == "1.0"
            and isinstance(used, list)
            and "VRMC_vrm" in used
        )
    except (OSError, ValueError, TypeError, KeyError, struct.error, UnicodeDecodeError):
        return False


def _latest_avatar() -> str | None:
    saved = WORK / "avatar.vrm"
    if saved.is_file() and _has_vrm_container(saved):
        return str(saved)
    if OUTPUT.is_dir():
        candidates = sorted(
            OUTPUT.glob("**/avatar.vrm"),
            key=lambda p: p.stat().st_mtime if p.is_file() else 0,
            reverse=True,
        )
        from tools.colab_download_contract import checked_avatar
        for candidate in candidates:
            try:
                checked_avatar(candidate, OUTPUT)
                if _has_vrm_container(candidate):
                    return str(candidate)
            except (OSError, ValueError):
                continue
    return None


def _build_arguments(mode, usage, upload, job_folder, *, image_path,
                     full_body, texture_size, rigging_provider,
                     accessory_anchor, accessory_base_path,
                     reference_face_path="", accessory_image_paths=(),
                     layers_zip_path="", reference_back_path="",
                     reference_left_path="", reference_right_path="",
                     sheet_zip_path=""):
    if mode in ("inochi2d", "live2d", "3d"):
        if sheet_zip_path:
            from tools.sheet_input_loader import inspect_sheet_archive
            sheet = Path(sheet_zip_path).expanduser().resolve(strict=True)
            inspect_sheet_archive(str(sheet),mode)
            if mode in ("inochi2d","live2d"):
                return mode, [str(sheet),usage,"__sheet_pack__"]
            return "avatar", [str(sheet),usage,"__sheet_pack__",None,None,
                              True,int(texture_size),None,None,rigging_provider]
        front = (
            _existing_image(image_path, description="캐릭터 원본")
            if image_path else _stored_uploads(
                upload, job_folder / "front", images=True, multiple=False,
            )[0]
        )
        if mode in ("inochi2d", "live2d"):
            if layers_zip_path:
                archive = Path(layers_zip_path).expanduser().resolve(strict=True)
                if archive.suffix.casefold() != ".zip":
                    raise ValueError("2D artwork package must be a .zip file")
                return mode, [front, usage, str(archive)]
            if __import__("os").environ.get("VTUBER_2D_SUPPLIED_LAYERS") == "1":
                raise ValueError("2D layered mode requires the 24 outfit-free PNG parts ZIP")
            return mode, [front, usage]
        face = None
        if full_body:
            print("고품질 다중 참조 모드: 동일 캐릭터의 정면 얼굴 확대 이미지를 업로드하세요.", flush=True)
            face = (
                _existing_image(reference_face_path, description="정면 얼굴 참조")
                if reference_face_path else _stored_uploads(
                    upload, job_folder / "face", images=True, multiple=False,
                )[0]
            )
        # Additional view inputs are optional advanced pipeline inputs, not
        # part of the one-image default path.
        back = (_existing_image(reference_back_path, description="후면")
                if reference_back_path else None)
        left = (_existing_image(reference_left_path, description="좌측")
                if reference_left_path else None)
        right = (_existing_image(reference_right_path, description="우측")
                 if reference_right_path else None)
        return "avatar", [
            front, usage, None, face, back, bool(full_body),
            int(texture_size), left, right, rigging_provider,
        ]

    if accessory_anchor not in ACCESSORY_ANCHOR_OPTIONS:
        raise ValueError("지원하지 않는 액세서리 부착 위치: " + str(accessory_anchor))
    latest = None if accessory_base_path else _latest_avatar()
    if accessory_base_path:
        base = str(Path(accessory_base_path).expanduser().resolve(strict=True))
        if Path(base).suffix.casefold() != ".vrm":
            raise ValueError("기준 캐릭터 파일은 .vrm이어야 합니다.")
    elif latest:
        base = None
    else:
        print("기준 VRM을 먼저 업로드하세요.", flush=True)
        base = _stored_uploads(
            upload, job_folder / "base", images=False, multiple=False,
        )[0]
    print("액세서리 이미지를 한 번에 1~8장 업로드하세요.", flush=True)
    images = (
        [_existing_image(str(path), description="액세서리 이미지")
         for path in accessory_image_paths]
        if accessory_image_paths else _stored_uploads(
            upload, job_folder / "accessories", images=True, multiple=True,
        )
    )
    if len(images) > 8:
        raise ValueError("한 번에 생성 가능한 액세서리는 최대 8개입니다.")
    placements = [(img, anchor)
                  for img in images
                  for anchor in _resolve_accessory_anchors(img, accessory_anchor)]
    if len(placements) > 8 * len(ANCHORS):
        raise ValueError("액세서리 부착 작업이 최대 개수를 초과했습니다.")
    print(
        f"액세서리 이미지 {len(images)}장 → 부착 {len(placements)}회 (모드: {accessory_anchor})",
        flush=True,
    )
    slots = [
        value for img, anchor in placements
        for value in (img, anchor, "", 0.0, 0.0, 0.0, 1.0)
    ]
    return "accessory", [bool(latest), base, latest, *slots]


def _event_printer(event):
    """Show EVERY worker log line in the Colab cell, unfiltered and uncut.

    generation.log remains on disk. A fatal compiler/linker diagnostic is
    usually before the final 'cc failed' line, so do not grep or take tails.
    """
    kind = event[0]
    if kind == "stage":
        _, name, status, detail = event
        print(f"[단계] {name}: {status} {detail}", flush=True)
    elif kind == "progress":
        fraction, description = event[1:3]
        print(f"[진행] {100.0 * float(fraction):.0f}% {description}", flush=True)
    elif kind == "log":
        # Preserve original newlines, blank lines, long linker commands,
        # stderr tracebacks, pip warnings, and compiler diagnostics.
        message = str(event[1])
        print(message, end="" if message.endswith("\n") else "\n", flush=True)
    else:
        print(repr(event), flush=True)


def generate(
    mode: str = "3d",
    usage: str = "corporation",
    *,
    image_path: str = "",
    full_body: bool = False,
    texture_size: int = 2048,
    rigging_provider: str = "canonical",
    accessory_anchor: str = "AUTO",
    accessory_base_path: str = "",
    reference_face_path: str = "",
    accessory_image_paths: tuple[str, ...] = (),
    layers_zip_path: str = "",
    reference_back_path: str = "",
    reference_left_path: str = "",
    reference_right_path: str = "",
    sheet_zip_path: str = "",
    upload=None,
    runner=None,
) -> str | None:
    """One Colab cell, one generation, one result. No persistent server.

    The optional uploader/runner arguments permit CPU-only contract tests
    without importing Google Colab or downloading checkpoints.
    """
    if mode not in MODES:
        raise ValueError(f"지원하지 않는 제작 모드: {mode}")
    if usage not in USAGES:
        raise ValueError(f"지원하지 않는 상업 사용 범위: {usage}")
    if int(texture_size) not in (1024, 2048):
        raise ValueError("텍스처 해상도는 1024 또는 2048이어야 합니다.")
    if upload is None:
        def upload():
            from google.colab import files
            return files.upload()
    if runner is None:
        from tools.colab_generation_process import run_isolated
        runner = run_isolated
    job_folder = WORK / "notebook_inputs" / uuid.uuid4().hex
    if sheet_zip_path:
        print("[sheet] 고정 격자 입력 · 파츠 분할 및 AI 업스케일 예정", flush=True)
    elif mode in ("inochi2d", "live2d") and layers_zip_path:
        print("[layers] supplied artwork archive verified",flush=True)
    elif mode != "accessory":
        print("기존 캐릭터 입력 이미지를 사용해 제작합니다.", flush=True)
    else:
        print("액세서리 제작 모드", flush=True)
    worker_mode, args = _build_arguments(
        mode, usage, upload, job_folder, image_path=image_path,
        full_body=full_body, texture_size=texture_size,
        rigging_provider=rigging_provider, accessory_anchor=accessory_anchor,
        accessory_base_path=accessory_base_path,
        reference_face_path=reference_face_path,
        accessory_image_paths=accessory_image_paths,
        layers_zip_path=layers_zip_path,
        reference_back_path=reference_back_path,
        reference_left_path=reference_left_path,
        reference_right_path=reference_right_path,
        sheet_zip_path=sheet_zip_path,
    )
    print("생성 시작. 이 셀의 ■ 중지를 누르면 모델 작업까지 종료합니다.", flush=True)
    try:
        result = runner(worker_mode, args, on_event=_event_printer)
    except KeyboardInterrupt:
        print("사용자가 제작 셀을 중단했습니다. 생성 프로세스 종료 요청을 처리했습니다.", flush=True)
        raise
    status, details, output = result[:3]
    print("결과:", status, flush=True)
    if details:
        # Never hide the beginning of a traceback or the first linker error.
        print(str(details), flush=True)
    # A callback may return an intermediate file even after a failed build.
    # Never turn that file into a successful Colab generation/download result.
    # Match the same failure markers used by colab_generation_process.
    failed = str(status).startswith("❌") or " 제작 실패" in str(status)
    if failed:
        print("제작 실패: 결과 파일을 완성 모델로 제공하지 않습니다.", flush=True)
        return None
    if not output or not Path(str(output)).is_file():
        return None
    output = str(Path(output).resolve())
    if worker_mode == "avatar":
        from tools.colab_download_contract import save_latest_avatar
        stable = save_latest_avatar(output, OUTPUT, WORK / "avatar.vrm")
        print("최신 VRM:", stable, flush=True)
    print("생성 파일:", output, flush=True)
    print("Colab 왼쪽 파일 탐색기에서 열거나 별도 다운로드 셀을 실행하세요.", flush=True)
    return output
