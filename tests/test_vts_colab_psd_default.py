"""Live2D Colab notebook must preserve PSD-first input and no prewrite side effects."""
import ast
import json
from pathlib import Path

NOTEBOOK = Path(__file__).resolve().parents[1] / "notebooks" / "VTuber_Commercial_Pipeline_Colab_v8.ipynb"


def _source():
    cells = json.loads(NOTEBOOK.read_text(encoding="utf-8"))["cells"]
    codes = ["".join(c["source"]) for c in cells if c["cell_type"] == "code"]
    for i, code in enumerate(codes):
        ast.parse(code, filename=f"colab_v8_cell_{i}")
    return codes


def test_defaults_are_single_character_png_and_artwork_only():
    source = _source()
    choice = next(c for c in source if 'INPUT_KIND = "single_image"' in c)
    assert 'RIGGING = "artwork_only"' in choice
    assert 'DO_NATIVE_RIG = RIGGING == "auto"' in choice


def test_upload_rejects_extension_and_empty_payload_before_write():
    upload = next(c for c in _source() if "def _upload_one(label, slot):" in c)
    assert upload.index('expected_suffix = ".png"') < upload.index("output.write_bytes(raw)")
    assert upload.index("len(raw) == 0") < upload.index("output.write_bytes(raw)")
    assert upload.index("len(raw) == 0") < upload.index("destination_dir.mkdir(")
    assert 'slot == "reference"' in upload


def test_existing_psd_zip_can_be_reused_without_native_rigging():
    production = next(c for c in _source() if "rig_existing_artwork_zip" in c)
    assert 'if DO_NATIVE_RIG:' in production
    assert '"reused_existing_psd": True' in production
    assert '"package": str(INPUT_FILE)' in production
    assert 'if not DO_NATIVE_RIG:\n        raise ValueError' not in production
    assert 'required = {' in production and 'if not DO_NATIVE_RIG:' in production


def test_readme_does_not_recommend_native_rigging_for_existing_psd_zip():
    readme = (NOTEBOOK.parents[1] / "README.md").read_text(encoding="utf-8")
    section = readme.split("### 이미 받은 PSD 결과 ZIP을 다시 분해하지 않고 재사용하기", 1)[1]
    section = section.split("### 사용하지 않는 것", 1)[0]
    assert "RIGGING=artwork_only, INPUT_KIND=existing_psd_zip" in section
    assert "원래 바이트" in section
    assert "RIGGING=auto를 명시적으로 선택" in section
    assert "완성 캐릭터 PNG 한 장" in section
