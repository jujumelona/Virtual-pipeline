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
    name = name.casefold().replace("_", " ").replace("-", " ")
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
        tile = layer.composite()  # compose PSD alpha/masks; topil() loses RGBA on RGB PSDs
        if tile is None:
            continue
        tile = tile.convert("RGBA")
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
    if len(leaves) > 512:
        raise ValueError("Excessive PSD layer count (>512)")
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
    started = time.monotonic()
    with log.open("w", encoding="utf-8") as out:
        proc = subprocess.Popen(command, cwd=third_party, env=env,
                                stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                text=True, bufsize=1)
        try:
            for line in proc.stdout:
                out.write(line)
                out.flush()
                print(line, end="", flush=True)
                if time.monotonic() - started > timeout:
                    raise TimeoutError(f"See-through timed out after {timeout}s")
            code = proc.wait(timeout=15)
        except BaseException:
            proc.kill()
            proc.wait(timeout=20)
            raise
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
                        external_psd: Path | None = None,
                        third_party: Path | None = None,
                        qwen: bool = False,
                        assets_dir: Path | None = None) -> dict:
    """Generate a real Cubism-editable artwork package and JSON rigging assets."""
    if edition not in ("free", "pro") or scope not in ("upper", "full"):
        raise ValueError("Invalid VTS edition or scope")
    _image(master)
    companion_assets = []
    if edition == "pro":
        if assets_dir is None:
            raise ValueError("PRO requires separately generated base/hair/outfit asset images")
        required = [f"pro_{scope}_{name}.png" for name in
                    ("base_master", "hair_variant", "outfit_variant")]
        for name in required:
            path = assets_dir/name
            _image(path)
            companion_assets.append(path)
        extra = assets_dir/f"pro_{scope}_accessories_variant.png"
        if extra.is_file():
            _image(extra)
            companion_assets.append(extra)
    output.mkdir(parents=True, exist_ok=True)
    state_path = output / "vts_status.json"
    status = {"edition": edition, "scope": scope, "state": "running",
              "moc3_generated": False, "editor_required": True}
    _write(state_path, status)
    try:
        psd = (external_psd.resolve(strict=True) if external_psd
               else run_see_through(
                   master, output / "decomposition",
                   third_party=(third_party or Path("/content/vtuber_builder/third_party/see-through"))
               ))
        qwen_result = None
        if qwen:
            from tools.vts_qwen_refine import infer
            print("[VTS] quantized Qwen + Stable-Layers Heun 50-step stage",flush=True)
            qwen_result = infer(master, output / "qwen_refinement", third_party=(third_party or Path("/content/vtuber_builder/third_party/see-through")).parent,
                                python=os.environ.get("VTUBER_SEETHROUGH_PYTHON"))
        source, layers, count = psd_to_registered_rgba(
            psd, output / "layers",
            artmesh_max=100 if edition == "free" else None,
        )
        from vtuber_pipeline.common.schemas import SourceSet
        from vtuber_pipeline.two_d.build import build_live2d
        # Do not inherit strict legacy 20-part hairless base validation.
        previous = os.environ.pop("VTUBER_2D_STRICT_LAYER_INPUT", None)
        try:
            result = build_live2d(SourceSet(
                "live2d", str(source), user_layers_zip=str(layers),
                output_dir=str(output / "cubism"), artwork_profile="vts_auto",
            ))
        finally:
            if previous is not None:
                os.environ["VTUBER_2D_STRICT_LAYER_INPUT"] = previous
        if result.status != "needs_editor_export":
            raise RuntimeError("Cubism artwork rigging failed: " + (result.error or result.status))
        report = {
            **status, "state": "needs_editor_export", "psd_source": str(psd),
            "visible_artmesh_candidates": count, "source_master": str(master),
            "cubism_handoff": result.primary_path, "art_psd": result.secondary_path,
            "qwen_refinement": qwen_result,
            "pro_companion_artworks": [str(p) for p in companion_assets],
            "free_artmesh_within_limit": edition != "free" or count <= 100,
            "unverified_editor_limits": [
                "Cubism parameter count", "deformer count", "part-folder count",
                "2048px single texture atlas", "native deformation quality",
            ],
            "warning": "PSD/rig JSON only. No .moc3 or .cmo3 created. "
                       "Finish/validate in official Cubism Editor.",
        }
        _write(state_path, report)
        result_zip = output / f"vts_{edition}_{scope}_cubism_handoff.zip"
        with ZipFile(result_zip, "w", ZIP_DEFLATED) as archive:
            for name, path in (
                ("vts_status.json", state_path),
                ("see_through_layers.psd", psd),
                ("registered_layers.zip", layers),
                ("cubism_handoff.zip", Path(result.primary_path)),
                ("psd_composite.png", source),
            ):
                archive.write(path, name)
            for companion in companion_assets:
                archive.write(companion, "pro_original_assets/"+companion.name)
            if qwen_result:
                for i, path in enumerate(qwen_result["layers"]):
                    archive.write(path, f"qwen_4bit_stable_layers/layer_{i}.png")
                archive.write(output/"qwen_refinement/qwen_stage.json",
                              "qwen_4bit_stable_layers/qwen_stage.json")
        return {**report, "package": str(result_zip)}
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
    ap.add_argument("--assets-dir", type=Path, help="PRO companion original asset directory")
    args = ap.parse_args()
    out = make_cubism_handoff(
        args.master, args.output, edition=args.edition, scope=args.scope,
        external_psd=args.psd, third_party=args.third_party, qwen=args.qwen,
        assets_dir=args.assets_dir,
    )
    print(json.dumps({"status": out["state"], "package": out["package"],
                      "moc3_generated": False}, ensure_ascii=False))


if __name__ == "__main__":
    main()
