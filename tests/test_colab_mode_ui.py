"""FACE is a seventh independent top-level choice, without framing."""
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


def test_one_shared_face_plus_six_frwing_modes():
    assert tuple(TOP_MODE_CHOICES) == (
        "face", "live2d_bust_up", "live2d_upper", "live2d_full", "inochi2d_upper", "inochi2d_full", "3d")
    assert tuple(ASSET_KINDS) == ("face", "character", "body", "hair", "accessory", "outfit")
    assert select_mode("face", "face").framing == "head"
    valid={("face","face"),("3d","character"),("3d","accessory")}
    valid|={(mode,asset) for mode in TOP_MODE_CHOICES if mode not in ("face","3d")
            for asset in ("body","hair","outfit","accessory")}
    assert {select_mode(m,a).asset_kind for m,a in valid} == set(ASSET_KINDS)


@pytest.mark.parametrize("mode,family,framing", [
    ("live2d_bust_up", "live2d", "upper"),
    ("live2d_upper", "live2d", "upper"),
    ("live2d_full", "live2d", "full"),
    ("inochi2d_upper", "inochi2d", "upper"),
    ("inochi2d_full", "inochi2d", "full"),
    ("3d", "3d", "full"),
])
def test_mode_routes_are_exact(mode, family, framing):
    for asset in (("character","accessory") if mode=="3d" else ("body","hair","accessory","outfit")):
        selected = select_mode(mode, asset)
        assert (selected.family, selected.framing, selected.asset_kind) == (
            family, framing, asset)
        assert selected.as_dict()["schema"] == "vtuber/asset-selection-v1"


@pytest.mark.parametrize("mode", ["", "live2d", "inochi2d", "accessory", "unknown"])
def test_deprecated_modes_are_not_accepted(mode):
    with pytest.raises(ValueError):
        select_mode(mode, "face")


@pytest.mark.parametrize("asset", ["", "free", "pro", "automatic", "other"])
def test_deprecated_asset_modes_are_not_accepted(asset):
    with pytest.raises(ValueError):
        select_mode("live2d_upper", asset)


def test_static_native_colab_controls_are_only_two_selectors():
    codes = code_cells()
    assert len(codes) >= 9  # Four selection cells plus Live2D upload/build/download
    assert '#@param ["Live2D 바스트업", "Live2D 상반신", "Live2D 전신", "Inochi2D 상반신", "Inochi2D 전신", "3D"]' in codes[1]
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
    assert apply_submode(state, "live2d_upper", {"ASSET_KIND": "hair"})
    assert require_submode_config(state).asset_kind == "hair"
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
    assert "FACE 공통(구도 없음)" in text and "액세서리만" in text
    assert "VTuber_Finished_AI_ZIP_All_Modes.ipynb" in text
    assert "PSD2Live" in text and "MOC3" in text
    assert "미지원" in text and "방송" in text


def test_v8_live2d_real_native_rigging_is_executed_when_requested():
    """Regression: a completed image-AI ZIP must not silently stop at a PSD."""
    cells = code_cells()
    assert len(cells) >= 9
    assert 'EDITION = "free"' in cells[4]
    assert '완성 캐릭터 PNG 한 장' in cells[4]
    assert '신체만 ZIP은 PRO body를 선택하세요' not in cells[4]
    assert 'RIGGING = "artwork_only"' in cells[4]
    assert 'INPUT_KIND = "single_image"' in cells[4]
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


def test_v8_can_resume_existing_live2d_psd_zip_without_resplitting():
    cells = code_cells()
    assert '"existing_psd_zip"' in cells[4]
    assert '"existing_psd_zip"' in cells[5]
    assert "rig_existing_artwork_zip" in cells[7]
    assert 'if INPUT_KIND == "existing_psd_zip"' in cells[7]
    assert 'if DO_NATIVE_RIG:' in cells[7]
    assert '"reused_existing_psd": True' in cells[7]
    assert '"package": str(INPUT_FILE)' in cells[7]
    assert '재사용' in cells[7]
    assert "psd2live=DO_NATIVE_RIG" in cells[7]


def test_readme_live2d_production_matches_default_artwork_only():
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    cells = code_cells()
    assert 'RIGGING = "artwork_only"' in cells[4]
    assert "RIGGING=auto" in readme
    assert "자동 리깅을 기본 실행" not in readme
    assert "프로그램으로 만든 중립색 도형 베이스" not in readme
    assert "단색 마네킹 실루엣을 조립" not in readme
    assert "공식 Cubism Editor" in readme


def test_face_has_no_bustup_full_or_engine_selection():
    assert select_mode("face", "face").framing == "head"
    for mode in ("live2d_bust_up", "live2d_upper", "live2d_full",
                 "inochi2d_upper", "inochi2d_full", "3d"):
        with pytest.raises(ValueError, match="공통"):
            select_mode(mode, "face")
    for asset in ("hair", "outfit", "accessory"):
        with pytest.raises(ValueError, match="공통"):
            select_mode("face", asset)


def test_3d_never_requires_head_only_or_detached_hair_outfit():
    assert select_mode("3d","character").asset_label == "전체 캐릭터"
    for wrong in ("face","body","hair","outfit"):
        with pytest.raises(ValueError):
            select_mode("3d",wrong)


def test_2d_body_selection_reaches_native_rig_contract():
    """Live2D/Inochi2D can select a full BODY while 3D uses character."""
    from tools.colab_mode_ui import DISPLAY_TO_ASSET
    assert DISPLAY_TO_ASSET["신체만"] == "body"
    for mode in ("live2d_bust_up", "live2d_upper", "live2d_full",
                 "inochi2d_upper", "inochi2d_full"):
        assert select_mode(mode, DISPLAY_TO_ASSET["신체만"]).asset_kind == "body"
    with pytest.raises(ValueError):
        select_mode("3d", "body")
