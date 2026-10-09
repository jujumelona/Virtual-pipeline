"""Colab v8 clothing selector is disjoint from rigid accessory route."""
import ast
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
NB=ROOT/"notebooks"/"VTuber_Commercial_Pipeline_Colab_v8.ipynb"

def code_cells():
    notebook=json.loads(NB.read_text(encoding="utf-8"))
    return [("".join(x["source"])) for x in notebook["cells"]
            if x["cell_type"]=="code"]

def test_wardrobe_cells_compile_without_notebook_controlflow_errors():
    for index in (1,2,3,4):
        ast.parse(code_cells()[index],filename=f"colab_v8_code_{index}")

def test_wardrobe_is_accessory_subtype_not_falsely_static_bone_attachment():
    cells=code_cells()
    options=cells[1]
    uploads=cells[3]
    build=cells[4]
    assert 'ACCESSORY_SUBTYPE = "소품"' in options
    for subtype in ("2D 교체 의상","3D 교체 의상(XWear)"):
        assert subtype in options and subtype in uploads and subtype in build
    assert 'OUTFIT_2D_TARGET' in options
    assert 'outfit_variant.png' in uploads
    assert 'costume.xwear' in uploads
    assert 'sheet_prepare_worker.py' in build
    assert 'wardrobe_2d' in build
    assert 'inspect_garment_image' in uploads
    assert 'prepare_vroid_dressup(' in build
    assert 'generate(' in build
    # The generic static attach path must be the last accessory branch.
    assert build.index('prepare_vroid_dressup(')<build.index(
        'elif TASK == "액세서리 제작":\n    accessories'
    )

def test_wardrobe_3d_never_claims_complete_automatically_skinned_vrm():
    cells=code_cells()
    download=cells[2]
    assert 'if wardrobe_3d:' in download
    assert 'GPU를 설치하지 않습니다.' in download
    generation=cells[4]
    assert '착용 완료 VRM이 아닙니다' in generation
    assert 'prepare_vroid_dressup(' in generation

def test_readme_cites_correct_2d_and_3d_wardrobe_file_names():
    readme=(ROOT/"README.md").read_text(encoding="utf-8")
    for name in (
        "outfit_variant.png", "costume.xwear", "base_avatar.vrm",
        "vroid_dressup_handoff.zip",
        "garment_front_back_ref.png",
        "garment_side_views_ref.png",
        "garment_details_ref.png",
    ):
        assert name in readme
    assert "STATIC" not in readme or "static" in readme.lower()
