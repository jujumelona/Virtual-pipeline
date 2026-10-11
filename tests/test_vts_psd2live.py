"""Offline PSD2Live CLI -> validated native model -> final ZIP contracts."""
from __future__ import annotations

import json
from pathlib import Path
import shlex
from zipfile import ZipFile

import pytest
from PIL import Image

from tools import vts_psd2live as bridge


def sample_model(dest: Path):
    dest.mkdir(parents=True, exist_ok=True)
    (dest / "avatar.moc3").write_bytes(b"MOC3" + bytes(64))
    Image.new("RGBA", (16, 16), (255, 0, 0, 255)).save(dest / "texture_00.png")
    (dest / "avatar.physics3.json").write_text("{}")
    (dest / "avatar.model3.json").write_text(json.dumps({
        "Version": 3, "FileReferences": {
            "Moc": "avatar.moc3", "Textures": ["texture_00.png"],
            "Physics": "avatar.physics3.json",
        },
    }))
    (dest / "avatar.cmo3").write_bytes(b"CMO3\x00")
    (dest / "avatar.psd2live").write_bytes(b"PK\x03\x04" + b"x" * 32)
    (dest / "vts_atlas.json").write_text(json.dumps({
        "schema": "vtuber/psd2live-atlas-v1", "page_size": 2048,
        "max_pages": 1, "padding": 2, "fit": 1.0,
        "source_layer_count": 1, "packed_layer_count": 1,
        "pages": [{"size": [16, 16]}], "canvas_coordinate_scale": 1.0,
        "source_rasters_preserved": True, "artwork_resized": False,
    }))


@pytest.mark.parametrize("edition,page_size,page_count", [
    ("free", 2048, 1), ("pro", 4096, 8),
])
def test_budget_is_supplied_before_official_generation(
        monkeypatch, tmp_path, edition, page_size, page_count):
    """An atlas-size flag alone left the real sixty-layer run at eight pages."""
    psd = tmp_path / "source art" / "avatar.psd"
    psd.parent.mkdir()
    original = b"8BPS" + bytes(64)
    psd.write_bytes(original)
    vendor = tmp_path / "external source" / "psd2live"
    vendor.mkdir(parents=True)
    (vendor / "gradlew").write_text("stub")
    monkeypatch.setattr(bridge, "ensure_psd2live", lambda *a, **k: vendor)
    monkeypatch.setattr(bridge, "_java_env", lambda: {})
    dest = tmp_path / "native model"
    called = []

    def official_process(command, **kwargs):
        tokens = shlex.split(next(x.removeprefix("--args=") for x in command
                                 if x.startswith("--args=")))
        options = dict(zip(tokens[::2], tokens[1::2]))
        assert options.get("--atlas-pages") == str(page_count), (
            "The official generator must receive a page budget before packing")
        assert options["--atlas"] == str(page_size)
        assert options["--upscale"] == "1"
        assert "--nunif-dir" not in options
        assert Path(options["--input"]) == psd
        assert Path(options["--output"]) == dest
        assert "vtsRig" in command
        assert "--init-script" in command
        called.append(command)
        sample_model(dest)
        (dest / "vts_atlas.json").write_text(json.dumps({
            "schema": "vtuber/psd2live-atlas-v1", "max_pages": page_count,
            "page_size": page_size, "padding": 2, "fit": .35,
            "source_layer_count": 60, "packed_layer_count": 60,
            "pages": [{"size": [16, 16]}], "canvas_coordinate_scale": 1.0,
            "source_rasters_preserved": True, "artwork_resized": False,
        }))
        return 0

    result = bridge.run_psd2live(psd, dest, edition=edition, runner=official_process)
    assert len(called) == 1
    assert result["atlas_budget"]["max_pages"] == page_count
    assert result["atlas_fit"]["packed_layer_count"] == 60
    assert result["atlas_fit"]["fit"] == .35
    assert result["atlas_quality"] == "severely_downscaled"
    assert result["effective_texture_detail_verified"] is False
    assert result["rig_options"]["upscale_factor"] == 1
    assert result["nunif_model_configured"] is False
    assert psd.read_bytes() == original


def test_official_cli_free_atlas_and_model_bundle(monkeypatch, tmp_path):
    source = tmp_path / "source PSD" / "avatar.psd"
    source.parent.mkdir()
    source.write_bytes(b"8BPS" + bytes(64))
    root = tmp_path / "third party" / "psd2live"
    root.mkdir(parents=True)
    (root / "gradlew").write_text("#!/bin/sh\n")
    monkeypatch.setattr(bridge, "ensure_psd2live", lambda *a, **k: root)
    monkeypatch.setattr(bridge, "_java_env", lambda: {"JAVA_HOME": "/test/jdk21"})
    calls = []

    def execute(command, *, cwd, env, log_path, timeout_seconds):
        calls.append((command, cwd, env, log_path, timeout_seconds))
        assert command[1] == "--no-daemon"
        assert "vtsRig" in command
        args = next(x for x in command if x.startswith("--args="))
        assert "--atlas 2048" in args
        assert "--atlas-pages 1" in args
        assert "--mesh-spacing 40" in args
        assert "--mesh-wrap 0" in args
        assert "--head-strength 1.0" in args
        assert "--body-strength 1.0" in args
        assert "--upscale 1" in args
        assert "--preset" not in args  # unsupported in v3.3.1 CLI
        assert "'source PSD'" not in args  # quote the whole input path
        assert "'" in args
        assert cwd == root
        assert env["JAVA_HOME"] == "/test/jdk21"
        sample_model(tmp_path / "model")
        Path(log_path).write_text("fake Gradle success")
        return 0

    target = tmp_path / "model"
    result = bridge.run_psd2live(
        source, target, edition="free", runner=execute, timeout_seconds=123)
    assert len(calls) == 1
    assert calls[0][-1] == 123
    assert result["runtime_references_valid"]
    assert result["runtime_execution_verified"] is False
    assert result["cubism_free_editor_limits_verified"] is False
    assert result["atlas_size"] == 2048
    assert len(result["cmo3"]) == 1
    archive = tmp_path / "original.zip"
    with ZipFile(archive, "w") as z:
        z.write(source, "avatar.psd")
    packaged = bridge.package_psd2live(result, archive, tmp_path / "final.zip")
    with ZipFile(packaged) as z:
        names = set(z.namelist())
        assert {"avatar.moc3", "avatar.model3.json", "avatar.physics3.json",
                "texture_00.png", "avatar.cmo3", "avatar.psd2live",
                "source_artwork/original.zip",
                "metadata/psd2live_bridge.json"} <= names
        meta = json.loads(z.read("metadata/psd2live_bridge.json"))
        assert meta["runtime_execution_verified"] is False


def test_missing_texture_rejects_false_success(tmp_path):
    sample_model(tmp_path / "bad")
    (tmp_path / "bad" / "texture_00.png").unlink()
    with pytest.raises(FileNotFoundError, match="missing or unsafe"):
        bridge.validate_psd2live_output(tmp_path / "bad")


def test_fake_moc3_rejects_false_success(tmp_path):
    sample_model(tmp_path / "bad")
    (tmp_path / "bad" / "avatar.moc3").write_bytes(b"FAKE")
    with pytest.raises(ValueError, match="signature"):
        bridge.validate_psd2live_output(tmp_path / "bad")


def test_stale_rigged_model_is_never_accepted(monkeypatch, tmp_path):
    psd = tmp_path / "artwork" / "avatar.psd"
    psd.parent.mkdir()
    psd.write_bytes(b"8BPS" + bytes(64))
    sample_model(tmp_path / "output")
    with pytest.raises(RuntimeError, match="PSD2LIVE_OUTPUT_NOT_EMPTY"):
        bridge.run_psd2live(psd, tmp_path / "output", edition="free")


def test_nonzero_external_cli_does_not_yield_model(monkeypatch, tmp_path):
    psd = tmp_path / "artwork" / "avatar.psd"
    psd.parent.mkdir()
    psd.write_bytes(b"8BPS" + bytes(64))
    root = tmp_path / "psd2live"
    root.mkdir()
    (root / "gradlew").write_text("stub")
    monkeypatch.setattr(bridge, "ensure_psd2live", lambda *a, **k: root)
    monkeypatch.setattr(bridge, "_java_env", lambda: {})
    with pytest.raises(RuntimeError, match="PSD2LIVE_CLI_FAILED"):
        bridge.run_psd2live(psd, tmp_path / "model", edition="pro",
                            runner=lambda *a, **k: 13)


def test_vendor_label_metadata_does_not_claim_cubism_free_validation(tmp_path):
    sample_model(tmp_path / "full")
    checked = bridge.validate_psd2live_output(tmp_path / "full")
    assert checked["cubism_free_editor_limits_verified"] is False
    assert checked["runtime_execution_verified"] is False


def test_free_character_exports_primary_psd2live_model_zip(monkeypatch, tmp_path):
    """Exercise production orchestration, not only the standalone bridge."""
    from psd_tools import PSDImage
    from psd_tools.api.layers import PixelLayer
    from tools import vts_production

    source = tmp_path / "source.png"
    Image.new("RGBA", (256, 384), (60, 80, 95, 255)).save(source)
    doc = PSDImage.new("RGB", (256, 384))
    face = Image.new("RGBA", (256, 384))
    hair = Image.new("RGBA", (256, 384))
    face.paste((100, 120, 150, 255), (48, 60, 160, 180))
    hair.paste((70, 30, 60, 255), (35, 25, 185, 70))
    PixelLayer.frompil(face, parent=doc, name="face")
    PixelLayer.frompil(hair, parent=doc, name="front hair")
    original = tmp_path / "existing.psd"
    doc.save(original)
    calls = []

    def fake_cli(psd, output, *, edition, third_party):
        calls.append((str(psd), edition))
        assert psd.name == "avatar.psd"
        assert edition == "free"
        sample_model(output)
        return {
            **bridge.validate_psd2live_output(output),
            "backend": "psd2live",
            "license": "GPL-3.0",
            "atlas_size": 2048,
        }
    monkeypatch.setattr(bridge, "run_psd2live", fake_cli)
    output = tmp_path / "final"
    report = vts_production.make_cubism_handoff(
        source, output, edition="free", scope="upper",
        external_psd=original, psd2live=True)
    assert len(calls) == 1
    assert report["state"] == "psd2live_rigged_unverified"
    assert report["moc3_generated"] is True
    assert report["editor_required"] is False
    assert Path(report["artwork_package"]).is_file()
    with ZipFile(report["package"]) as archive:
        names = archive.namelist()
        assert "avatar.model3.json" in names
        assert "avatar.moc3" in names
        assert "texture_00.png" in names
        assert any(name.startswith("source_artwork/") and name.endswith(".zip")
                   for name in names)
        assert "metadata/psd2live_bridge.json" in names


def test_autorig_failure_is_not_reported_as_success(monkeypatch, tmp_path):
    from psd_tools import PSDImage
    from psd_tools.api.layers import PixelLayer
    from tools import vts_production

    source = tmp_path / "source.png"
    Image.new("RGBA", (256, 384), (120, 125, 140, 255)).save(source)
    doc = PSDImage.new("RGB", (256, 384))
    first = Image.new("RGBA", (256, 384), (0, 0, 0, 0))
    second = Image.new("RGBA", (256, 384), (0, 0, 0, 0))
    first.paste((120, 130, 140, 255), (10, 10, 100, 100))
    second.paste((100, 120, 140, 255), (90, 20, 180, 160))
    PixelLayer.frompil(first, parent=doc, name="face")
    PixelLayer.frompil(second, parent=doc, name="hair.front")
    original = tmp_path / "original.psd"
    doc.save(original)

    def fail(*a, **k):
        raise RuntimeError("PSD2LIVE_CLI_FAILED simulated")
    monkeypatch.setattr(bridge, "run_psd2live", fail)
    output = tmp_path / "out"
    with pytest.raises(RuntimeError, match="PSD2LIVE_CLI_FAILED"):
        vts_production.make_cubism_handoff(
            source, output, edition="free", scope="upper",
            external_psd=original, psd2live=True)
    status = json.loads((output / "vts_status.json").read_text())
    assert status["state"] == "failed"
    assert status["moc3_generated"] is False
    assert not (output / "Live2D_PSD2Live_Rigged.zip").exists()
    assert any((output / "artwork").glob("*.zip"))


def test_colab_ui_has_no_preparation_or_rig_export_step_yet():
    notebook = (Path(__file__).resolve().parents[1] /
                "notebooks/VTuber_Commercial_Pipeline_Colab_v8.ipynb")
    sources = ["".join(c["source"]) for c in json.loads(notebook.read_text())["cells"]
               if c["cell_type"] == "code"]
    import ast
    assert len(sources) == 4
    for source in sources:
        ast.parse(source)
    assert 'TOP_MODE_LABEL = "Live2D 상반신" #@param' in sources[1]
    assert 'ASSET_KIND_LABEL = "신체만" #@param' in sources[2]
    assert "psd2live" not in "\n".join(sources).lower()
    assert "make_cubism_handoff(" not in "\n".join(sources)


@pytest.mark.parametrize("name,label,expected", [
    ("hair.front.03", None, "front hair"),
    ("hair.back.pass2.01", "hair", "back hair"),
    ("eye.left.iris.1", "eyes", "irides"),
    ("eye.right.sclera", "eyes", "eyewhite"),
    ("eye.left.lash", "eyes", "eyelash"),
    ("cloth.lower.01", None, "bottomwear"),
    ("cloth.sleeve.left", None, "handwear"),
    ("face.pass2.02", "mouth", "mouth"),
    ("body.pass2.01", "topwear", "topwear"),
    ("face.pass2.01", "eyes", "irides"),
    ("ornament.ears.right.2", None, "earwear"),
    ("unknown.pass2.01", "eyewear", "eyewear"),
])
def test_psd2live_vendor_semantic_name_and_side(name, label, expected):
    from tools.vts_psd2live_names import normalize_layer_names
    from PIL import Image
    image = Image.new("RGBA", (8, 8), (123, 4, 56, 90))
    layers, data = normalize_layer_names([
        {"name": name, "image": image, "sam_label": label}])
    renamed = layers[0]["name"]
    assert renamed.startswith(expected + "_0001")
    if ".left." in name or name.endswith(".left"):
        assert renamed.endswith("-l")
    if ".right." in name or name.endswith(".right"):
        assert renamed.endswith("-r")
    assert layers[0]["image"] is image
    assert len(layers) == 1
    assert data["pixel_operations"] == 0
    assert data["extra_inference_passes"] == 0


def test_unknown_layer_keeps_identity_not_fake_body_part():
    from tools.vts_psd2live_names import normalize_layer_names
    layer = {"name": "mystery-glyph", "image": Image.new("RGBA", (2, 2))}
    output, trace = normalize_layer_names([layer])
    assert output[0]["name"] == "mystery-glyph"
    assert trace["unclassified_count"] == 1


def test_vendor_sam_mask_evidence_preserved_on_split(tmp_path):
    from tools.vts_official_second_pass import partition_from_masks
    image = Image.new("RGBA", (40, 20), (45, 89, 130, 240))
    masks = [Image.new("L", image.size, 0) for _ in range(19)]
    masks[3].paste(255, (0, 0, 20, 20))
    masks[8].paste(255, (20, 0, 40, 20))
    from tools.vts_see_through_sam import SAM_LABELS_V2
    children, trace = partition_from_masks(
        {"name": "face", "image": image}, masks, mask_labels=SAM_LABELS_V2)
    assert trace["accepted"] and len(children) == 2
    assert {child["sam_label"] for child in children} == {"eyes", "mouth"}


def test_free_rejects_multiple_atlas_pages(tmp_path):
    bridge_psd = tmp_path / "result"
    sample_model(bridge_psd)
    Image.new("RGBA", (16, 16)).save(bridge_psd / "texture_01.png")
    model = bridge_psd / "avatar.model3.json"
    contents = json.loads(model.read_text())
    contents["FileReferences"]["Textures"].append("texture_01.png")
    model.write_text(json.dumps(contents))
    with pytest.raises(RuntimeError, match="PSD2LIVE_FREE_ATLAS_LIMIT"):
        bridge.validate_psd2live_output(bridge_psd, edition="free")


def test_free_rejects_oversize_atlas(tmp_path):
    bridge_psd = tmp_path / "result"
    sample_model(bridge_psd)
    Image.new("RGBA", (2049, 20)).save(bridge_psd / "texture_00.png")
    with pytest.raises(RuntimeError, match="PSD2LIVE_FREE_ATLAS_LIMIT"):
        bridge.validate_psd2live_output(bridge_psd, edition="free")


def test_vendor_names_are_exported_and_original_mappings_are_preserved(tmp_path):
    from tools import vts_artwork_export as export
    from io import BytesIO
    from psd_tools import PSDImage
    parts = [
        ("hair.front.01", (30, 45, 75, 90)),
        ("eye.left.iris.01", (70, 90, 82, 103)),
        ("eye.right.sclera.01", (111, 91, 125, 108)),
        ("mouth.open.01", (86, 115, 102, 125)),
    ]
    path = tmp_path / "layers.zip"
    with ZipFile(path, "w") as z:
        for name, rect in parts:
            png = Image.new("RGBA", (256, 384))
            png.paste((10, 140, 180, 255), rect)
            blob = BytesIO()
            png.save(blob, format="PNG")
            z.writestr(name + ".png", blob.getvalue())
    info = export.build_artwork_package(
        path, tmp_path / "output", edition="free", scope="upper",
        official_second_pass=False, psd2live_names=True, qwen=False)
    doc = PSDImage.open(info["art_psd"])
    leaves = [v for v in doc.descendants() if not v.is_group()]
    names = {v.name for v in leaves}
    assert any(x.startswith("front hair_") for x in names)
    assert any(x.startswith("irides_") and x.endswith("-l") for x in names)
    assert any(x.startswith("eyewhite_") and x.endswith("-r") for x in names)
    assert any(x.startswith("mouth open_") for x in names)
    with ZipFile(info["package"]) as z:
        data = json.loads(z.read("metadata/psd2live_layer_names.json"))
        assert data["source_layer_count"] == len(parts)
        assert data["output_layer_count"] == len(parts)
        assert data["pixel_operations"] == 0
        assert data["extra_inference_passes"] == 0
        assert data["unclassified_count"] == 0


def test_missing_editable_cmo3_blocks_success(tmp_path):
    root = tmp_path / "rigged"
    sample_model(root)
    (root / "avatar.cmo3").unlink()
    with pytest.raises(RuntimeError, match="PSD2LIVE_CMO3_MISSING"):
        bridge.validate_psd2live_output(root)


def test_sixty_layers_preserve_count_pixels_and_semantics():
    from tools.vts_psd2live_names import normalize_layer_names
    names = [f"hair.front.{i:03d}" for i in range(20)]
    names += [f"hair.back.{i:03d}" for i in range(10)]
    names += [f"face.pass2.{i:03d}" for i in range(10)]
    names += [f"eye.left.iris.{i:03d}" for i in range(10)]
    names += [f"eye.right.sclera.{i:03d}" for i in range(10)]
    pixels = Image.new("RGBA", (3, 4), (34, 56, 78, 128))
    original = [{"name": name, "image": pixels} for name in names]
    new, trace = normalize_layer_names(original)
    assert len(new) == 60
    assert all(before["image"] is after["image"]
               for before, after in zip(original, new))
    assert all(new[i]["name"].startswith("front hair_") for i in range(20))
    assert all(new[i]["name"].startswith("back hair_") for i in range(20, 30))
    assert len(set(item["name"] for item in new)) == 60
    assert trace["source_layer_count"] == trace["output_layer_count"] == 60
    assert trace["pixel_operations"] == trace["extra_inference_passes"] == 0


def test_psd2live_import_psd_uses_tight_alpha_bounds_without_moving_pixels(tmp_path):
    """60 full-canvas PSD rasters must not waste full atlas rectangles."""
    from psd_tools import PSDImage
    from tools.vts_artwork_export import _write_psd

    size = (256, 384)
    p1 = Image.new("RGBA", size, (47, 51, 68, 0))
    p2 = Image.new("RGBA", size, (0, 0, 0, 0))
    p1.paste((200, 90, 40, 128), (20, 35, 65, 95))
    p2.paste((30, 130, 220, 255), (130, 170, 220, 275))
    parts = [
        {"name": "front hair_0001", "image": p1},
        {"name": "topwear_0002", "image": p2},
    ]
    dest = tmp_path / "atlas_compact.psd"
    _write_psd(parts, dest, free=True, compact_for_atlas=True)
    doc = PSDImage.open(dest)
    leaves = list(reversed([p for p in doc.descendants() if not p.is_group()]))
    assert len(leaves) == 2
    assert (leaves[0].left, leaves[0].top, leaves[0].width, leaves[0].height) == (
        20, 35, 45, 60)
    assert (leaves[1].left, leaves[1].top, leaves[1].width, leaves[1].height) == (
        130, 170, 90, 105)
    for leaf, original in zip(leaves, (p1, p2)):
        bbox = original.getchannel("A").getbbox()
        assert leaf.topil(apply_icc=False).convert("RGBA").tobytes() == original.crop(bbox).tobytes()
    assert sum(p.width * p.height for p in leaves) < size[0] * size[1]


def test_configured_nunif_art_weights_enable_real_psd2live_neural_sr(monkeypatch, tmp_path):
    psd = tmp_path / "source" / "avatar.psd"
    psd.parent.mkdir()
    psd.write_bytes(b"8BPS" + bytes(64))
    vendor = tmp_path / "psd2live"
    vendor.mkdir()
    (vendor / "gradlew").write_text("stub")
    nunif = tmp_path / "nunif"
    (nunif / "waifu2x").mkdir(parents=True)
    weights = tmp_path / "Art weights"
    weights.mkdir()
    (weights / "scale4x.pth").write_bytes(b"fixture")
    monkeypatch.setenv("VTS_PSD2LIVE_NUNIF_DIR", str(nunif))
    monkeypatch.setenv("VTS_PSD2LIVE_NUNIF_MODELS", str(weights))
    monkeypatch.setenv("VTS_PSD2LIVE_UPSCALE", "4")
    monkeypatch.setattr(bridge, "ensure_psd2live", lambda *a, **k: vendor)
    monkeypatch.setattr(bridge, "_java_env", lambda: {})
    def runner(cmd, **kwargs):
        args = shlex.split(next(x[7:] for x in cmd if x.startswith("--args=")))
        opts = dict(zip(args[::2], args[1::2]))
        assert opts["--upscale"] == "4"
        assert Path(opts["--nunif-dir"]) == nunif
        assert Path(opts["--upscale-model"]) == weights
        assert Path(opts["--upscale-python"]).is_file()
        sample_model(tmp_path / "model")
        fit_path = tmp_path / "model" / "vts_atlas.json"
        fit = json.loads(fit_path.read_text())
        fit["page_size"], fit["max_pages"] = 4096, 8
        fit_path.write_text(json.dumps(fit))
        return 0
    result = bridge.run_psd2live(psd, tmp_path / "model", edition="pro", runner=runner)
    assert result["rig_options"]["upscale_factor"] == 4
    assert result["nunif_model_configured"] is True


def test_partial_nunif_setup_fails_explicitly(monkeypatch, tmp_path):
    psd = tmp_path / "art" / "avatar.psd"
    psd.parent.mkdir()
    psd.write_bytes(b"8BPS" + bytes(64))
    vendor = tmp_path / "vendor"
    vendor.mkdir()
    (vendor / "gradlew").write_text("stub")
    monkeypatch.setattr(bridge, "ensure_psd2live", lambda *a, **k: vendor)
    monkeypatch.setattr(bridge, "_java_env", lambda: {})
    monkeypatch.setenv("VTS_PSD2LIVE_NUNIF_DIR", str(tmp_path))
    monkeypatch.delenv("VTS_PSD2LIVE_NUNIF_MODELS", raising=False)
    with pytest.raises(RuntimeError, match="PSD2LIVE_NUNIF_CONFIG_INCOMPLETE"):
        bridge.run_psd2live(psd, tmp_path / "model", edition="free",
                            runner=lambda *a, **k: pytest.fail("unexpected CLI"))
