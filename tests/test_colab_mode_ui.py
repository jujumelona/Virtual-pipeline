"""User-facing Colab mode hierarchy and option visibility contract (no GPU)."""
import ast
import json
from pathlib import Path

import pytest

from tools.colab_mode_ui import (
    MODE_LABELS, EDITION_LABELS, FRAMING_LABELS, QWEN_LABELS,
    ACCESSORY_LABELS, ANCHOR_LABELS, internal_scope, input_profile, refresh_qwen,
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
    assert 'TASK = "캐릭터 생성" #@param ["캐릭터 생성", "액세서리 제작"]' in select
    assert 'MODE = "3d"' in select
    assert "render_notebook_controls(globals())" in select
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
