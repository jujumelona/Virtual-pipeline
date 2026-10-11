"""CPU contracts for the independently published See-through 19-part parser."""
from __future__ import annotations
import json
import numpy as np
import pytest
from PIL import Image


def test_sam_manifest_requires_official_checkpoint(tmp_path):
    from tools.vts_see_through_sam import find_checkpoint, SAM_REPO
    checkpoint_dir = tmp_path / "snapshot"
    checkpoint_dir.mkdir()
    manifest = tmp_path / "ready.json"
    manifest.write_text(json.dumps({"snapshots": [
        {"model": SAM_REPO, "snapshot": str(checkpoint_dir)}
    ]}))
    with pytest.raises(RuntimeError, match="missing/corrupt"):
        find_checkpoint(manifest)
    checkpoint = checkpoint_dir / "checkpoint-18000.pt"
    # Manifest preflight checks that model file is actually present, not an
    # accidentally created zero-length placeholder.
    with checkpoint.open("wb") as stream:
        stream.seek(1_000_001)
        stream.write(b"0")
    assert find_checkpoint(manifest) == checkpoint.resolve()


def test_sam_masks_are_exactly_nineteen_full_canvas_layers():
    from tools.vts_see_through_sam import check_masks
    x = np.zeros((19, 14, 20), dtype=np.uint8)
    assert check_masks(x, (20, 14)).shape == (19, 14, 20)
    with pytest.raises(RuntimeError, match="invalid mask tensor"):
        check_masks(x[:18], (20, 14))
    with pytest.raises(RuntimeError, match="invalid mask tensor"):
        check_masks(x, (14, 20))


def test_semantic_sam_partitions_unknown_layers_once_preserving_source_rgba(
        monkeypatch, tmp_path):
    from tools import vts_see_through_sam as sam
    from tools.vts_artwork_export import _apply_official_semantic_sam_once

    layers = [
        {"name": "mystery-A", "image": Image.new("RGBA", (40, 20), (10, 100, 160, 180)), "depth": 0},
        {"name": "mystery-B", "image": Image.new("RGBA", (40, 20), (200, 25, 90, 255)), "depth": 0},
    ]
    masks = [Image.new("L", (40, 20), 0) for _ in range(19)]
    masks[0].paste(255, (0, 0, 20, 20))
    masks[11].paste(255, (20, 0, 40, 20))
    calls = []

    def fake_run(parts, canvas, *, output, third_party):
        calls.append([item["name"] for item in parts])
        output.mkdir(parents=True, exist_ok=True)
        log = output / "sam19.log"
        log.write_text("one model call")
        return masks, log

    monkeypatch.setattr(sam, "run_sam_from_package", fake_run)
    parts, trace, log = _apply_official_semantic_sam_once(
        layers, (40, 20), output=tmp_path / "out",
        third_party=tmp_path, edition="free")
    assert calls == [["mystery-A", "mystery-B"]]
    assert len(parts) == 4 and len(trace) == 2 and log.is_file()
    assert all(x["accepted"] for x in trace)
    for original, children in zip(layers, (parts[:2], parts[2:])):
        rebuilt = np.zeros((20, 40, 4), dtype=np.uint8)
        for child in children:
            rgba = np.asarray(child["image"])
            occupied = rgba[..., 3] > 0
            rebuilt[occupied] = rgba[occupied]
        np.testing.assert_array_equal(rebuilt, np.asarray(original["image"]))


def test_semantic_sam_compatible_body_masks_partition_without_pixel_changes(
        monkeypatch, tmp_path):
    from tools import vts_see_through_sam as sam
    from tools.vts_artwork_export import _apply_official_semantic_sam_once

    layer = {"name": "body.compound", "image": Image.new(
        "RGBA", (40, 20), (10, 100, 160, 180)), "depth": 0}
    masks = [Image.new("L", (40, 20), 0) for _ in range(19)]
    masks[2].paste(255, (0, 0, 20, 20))
    masks[11].paste(255, (20, 0, 40, 20))
    monkeypatch.setattr(sam, "run_sam_from_package",
                        lambda *a, **k: (masks, tmp_path / "missing.log"))
    parts, trace, _ = _apply_official_semantic_sam_once(
        [layer], (40, 20), output=tmp_path, third_party=tmp_path, edition="pro")
    assert len(parts) == 2 and trace[0]["accepted"]
    assert trace[0]["reason"] == "exact_rgba_source_partition"
    rebuilt = np.zeros((20, 40, 4), dtype=np.uint8)
    for part in parts:
        rgba = np.asarray(part["image"])
        occupied = rgba[..., 3] > 0
        rebuilt[occupied] = rgba[occupied]
    np.testing.assert_array_equal(rebuilt, np.asarray(layer["image"]))


def test_semantic_sam_respects_free_artmesh_budget(monkeypatch, tmp_path):
    from tools import vts_see_through_sam as sam
    from tools.vts_artwork_export import _apply_official_semantic_sam_once
    masks = [Image.new("RGBA", (20, 20)) for _ in range(19)]
    masks[2].paste((0, 0, 0, 255), (0, 0, 10, 20))
    masks[11].paste((0, 0, 0, 255), (10, 0, 20, 20))
    def fake_run(layers, canvas, *, output, third_party):
        output.mkdir(parents=True, exist_ok=True)
        return masks, output / "unused.log"
    monkeypatch.setattr(sam, "run_sam_from_package", fake_run)
    layers = [{"name": f"body.compound.{i}", "image": Image.new(
        "RGBA", (20, 20), (40, 80, 120, 255)), "depth": 0} for i in range(100)]
    produced, trace, _ = _apply_official_semantic_sam_once(
        layers, (20, 20), output=tmp_path, third_party=tmp_path, edition="free")
    assert len(produced) == 100
    assert len(trace) == 100
    assert all(not t["accepted"] and t["reason"] == "free_artmesh_limit"
               for t in trace)


def test_sam_gpu_worker_command_and_output_contract_without_cuda(monkeypatch, tmp_path):
    """Exercise the real setup manifest -> worker command -> NPZ parser edge."""
    from pathlib import Path
    from tools import vts_see_through_sam as sam
    from tools import vts_subprocess
    third = tmp_path / "third_party"
    vendor = third / "see-through"
    vendor.mkdir(parents=True)
    snapshot = third / "hf_snapshot"
    snapshot.mkdir()
    checkpoint = snapshot / sam.SAM_FILE
    with checkpoint.open("wb") as stream:
        stream.seek(1_000_001)
        stream.write(b"X")
    (third / "vts_setup_manifest.json").write_text(
        json.dumps({"snapshots": [
            {"model": sam.SAM_REPO, "snapshot": str(snapshot)}]}),
        encoding="utf-8")
    observed = []

    def fake_logged(command, *, cwd, env, log_path, timeout_seconds):
        observed.append((list(command), cwd, timeout_seconds, env))
        assert cwd == vendor
        assert timeout_seconds == 3600
        assert env["HF_HUB_OFFLINE"] == env["TRANSFORMERS_OFFLINE"] == "1"
        assert command[command.index("--manifest") + 1] == str(
            third / "vts_setup_manifest.json")
        dst = Path(command[command.index("--output") + 1])
        masks = np.zeros((19, 16, 24), dtype=np.uint8)
        masks[0, :, :12] = 1
        masks[1, :, 12:] = 1
        np.savez_compressed(dst, masks=masks)
        Path(log_path).write_text("MOCKED official SAM-19 command; not GPU inference")
        return 0

    monkeypatch.setattr(vts_subprocess, "run_logged", fake_logged)
    source = {"name": "unknown-part", "image": Image.new(
        "RGBA", (24, 16), (123, 45, 67, 255)), "depth": 0}
    masks, log = sam.run_sam_from_package(
        [source], (24, 16), output=tmp_path / "out", third_party=vendor)
    assert len(observed) == 1
    assert len(masks) == 19
    assert all(mask.mode == "L" and mask.size == (24, 16) for mask in masks)
    assert sum(len(mask.tobytes()) for mask in masks) == 19 * 24 * 16
    assert masks[0].getbbox() == (0, 0, 12, 16)
    assert masks[1].getbbox() == (12, 0, 24, 16)
    assert masks[2].getbbox() is None
    assert masks[0].getpixel((0, 0)) == 255
    assert masks[1].getpixel((0, 0)) == 0
    from tools.vts_official_second_pass import partition_from_masks
    parts, decision = partition_from_masks(source, masks)
    assert decision["accepted"] and len(parts) == 2
    restored = np.zeros((16, 24, 4), dtype=np.uint8)
    for part in parts:
        rgba = np.asarray(part["image"])
        occupied = rgba[:, :, 3] > 0
        restored[occupied] = rgba[occupied]
    assert np.array_equal(restored, np.asarray(source["image"]))
    assert log.is_file()


@pytest.mark.parametrize("dtype,value", [
    (np.uint8, 2),
    (np.uint8, 255),
    (np.float32, 0.5),
    (np.float32, float("nan")),
    (np.int8, -1),
])
def test_sam_rejects_nonbinary_or_invalid_dtype_masks(dtype, value):
    """A corrupt NPZ must never be converted into incorrect alpha coverage."""
    from tools.vts_see_through_sam import check_masks
    masks = np.zeros((19, 4, 5), dtype=dtype)
    masks[0, 0, 0] = value
    with pytest.raises(RuntimeError, match="binary"):
        check_masks(masks, (5, 4))


def test_sam_accepts_exact_bool_and_uint8_binary_masks():
    from tools.vts_see_through_sam import check_masks
    for dtype in (np.bool_, np.uint8):
        masks = np.zeros((19, 4, 5), dtype=dtype)
        masks[0, 0, 0] = 1
        result = check_masks(masks, (5, 4))
        assert result.dtype == np.uint8
        assert result[0, 0, 0] == 1


def test_sam_output_sixty_layers_goes_to_psd_without_nf4_recursion(monkeypatch, tmp_path):
    """22 initial 2D layers may yield 60 SAM layers; do not infer them again."""
    from io import BytesIO
    from zipfile import ZipFile

    from tools import vts_artwork_export as export
    from tools import vts_see_through_sam as sam

    canvas = (90, 48)
    mask_images = [Image.new("L", canvas) for _ in range(19)]
    for index, interval in enumerate(((0, 30), (30, 60), (60, 90))):
        mask_images[index].paste(255, (interval[0], 0, interval[1], 48))
    source_layers = []
    for i in range(22):
        image = Image.new("RGBA", canvas)
        width = 90 if i < 19 else 30
        image.paste((i + 20, 65, 110, 255), (0, 0, width, 48))
        source_layers.append({"name": f"body.layer.{i:03d}", "image": image, "depth": 0})

    runs = []
    def once(parts, shape, *, output, third_party):
        runs.append((len(parts), shape))
        output.mkdir(parents=True, exist_ok=True)
        logfile = output / "sam19.log"
        logfile.write_text("one SAM model call")
        return mask_images, logfile

    monkeypatch.setattr(sam, "run_sam_from_package", once)
    parts, report, _ = export._apply_official_semantic_sam_once(
        source_layers, canvas, output=tmp_path / "sam",
        third_party=tmp_path, edition="free")
    assert runs == [(22, canvas)]
    assert len(parts) == 60
    assert sum(bool(item["accepted"]) for item in report) == 19
    assert all(item["output_count"] == (3 if i < 19 else 1)
               for i, item in enumerate(report))
    for i, parent in enumerate(source_layers):
        offset = i * 3 if i < 19 else 57 + i - 19
        children = parts[offset:offset + (3 if i < 19 else 1)]
        restored = np.zeros_like(np.asarray(parent["image"], dtype=np.uint8))
        for child in children:
            pixels = np.asarray(child["image"], dtype=np.uint8)
            visible = pixels[..., 3] > 0
            restored[visible] = pixels[visible]
        np.testing.assert_array_equal(restored, np.asarray(parent["image"]))

    archive = tmp_path / "registered.zip"
    with ZipFile(archive, "w") as z:
        for source in source_layers:
            buf = BytesIO()
            source["image"].save(buf, format="PNG")
            z.writestr(source["name"] + ".png", buf.getvalue())
    # Only this SAM stage may run; the second NF4 function must never execute.
    monkeypatch.setattr(export, "_refine_all_layers_official_once",
                        lambda *a, **k: (_ for _ in ()).throw(
                            AssertionError("second NF4 inference forbidden")),
                        raising=False)
    package = export.build_artwork_package(
        archive, tmp_path / "export", edition="free", scope="upper",
        third_party=tmp_path, official_second_pass=True, qwen=False)
    assert package["layer_count"] == 60
    assert package["official_second_pass_attempts"] == 0
    assert package["official_sam19_attempts"] == 22
    with ZipFile(package["package"]) as z:
        report = json.loads(z.read("metadata/official_second_pass.json"))
        assert report["enabled"] is False
        assert len([p for p in z.namelist() if p.startswith("layers_png/")]) == 60
