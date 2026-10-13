"""Offline synthetic regression for the canonical four Live2D broadcast ZIP migration."""
from pathlib import Path
from zipfile import ZipFile
import importlib.util
import pytest

HERE = Path(__file__).resolve().parents[1]
module_path = HERE / "tools" / "repair_broadcast_bustup_briefs.py"
spec = importlib.util.spec_from_file_location("broadcast_briefs", module_path)
assert spec and spec.loader
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)

NAMES = (
    "00_MASTER_FIRST.md", "00_DELIVERY_AND_RECHECK.md", "00_READ_FIRST.md",
    "01_COMMON_RULES.md", "02_ADVANCED_PARTS.md", "03_MODE_RULES.md",
    "04_OUTPUT_FILES.md", "05_OFFICIAL_REFERENCES.md",
    "06_ADVANCED_OFFICIAL_COMMUNITY.md", "07_REVIEW_BEFORE_FINAL_ZIP.md",
    "08_PRACTICAL_TIPS.md", "09_VISUAL_ART_QUALITY.md",
    "10_ANIME_STYLE.md", "11_OFFICIAL_IMAGE_EXAMPLES.md",
)

def sample(tmp_path):
    path = tmp_path / "source.zip"
    with ZipFile(path, "w") as archive:
        for name in NAMES:
            archive.writestr(name, "# " + name + "\n52~61% 옛 구도\n완성 원화 먼저\n")
    return path

@pytest.mark.parametrize("asset", m.ASSETS)
def test_canonical_broadcast_zip_remains_valid_and_has_new_guide(tmp_path, asset):
    source = sample(tmp_path)
    dest = tmp_path / "corrected.zip"
    m.rewrite_zip(source, dest, asset=asset, replacements=[])
    with ZipFile(dest) as archive:
        assert archive.testzip() is None
        assert len(archive.namelist()) == len(set(archive.namelist())) == 14
        docs = {name: archive.read(name).decode("utf-8") for name in NAMES}
    assert "배 바로 위" in docs["00_MASTER_FIRST.md"]
    assert "52~61%" not in docs["03_MODE_RULES.md"]
    assert "https://www.live2d.com/en/learn/sample/" in docs["00_MASTER_FIRST.md"]
    assert "BODY_flat_proxy.png" in docs["07_REVIEW_BEFORE_FINAL_ZIP.md"]
    if asset == "body":
        assert "BODY_flat_proxy.png는 최종 불합격" in docs["02_ADVANCED_PARTS.md"]

def test_corrupt_input_does_not_produce_fake_corrected_zip(tmp_path):
    source = tmp_path / "invalid.zip"
    with ZipFile(source, "w") as archive:
        archive.writestr("only.md", "missing required files")
    dest = tmp_path / "output.zip"
    with pytest.raises(ValueError, match="14-MD"):
        m.rewrite_zip(source, dest, asset="body", replacements=[])
    assert not dest.exists()

def test_rerun_does_not_double_prepend_top_priority_instructions(tmp_path):
    source = sample(tmp_path)
    dest = tmp_path / "first.zip"
    m.rewrite_zip(source, dest, asset="body", replacements=[])
    with pytest.raises(ValueError, match="duplicate broadcast upgrade marker"):
        m.rewrite_zip(dest, tmp_path / "second.zip", asset="body", replacements=[])
