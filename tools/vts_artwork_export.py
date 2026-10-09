"""Build honest, editable Cubism PSD artwork; never claim native rigging.

Qwen is used as a *mask proposal* on See-through layers. Visible pixels are
copied from the high-resolution See-through input without regeneration. A Qwen
proposal is adopted only when it makes a nontrivial, valid partition and the
reconstructed source layer is pixel-equivalent. No synthetic ArtMeshes, physics
or .moc3 files are emitted.
"""
from __future__ import annotations

from io import BytesIO
import json
from pathlib import Path
from zipfile import ZipFile, ZIP_DEFLATED

import numpy as np
from PIL import Image

ASSETS = ("body", "hair", "outfit", "accessory")
FREE_LIMIT = 100
FREE_BUDGET = {
    "art_mesh_max": 100, "part_folders_max": 30, "deformers_max": 50,
    "parameters_max": 30, "blendshape_parameters_max": 3,
    "art_paths_max": 3, "texture_atlas_count_max": 1,
    "texture_atlas_edge_px_max": 2048,
}


def _read_registered(path: Path):
    with ZipFile(path) as z:
        files = [n for n in z.namelist() if n.endswith(".png")]
        layers = []
        size = None
        for name in files:
            with Image.open(BytesIO(z.read(name))) as image:
                image.load()
                if image.mode != "RGBA":
                    raise ValueError("Layer must have actual RGBA transparency")
                if size is not None and image.size != size:
                    raise ValueError("Layers do not share an aligned canvas")
                size = image.size
                if image.getchannel("A").getbbox():
                    layers.append({"name": Path(name).stem, "image": image.copy(),
                                   "depth": 0})
    if not layers:
        raise ValueError("PSD extraction produced no nonempty drawable layers")
    return layers, size


def _candidate_score(part):
    name = part["name"].lower()
    group = next((k for k in ("hair", "eye", "mouth", "face", "cloth", "body",
                              "ornament", "accessory", "sleeve")
                  if name.startswith(k)), "")
    if not group:
        return -1
    alpha = np.asarray(part["image"].getchannel("A"))
    pixel_count = int(np.count_nonzero(alpha > 16))
    if pixel_count < 64:
        return -1
    priority = {"hair": 5, "eye": 5, "mouth": 5, "face": 4,
                "cloth": 4, "sleeve": 4, "body": 3,
                "ornament": 3, "accessory": 3}.get(group, 0)
    return priority * 10**9 + pixel_count


def _partition_part(part, suggestions):
    """Use Qwen alpha as labels, preserve all observed original RGBA pixels.

    This does not pretend to reconstruct missing occluded imagery; See-through
    remains responsible for its own hidden-layer restoration.
    """
    source = part["image"]
    bbox = source.getchannel("A").getbbox()
    if bbox is None or len(suggestions) < 2:
        return None
    crop = source.crop(bbox)
    ow, oh = crop.size
    if ow < 4 or oh < 4:
        return None
    proposal_masks = []
    for path in suggestions:
        with Image.open(path) as im:
            im.load()
            if im.mode != "RGBA":
                raise ValueError("Qwen output must be genuine RGBA")
            # Reject a prediction with a changed aspect, rather than
            # silently stretching a different character's output.
            ratio_error = abs(im.width / im.height - ow / oh) / (ow / oh)
            if ratio_error > .08:
                return None
            region = im.getchannel("A").resize((ow, oh), Image.Resampling.BILINEAR)
            proposal_masks.append(np.asarray(region, dtype=np.uint8))
    candidate = np.stack(proposal_masks, axis=0)
    original = np.asarray(crop, dtype=np.uint8)
    valid = original[:, :, 3] > 8
    if int(valid.sum()) < 64:
        return None
    has_proposal = candidate.max(axis=0) > 24
    if (valid & has_proposal).sum() < .75 * valid.sum():
        return None
    index = np.argmax(candidate, axis=0)
    distribution = [int(np.count_nonzero(valid & (index == i)))
                    for i in range(len(proposal_masks))]
    relevant = [i for i, amount in enumerate(distribution)
                if amount >= max(24, int(.04 * valid.sum()))]
    if len(relevant) < 2:
        return None
    # Re-assign all pixels (including translucent edge pixels) to accepted
    # masks. Source RGBA values are copied, not upscaled Qwen colors.
    accepted = candidate[relevant].argmax(axis=0)
    children = []
    for rank, original_index in enumerate(relevant):
        segment = np.zeros_like(original)
        segment[accepted == rank] = original[accepted == rank]
        if not np.any(segment[:, :, 3]):
            continue
        canvas = Image.new("RGBA", source.size, (0, 0, 0, 0))
        canvas.paste(Image.fromarray(segment, "RGBA"), bbox[:2])
        children.append({"name": part["name"] + ".q" + str(rank + 1),
                         "image": canvas, "depth": part["depth"] + 1})
    if len(children) < 2:
        return None
    # Disjoint masks must reproduce every original source pixel exactly.
    verified = np.zeros_like(original)
    for child in children:
        frag = np.asarray(child["image"].crop(bbox), dtype=np.uint8)
        occupied = frag[:, :, 3] > 0
        verified[occupied] = frag[occupied]
    if not np.array_equal(verified, original):
        return None
    return children


def _write_psd(parts, target: Path):
    from psd_tools import PSDImage
    psd = PSDImage.new("RGB", parts[0]["image"].size, depth=8)
    # Our list is top-to-bottom; PSD creation appends bottom-to-top.
    for part in reversed(parts):
        psd.create_pixel_layer(part["image"], name=part["name"], top=0, left=0)
    target.parent.mkdir(parents=True, exist_ok=True)
    psd.save(str(target))
    if target.read_bytes()[:4] != b"8BPS":
        raise RuntimeError("Output is not a native layered PSD")
    document = PSDImage.open(str(target))
    if len(list(document.descendants())) != len(parts):
        raise RuntimeError("PSD lost layers on serialization")


def _editor_readme(edition, asset_kind, count, qwen_count):
    label = "FREE finished character" if edition == "free" else "PRO independent " + asset_kind
    limits = "\n".join("- %s: %s" % item for item in FREE_BUDGET.items())
    return (
        "# Live2D Cubism layered artwork — " + label + "\n\n"
        "This ZIP contains **separated illustration layers, not a rigged model**.\n"
        "It does NOT contain .moc3, .cmo3, deformers, keyforms or physics.\n\n"
        "## In Cubism Editor\n\n"
        "1. Import the PSD. Check layer order, hidden edges and exact artwork identity.\n"
        "2. Refine ArtMeshes using the Editor's mesh tools; apply model templates"
        " or create deformers and animation keyforms as appropriate.\n"
        "3. Add eyes, mouth, head/body motion, hair/clothing dynamics and physics in the Editor.\n"
        "4. Save the editable .cmo3 and use the official Editor to export .moc3,"
        " .model3.json, textures and any needed physics/expression data.\n"
        "5. Open the exported model in VTube Studio and check tracking and clipping.\n\n"
        "## Observed artwork\n\n"
        "- Transparent PSD leaves: " + str(count) + "\n"
        "- Accepted Qwen splits: " + str(qwen_count) + "\n"
        + ("- Cubism FREE limits (the 7 final-object constraints must be checked"
           " **inside the Editor**):\n" + limits + "\n"
           "- Allocate the single 2048px atlas to face/eyes/outline detail first.\n"
           if edition == "free" else
           "- PRO has no FREE ArtMesh/parts/deformer/parameter limit, but"
           " Editor/GPU memory and runtime quality still matter.\n"
           "- Import each new asset PSD into the matching existing body project;"
           " preserve canvas origin and dimensions.\n")
        + "\n## No automatic completion claim\n\n"
        "Layer separation does not create animation. No auto-generated physics"
        " or JSON in this package should be mistaken for a native Cubism rig.\n"
    )


def build_artwork_package(registered_zip: Path, output: Path, *, edition: str,
                          scope: str, asset_kind: str | None = None,
                          qwen: bool = False, qwen_infer=None, third_party=None,
                          python_path=None, max_qwen_passes: int = 4,
                          per_pass_layers: int = 4) -> dict:
    """Build one FREE character or one independently authored PRO asset PSD."""
    if edition not in ("free", "pro") or scope not in ("upper", "full"):
        raise ValueError("Invalid Cubism edition/framing")
    if edition == "pro" and asset_kind not in ASSETS:
        raise ValueError("PRO must select exactly one body/hair/outfit/accessory asset")
    if edition == "free" and asset_kind is not None:
        raise ValueError("FREE is one complete fixed-look character")
    if not 2 <= per_pass_layers <= 10 or not 0 <= max_qwen_passes <= 12:
        raise ValueError("Invalid Qwen recursion budget")
    layers, canvas = _read_registered(registered_zip)
    if edition == "free" and len(layers) > FREE_LIMIT:
        raise ValueError("FREE ArtMesh budget exceeded by source PSD; no silent merging")
    output.mkdir(parents=True, exist_ok=True)
    generated = []
    attempted = []
    if qwen:
        if qwen_infer is None:
            from tools.vts_qwen_refine import infer as qwen_infer
        tried = set()
        for serial in range(max_qwen_passes):
            selectable = [
                (idx, layer) for idx, layer in enumerate(layers)
                if layer["name"] not in tried and layer["depth"] < 3
                and _candidate_score(layer) > 0
            ]
            if not selectable or (edition == "free" and len(layers) >= FREE_LIMIT):
                break
            index, item = max(selectable, key=lambda pair: _candidate_score(pair[1]))
            tried.add(item["name"])
            stem = "qwen_" + str(serial).zfill(3)
            crop = item["image"].crop(item["image"].getchannel("A").getbbox())
            source = output / "qwen_work" / (stem + ".png")
            source.parent.mkdir(parents=True, exist_ok=True)
            crop.save(source)
            run_dir = output / "qwen_work" / stem
            kw = {"layer_count": per_pass_layers}
            if third_party is not None:
                kw["third_party"] = third_party
            if python_path is not None:
                kw["python"] = python_path
            result = qwen_infer(source, run_dir, **kw)
            proposed = _partition_part(item, result["layers"])
            accepted = bool(proposed and
                            (edition != "free" or len(layers) + len(proposed) - 1 <= FREE_LIMIT))
            attempted.append({"source_layer": item["name"], "accepted": accepted,
                              "candidate_count": len(result["layers"])})
            if accepted:
                layers[index:index+1] = proposed
                generated.append(item["name"])
    if edition == "free" and len(layers) > FREE_LIMIT:
        raise ValueError("FREE ArtMesh ceiling exceeded")
    name = "avatar" if edition == "free" else asset_kind
    psd_path = output / (name + ".psd")
    _write_psd(layers, psd_path)
    package = output / ("Live2D_" + edition.upper() +
                         ("_" + scope if edition == "free" else "_" + asset_kind)
                         + ".zip")
    readme = _editor_readme(edition, asset_kind, len(layers), len(generated))
    with ZipFile(package, "w", ZIP_DEFLATED, compresslevel=6) as z:
        z.write(psd_path, name + ".psd")
        z.writestr("README_CUBISM.md", readme)
        for n, layer in enumerate(layers):
            img = BytesIO()
            layer["image"].save(img, format="PNG")
            z.writestr("layers_png/%03d_%s.png" % (n, layer["name"]), img.getvalue())
    return {
        "status": "artwork_ready_editor_rig_required",
        "package": str(package), "art_psd": str(psd_path),
        "layer_count": len(layers), "edition": edition, "scope": scope,
        "asset_kind": asset_kind, "canvas": list(canvas),
        "qwen_attempts": attempted, "qwen_splits_accepted": generated,
        "moc3_generated": False, "editor_required": True,
    }
