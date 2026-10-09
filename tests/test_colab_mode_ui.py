"""User-facing Colab mode hierarchy and option visibility contract (no GPU)."""
import ast
import json
from pathlib import Path

import pytest

from tools.colab_mode_ui import (
    MODE_LABELS, EDITION_LABELS, FRAMING_LABELS, QWEN_LABELS,
    ACCESSORY_LABELS, ANCHOR_LABELS, internal_scope, input_profile, refresh_qwen,
    selection_signature, require_confirmed_selection, choose_notebook_controls,
    _browser_form_js,
)

ROOT = Path(__file__).resolve().parents[1]
NB = ROOT / "notebooks" / "VTuber_Commercial_Pipeline_Colab_v8.ipynb"


@pytest.mark.parametrize("edition,scope,expected", [
    ("free", "upper", "live2d_free"),
    ("pro", "full", "live2d_pro"),
    ("free", "full", "live2d_free"),
    ("pro", "upper", "live2d_pro"),
])
def test_live2d_has_two_cubism_subeditions(edition, scope, expected):
    assert "live2d" in MODE_LABELS
    assert "vts_free" not in MODE_LABELS and "vts_pro" not in MODE_LABELS
    assert internal_scope("캐릭터 생성", "live2d", edition, "소품", "live2d") == expected
    assert "FREE" in EDITION_LABELS["free"]
    assert "PRO" in EDITION_LABELS["pro"]
    assert scope in FRAMING_LABELS


def test_free_and_pro_have_same_parent_input_profile():
    for edition in EDITION_LABELS:
        assert input_profile("캐릭터 생성", "live2d", "소품", "sheets", True) == "live2d_artwork"


def test_legacy_modes_and_accessories_unchanged():
    assert internal_scope("캐릭터 생성", "3d", "free", "소품", "live2d") == "3d"
    assert internal_scope("캐릭터 생성", "inochi2d", "free", "소품", "live2d") == "inochi2d"
    assert internal_scope("액세서리 제작", "3d", "free", "소품", "live2d") == "3d"
    assert internal_scope("액세서리 제작", "live2d", "free", "2D 교체 의상", "inochi2d") == "inochi2d"
    assert internal_scope("액세서리 제작", "3d", "free", "3D 교체 의상(XWear)", "live2d") == "wardrobe_handoff"
    assert len(ACCESSORY_LABELS) == 3
    assert "AUTO" in ANCHOR_LABELS and "HIPS" in ANCHOR_LABELS


def test_qwen_auto_is_free_off_pro_on():
    d = {"LIVE2D_EDITION": "free", "LIVE2D_QWEN": "auto"}
    refresh_qwen(d)
    assert d["LIVE2D_USE_QWEN"] is False
    d["LIVE2D_EDITION"] = "pro"
    refresh_qwen(d)
    assert d["LIVE2D_USE_QWEN"] is True
    d["LIVE2D_QWEN"] = "off"
    refresh_qwen(d)
    assert d["LIVE2D_USE_QWEN"] is False
    d["LIVE2D_QWEN"] = "on"
    refresh_qwen(d)
    assert d["LIVE2D_USE_QWEN"] is True
    assert set(QWEN_LABELS) == {"auto", "on", "off"}


def test_notebook_has_task_scoped_controls_without_prompt_creation():
    nb = json.loads(NB.read_text(encoding="utf-8"))
    cells = ["".join(c["source"]) for c in nb["cells"] if c["cell_type"] == "code"]
    assert len(cells) == 8
    for cell in cells:
        ast.parse(cell)
    select, setup, upload, build = cells[1:5]
    assert 'TASK = "캐릭터 생성"' in select
    assert 'TASK = "캐릭터 생성" #@param' not in select
    assert "require_confirmed_selection(globals())" in setup
    assert "require_confirmed_selection(globals())" in upload
    assert "require_confirmed_selection(globals())" in build
    assert "MODEL_DOWNLOAD_SELECTION = CONFIRMED_SELECTION" in setup
    assert "choose_notebook_controls(globals())" in select
    assert 'MODE = "3d"' in select
    assert "choose_notebook_controls(globals())" in select
    assert '"vts_free"' not in select and '"vts_pro"' not in select
    assert "vts_notebook_brief" not in select
    assert "write_vts_brief_package" not in "\n".join(cells)
    assert "prepare_vts_notebook_brief" not in "\n".join(cells)
    assert "VTS_SCOPE" not in "\n".join(cells)
    assert 'MODE == "live2d"' in upload
    assert "LIVE2D_EDITION" in setup and "LIVE2D_EDITION" in build
    assert 'edition=LIVE2D_EDITION,scope=LIVE2D_FRAMING' in build
    assert 'TASK == "캐릭터 생성" and MODE == "live2d"' in build
    assert "ACCESSORY_SUBTYPE = \"소품\" #@param" not in select
    assert 'MODE = "3d" #@param' not in select


def test_readme_is_external_prompt_reference_and_explains_all_scopes():
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    assert "LIVE2D_FRAMING" in readme
    assert "VTS_SCOPE" in readme  # documented as old variable, not UI control
    assert "ACCESSORY_SUBTYPE" in readme
    assert "pro_{upper|full}_appearance_master.png" in readme
    assert "pro_{upper|full}_base_master.png" in readme
    assert "pro_{upper|full}_hair_variant.png" in readme
    assert "pro_{upper|full}_outfit_variant.png" in readme
    assert "free_upper_master.png" in readme
    assert "free_full_master.png" in readme


def test_bad_edition_rejected():
    with pytest.raises(ValueError):
        internal_scope("캐릭터 생성", "live2d", "enterprise", "소품", "live2d")


def _values(**overrides):
    d = {
        "TASK": "캐릭터 생성", "MODE": "live2d",
        "USAGE": "personalNonProfit", "LIVE2D_EDITION": "free",
        "LIVE2D_FRAMING": "upper", "LIVE2D_QWEN": "auto",
        "LIVE2D_USE_QWEN": False, "EXISTING_IMAGE_PATH": "",
        "ACCESSORY_SUBTYPE": "소품", "OUTFIT_2D_TARGET": "live2d",
        "ACCESSORY_ANCHOR": "AUTO",
        "ACCESSORY_BASE_VRM_PATH": "", "WARDROBE_2D_BASE_ZIP_PATH": "",
        "WARDROBE_XWEAR_PATH": "", "MULTI_REFERENCE_3D": True,
        "TWO_D_INPUT": "sheets", "MODE_SELECTION_CONFIRMED": False,
    }
    d.update(overrides)
    return d


def test_run_all_does_not_download_models_before_explicit_confirmation():
    vals = _values()
    with pytest.raises(RuntimeError, match="② 설정 미확정"):
        require_confirmed_selection(vals)
    vals["MODE_SELECTION_SNAPSHOT"] = selection_signature(vals)
    vals["MODE_SELECTION_CONFIRMED"] = True
    assert require_confirmed_selection(vals) == vals["MODE_SELECTION_SNAPSHOT"]
    vals["LIVE2D_FRAMING"] = "full"
    with pytest.raises(RuntimeError, match="다시 누르세요"):
        require_confirmed_selection(vals)
    assert vals["MODE_SELECTION_CONFIRMED"] is False


def test_task_switch_changes_active_signature():
    vals = _values()
    before = selection_signature(vals)
    vals.update(TASK="액세서리 제작", ACCESSORY_SUBTYPE="소품")
    after = selection_signature(vals)
    assert after != before
    # Changing hidden Live2D values while working on accessories must
    # not invalidate the unrelated accessory selection.
    vals["LIVE2D_EDITION"] = "pro"
    assert selection_signature(vals) == after


def test_notebook_has_confirmation_guard_before_download_and_upload():
    nb = json.loads(NB.read_text(encoding="utf-8"))
    cells = ["".join(c["source"]) for c in nb["cells"] if c["cell_type"] == "code"]
    selection, setup, upload, build = cells[1:5]
    assert '#@param ["캐릭터 생성", "액세서리 제작"]' not in selection
    assert "choose_notebook_controls(globals())" in selection
    assert "② 설정 확정" in selection
    for code in (setup, upload, build):
        assert "require_confirmed_selection(globals())" in code
    assert setup.index("require_confirmed_selection(globals())") < setup.index("run(command")
    assert upload.index("require_confirmed_selection(globals())") < upload.index("files.upload()")
    assert build.index("require_confirmed_selection(globals())") < build.index("make_cubism_handoff(")



def test_colab_browser_picker_is_a_blocking_promise_and_stays_task_scoped():
    js = _browser_form_js(_values())
    assert js.startswith("new Promise((resolve, reject) => {")
    assert "submit.addEventListener('click'" in js
    assert "resolve(result)" in js
    assert "visible('ACCESSORY_SUBTYPE', !character)" in js
    assert "visible('LIVE2D_EDITION', live2d)" in js
    assert "window.setTimeout" not in js
    assert "run(command" not in js


def test_browser_selection_returns_values_before_cell_completes():
    selected = _values()
    selected.pop("MODE_SELECTION_CONFIRMED")
    selected.pop("LIVE2D_USE_QWEN")
    selected.pop("MODE_SELECTION_SNAPSHOT", None)
    selected.update(MODE="live2d", LIVE2D_EDITION="pro", LIVE2D_FRAMING="full")
    captured = []

    def fake_browser(js):
        captured.append(js)
        return {key: selected[key] for key in (
            "TASK", "MODE", "LIVE2D_EDITION", "LIVE2D_FRAMING", "LIVE2D_QWEN",
            "TWO_D_INPUT", "MULTI_REFERENCE_3D", "ACCESSORY_SUBTYPE",
            "ACCESSORY_ANCHOR", "OUTFIT_2D_TARGET", "USAGE",
            "EXISTING_IMAGE_PATH", "ACCESSORY_BASE_VRM_PATH",
            "WARDROBE_2D_BASE_ZIP_PATH", "WARDROBE_XWEAR_PATH",
        )}

    live = _values()
    snapshot = choose_notebook_controls(live, evaluate=fake_browser)
    assert len(captured) == 1
    assert live["MODE_SELECTION_CONFIRMED"] is True
    assert snapshot == selection_signature(live)
    assert live["MODE"] == "live2d"
    assert live["LIVE2D_EDITION"] == "pro"
    assert live["LIVE2D_USE_QWEN"] is True


def test_invalid_browser_choice_does_not_confirm_or_trigger_fallback():
    live = _values()
    with pytest.raises(RuntimeError, match="올바르지"):
        choose_notebook_controls(live, evaluate=lambda js: {"TASK": "캐릭터 생성"})
    assert live["MODE_SELECTION_CONFIRMED"] is False
