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
    # The See-through / Qwen layer name is a semantic identity, not just an
    # annotation. Never discard left/right, front/back, iris or lid suffixes.
    canonical = ("hair.", "eye.", "eyebrow.", "mouth.", "cloth.",
                 "body.", "arm.", "leg.", "hand.", "shoe.", "accessory.")
    if raw.startswith(canonical):
        return raw
    name = raw.replace(".", " ")
    side = "left" if "left" in name else "right" if "right" in name else None
    if "iris" in name or "pupil" in name or "eyelid" in name or "sclera" in name:
        detail = next(x for x in ("iris", "pupil", "eyelid", "sclera") if x in name)
        return ("eye." + side + "." + detail) if side else ("eye." + detail)
    if "eye" in name and side:
        return "eye." + side
    if ("eyebrow" in name or "brow" in name) and side:
        return "eyebrow." + side
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


def run_see_through(master: Path, work: Path, *, third_party: Path, timeout: int = 7200):
    """Use the published NF4 PSD inference entrypoint, not a fake layer splitter."""
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
    worker_python = os.environ.get("VTUBER_SEETHROUGH_PYTHON", sys.executable)
    command = [
        worker_python, "-u", str(program),
        "--srcp", str(unique_source), "--save_dir", str(base),
        "--save_to_psd", "--resolution", "1024",
    ]
    print("[VTS] See-through NF4:", " ".join(command), flush=True)
    from tools.vts_subprocess import run_logged
    code = run_logged(command, cwd=third_party, env=env, log_path=log,
                      timeout_seconds=timeout)
    if code:
        raise RuntimeError(f"See-through exited {code}; full log: {log}")
    after = sorted(
        (f for f in base.rglob("*.psd")
         if (f.stat().st_size, f.stat().st_mtime_ns) != before.get(str(f))),
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
    return psd


def make_cubism_handoff(master: Path, output: Path, *, edition: str, scope: str,
                        asset_kind: str | None = None,
                        reference_image: Path | None = None,
                        external_psd: Path | None = None,
                        third_party: Path | None = None,
                        qwen: bool = False) -> dict:
    """Produce a *layered image* ZIP, not an unimportable pseudo-rig.

    Each PRO call processes exactly one body/hair/outfit/accessory asset.
    It never requires all detachable assets from the same user.
    """
    if edition not in ("free", "pro") or scope not in ("upper", "full"):
        raise ValueError("Invalid VTS edition or scope")
    if edition == "free" and asset_kind is not None:
        raise ValueError("FREE requires one finished character image, not PRO assets")
    if edition == "pro" and asset_kind not in ("body", "hair", "outfit", "accessory"):
        raise ValueError("PRO requires one independent body/hair/outfit/accessory submode")
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
        from tools.vts_artwork_export import build_artwork_package
        produced = build_artwork_package(
            registered, output / "artwork", edition=edition, scope=scope,
            asset_kind=asset_kind, qwen=qwen,
            third_party=(third_party or Path("/content/vtuber_builder/third_party/see-through")).parent,
            python_path=os.environ.get("VTUBER_SEETHROUGH_PYTHON"),
        )
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
    ap.add_argument("--asset", choices=("body", "hair", "outfit", "accessory"), help="Required for PRO")
    ap.add_argument("--reference", type=Path, help="Existing body image for a detachable PRO asset")
    args = ap.parse_args()
    out = make_cubism_handoff(
        args.master, args.output, edition=args.edition, scope=args.scope,
        external_psd=args.psd, third_party=args.third_party, qwen=args.qwen,
        asset_kind=args.asset, reference_image=args.reference,
    )
    print(json.dumps({"status": out["state"], "package": out["package"],
                      "moc3_generated": False}, ensure_ascii=False))


if __name__ == "__main__":
    main()
