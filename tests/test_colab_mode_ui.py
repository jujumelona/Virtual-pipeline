"""Colab native form architecture: one parent mode + mode-specific cells.

All visible choices are Colab #@param values that exist BEFORE the user runs
a cell. No JavaScript/ipywidgets popup and no confirmation-button contract.
"""
import ast
import json
from pathlib import Path

import pytest

from tools.colab_mode_ui import (
    MODE_LABELS, EDITION_LABELS, FRAMING_LABELS, QWEN_LABELS,
    ACCESSORY_LABELS, ANCHOR_LABELS, internal_scope,
    input_profile, refresh_qwen, selection_signature,
)

ROOT = Path(__file__).resolve().parents[1]
NB = ROOT / "notebooks/VTuber_Commercial_Pipeline_Colab_v8.ipynb"


def cells():
    nb = json.loads(NB.read_text(encoding="utf-8"))
    c = ["".join(cell["source"]) for cell in nb["cells"]
         if cell["cell_type"] == "code"]
    assert len(c) == 12
    return c


@pytest.mark.parametrize("edition,framing,expected", [
    ("free", "upper", "live2d_free"),
    ("pro", "full", "live2d_pro"),
    ("free", "full", "live2d_free"),
    ("pro", "upper", "live2d_pro"),
])
def test_live2d_is_parent_mode(edition, framing, expected):
    assert internal_scope("캐릭터 생성", "live2d", edition, "소품", "live2d") == expected
    assert set(EDITION_LABELS) == {"free", "pro"}
    assert framing in FRAMING_LABELS
    assert set(MODE_LABELS) == {"3d", "inochi2d", "live2d"}


def test_inactive_2d_options_stay_separate():
    assert internal_scope("캐릭터 생성", "3d", "free", "소품", "live2d") == "3d"
    assert internal_scope("캐릭터 생성", "inochi2d", "free", "소품", "live2d") == "inochi2d"
    assert internal_scope("액세서리 제작", "3d", "free", "소품", "live2d") == "3d"
    assert internal_scope("액세서리 제작", "3d", "free", "2D 교체 의상", "inochi2d") == "inochi2d"
    assert internal_scope("액세서리 제작", "3d", "free", "3D 교체 의상(XWear)", "live2d") == "wardrobe_handoff"
    assert input_profile("캐릭터 생성", "live2d", "소품", "sheets", True) == "live2d_artwork"
    assert "소품" in ACCESSORY_LABELS
    assert "AUTO" in ANCHOR_LABELS


def test_qwen_auto_modes():
    v = {"LIVE2D_QWEN": "auto", "LIVE2D_EDITION": "free"}
    refresh_qwen(v)
    assert v["LIVE2D_USE_QWEN"] is False
    v["LIVE2D_EDITION"] = "pro"
    refresh_qwen(v)
    assert v["LIVE2D_USE_QWEN"] is True
    v["LIVE2D_QWEN"] = "off"
    refresh_qwen(v)
    assert v["LIVE2D_USE_QWEN"] is False
    v["LIVE2D_QWEN"] = "on"
    refresh_qwen(v)
    assert v["LIVE2D_USE_QWEN"] is True
    assert set(QWEN_LABELS) == {"auto", "on", "off"}


def test_all_cells_compile_and_submode_settings_are_native_colab_forms():
    c = cells()
    for i, cell in enumerate(c):
        ast.parse(cell, filename=f"colab_cell_{i}")
    parent = c[1]
    assert '#@param ["live2d", "inochi2d", "3d", "accessory"]' in parent
    assert 'TOP_MODE = "live2d"' in parent
    assert '#@param ["free", "pro"]' not in parent
    assert 'ACCESSORY_SUBTYPE_OPTION' not in parent
    assert "choose_notebook_controls(" not in "\n".join(c)
    assert "render_notebook_controls(" not in "\n".join(c)
    assert "require_confirmed_selection(" not in "\n".join(c)
    assert "output.eval_js" not in "\n".join(c)
    for i, mode in [(2, "live2d"), (3, "inochi2d"), (4, "3d"), (5, "accessory")]:
        cell = c[i]
        assert "#@param" in cell
        assert f'globals().get("TOP_MODE") == "{mode}"' in cell
        assert 'else:' in cell
        assert f'MODE_DETAILS_SELECTED = TOP_MODE' in cell
    assert 'LIVE2D_EDITION_OPTION = "free" #@param' in c[2]
    assert 'INOCHI_INPUT_OPTION = "sheets" #@param' in c[3]
    assert 'THREE_D_MULTIVIEW_OPTION = True #@param' in c[4]
    assert 'ACCESSORY_SUBTYPE_OPTION = "소품" #@param' in c[5]


@pytest.mark.parametrize("upper,active_index,task,mode", [
    ("live2d", 2, "캐릭터 생성", "live2d"),
    ("inochi2d", 3, "캐릭터 생성", "inochi2d"),
    ("3d", 4, "캐릭터 생성", "3d"),
    ("accessory", 5, "액세서리 제작", "3d"),
])
def test_only_selected_mode_cell_sets_active_details(upper, active_index, task, mode, capsys):
    c = cells()
    scope = {}
    exec(compile(c[1], "select_parent", "exec"), scope)
    assert scope["TOP_MODE"] == "live2d"
    scope["TOP_MODE"] = upper
    scope["TASK"] = task
    scope["MODE"] = mode
    for i in range(2, 6):
        exec(compile(c[i], f"submode_{i}", "exec"), scope)
        if i < active_index:
            assert scope["MODE_DETAILS_SELECTED"] is None
    assert scope["MODE_DETAILS_SELECTED"] == upper
    assert scope["MODE_DETAILS_SNAPSHOT"] == selection_signature(scope)
    assert "생략" in capsys.readouterr().out or upper == "live2d"


def test_model_download_requires_matching_mode_detail_not_popup():
    c = cells()
    setup, upload, build = c[6:9]
    assert 'MODE_DETAILS_SELECTED' in setup
    assert 'MODE_DETAILS_SNAPSHOT' in setup
    assert setup.index('MODE_DETAILS_SELECTED') < setup.index('run([sys.executable')
    assert 'MODEL_DOWNLOAD_SELECTION = SELECTED_MODE' in setup
    assert 'selection_signature(globals())' in upload
    assert 'selection_signature(globals())' in build
    assert 'make_cubism_handoff(' in build
    assert "MODE_SELECTION_CONFIRMED" not in "\n".join(c)


def test_no_prompt_generator_in_notebook():
    content = "\n".join(cells())
    for forbidden in ("prepare_vts_notebook_brief", "write_vts_brief_package",
                      "FLUX.2 Klein", "VTS_SCOPE"):
        assert forbidden not in content


def test_readme_describes_static_submode_form():
    text = (ROOT/"README.md").read_text(encoding="utf-8")
    assert "Live2D" in text and "Inochi2D" in text
    assert "FREE" in text and "PRO" in text
    assert "pro_{upper|full}_appearance_master.png" in text
    assert "free_upper_master.png" in text
    assert "TOP_MODE" in text


def test_invalid_cubism_edition_fails():
    with pytest.raises(ValueError):
        internal_scope("캐릭터 생성", "live2d", "enterprise", "소품", "live2d")
