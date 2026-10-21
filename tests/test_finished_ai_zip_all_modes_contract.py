"""CPU-only contract for the existing-artwork-ZIP Colab entrypoint.

Do not treat these static tests as GPU inference or native animation proof.
"""
from __future__ import annotations
import ast
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
NOTEBOOK = ROOT / "notebooks" / "VTuber_Finished_AI_ZIP_All_Modes.ipynb"


def test_all_modes_notebook_has_compilable_python_cells():
    notebook = json.loads(NOTEBOOK.read_text(encoding="utf-8"))
    assert notebook["nbformat"] == 4
    code = ["".join(cell["source"]) for cell in notebook["cells"]
            if cell["cell_type"] == "code"]
    assert len(code) == 6
    for index, content in enumerate(code):
        ast.parse(content, filename=f"finished-zip-cell-{index}")


def test_finished_zip_is_consumed_without_regenerating_artwork():
    notebook = json.loads(NOTEBOOK.read_text(encoding="utf-8"))
    code = "\n".join("".join(cell.get("source", [])) for cell in notebook["cells"]
                     if cell["cell_type"] == "code")
    for required in (
        "files.upload()", "finished_artwork.zip", "inspect_large_ai_pack",
        "prepare_large_ai_pack", "process_completed_ai_2d_zip", "prepare_psd2live",
        "build_inochi2d", "inspect_native_inp", "run_isolated",
        "validate_vrm", "files.download(", "native_files_created",
    ):
        assert required in code, required
    for forbidden in ("write_prompt_package(", "build_prompts("):
        assert forbidden not in code, forbidden
    # Source-only Inochi BODY legitimately invokes See-through.
    # Pre-partitioned Live2D input must keep its authored PSD unchanged.
    assert "if not MODE.startswith('live2d'):" in code


def test_native_and_detached_paths_have_explicit_outcome():
    notebook = json.loads(NOTEBOOK.read_text(encoding="utf-8"))
    code = "\n".join("".join(c["source"]) for c in notebook["cells"]
                     if c["cell_type"] == "code")
    assert "3D 개별 헤어/의상" in code
    assert "ASSET=='body'" in code
    assert "manual_attachment_needed" in code
    assert "application_runtime_verified':False" in code
    assert "source_artwork/imported_parts.psd" in code
    assert "raise RuntimeError('네이티브 모델 누락')" in code


def test_free_body_is_not_forced_to_pro_in_all_modes():
    """FREE is a legitimate Cubism edition even for a body-only source ZIP."""
    notebook = json.loads(NOTEBOOK.read_text(encoding="utf-8"))
    cells = ["".join(cell["source"]) for cell in notebook["cells"]
             if cell["cell_type"] == "code"]
    selection, production = cells[1], cells[4]
    assert "EDITION='free' #@param ['free','pro']" in selection
    assert "FREE에서도 신체만 원화 제작/리깅 가능" in selection
    assert "edition=EDITION" in production
    assert "asset=ASSET" in production
    assert "process_completed_ai_2d_zip(" in production
    assert "EDITION='pro' #@param" not in selection


def test_no_global_license_or_accessory_anchor_selector():
    notebook = json.loads(NOTEBOOK.read_text(encoding="utf-8"))
    cells = ["".join(cell["source"]) for cell in notebook["cells"]
             if cell["cell_type"] == "code"]
    selection, validation, production = cells[1], cells[3], cells[4]
    assert "USAGE" not in "\n".join(cells)
    assert "ANCHOR" not in "\n".join(cells)
    assert "#@param ['corporation'" not in selection
    assert "'HEAD_TOP' #@param" not in selection
    assert "prepare_selected_mode('3d',prewarm_first_gpu=False)" in production
    assert "prepare_selected_mode('inochi2d',provided_2d_layers=True)" in production
    assert "commercial_usage=USAGE" not in production
    assert "resolve_accessory_placement(SOURCE,views['front'])" in validation
    assert "str(paths['front']),ATTACHMENT" in production
