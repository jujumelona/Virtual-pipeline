"""Accept raw image files from the Colab uploader; never ask for archives.

An internal ZIP adapts the validated images to the stable 2D builder contract.
Users provide only 27 individual PNGs. Original filenames, geometry and
alpha are validated before writing any generation-ready receipt.
"""
from __future__ import annotations

from io import BytesIO
from pathlib import Path
import zipfile

from PIL import Image
from vtuber_pipeline.prompt_contract import CANVAS_2D, LAYER_PARTS

MAX_IMAGE_BYTES = 32 * 1024 * 1024
MAX_TOTAL_BYTES = 256 * 1024 * 1024
EXPECTED = frozenset({"front_master.png"} | {name + ".png" for name, _ in LAYER_PARTS})


def prepare_2d_image_uploads(uploaded: dict[str, bytes], output_dir: str) -> tuple[str, str]:
    """Return validated master PNG and *internal* builder archive paths."""
    if not isinstance(uploaded, dict) or not uploaded:
        raise ValueError("2D PNG 이미지 업로드가 비어 있습니다")
    names = set(uploaded)
    missing = EXPECTED - names
    unexpected = names - EXPECTED
    if missing or unexpected:
        raise ValueError(
            "2D 이미지는 정확히 27장이어야 합니다. "
            f"빠진 파일: {sorted(missing)}; 잘못된 파일: {sorted(unexpected)}"
        )
    prepared = {}
    total = 0
    for name in sorted(EXPECTED):
        payload = uploaded[name]
        if not isinstance(payload, bytes) or not payload:
            raise ValueError(f"{name}: 비어 있거나 유효하지 않은 PNG")
        if len(payload) > MAX_IMAGE_BYTES:
            raise ValueError(f"{name}: 32MiB 이미지 크기 제한 초과")
        total += len(payload)
        if total > MAX_TOTAL_BYTES:
            raise ValueError("2D 입력 이미지 합계는 256MiB 이하로 준비하세요")
        try:
            with Image.open(BytesIO(payload)) as raw:
                if raw.format != "PNG":
                    raise ValueError(f"{name}: PNG 형식이 아닙니다")
                if raw.size != CANVAS_2D:
                    raise ValueError(
                        f"{name}: {CANVAS_2D[0]}x{CANVAS_2D[1]} 필수, "
                        f"실제 {raw.size[0]}x{raw.size[1]}"
                    )
                if name != "front_master.png" and "A" not in raw.getbands():
                    raise ValueError(f"{name}: 실제 RGBA 알파 채널이 필요합니다")
                raw.load()
                if name != "front_master.png":
                    from PIL import ImageStat

                    alpha = raw.getchannel("A")
                    histogram = alpha.histogram()
                    transparent = histogram[0]
                    visible = sum(histogram[1:])
                    if not visible:
                        raise ValueError(f"{name}: 완전히 투명한 레이어입니다")
                    if visible > CANVAS_2D[0] * CANVAS_2D[1] * 0.85:
                        raise ValueError(
                            f"{name}: 배경까지 불투명합니다. "
                            "캐릭터 파츠 밖은 진짜 투명(alpha=0)이어야 합니다"
                        )
                    if not transparent:
                        raise ValueError(f"{name}: 바깥 배경 투명 영역이 없습니다")
        except (OSError, Image.DecompressionBombError) as exc:
            raise ValueError(f"{name}: 잘못된 이미지 데이터: {exc}") from exc
        prepared[name] = payload

    folder = Path(output_dir)
    folder.mkdir(parents=True, exist_ok=True)
    master = folder / "front_master.png"
    master.write_bytes(prepared["front_master.png"])
    # This archive is an internal implementation detail. It is never an
    # uploaded/downloaded artifact and no user is asked to create a ZIP.
    internal = folder / "verified_layers.internal.zip"
    tmp = internal.with_suffix(".tmp")
    with zipfile.ZipFile(tmp, "w", compression=zipfile.ZIP_STORED) as archive:
        for name in sorted(EXPECTED - {"front_master.png"}):
            archive.writestr(name, prepared[name])
    tmp.replace(internal)
    return str(master), str(internal)
