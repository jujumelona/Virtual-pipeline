"""Guard the 24 README-linked ZIPs against stale duplicate delivery locations."""
from pathlib import Path
from zipfile import ZipFile
import pytest

ROOT = Path(__file__).resolve().parents[1]
KITS = ROOT / "docs" / "image_ai_kits_v2"
MODES = ("live2d_bust_up", "live2d_upper", "live2d_full")
ASSETS = ("body", "hair", "outfit", "accessory")
BODY_CONTRACT = "2026-10-13 사용자 지정 BODY 최상위 제작 규칙"

@pytest.mark.parametrize("mode", MODES)
def test_live2d_body_is_replaced_at_readme_target_not_in_parallel_zip(mode):
    filename = f"{mode}__body.zip"
    listing = (KITS / "README.md").read_text(encoding="utf-8")
    assert f"zips/{filename}" in listing
    with ZipFile(KITS / "zips" / filename) as z:
        assert z.testzip() is None
        assert len(z.namelist()) == len(set(z.namelist())) == 14
        for name in ("00_MASTER_FIRST.md", "00_READ_FIRST.md", "02_ADVANCED_PARTS.md",
                     "03_MODE_RULES.md", "07_REVIEW_BEFORE_FINAL_ZIP.md",
                     "09_VISUAL_ART_QUALITY.md", "10_ANIME_STYLE.md"):
            content = z.read(name).decode("utf-8")
            assert BODY_CONTRACT in content, (filename, name)
        master = z.read("00_MASTER_FIRST.md").decode("utf-8")
        advanced = z.read("02_ADVANCED_PARTS.md").decode("utf-8")
        assert "U형" in master and "겨드랑이" in master
        assert "BODY_flat_proxy.png" in advanced
        assert "from PIL import Image, ImageDraw" in advanced

def test_live2d_delivery_remains_one_zip_per_mode_and_asset():
    zips = sorted((KITS / "zips").glob("*.zip"))
    assert len(zips) == 24
    for path in zips:
        assert "_V3" not in path.stem and "_FIXED" not in path.stem
    index = (KITS / "README.md").read_text(encoding="utf-8")
    for mode in MODES:
        for asset in ASSETS:
            assert f"zips/{mode}__{asset}.zip" in index
    root = (ROOT / "README.md").read_text(encoding="utf-8")
    assert "docs/image_ai_kits_v2/README.md" in root
