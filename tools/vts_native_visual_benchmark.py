"""Reference-guided *measured* native Live2D pose image comparison.

A native Cubism pose changing pixels is not a quality benchmark. Compare its
actual transparent frames to independently authored, registered 3/4 drawings
on the same canvas, optionally against a previous native rig. Image metrics
remain geometric/pixel evidence, never proof of artistic excellence.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
from PIL import Image, ImageChops

PAIRS = {
    "head_three_quarter_L": "yaw_left_45",
    "head_three_quarter_R": "yaw_right_45",
}


def compare_transparent_images(reference: Path, rendered: Path) -> dict:
    with Image.open(reference) as src, Image.open(rendered) as tgt:
        src.load()
        tgt.load()
        if src.size != tgt.size:
            raise ValueError("NATIVE_VISUAL_CANVAS_MISMATCH: registered views required")
        if min(src.size) < 128:
            raise ValueError("NATIVE_VISUAL_CANVAS_TOO_SMALL")
        a = np.asarray(src.convert("RGBA"), dtype=np.float32)
        b = np.asarray(tgt.convert("RGBA"), dtype=np.float32)
    ra, rb = a[:, :, 3], b[:, :, 3]
    for name, alpha in (("reference", ra), ("native", rb)):
        if float(alpha.max()) < 16 or float(alpha.min()) >= 250:
            raise ValueError("NATIVE_VISUAL_TRANSPARENCY_REQUIRED: " + name)
    mask_a, mask_b = ra > 10, rb > 10
    inter = mask_a & mask_b
    union = mask_a | mask_b
    if not np.any(inter) or not np.any(union):
        raise ValueError("NATIVE_VISUAL_FOREGROUND_MISSING")
    alpha_iou = float(np.count_nonzero(inter) / np.count_nonzero(union))
    # Color errors are meaningful only where both registered drawings exist:
    # avoid treating transparent background RGB as a painted part defect.
    mae = float(np.abs(a[:, :, :3][inter] - b[:, :, :3][inter]).mean() / 255)
    alpha_mae = float(np.abs(ra - rb).mean() / 255)
    ys_a, xs_a = np.where(mask_a)
    ys_b, xs_b = np.where(mask_b)
    diag = float(np.hypot(a.shape[1], a.shape[0]))
    centroid_displacement = float(np.hypot(
        xs_a.mean() - xs_b.mean(), ys_a.mean() - ys_b.mean()) / diag)
    return {
        "alpha_iou": round(alpha_iou, 6),
        "overlap_rgb_mae_0_1": round(mae, 6),
        "alpha_mae_0_1": round(alpha_mae, 6),
        "foreground_centroid_offset_fraction": round(centroid_displacement, 6),
        "compared_overlap_pixels": int(np.count_nonzero(inter)),
        "both_true_alpha": True,
        "reference_artistic_equivalence_verified": False,
    }


def _native_evidence(folder: Path) -> None:
    report = folder / "native_pose_report.json"
    if not report.is_file():
        raise RuntimeError("NATIVE_VISUAL_NEEDS_ACTUAL_MOC3_RUNTIME_REPORT")
    data = json.loads(report.read_text(encoding="utf-8"))
    if (data.get("source") != "live2d_py_cubism_native_runtime"
            or data.get("native_pose_rendered") is not True
            or data.get("pose_activity_passed") is not True):
        raise RuntimeError("NATIVE_VISUAL_MOC3_RUNTIME_NOT_VERIFIED")


def _measured(reference_dir: Path, native_dir: Path) -> dict:
    _native_evidence(native_dir)
    result = {}
    for source, pose in PAIRS.items():
        source_image = reference_dir / (source + ".png")
        native_image = native_dir / (pose + ".png")
        if not source_image.is_file() or not native_image.is_file():
            raise FileNotFoundError("NATIVE_VISUAL_REFERENCE_PAIR_MISSING: " + source)
        result[source] = compare_transparent_images(source_image, native_image)
    return result


def evaluate_native_visual_change(reference_dir: Path, native_dir: Path,
                                  output: Path, *,
                                  previous_native_dir: Path | None = None) -> dict:
    """Observe real images and fail closed on regressed/absent improvements."""
    reference_dir, native_dir = Path(reference_dir), Path(native_dir)
    now = _measured(reference_dir, native_dir)
    before = (_measured(reference_dir, Path(previous_native_dir))
              if previous_native_dir is not None else None)
    comparisons = {}
    for label, measured in now.items():
        if before is None:
            comparisons[label] = {"measured": True, "relative_improvement_verified": False}
            continue
        old = before[label]
        delta_iou = measured["alpha_iou"] - old["alpha_iou"]
        delta_rgb = old["overlap_rgb_mae_0_1"] - measured["overlap_rgb_mae_0_1"]
        delta_centroid = (old["foreground_centroid_offset_fraction"]
                          - measured["foreground_centroid_offset_fraction"])
        # Never accept a large regression in one metric to improve another.
        no_regression = (delta_iou >= -0.005 and delta_rgb >= -0.008
                         and delta_centroid >= -0.005)
        meaningful = (delta_iou >= 0.01 or delta_rgb >= 0.015
                      or delta_centroid >= 0.01)
        comparisons[label] = {
            "alpha_iou_delta": round(delta_iou, 6),
            "overlap_rgb_mae_reduction": round(delta_rgb, 6),
            "centroid_offset_reduction": round(delta_centroid, 6),
            "no_large_regression": no_regression,
            "measurable_improvement": meaningful,
            "relative_improvement_verified": no_regression and meaningful,
        }
    relative_pass = bool(
        before is not None and
        all(item["no_large_regression"] for item in comparisons.values()) and
        any(item["measurable_improvement"] for item in comparisons.values()))
    report = {
        "schema": "vtuber/native-3quarter-pixel-quality-v1",
        "status": ("measurably_improved_not_artistically_certified" if relative_pass
                   else "measured_without_quality_improvement_certification"),
        "pixel_improvement_verified": relative_pass,
        "native_reference_pose_image_comparisons": now,
        "baseline": before,
        "relative_comparison": comparisons,
        "registered_original_canvas_required": True,
        "human_or_vlm_artistic_review_required": True,
        "actual_vtube_studio_tracking_verified": False,
        "artistic_quality_verified": False,
        "view_angles": [-45, 45],
    }
    output = Path(output)
    output.mkdir(parents=True, exist_ok=True)
    (output / "native_pixel_quality.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    if previous_native_dir is not None and not relative_pass:
        raise RuntimeError("NATIVE_VISUAL_DID_NOT_IMPROVE: " +
                           str(output / "native_pixel_quality.json"))
    return report


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--reference-dir", type=Path, required=True)
    p.add_argument("--native-dir", type=Path, required=True)
    p.add_argument("--previous-native-dir", type=Path)
    p.add_argument("--output", type=Path, required=True)
    args = p.parse_args()
    report = evaluate_native_visual_change(
        args.reference_dir, args.native_dir, args.output,
        previous_native_dir=args.previous_native_dir)
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
