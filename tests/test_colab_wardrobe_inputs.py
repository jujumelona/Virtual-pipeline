"""The new Colab selector treats outfit and accessories as shared assets.

Legacy wardrobe implementation stays isolated until its production route
is replaced after the common body contract and prompt work.
"""
import ast
import json
from pathlib import Path

from tools.colab_mode_ui import TOP_MODE_CHOICES, ASSET_KINDS, select_mode

ROOT=Path(__file__).resolve().parents[1]
NB=ROOT/"notebooks"/"VTuber_Commercial_Pipeline_Colab_v8.ipynb"


def code_cells():
    n=json.loads(NB.read_text(encoding="utf-8"))
    return ["".join(c["source"]) for c in n["cells"] if c["cell_type"]=="code"]


def test_shared_outfit_and_accessory_assets_across_all_mode_families():
    assert set(ASSET_KINDS) == {"body", "hair", "accessory", "outfit"}
    for mode in TOP_MODE_CHOICES:
        for kind in ("outfit", "accessory"):
            assert select_mode(mode, kind).asset_kind == kind


def test_removed_separate_wardrobe_ui_cannot_install_models_or_build():
    cells=code_cells()
    assert len(cells)==4
    for index, code in enumerate(cells):
        ast.parse(code,filename=f"colab_v8_code_{index}")
    joined="\n".join(cells)
    assert '["신체만", "헤어만", "액세서리만", "의상만"]' in joined
    for previous in ("ACCESSORY_SUBTYPE_OPTION", "WARDROBE_2D_BASE",
                     "costume.xwear", "prepare_vroid_dressup(",
                     "sheet_prepare_worker.py", "colab_mode_prepare.py",
                     "files.upload", "files.download"):
        assert previous not in joined


def test_readme_reserves_wardrobe_generation_for_followup_phase():
    r=(ROOT/"README.md").read_text(encoding="utf-8")
    assert "신체만" in r and "의상만" in r
    assert "후속 단계" in r
