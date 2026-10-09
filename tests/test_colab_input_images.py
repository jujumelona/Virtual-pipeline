"""Colab v8 accepts raw image files only; users never upload a ZIP."""
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


def test_27_raw_pngs_are_verified_and_packed_internally(tmp_path, small_png_set):
    master, internal = inputs.prepare_2d_image_uploads(small_png_set, str(tmp_path))
    assert Image.open(master).size == (64, 96)
    with zipfile.ZipFile(internal) as z:
        assert set(z.namelist()) == inputs.EXPECTED - {"front_master.png"}
        assert len(z.namelist()) == 26
    assert set(tmp_path.glob("*")) == {tmp_path / "front_master.png",
                                        tmp_path / "verified_layers.internal.zip"}


def test_missing_or_misnamed_png_rejected_before_any_archive(tmp_path, small_png_set):
    small_png_set.pop("hair_front.png")
    with pytest.raises(ValueError, match="hair_front.png"):
        inputs.prepare_2d_image_uploads(small_png_set, str(tmp_path))
    assert not list(tmp_path.iterdir())


def test_wrong_size_and_non_rgba_rejected(tmp_path, small_png_set):
    small_png_set["hair_back.png"] = _make_png(size=(80, 96))
    with pytest.raises(ValueError, match="2048|64x96"):
        inputs.prepare_2d_image_uploads(small_png_set, str(tmp_path))

    small_png_set["hair_back.png"] = _make_png(opaque_layer=False)
    with pytest.raises(ValueError, match="완전히 투명"):
        inputs.prepare_2d_image_uploads(small_png_set, str(tmp_path))

    png = BytesIO()
    Image.new("RGB", (64, 96), "white").save(png, "PNG")
    small_png_set["hair_back.png"] = png.getvalue()
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
    assert "## 모드별 외부 이미지 AI 제작 프롬프트" in readme
    assert "front_master.png" in readme
    assert "hair_front.png" in readme
    assert "right.png" in readme
    assert "build_prompts(" not in code
    assert "write_prompt_package" not in code
    assert "Identity(" not in code
    assert "HAIR_COLOR =" not in code
    assert "prepare_2d_image_uploads(" in code
    assert "files.upload()" in code
