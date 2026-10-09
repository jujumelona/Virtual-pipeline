"""Optional raw input path takes outfit-free parts; high-quality sheet mode takes ZIP."""
from io import BytesIO
import zipfile

from PIL import Image
import pytest

from tools import colab_input_images as inputs


def _make_png(rgba=(0, 0, 0, 0), *, size=(64, 96), opaque_layer=True):
    image = Image.new("RGBA", size, rgba)
    if opaque_layer:
        from PIL import ImageDraw
        ImageDraw.Draw(image).rectangle((20, 20, 30, 45), fill=(90, 25, 75, 255))
    payload = BytesIO()
    image.save(payload, format="PNG")
    return payload.getvalue()


@pytest.fixture
def small_png_set(monkeypatch):
    monkeypatch.setattr(inputs, "CANVAS_2D", (64, 96))
    return {name: _make_png() for name in inputs.EXPECTED}


def test_21_neutral_pngs_are_verified_and_packed_internally(tmp_path, small_png_set):
    master, internal = inputs.prepare_2d_image_uploads(small_png_set, str(tmp_path))
    assert Image.open(master).size == (64, 96)
    with zipfile.ZipFile(internal) as z:
        assert set(z.namelist()) == inputs.EXPECTED - {"front_master.png"}
        assert len(z.namelist()) == 20
    assert set(tmp_path.glob("*")) == {tmp_path / "front_master.png",
                                        tmp_path / "verified_layers.internal.zip"}


def test_missing_or_misnamed_png_rejected_before_any_archive(tmp_path, small_png_set):
    small_png_set.pop("eye_left_white.png")
    with pytest.raises(ValueError, match="eye_left_white.png"):
        inputs.prepare_2d_image_uploads(small_png_set, str(tmp_path))
    assert not list(tmp_path.iterdir())


def test_wrong_size_and_non_rgba_rejected(tmp_path, small_png_set):
    small_png_set["brow_left.png"] = _make_png(size=(80, 96))
    with pytest.raises(ValueError, match="2048|64x96"):
        inputs.prepare_2d_image_uploads(small_png_set, str(tmp_path))

    small_png_set["brow_left.png"] = _make_png(opaque_layer=False)
    with pytest.raises(ValueError, match="완전히 투명"):
        inputs.prepare_2d_image_uploads(small_png_set, str(tmp_path))

    png = BytesIO()
    Image.new("RGB", (64, 96), "white").save(png, "PNG")
    small_png_set["brow_left.png"] = png.getvalue()
    with pytest.raises(ValueError, match="RGBA"):
        inputs.prepare_2d_image_uploads(small_png_set, str(tmp_path))


def test_readme_is_the_only_colab_prompt_source():
    import json
    from pathlib import Path

    root = Path(__file__).resolve().parents[1]
    readme = (root / "README.md").read_text(encoding="utf-8")
    notebook = json.loads((root / "notebooks" /
                           "VTuber_Commercial_Pipeline_Colab_v8.ipynb").read_text())
    code = "\n".join("".join(c["source"]) for c in notebook["cells"]
                     if c["cell_type"] == "code")
    assert "## 모드별 이미지 생성 — 영구 베이스 캐릭터와 교체형 의상 분리" in readme
    assert "sheet_body_base.png" in readme
    assert "outfit_variant.png" in readme
    assert "front_master.png" in readme
    assert "hair_variant.png" in readme
    assert "sheet_front_back.png" in readme
    assert "sheet_side_views.png" in readme
    assert "sheet_eye_left.png" in readme
    assert "sheet_eye_right.png" in readme
    assert "sheet_mouth.png" in readme
    assert "sheet_arms_hands.png" in readme
    assert "character_2d_sheet_pack.zip" in readme
    assert "character_3d_sheet_pack.zip" in readme
    assert "build_prompts(" not in code
    assert "write_prompt_package" not in code
    assert "Identity(" not in code
    assert "HAIR_COLOR =" not in code
    assert "store_uploaded_zip(" in code
    assert "sheet_zip_path=" in code
    assert "files.upload()" in code


def test_every_external_2d_layer_name_has_a_valid_rig_semantic():
    """All README-listed PNGs must map to real z-order, not crash after upload."""
    from vtuber_pipeline.two_d.build import KNOWN
    from vtuber_pipeline.common.part_taxonomy import z_order

    actual = {name.removesuffix(".png") for name in inputs.EXPECTED
              if name != "front_master.png"}
    assert len(actual) == 20
    semantic = [KNOWN.get(name, name.replace("_", ".")) for name in sorted(actual)]
    assert len(set(semantic)) == 20
    assert all(isinstance(z_order(part), int) for part in semantic)


def test_generated_colab_2d_layer_pack_resolves_to_all_real_parts(tmp_path, monkeypatch):
    """No SAM/FLUX fallback when all user images are complete and registered."""
    from vtuber_pipeline.two_d.build import _layers
    from vtuber_pipeline.common.schemas import SourceSet

    monkeypatch.setattr(inputs, "CANVAS_2D", (256, 256))
    uploaded = {}
    for name in inputs.EXPECTED:
        image = Image.new("RGBA", (256, 256), (0, 0, 0, 0))
        if name != "front_master.png":
            from PIL import ImageDraw
            ImageDraw.Draw(image).rectangle((90, 90, 120, 130),
                                            fill=(90, 100, 110, 255))
        else:
            image.paste((90, 100, 110, 255), (65, 20, 191, 220))
        buffer = BytesIO()
        image.save(buffer, "PNG")
        uploaded[name] = buffer.getvalue()
    master, archive = inputs.prepare_2d_image_uploads(uploaded, str(tmp_path))
    source = SourceSet(mode="live2d", front_image=master,
                       user_layers_zip=archive, output_dir=str(tmp_path / "rig"))
    result = _layers(source, tmp_path / "resolved")
    assert result is not None
    assert len(result.parts) == 20
    assert all(part.hidden_fill_mask_png is None for part in result.parts)
    assert len({part.semantic_id for part in result.parts}) == 20
