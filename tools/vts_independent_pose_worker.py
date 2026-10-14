"""Render repeatable parameter sweeps with the *independent* image2live2d rig.

This is NOT Cubism Core or a PSD2Live MOC3 renderer. Separate provenance is
mandatory, since conflating the two backends concealed eye/neck defects.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

POSES = (
    ("neutral", {}),
    ("yaw_left", {"ParamAngleX": -30}),
    ("yaw_right", {"ParamAngleX": 30}),
    ("pitch_up", {"ParamAngleY": 30}),
    ("pitch_down", {"ParamAngleY": -30}),
    ("roll_left", {"ParamAngleZ": -30}),
    ("roll_right", {"ParamAngleZ": 30}),
    ("yaw_left_blink", {"ParamAngleX": -30, "ParamEyeLOpen": 0, "ParamEyeROpen": 0}),
    ("yaw_right_blink", {"ParamAngleX": 30, "ParamEyeLOpen": 0, "ParamEyeROpen": 0}),
    ("mouth_open", {"ParamMouthOpenY": 1}),
)

def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--psd", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    from image2live2d.core import decompose
    from image2live2d.pipeline import rig_from_stack
    from image2live2d.preview import render_pose
    from image2live2d.core.qa import evaluate
    from PIL import ImageChops
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=True)
    stack = decompose.from_psd(args.psd, output / "imported_layers")
    rig = rig_from_stack(stack, name=args.psd.stem,
                         source=str(args.psd))
    # A real second OSS rig artifact, distinct from Cubism MOC3.
    from image2live2d.backends.nijilive import NijiliveEmitter
    independent_inp = NijiliveEmitter(asset_root=output / "imported_layers").emit(
        rig, output / "independent_nijilive")
    valid_params = {p.id: p for p in rig.parameters}
    report = {"schema": "vtuber/independent-pose-sweep-v1",
              "source": "image2live2d_independent_rig",
              "psd": str(args.psd), "frames": [], "errors": [],
              "native_psd2live_model_verified": False,
              "render_engine": "image2live2d.preview.render_pose",
              "independent_nijilive_inp": str(independent_inp)}
    original = None
    for label, values in POSES:
        actual = {k: min(max(v, valid_params[k].min), valid_params[k].max)
                  for k, v in values.items() if k in valid_params}
        skipped = sorted(set(values) - set(actual))
        frame = render_pose(stack, rig.meshes, rig.parameters, actual, res=768)
        if frame.mode != "RGBA":
            frame = frame.convert("RGBA")
        path = output / (label + ".png")
        frame.save(path)
        bbox = frame.getchannel("A").getbbox()
        pixels = sum(1 for a in frame.getchannel("A").getdata() if a > 10)
        if not pixels or not bbox:
            report["errors"].append({"pose": label, "code": "EMPTY_POSE_FRAME"})
        if label == "neutral":
            original = frame.copy()
        delta = None
        if original is not None and label != "neutral":
            delta = ImageChops.difference(frame.convert("RGB"), original.convert("RGB")).getbbox()
            if not actual:
                report["errors"].append({"pose": label, "code": "DRIVER_PARAMETERS_ABSENT",
                                         "missing": skipped})
            elif delta is None:
                report["errors"].append({"pose": label, "code": "POSE_NOT_CHANGING",
                                         "params": actual})
        report["frames"].append({
            "pose": label, "image": str(path), "actual_parameters": actual,
            "missing_parameters": skipped, "visible_pixels": pixels,
            "alpha_bounds": bbox, "differs_from_neutral": bool(delta),
        })
    qa = evaluate(rig, rig.meta.name)
    report["image2live2d_qa_passed"] = bool(qa.passed)
    report["source_render_checks_passed"] = not report["errors"]
    report["actual_native_pose_rendered"] = False
    report["vts_runtime_verified"] = False
    result = output / "pose_review.json"
    result.write_text(json.dumps(report, ensure_ascii=False, indent=2),
                      encoding="utf-8")
    print("SECONDARY_POSE_SWEEP " + str(result), flush=True)
    return 0 if not report["errors"] else 2

if __name__ == "__main__":
    raise SystemExit(main())
