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


def _latest_avatar() -> str | None:
    saved = WORK / "avatar.vrm"
    if saved.is_file():
        with saved.open("rb") as handle:
            if saved.stat().st_size > 20 and handle.read(4) == b"glTF":
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
                return str(candidate)
            except (OSError, ValueError):
                continue
    return None


def _build_arguments(mode, usage, upload, job_folder, *, image_path,
                     full_body, texture_size, rigging_provider,
                     accessory_anchor, accessory_base_path):
    if mode in ("inochi2d", "live2d", "3d"):
        front = (
            _existing_image(image_path, description="캐릭터 원본")
            if image_path else _stored_uploads(
                upload, job_folder / "front", images=True, multiple=False,
            )[0]
        )
        if mode in ("inochi2d", "live2d"):
            return mode, [front, usage]
        face = None
        if full_body:
            print("고품질 다중 참조 모드: 동일 캐릭터의 정면 얼굴 확대 이미지를 업로드하세요.", flush=True)
            face = _stored_uploads(
                upload, job_folder / "face", images=True, multiple=False,
            )[0]
        # Additional view inputs are optional advanced pipeline inputs, not
        # part of the one-image default path.
        return "avatar", [
            front, usage, None, face, None, bool(full_body),
            int(texture_size), None, None, rigging_provider,
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
    images = _stored_uploads(
        upload, job_folder / "accessories", images=True, multiple=True,
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
    """Show concise notebook progress; entire raw output is kept in job log."""
    kind = event[0]
    if kind == "stage":
        _, name, status, detail = event
        print(f"[단계] {name}: {status} {detail}", flush=True)
    elif kind == "progress":
        fraction, description = event[1:3]
        print(f"[진행] {100.0 * float(fraction):.0f}% {description}", flush=True)
    elif kind == "log":
        # pip often prints a nonfatal "ERROR: pip's dependency resolver..."
        # despite returning 0; git checkout HEAD notes may contain "error"
        # inside commit titles. Neither is a model failure.
        lines = []
        for line in str(event[1]).splitlines():
            stripped = line.strip()
            if not stripped or stripped.startswith(
                ("ERROR: pip's dependency resolver", "HEAD is now at",
                 "Not uninstalling ", "Can't uninstall ")
            ):
                continue
            meaningful = (
                stripped.startswith(("Traceback (most recent call last):",
                                     "Error:", "ERROR:", "RuntimeError:",
                                     "ImportError:", "FileNotFoundError:",
                                     "subprocess.CalledProcessError:",
                                     "/usr/bin/ld:", "/usr/bin/ld.gold:",
                                     "ld:", "ld.lld:", "collect2:"))
                or any(phrase in stripped.casefold() for phrase in (
                    "undefined reference", "cannot find -l", "cannot find library",
                    "dso missing from command line", "file format not recognized",
                    "linker command failed", "fatal error:", "linker error",
                    "error: /usr/bin/cc failed", "native_build.log"))
                or "[setup]" in stripped and "FAILED" in stripped
                or "[inochi-sdk]" in stripped and "unavailable" in stripped
                or re.search(r"(worker-import-smoke-ok|flux-transformers-hub-import-ok|실패|준비 완료)", stripped)
            )
            if meaningful:
                lines.append(stripped)
        for line in lines[-3:]:
            print("[작업] " + line[:280], flush=True)


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
    print("캐릭터 사진 한 장을 선택하세요." if mode != "accessory"
          else "액세서리 제작 모드", flush=True)
    worker_mode, args = _build_arguments(
        mode, usage, upload, job_folder, image_path=image_path,
        full_body=full_body, texture_size=texture_size,
        rigging_provider=rigging_provider, accessory_anchor=accessory_anchor,
        accessory_base_path=accessory_base_path,
    )
    print("생성 시작. 이 셀의 ■ 중지를 누르면 모델 작업까지 종료합니다.", flush=True)
    try:
        result = runner(worker_mode, args, on_event=_event_printer)
    except KeyboardInterrupt:
        print("사용자가 제작 셀을 중단했습니다. 생성 프로세스 종료 요청을 처리했습니다.", flush=True)
        raise
    status, details, output = result[:3]
    print("결과:", status, flush=True)
    if details and ("실패" in str(status) or "❌" in str(status)):
        print(str(details)[-2200:], flush=True)
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
