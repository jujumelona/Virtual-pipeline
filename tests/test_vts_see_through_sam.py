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


def test_semantic_sam_attempts_every_observed_first_pass_layer(monkeypatch, tmp_path):
    from tools import vts_see_through_sam as sam
    from tools.vts_artwork_export import _apply_official_semantic_sam_once

    source_a = {"name": "mystery-A", "image": Image.new(
        "RGBA", (40, 20), (10, 100, 160, 180)), "depth": 0}
    source_b = {"name": "mystery-B", "image": Image.new(
        "RGBA", (40, 20), (200, 25, 90, 255)), "depth": 0}
    masks = [Image.new("RGBA", (40, 20)) for _ in range(19)]
    masks[0].paste((0, 0, 0, 255), (0, 0, 20, 20))
    masks[1].paste((0, 0, 0, 255), (20, 0, 40, 20))
    calls = []

    def fake_run(layers, canvas, *, output, third_party):
        calls.append([item["name"] for item in layers])
        output.mkdir(parents=True, exist_ok=True)
        log = output / "sam19.log"
        log.write_text("single-load fake; no GPU test")
        return masks, log

    monkeypatch.setattr(sam, "run_sam_from_package", fake_run)
    parts, trace, log = _apply_official_semantic_sam_once(
        [source_a, source_b], (40, 20),
        output=tmp_path / "out", third_party=tmp_path, edition="free")
    assert calls == [["mystery-A", "mystery-B"]]
    assert len(trace) == 2 and all(t["accepted"] for t in trace)
    assert len(parts) == 4 and log.is_file()
    for input_part, child_group in zip([source_a, source_b], [parts[:2], parts[2:]]):
        # Check stored pixels, not Pillow compositing round-trip arithmetic.
        rebuilt = np.zeros((20, 40, 4), dtype=np.uint8)
        for child in child_group:
            rgba = np.asarray(child["image"], dtype=np.uint8)
            owns = rgba[..., 3] > 0
            rebuilt[owns] = rgba[owns]
        assert np.array_equal(rebuilt, np.asarray(input_part["image"]))


def test_semantic_sam_respects_free_artmesh_budget(monkeypatch, tmp_path):
    from tools import vts_see_through_sam as sam
    from tools.vts_artwork_export import _apply_official_semantic_sam_once
    masks = [Image.new("RGBA", (20, 20)) for _ in range(19)]
    masks[0].paste((0, 0, 0, 255), (0, 0, 10, 20))
    masks[1].paste((0, 0, 0, 255), (10, 0, 20, 20))
    def fake_run(layers, canvas, *, output, third_party):
        output.mkdir(parents=True, exist_ok=True)
        return masks, output / "unused.log"
    monkeypatch.setattr(sam, "run_sam_from_package", fake_run)
    layers = [{"name": f"unclassified-{i}", "image": Image.new(
        "RGBA", (20, 20), (40, 80, 120, 255)), "depth": 0} for i in range(100)]
    produced, trace, _ = _apply_official_semantic_sam_once(
        layers, (20, 20), output=tmp_path, third_party=tmp_path, edition="free")
    assert len(produced) == 100
    assert len(trace) == 100
    assert all(not t["accepted"] and t["reason"] == "free_artmesh_limit"
               for t in trace)
