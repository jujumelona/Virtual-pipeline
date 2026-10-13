"""Protect the contents of all 20 external 2D image-AI instruction ZIPs.

Production output ZIP checks are exercised independently from importer reporting.
"""
from io import BytesIO
from pathlib import Path
from zipfile import ZipFile, ZIP_DEFLATED

import pytest
from PIL import Image

from tools.validate_image_ai_artwork_zip import validate

ROOT = Path(__file__).resolve().parents[1]
KITS = ROOT / "docs" / "image_ai_kits_v2"
MODES_2D = ("live2d_bust_up", "live2d_upper", "live2d_full",
            "inochi2d_upper", "inochi2d_full")
ASSETS = ("body", "hair", "outfit", "accessory")
REQUIRED = ("00_MASTER_FIRST.md", "00_DELIVERY_AND_RECHECK.md",
            "04_OUTPUT_FILES.md", "07_REVIEW_BEFORE_FINAL_ZIP.md")
MARKER = "2D 결과 ZIP 레이어 정확성 사전 차단"


@pytest.mark.parametrize("mode", MODES_2D)
@pytest.mark.parametrize("asset", ASSETS)
def test_artwork_instruction_zip_includes_real_preflight_code(mode, asset):
    path = KITS / "zips" / f"{mode}__{asset}.zip"
    script = (ROOT / "tools/validate_image_ai_artwork_zip.py").read_text(encoding="utf-8")
    contract = (KITS / "source/ARTWORK_LAYER_ORDER_CONTRACT.md").read_text(encoding="utf-8")
    with ZipFile(path) as archive:
        assert archive.testzip() is None
        assert len(archive.namelist()) == len(set(archive.namelist())) == 14
        text = {name: archive.read(name).decode("utf-8") for name in REQUIRED}
    assert all(MARKER in body for body in text.values())
    assert contract.strip() in text["04_OUTPUT_FILES.md"]
    assert script.strip() in text["04_OUTPUT_FILES.md"]
    assert f"validate_artwork_zip.py {mode}__{asset}__ARTWORK.zip" in text["04_OUTPUT_FILES.md"]
    assert "layer_order.txt" in text["00_MASTER_FIRST.md"]
    delivery = text["00_DELIVERY_AND_RECHECK.md"]
    assert "검사 실행 불가 또는 FAIL 상태면 완료라고 선언하지 않는다" in delivery
    assert "구조 통과와 별도로 원화·합성 미술 검수를 계속한다" in delivery


def _image_bytes(mode, size=(320, 320)):
    im = Image.new(mode, size, (0, 0, 0, 0) if mode == "RGBA" else (240, 240, 240))
    if mode == "RGBA":
        for x in range(40, 130):
            for y in range(50, 160):
                im.putpixel((x, y), (255, 70, 40, 255))
    out = BytesIO()
    im.save(out, format="PNG")
    return out.getvalue()


def _archive(tmp_path, order, extra=None, edition="pro"):
    path = tmp_path / "ARTWORK.zip"
    entries = {
        "outputs/master.png": _image_bytes("RGB"),
        "isolated_parts/part_one.png": _image_bytes("RGBA"),
        "layer_order.txt": order.encode("utf-8"),
    }
    if extra:
        entries.update(extra)
    with ZipFile(path, "w", ZIP_DEFLATED) as archive:
        for filename, data in entries.items():
            archive.writestr(filename, data)
    return path


def test_valid_artwork_result_passes(tmp_path):
    source = _archive(tmp_path, "isolated_parts/part_one.png\n")
    validate(source, "pro")


@pytest.mark.parametrize(
    ("lines", "extra", "expected"),
    [
        ("isolated_parts/not_there.png\n", None, "listed_but_missing_png"),
        ("isolated_parts/part_one.png\nisolated_parts/part_one.png\n",
         None, "duplicate="),
        ("isolated_parts/part_one.png\n",
         {"isolated_parts/extra.png": _image_bytes("RGBA")},
         "png_not_in_layer_order"),
        ("part_one.png\n", None, "layer_order mismatch"),
    ],
)
def test_incorrect_layer_order_is_never_accepted(tmp_path, lines, extra, expected):
    result = _archive(tmp_path, lines, extra)
    with pytest.raises(ValueError, match=expected):
        validate(result, "pro")


def test_same_canvas_is_required(tmp_path):
    source = _archive(
        tmp_path,
        "isolated_parts/part_one.png\n",
        {"isolated_parts/part_one.png": _image_bytes("RGBA", (400, 400))},
    )
    with pytest.raises(ValueError, match="mode/canvas mismatch"):
        validate(source, "pro")
