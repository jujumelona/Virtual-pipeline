"""2D generation kits must be reproducible, source-only and See-through-targeted."""
from io import BytesIO
from pathlib import Path
from zipfile import ZipFile
import pytest
from PIL import Image
from tools.vts_see_through_only import composite_2d

ZIP_ROOT = Path(__file__).resolve().parents[1] / "docs/image_ai_kits_v2/zips"
MODES = ("live2d_bust_up", "live2d_upper", "live2d_full",
         "inochi2d_upper", "inochi2d_full")
FILES = ("face.zip",) + tuple(f"{m}__{a}.zip" for m in MODES
                                for a in ("hair", "outfit", "accessory"))

@pytest.mark.parametrize("filename", FILES)
def test_see_through_2d_zip_contract(filename):
    with ZipFile(ZIP_ROOT / filename) as archive:
        assert archive.testzip() is None
        assert len(archive.namelist()) == 14
        for name in archive.namelist():
            text = archive.read(name).decode("utf-8")
            assert text.startswith("【SEE_THROUGH_ONLY_2D_V1")
            assert "단독 그림을 See-through 전체 캐릭터 입력에 직접 주지 않는다" in text

def test_3d_zip_unmodified():
    with ZipFile(ZIP_ROOT / "3d__character.zip") as archive:
        assert "SEE_THROUGH_ONLY_2D_V1" not in archive.read("00_MASTER_FIRST.md").decode()

def _archive(path, *, opaque=False, size=(320, 320)):
    image = Image.new("RGBA", size, (0, 0, 0, 0) if not opaque else (255, 255, 255, 255))
    image.paste((255, 90, 40, 255), (80, 80, 140, 140))
    stream = BytesIO()
    image.save(stream, format="PNG")
    with ZipFile(path, "w") as z:
        z.writestr("outputs/master.png", stream.getvalue())
    return path

def test_three_registered_zip_masters_composite(tmp_path):
    a = {name: _archive(tmp_path / f"{name}.zip")
         for name in ("face", "outfit", "hair")}
    result = composite_2d(a["face"], a["outfit"], a["hair"], tmp_path / "result")
    assert Path(result["composite_png"]).is_file()
    assert result["manual_visual_review_required"]
    assert result["segmentation_provider"] == "see-through"

def test_refuse_opaque_and_misaligned_inputs(tmp_path):
    a = {name: _archive(tmp_path / f"{name}.zip")
         for name in ("face", "outfit", "hair")}
    a["face"] = _archive(tmp_path / "face.zip", opaque=True)
    with pytest.raises(ValueError, match="transparent background"):
        composite_2d(a["face"], a["outfit"], a["hair"], tmp_path / "bad1")
    a["face"] = _archive(tmp_path / "face.zip", size=(512, 512))
    with pytest.raises(ValueError, match="register artworks manually"):
        composite_2d(a["face"], a["outfit"], a["hair"], tmp_path / "bad2")


def test_explicit_psd2live_requires_a_completed_artwork_zip(tmp_path):
    from tools.vts_see_through_only import rig_see_through_artwork
    with pytest.raises(ValueError, match="completed See-through"):
        rig_see_through_artwork({"state": "failed"}, tmp_path)
    with pytest.raises(FileNotFoundError, match="layered PSD"):
        rig_see_through_artwork({
            "state": "artwork_ready_editor_rig_required",
            "package": str(tmp_path / "not-created.zip"),
        }, tmp_path)


def test_explicit_psd2live_reuses_validated_psd_without_gpu_split(tmp_path, monkeypatch):
    from tools.vts_see_through_only import rig_see_through_artwork
    import tools.vts_psd2live as psd2live
    input_zip = tmp_path / "layered.zip"
    with ZipFile(input_zip, "w") as archive:
        archive.writestr("avatar.psd", b"TEST_LAYERED_ARTWORK")
    calls = []
    def fake_prepare():
        calls.append("prepare")
    def fake_rig(artwork_zip, output, *, edition, scope):
        assert artwork_zip == input_zip
        assert edition == "free"
        assert scope == "upper"
        assert output == tmp_path / "rig" / "psd2live_result"
        calls.append("rig-existing-psd")
        return {"state": "psd2live_rigged_unverified",
                "moc3_generated": True, "package": str(tmp_path / "rigged.zip")}
    monkeypatch.setattr(psd2live, "prepare_psd2live", fake_prepare)
    monkeypatch.setattr(psd2live, "rig_existing_artwork_zip", fake_rig)
    result = rig_see_through_artwork({
        "state": "artwork_ready_editor_rig_required",
        "package": str(input_zip),
    }, tmp_path / "rig")
    assert calls == ["prepare", "rig-existing-psd"]
    assert result["moc3_generated"] is True


def test_see_through_notebook_has_separate_explicit_native_stage():
    import ast
    import json
    notebook_path = Path(__file__).resolve().parents[1] / (
        "notebooks/VTuber_SeeThrough_Only_Source_ZIPs.ipynb")
    notebook = json.loads(notebook_path.read_text(encoding="utf-8"))
    code = ["".join(cell["source"]) for cell in notebook["cells"]
            if cell["cell_type"] == "code"]
    for index, cell in enumerate(code):
        ast.parse(cell, filename=f"see-through-cell-{index}")
    assert len(code) == 7
    assert 'RIGGING = "artwork_only"' in code[-3]
    assert "rig_see_through_artwork(SEPARATION" in code[-3]
    assert "render_actual_native_moc3" in code[-2]
    assert "VERIFY_NATIVE_POSES = False" in code[-2]
    assert "files.download(str(PACKAGE))" in code[-1]


def _register_zip_anchors(archive_path, anchors):
    import json
    with ZipFile(archive_path, "a") as archive:
        archive.writestr("metadata/registration_anchors.json",
                         json.dumps({"anchors": anchors}))


def test_shared_landmarks_translate_layers_without_resizing(tmp_path):
    sources = {name: _archive(tmp_path / f"{name}.zip")
               for name in ("face", "hair", "outfit")}
    _register_zip_anchors(sources["outfit"], {"neck_joint": [155, 158]})
    _register_zip_anchors(sources["face"], {
        "neck_joint": [145, 158], "hairline_center": [145, 105]})
    _register_zip_anchors(sources["hair"], {"hairline_center": [135, 105]})
    report = composite_2d(
        sources["face"], sources["outfit"], sources["hair"], tmp_path / "merged")
    assert report["landmark_registration"]["face"]["translation_xy"] == [10, 0]
    assert report["landmark_registration"]["hair"]["translation_xy"] == [20, 0]
    assert report["visual_alignment_verified"] is False
    with Image.open(report["composite_png"]) as image:
        assert image.size == (320, 320)
        assert image.getpixel((150, 100))[3] != 0


def test_conflicting_anchors_fail_instead_of_warping_art(tmp_path):
    sources = {name: _archive(tmp_path / f"{name}.zip")
               for name in ("face", "hair", "outfit")}
    _register_zip_anchors(sources["outfit"], {
        "neck_joint": [155, 158], "second_point": [180, 130]})
    _register_zip_anchors(sources["face"], {
        "neck_joint": [145, 158], "second_point": [180, 130]})
    with pytest.raises(ValueError, match="inconsistent registration landmarks"):
        composite_2d(
            sources["face"], sources["outfit"], sources["hair"],
            tmp_path / "failed")


def test_anchor_translation_cannot_crop_opaque_pixels(tmp_path):
    sources = {name: _archive(tmp_path / f"{name}.zip")
               for name in ("face", "hair", "outfit")}
    _register_zip_anchors(sources["outfit"], {"neck_joint": [290, 160]})
    _register_zip_anchors(sources["face"], {"neck_joint": [60, 160]})
    with pytest.raises(ValueError, match="crop visible artwork"):
        composite_2d(
            sources["face"], sources["outfit"], sources["hair"],
            tmp_path / "failed")
