"""The production notebook UI uses five top-level modes and a shared asset selector."""
import ast
import json
from pathlib import Path

import pytest

from tools.colab_mode_ui import (
    ASSET_KINDS, TOP_MODE_CHOICES, apply_submode, begin_mode_selection,
    require_submode_config, select_mode, selection_signature,
)

ROOT = Path(__file__).resolve().parents[1]
NOTEBOOK = ROOT / "notebooks/VTuber_Commercial_Pipeline_Colab_v8.ipynb"


def code_cells():
    notebook = json.loads(NOTEBOOK.read_text(encoding="utf-8"))
    cells = ["".join(c["source"]) for c in notebook["cells"] if c["cell_type"] == "code"]
    for index, cell in enumerate(cells):
        ast.parse(cell, filename=f"notebook-cell-{index}")
    return cells


def test_five_top_modes_and_four_shared_assets():
    assert tuple(TOP_MODE_CHOICES) == (
        "live2d_upper", "live2d_full", "inochi2d_upper", "inochi2d_full", "3d")
    assert tuple(ASSET_KINDS) == ("body", "hair", "accessory", "outfit")
    assert {select_mode(m, a).asset_kind for m in TOP_MODE_CHOICES
            for a in ASSET_KINDS} == set(ASSET_KINDS)


@pytest.mark.parametrize("mode,family,framing", [
    ("live2d_upper", "live2d", "upper"),
    ("live2d_full", "live2d", "full"),
    ("inochi2d_upper", "inochi2d", "upper"),
    ("inochi2d_full", "inochi2d", "full"),
    ("3d", "3d", "full"),
])
def test_mode_routes_are_exact(mode, family, framing):
    for asset in ASSET_KINDS:
        selected = select_mode(mode, asset)
        assert (selected.family, selected.framing, selected.asset_kind) == (
            family, framing, asset)
        assert selected.as_dict()["schema"] == "vtuber/asset-selection-v1"


@pytest.mark.parametrize("mode", ["", "live2d", "inochi2d", "accessory", "unknown"])
def test_deprecated_modes_are_not_accepted(mode):
    with pytest.raises(ValueError):
        select_mode(mode, "body")


@pytest.mark.parametrize("asset", ["", "free", "pro", "automatic", "other"])
def test_deprecated_asset_modes_are_not_accepted(asset):
    with pytest.raises(ValueError):
        select_mode("live2d_upper", asset)


def test_static_native_colab_controls_are_only_two_selectors():
    codes = code_cells()
    assert len(codes) >= 9  # Four selection cells plus Live2D upload/build/download
    assert '#@param ["Live2D 상반신", "Live2D 전신", "Inochi2D 상반신", "Inochi2D 전신", "3D"]' in codes[1]
    assert '#@param ["신체만", "헤어만", "액세서리만", "의상만"]' in codes[2]
    assert "MODE_CONFIG_APPLIED" in codes[2]
    assert "require_submode_config(globals())" in codes[3]
    assert all("#@param" not in code for code in (codes[0], codes[3]))


def test_no_legacy_splitters_or_their_installs_in_runtime_cells():
    joined = "\n".join(code_cells()[:4])  # Later Live2D cells intentionally run production
    prohibited = (
        "vts_setup", "See-through", "see_through", "SAM", "sam2",
        "FLUX", "Qwen", "qwen", "split_layer", "activate_2d_environment",
        "MODEL_DOWNLOAD", "LIVE2D_EDITION_OPTION", "FREE", "PRO",
        "ACCESSORY_SUBTYPE", "TWO_D_INPUT", "MULTI_REFERENCE_3D",
        "psd2live", "pip install", "runpy", "colab_mode_prepare",
    )
    # The four top-level selector cells remain UI-only; production is isolated in ⑤~⑨.
    for forbidden in prohibited:
        assert forbidden not in joined


def test_shared_submode_must_be_reapplied_after_parent_change():
    state = {"TOP_MODE": "live2d_upper"}
    begin_mode_selection(state)
    assert state["ASSET_KIND"] is None
    assert apply_submode(state, "live2d_upper", {"ASSET_KIND": "body"})
    assert require_submode_config(state).asset_kind == "body"
    state["TOP_MODE"] = "inochi2d_full"
    with pytest.raises(RuntimeError):
        require_submode_config(state)
    begin_mode_selection(state)
    assert apply_submode(state, "live2d_upper", {"ASSET_KIND": "hair"}) is False
    assert apply_submode(state, "inochi2d_full", {"ASSET_KIND": "outfit"})
    assert selection_signature(state) == ("inochi2d_full", "outfit")


def test_readme_explains_real_import_and_native_rig_scope():
    text = (ROOT / "README.md").read_text(encoding="utf-8")
    assert "Live2D 상반신" in text and "Inochi2D 전신" in text
    assert "신체만" in text and "액세서리만" in text
    assert "VTuber_Finished_AI_ZIP_All_Modes.ipynb" in text
    assert "PSD2Live" in text and "MOC3" in text
    assert "미지원" in text and "방송" in text


def test_v8_live2d_real_native_rigging_is_executed_when_requested():
    """Regression: a completed image-AI ZIP must not silently stop at a PSD."""
    cells = code_cells()
    assert len(cells) >= 9
    assert 'EDITION = "pro"' in cells[4]
    assert 'RIGGING = "auto"' in cells[4]
    assert 'DO_NATIVE_RIG' in cells[4]
    assert 'prepare_psd2live()' in cells[6]
    assert 'psd2live=DO_NATIVE_RIG' in cells[7]
    assert 'psd2live=False' not in cells[7]
    assert 'result.get("moc3_generated")' in cells[7]
    for filename in (".moc3", ".model3.json", ".cmo3"):
        assert filename in cells[7]
    assert 'metadata/psd2live_bridge.json' in cells[7]
    assert 'files.download' in cells[8]
    # The first four cells must remain side-effect-free selectors.
    assert "prepare_psd2live" not in "\n".join(cells[:4])
