"""Executable VTube Studio FREE/PRO artwork preparation via See-through PSD.

Only authentic Cubism exports are reported as complete. This runner prepares
PSD and rigging data for the official editor; it does not synthesize MOC3.
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time
from zipfile import ZipFile, ZIP_DEFLATED


def _write(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(".tmp")
    temp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    temp.replace(path)


def _image(path: Path):
    from PIL import Image
    if not path.is_file():
        raise FileNotFoundError(path)
    if path.suffix.lower() not in {".png", ".jpg", ".jpeg", ".webp"}:
        raise ValueError("Master is not a supported raster image: " + str(path))
    with Image.open(path) as im:
        im.load()
        if im.width < 256 or im.height < 256:
            raise ValueError("Master is too small for rigging")
        if im.width * im.height > 32_000_000:
            raise ValueError("Master exceeds 32 megapixels")
        return im.size


def _semantic_family(name: str) -> str:
    """Choose an evidenced functional rig family from a PSD layer title.

    Unknown layers become fixed clothing/decoration graphics, not invented eyes.
    This classification needs validation before a production-quality rig claim.
    """
    raw = name.casefold().replace("_", ".").replace("-", ".")
    # Pinned See-through publishes 19 combined categories; body/head passes
    # include 24 fine prompts. Distinguish wearable objects before the
    # more general "neck", "ear" and "hand" string fallbacks.
    exact_upstream = {
        "headwear": "ornament.head", "eyewear": "ornament.eyes",
        "earwear": "ornament.ears", "neckwear": "ornament.neck",
        "handwear": "cloth.gloves", "topwear": "cloth.upper",
        "bottomwear": "cloth.lower", "legwear": "cloth.legs",
        "footwear": "shoe", "tail": "accessory.tail",
        "wings": "accessory.wings", "objects": "ornament.objects",
        "eyes": "eye", "irides": "eye.iris",
        "eyewhite": "eye.sclera", "eyelash": "eye.lash",
        "head": "body.head", "hair": "hair.general",
        "face": "face", "ears": "ear",
    }
    split_aliases = {"hairf": "hair.front", "hairb": "hair.back",
                     "eyel": "eye.left", "eyer": "eye.right",
                     "browl": "eyebrow.left", "browr": "eyebrow.right",
                     "earl": "ear.left", "earr": "ear.right"}
    if raw in split_aliases:
        return split_aliases[raw]
    # part_lr_split emits e.g. irides-l and handwear-r. These suffixes
    # describe the upstream semantic side; preserve them rather than infer
    # anatomical left/right again from image position.
    stem, _, suffix = raw.rpartition(".")
    if suffix in ("l", "r") and stem in exact_upstream | {"eyebrow": "eyebrow"}:
        family = (exact_upstream | {"eyebrow": "eyebrow"})[stem]
        side = "left" if suffix == "l" else "right"
        if family.startswith("eye."):
            return "eye." + side + "." + family.split(".", 1)[1]
        return family + "." + side
    if raw in exact_upstream:
        return exact_upstream[raw]
    # The See-through / Qwen layer name is a semantic identity, not just an
    # annotation. Never discard left/right, front/back, iris or lid suffixes.
    canonical = ("hair.", "eye.", "eyebrow.", "mouth.", "cloth.",
                 "body.", "arm.", "leg.", "hand.", "foot.", "shoe.", "accessory.",
                 "ornament.", "ear.", "neck.", "nose.", "face.", "head.",
                 "outfit.", "sleeve.")
    if raw.startswith(canonical):
        return raw
    name = raw.replace(".", " ")
    side = "left" if "left" in name else "right" if "right" in name else None
    if "iris" in name or "pupil" in name or "eyelid" in name or "sclera" in name:
        detail = next(x for x in ("iris", "pupil", "eyelid", "sclera") if x in name)
        return ("eye." + side + "." + detail) if side else ("eye." + detail)
    if ("eyebrow" in name or "brow" in name) and side:
        return "eyebrow." + side
    if "eye" in name and side:
        return "eye." + side
    if "hair" in name and side:
        return "hair.side." + side
    checks = (
        ("hair.back", ("back hair", "hair back", "rear hair")),
        ("hair.front", ("bang", "fringe", "front hair", "hair front")),
        ("hair.side", ("side hair", "hair side", "twintail", "ponytail")),
        ("hair.front", ("hair",)),
        ("eyebrow", ("eyebrow", "brow")),
        ("eye", ("eye", "iris", "pupil", "eyelash", "eyelid", "sclera")),
        ("mouth", ("mouth", "lip", "tongue", "teeth")),
        ("face", ("face", "skin", "cheek", "forehead")),
        ("nose", ("nose",)),
        ("ear", ("ear",)),
        ("neck", ("neck",)),
        ("hand", ("hand", "finger")),
        ("arm", ("arm",)),
        ("leg", ("leg", "thigh", "knee")),
        ("shoe", ("shoe", "boot", "sock", "foot")),
        ("body", ("torso", "body")),
        ("cloth", ("cloth", "skirt", "shirt", "coat", "sleeve", "dress",
                   "outfit", "fabric", "jacket", "trouser", "pants")),
        ("ornament", ("accessory", "accessories", "ornament", "jewel",
                      "pendant", "ribbon", "clip", "pin", "hat")),
    )
    for family, keys in checks:
        if any(key in name for key in keys):
            return family
    return "cloth"


def psd_to_registered_rgba(psd_path: Path, dest: Path, *, artmesh_max: int | None):
    """Losslessly register PSD pixel layers onto a common canvas.

    A PSD group is *not* an ArtMesh. Only drawable raster leaves are exported.
    Transparent empty leaves are omitted; all image coordinates are preserved.
    """
    from psd_tools import PSDImage
    from PIL import Image

    dest.mkdir(parents=True, exist_ok=True)
    psd = PSDImage.open(psd_path)
    size = (psd.width, psd.height)
    if size[0] < 256 or size[1] < 256:
        raise ValueError("PSD canvas is too small")
    leaves = []
    for layer in psd.descendants():
        if layer.is_group() or not layer.is_visible():
            continue
        # psd-tools stores RGBA layer alpha as USER_LAYER_MASK in RGB
        # documents (including our own PSD exporter). composite() can return
        # opaque RGB on such files, so restore the actual mask channel.
        tile = layer.topil()
        if tile is None:
            continue
        tile = tile.convert("RGBA")
        if layer.mask is not None:
            actual_alpha = layer.mask.topil()
            if actual_alpha is None:
                raise ValueError("PSD layer mask cannot be decoded: "+str(layer.name))
            if actual_alpha.size != tile.size:
                full_alpha = Image.new("L", tile.size, 0)
                full_alpha.paste(actual_alpha.convert("L"),
                                 (int(layer.mask.left)-int(layer.left),
                                  int(layer.mask.top)-int(layer.top)))
                actual_alpha = full_alpha
            tile.putalpha(actual_alpha.convert("L"))
        if not tile.getchannel("A").getbbox():
            continue
        left, top = int(layer.left), int(layer.top)
        if (left >= size[0] or top >= size[1]
                or left + tile.width <= 0 or top + tile.height <= 0):
            continue
        # Exclude opaque painted scene backgrounds: VTuber ArtMeshes only.
        from PIL import ImageStat
        opacity_ratio = ImageStat.Stat(tile.getchannel("A")).sum[0] / (255 * size[0] * size[1])
        if opacity_ratio > 0.85:
            print("[VTS PSD] skipping near-full-canvas background:",layer.name,flush=True)
            continue
        leaves.append((str(layer.name or "layer"), tile, left, top))
    if not leaves:
        raise ValueError("See-through PSD contains no visible pixel ArtMeshes")
    if artmesh_max is not None and len(leaves) > artmesh_max:
        raise ValueError(f"Cubism FREE ArtMesh limit exceeded: {len(leaves)} > {artmesh_max}. "
                         "Refusing to silently flatten animation layers.")
    out_zip = dest / "registered_layers.zip"
    source = dest / "psd_composite.png"
    composite = psd.composite()
    if composite is None:
        raise ValueError("PSD composite missing")
    composite.convert("RGBA").save(source)
    with ZipFile(out_zip, "w", ZIP_DEFLATED) as archive:
        for index, (name, tile, left, top) in enumerate(leaves):
            canvas = Image.new("RGBA", size, (0, 0, 0, 0))
            canvas.paste(tile, (left, top))
            from io import BytesIO
            buf = BytesIO()
            canvas.save(buf, format="PNG")
            label = _semantic_family(name)
            archive.writestr(f"{label}.{index:03d}.png", buf.getvalue())
    return source, out_zip, len(leaves)


def restore_source_canvas(registered: Path, source_size: tuple[int, int], target: Path):
    """Invert the pinned See-through center-square-pad/resize transform.

    Use only for this model's generated PSD, never guess external PSD geometry.
    Resampling does not recover source RGB detail lost during inference.
    """
    from io import BytesIO
    from PIL import Image
    width, height = source_size
    edge = max(width, height)
    pad_x, pad_y = (edge - width) // 2, (edge - height) // 2
    observed_size = None
    target.parent.mkdir(parents=True, exist_ok=True)
    with ZipFile(registered) as src, ZipFile(target, "w", ZIP_DEFLATED) as dst:
        for name in src.namelist():
            with Image.open(BytesIO(src.read(name))) as im:
                im.load()
                if im.mode != "RGBA" or im.width != im.height:
                    raise ValueError("Pinned See-through output must be square RGBA")
                if observed_size is not None and im.size != observed_size:
                    raise ValueError("Inconsistent inference layer canvas")
                observed_size = im.size
                square = im if im.size == (edge, edge) else im.resize(
                    (edge, edge), Image.Resampling.LANCZOS)
                layer = square.crop((pad_x, pad_y, pad_x + width, pad_y + height))
                buf = BytesIO(); layer.save(buf, format="PNG")
                dst.writestr(name, buf.getvalue())
    return target, {
        "method": "inverse_pinned_center_square_pad_resize",
        "inference_canvas": list(observed_size) if observed_size else None,
        "source_canvas": list(source_size), "padding_removed_xy": [pad_x, pad_y],
        "resampled": observed_size != (edge, edge),
        "source_rgb_fidelity_verified": False,
    }


def _observed_split_tags(metadata: Path, *, depth: bool) -> list[str]:
    """Only submit tags that really exist in the pinned See-through PSD."""
    if not metadata.is_file():
        return []
    data = json.loads(metadata.read_text(encoding="utf-8"))
    parts = data.get("parts")
    if not isinstance(parts, dict):
        return []
    allowed = ("hair", "arm", "hand", "sleeve", "leg", "foot",
               "shoe", "cloth", "outfit", "ribbon", "accessor",
               "eye", "irid", "eyebrow", "eyelash", "eyewhite",
               "ear", "wings", "tail", "objects")
    result = []
    for tag in parts:
        if not isinstance(tag, str) or "," in tag:
            continue
        name = tag.lower()
        if any(word in name for word in allowed) and (depth or
            not any(x in name for x in ("left", "right", "_l", "_r"))):
            result.append(tag)
    return result[:32]


def _safe_refine_psd(src: Path, *, third_party: Path, worker_python: str,
                     timeout: int = 1800) -> Path:
    """Run the *real* optional upstream depth/LR stage with its required sidecars.

    Both original and candidate remain available; invalid/changed composites
    never replace the source or falsely increase ArtMesh candidate counts.
    """
    from PIL import ImageChops, ImageStat
    from psd_tools import PSDImage
    from tools.vts_subprocess import run_logged

    script = third_party / "inference/scripts/heuristic_partseg.py"
    if not script.is_file():
        print("[See-through] official depth/LR script unavailable: using original PSD", flush=True)
        return src
    current = src
    for mode in ("seg_wdepth", "seg_wlr"):
        meta = Path(str(current) + ".json")
        depth_src = current.with_name(current.stem + "_depth.psd")
        if not meta.is_file() or not depth_src.is_file():
            print("[See-through] depth/metadata companion files absent: "
                  "cannot run native heuristic safely", flush=True)
            break
        tags = _observed_split_tags(meta, depth=(mode == "seg_wdepth"))
        if not tags:
            break
        cmd = [worker_python, "-u", str(script), mode,
               "--srcp", str(current), "--target_tags", ",".join(tags)]
        log = current.with_name(current.stem + "_" + mode + ".log")
        status = run_logged(cmd, cwd=third_party, log_path=log,
                            timeout_seconds=timeout)
        suffix = "_wdepth" if mode == "seg_wdepth" else "_lrsplit"
        result = current.with_name(current.stem + suffix + ".psd")
        if status != 0 or not result.is_file():
            print("[See-through] native heuristic rejected:", mode, str(log), flush=True)
            break
        old = PSDImage.open(current)
        new = PSDImage.open(result)
        if old.size != new.size:
            print("[See-through] heuristic changed canvas; rejected", flush=True)
            break
        first, second = old.composite(), new.composite()
        if first is None or second is None:
            break
        # Pixel-level difference in visible composite, not an invented rig metric.
        diff = ImageChops.difference(first.convert("RGBA"), second.convert("RGBA"))
        mean_error = max(ImageStat.Stat(diff).mean)
        old_n = sum(1 for x in old.descendants() if not x.is_group())
        new_n = sum(1 for x in new.descendants() if not x.is_group())
        if mean_error > 3 or new_n < old_n:
            print("[See-through] heuristic composite/part count regression rejected:",
                  mode, mean_error, old_n, new_n, flush=True)
            break
        current = result
        print("[See-through] native extra split accepted:",
              mode, old_n, "->", new_n, flush=True)
    return current


def run_see_through(master: Path, work: Path, *, third_party: Path, timeout: int = 7200):
    """Use the published NF4 PSD inference entrypoint, not a fake layer splitter."""
    master = master.expanduser().resolve(strict=True)
    work = work.expanduser().resolve()
    third_party = third_party.expanduser().resolve()
    program = third_party / "inference/scripts/inference_psd_quantized.py"
    if not program.is_file():
        raise FileNotFoundError(
            f"See-through quantized entrypoint missing: {program}. Run Colab cell ③ first."
        )
    # Turing GPUs (T4, compute capability 7.5) do not provide native BF16.
    # Adapt the pinned quantized script's requested math dtype only; weights
    # remain the upstream pre-quantized NF4 snapshots.
    import torch
    if not torch.cuda.is_available():
        raise RuntimeError("See-through NF4 decomposition requires a CUDA GPU")
    capability = torch.cuda.get_device_capability(0)
    if capability[0] < 8:
        source_program = program.read_text(encoding="utf-8")
        if source_program.count("torch.bfloat16") < 8:
            raise RuntimeError("See-through upstream BF16 patch contract changed")
        patched = source_program.replace("torch.bfloat16", "torch.float16")
        program = program.with_name("inference_psd_quantized_vts_fp16.py")
        program.write_text(patched, encoding="utf-8")
        print("[VTS] T4/older GPU: NF4 weights retained, compute dtype FP16. "
              "FP16 correctness remains subject to image QA.",flush=True)
    work.mkdir(parents=True, exist_ok=True)
    # Upstream writes to a fixed workspace relative to its cwd. A unique source
    # filename and input-only checksum avoid accepting a stale PSD from past jobs.
    unique_source = work / ("vts_" + work.name + master.suffix.lower())
    shutil.copyfile(master, unique_source)
    base = work / "see_through_output"
    base.mkdir(parents=True, exist_ok=True)
    before = {str(f): (f.stat().st_size, f.stat().st_mtime_ns)
              for f in base.rglob("*.psd")}
    log = work / "see_through_full.log"
    env = os.environ.copy()
    env["PYTHONUNBUFFERED"] = "1"
    env["HF_HUB_OFFLINE"] = "1"
    env["TRANSFORMERS_OFFLINE"] = "1"
    worker_python = os.environ.get("VTUBER_SEETHROUGH_PYTHON", sys.executable)
    command = [
        worker_python, "-u", str(program),
        "--srcp", str(unique_source), "--save_dir", str(base),
        "--save_to_psd", "--resolution", "1280",
        "--num_inference_steps", "30", "--resolution_depth", "768",
    ]
    print("[VTS] See-through NF4:", " ".join(command), flush=True)
    from tools.vts_subprocess import run_logged
    code = run_logged(command, cwd=third_party, env=env, log_path=log,
                      timeout_seconds=timeout)
    if code:
        raise RuntimeError(f"See-through exited {code}; full log: {log}")
    after = sorted(
        (f for f in base.rglob("*.psd")
         if not f.stem.endswith("_depth")
         and (f.stat().st_size, f.stat().st_mtime_ns) != before.get(str(f))),
        key=lambda f: f.stat().st_mtime_ns, reverse=True,
    )
    if not after:
        raise RuntimeError(f"See-through exited without a new PSD; full log: {log}")
    matched = [p for p in after if unique_source.stem in p.stem]
    if not matched:
        raise RuntimeError("See-through output PSD cannot be attributed to input; "
                           "refusing to reuse a possibly unrelated workspace result. "
                           f"Candidates: {[p.name for p in after[:5]]}; log: {log}")
    psd = work / "see_through_layers.psd"
    shutil.copy2(matched[0], psd)
    # The public heuristic reads source.psd.json AND source_depth.psd.
    # Copy both *only* when the pinned upstream actually produced them.
    generated_meta = Path(str(matched[0]) + ".json")
    generated_depth = matched[0].with_name(matched[0].stem + "_depth.psd")
    if generated_meta.is_file() and generated_depth.is_file():
        shutil.copy2(generated_meta, Path(str(psd) + ".json"))
        shutil.copy2(generated_depth, psd.with_name(psd.stem + "_depth.psd"))
    return _safe_refine_psd(psd, third_party=third_party,
                            worker_python=worker_python)


def make_cubism_handoff(master: Path, output: Path, *, edition: str, scope: str,
                        asset_kind: str | None = None,
                        reference_image: Path | None = None,
                        external_psd: Path | None = None,
                        third_party: Path | None = None,
                        qwen: bool = False, qwen_layers: int = 6,
                        qwen_passes: int = 8) -> dict:
    """Produce a *layered image* ZIP, not an unimportable pseudo-rig.

    Each PRO call processes exactly one body/hair/outfit/accessory asset.
    It never requires all detachable assets from the same user.
    """
    from tools.vts_artwork_export import validate_artwork_request
    validate_artwork_request(edition=edition, scope=scope, asset_kind=asset_kind,
                             per_pass_layers=qwen_layers, max_qwen_passes=qwen_passes)
    canvas = _image(master)
    if edition == "pro" and asset_kind != "body":
        if reference_image is None:
            raise ValueError("PRO detachable asset requires an existing body reference")
        reference_canvas = _image(reference_image)
        if canvas != reference_canvas:
            raise ValueError("PRO body reference and asset must share exact canvas dimensions")
    output.mkdir(parents=True, exist_ok=True)
    state_path = output / "vts_status.json"
    status = {"edition": edition, "scope": scope, "asset_kind": asset_kind,
              "state": "running", "moc3_generated": False, "editor_required": True}
    _write(state_path, status)
    try:
        psd = (external_psd.resolve(strict=True) if external_psd
               else run_see_through(
                   master, output / "decomposition",
                   third_party=(third_party or Path("/content/vtuber_builder/third_party/see-through"))
               ))
        # PSD mask/alpha extraction preserves original See-through pixels.
        _, registered, count = psd_to_registered_rgba(
            psd, output / "layers", artmesh_max=100 if edition == "free" else None,
        )
        registration = {"method": "external_psd_already_registered"}
        if external_psd is None:
            registered, registration = restore_source_canvas(
                registered, canvas, output / "layers/source_frame_layers.zip")
        else:
            from psd_tools import PSDImage
            if PSDImage.open(psd).size != canvas:
                raise ValueError("External PSD must match the input reference canvas; "
                                 "cannot infer its crop/padding transform")
        from tools.vts_artwork_export import build_artwork_package
        produced = build_artwork_package(
            registered, output / "artwork", edition=edition, scope=scope,
            asset_kind=asset_kind, qwen=qwen,
            per_pass_layers=qwen_layers, max_qwen_passes=qwen_passes,
            third_party=(third_party or Path("/content/vtuber_builder/third_party/see-through")).parent,
            python_path=os.environ.get("VTUBER_SEETHROUGH_PYTHON"),
        )
        # Keep actual submitted imagery alongside the split PSD for manual
        # registration checks and independent PRO asset re-import.
        with ZipFile(produced["package"], "a", ZIP_DEFLATED) as archive:
            archive.write(master, "input_reference/source_" + master.name)
            archive.write(psd, "source_psd/see_through_layers.psd")
            # Side-by-side visual check: source may be a higher resolution
            # portrait while See-through renders square 1280px internally.
            # Never silently claim the returned layer pixels are native
            # master-resolution RGB.
            from PIL import Image, ImageDraw
            from io import BytesIO
            with Image.open(master) as original:
                original.load()
                final = Image.open(BytesIO(archive.read("preview/composite.png")))
                final.load()
                thumb = (720, 720)
                source_t = original.convert("RGBA")
                result_t = final.convert("RGBA")
                source_t.thumbnail(thumb, Image.Resampling.LANCZOS)
                result_t.thumbnail(thumb, Image.Resampling.LANCZOS)
                panel = Image.new("RGBA", (1440, 770), (235, 235, 235, 255))
                sx, sy = (720 - source_t.width) // 2, (720 - source_t.height) // 2 + 35
                rx, ry = 720 + (720 - result_t.width) // 2, (720 - result_t.height) // 2 + 35
                panel.alpha_composite(source_t, (sx, sy))
                panel.alpha_composite(result_t, (rx, ry))
                draw = ImageDraw.Draw(panel)
                draw.text((16, 12), "INPUT ORIGINAL", fill=(0, 0, 0, 255))
                draw.text((736, 12), "EXTRACTED PSD COMPOSITE", fill=(0, 0, 0, 255))
                stream = BytesIO()
                panel.convert("RGB").save(stream, format="PNG")
                archive.writestr("preview/input_vs_psd_comparison.png", stream.getvalue())
                geometry = {
                    "schema": "vtuber/artwork-source-comparison-v1",
                    "source_canvas": list(original.size),
                    "output_psd_canvas": list(final.size),
                    "same_pixel_canvas": original.size == final.size,
                    "coordinate_transform": registration,
                    "source_fidelity_verified": False,
                    "visible_rgb_original_resolution_guaranteed": False,
                    "note": "Review the two visual images. Inference may resize or "
                            "inpaint pixels; source file is preserved separately.",
                }
                archive.writestr(
                    "metadata/input_vs_psd_geometry.json",
                    json.dumps(geometry, ensure_ascii=False, indent=2),
                )
            if reference_image is not None:
                archive.write(reference_image, "input_reference/body_" + reference_image.name)
                # Visual registration evidence, NOT automatic feature matching.
                # Cap review resolution without altering output PSD/PNG pixels.
                from PIL import Image
                from io import BytesIO
                with Image.open(reference_image) as original, Image.open(
                    BytesIO(archive.read("preview/composite.png"))) as asset:
                    original.load()
                    asset.load()
                    preview = original.convert("RGBA")
                    overlay = asset.convert("RGBA")
                    preview.thumbnail((1400, 1400), Image.Resampling.LANCZOS)
                    overlay = overlay.resize(preview.size, Image.Resampling.LANCZOS)
                    mixed = Image.blend(preview, overlay, 0.5)
                    stream = BytesIO()
                    mixed.save(stream, format="PNG")
                    archive.writestr("preview/pro_body_asset_overlay.png", stream.getvalue())
                    report_align = {
                        "schema": "vtuber/pro-manual-registration-v1",
                        "input_canvas_identical": original.size == asset.size,
                        "output_psd_canvas": produced["canvas"],
                        "output_canvas_matches_body": list(original.size) == produced["canvas"],
                        "input_size": list(original.size),
                        "method": "50-percent body / final PSD composite visual overlay only",
                        "automatic_pose_landmark_alignment_verified": False,
                        "automatic_character_identity_verified": False,
                        "warning": "Visually inspect hair/outfit/accessory boundaries "
                                   "before importing into Cubism Editor.",
                    }
                    archive.writestr(
                        "metadata/pro_reference_alignment.json",
                        json.dumps(report_align, ensure_ascii=False, indent=2),
                    )
            for log_path in sorted((output / "decomposition").rglob("*.log")):
                archive.write(log_path, "logs/see_through/" + str(
                    log_path.relative_to(output / "decomposition")))
            produced["supporting_files"] = [
                name for name in archive.namelist()
                if name != Path(produced["art_psd"]).name]
        report = {
            **status, **produced, "state": "artwork_ready_editor_rig_required",
            "psd_source": str(psd), "source_master": str(master),
            "source_layer_count": count, "reference_image": (
                str(reference_image) if reference_image else None),
            "warning": "Genuine layered PSD artwork only; Cubism Editor must "
                       "create ArtMeshes, deformers, keyforms, physics and export MOC3. "
                       "PRO alignment requires visual review in Editor.",
        }
        _write(state_path, report)
        return report
    except Exception as exc:
        _write(state_path, {**status, "state": "failed", "error": str(exc)})
        raise


def main() -> None:
    ap = argparse.ArgumentParser(description="VTS FREE/PRO Cubism PSD handoff (not MOC3)")
    ap.add_argument("--edition", required=True, choices=("free", "pro"))
    ap.add_argument("--scope", required=True, choices=("upper", "full"))
    ap.add_argument("--master", type=Path, required=True)
    ap.add_argument("--output", type=Path, required=True)
    ap.add_argument("--psd", type=Path, help="Pre-generated See-through PSD, skip GPU decomposition")
    ap.add_argument("--third-party", type=Path)
    ap.add_argument("--qwen", action="store_true", help="Run quantized Qwen+Stable-Layers candidate refinement")
    ap.add_argument("--qwen-layers", type=int, default=6)
    ap.add_argument("--qwen-passes", type=int, default=8)
    ap.add_argument("--asset", choices=("body", "hair", "outfit", "accessory"), help="Required for PRO")
    ap.add_argument("--reference", type=Path, help="Existing body image for a detachable PRO asset")
    args = ap.parse_args()
    out = make_cubism_handoff(
        args.master, args.output, edition=args.edition, scope=args.scope,
        external_psd=args.psd, third_party=args.third_party, qwen=args.qwen,
        asset_kind=args.asset, reference_image=args.reference,
        qwen_layers=args.qwen_layers, qwen_passes=args.qwen_passes,
    )
    print(json.dumps({"status": out["state"], "package": out["package"],
                      "moc3_generated": False}, ensure_ascii=False))


if __name__ == "__main__":
    main()
