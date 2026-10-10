"""Fail-closed batching of pinned See-through NF4 vendor worker.

The published quantized worker accepts a single image.  This adaptation
groups all images into two phases (LayerDiff, then Marigold) to build each
GPU model once per batch rather than once per part.  Models are intentionally
released between phases to respect 16-GB T4 VRAM.
"""
from __future__ import annotations

import ast

START = "    srcp = args.srcp\n"
END = """    print(f'Stats saved to {osp.join(saved, "stats.json")}')"""


def patch_quantized_batch(source: str) -> str:
    """Adapt a pinned quantized worker; reject changed upstream boundaries.

    No override to weights, sampling, resolution, or head/body tags.
    """
    if source.count(START) != 1 or source.count(END) != 1:
        raise RuntimeError("Pinned See-through NF4 single-image worker changed")
    if source.index(END) < source.index(START):
        raise RuntimeError("Invalid pinned See-through NF4 main() boundaries")
    prefix = source.split(START, 1)[0]
    suffix = source.split(END, 1)[1]
    if suffix.strip():
        raise RuntimeError("Unexpected See-through NF4 code after stats")
    body = '''    # VTS-only batch: an input directory of uniquely named PNG images.
    # Use a single LayerDiff model for all images, then release it and use
    # a single Marigold model for all images.  Never keep both on the GPU.
    from pathlib import Path
    source_dir = Path(args.srcp)
    if not source_dir.is_dir():
        raise ValueError("VTS batch requires an input image directory")
    sources = sorted(str(p) for p in source_dir.iterdir()
                     if p.is_file() and p.suffix.lower() == ".png")
    if not sources:
        raise ValueError("VTS batch input directory contains no PNG images")
    if len({Path(p).stem for p in sources}) != len(sources):
        raise ValueError("Duplicate source stems in VTS batch")
    print(f"[VTS BATCH] source_count={len(sources)}", flush=True)
    seed_everything(args.seed)
    torch.cuda.reset_peak_memory_stats()
    total_t0 = time.time()

    print("[VTS BATCH] load LayerDiff once", flush=True)
    pipeline = build_layerdiff_pipeline(args)
    for index, srcp in enumerate(sources, 1):
        print(f"[VTS BATCH] LayerDiff {index}/{len(sources)} "
              f"source={Path(srcp).name}", flush=True)
        run_layerdiff(pipeline, srcp, args.save_dir, args.seed,
                      args.num_inference_steps, args.resolution)
        torch.cuda.empty_cache()
    del pipeline
    torch.cuda.empty_cache()

    print("[VTS BATCH] load Marigold once", flush=True)
    marigold_pipe = build_marigold_pipeline(args)
    for index, srcp in enumerate(sources, 1):
        print(f"[VTS BATCH] Marigold {index}/{len(sources)} "
              f"source={Path(srcp).name}", flush=True)
        run_marigold(marigold_pipe, srcp, args.save_dir, args.seed,
                     resolution_depth=args.resolution_depth)
        torch.cuda.empty_cache()
    del marigold_pipe
    torch.cuda.empty_cache()

    for index, srcp in enumerate(sources, 1):
        srcname = osp.basename(osp.splitext(srcp)[0])
        saved = osp.join(args.save_dir, srcname)
        print(f"[VTS BATCH] PSD {index}/{len(sources)} "
              f"source={Path(srcp).name}", flush=True)
        further_extr(saved, rotate=False, save_to_psd=args.save_to_psd,
                     tblr_split=args.tblr_split)
        stats = {"quant_mode": args.quant_mode,
                 "batch_size": len(sources),
                 "source": Path(srcp).name,
                 "peak_vram_gb": torch.cuda.max_memory_allocated() / 1024**3,
                 "total_batch_elapsed_s": time.time() - total_t0}
        with open(osp.join(saved, "stats.json"), "w") as f:
            json.dump(stats, f, indent=2)
    print(f"[VTS BATCH] complete count={len(sources)} "
          f"seconds={time.time()-total_t0:.1f}", flush=True)
'''
    generated = prefix + body + suffix
    ast.parse(generated)
    compile(generated, "<vts_quantized_batch>", "exec")
    return generated
