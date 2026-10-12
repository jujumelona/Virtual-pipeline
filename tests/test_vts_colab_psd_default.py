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
