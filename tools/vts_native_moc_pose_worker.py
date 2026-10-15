"""Native MOC3 angle-frame capture with live2d-py/Cubism Core and OpenGL.

Execute under Xvfb on Linux (e.g. xvfb-run -a python -m tools.vts_native_moc_pose_worker ...).
Third-party Cubism runtime licenses remain independent of our project.
This is a real MOC3 runtime screenshot, unlike image2live2d's proxy preview.
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
    ("blink_neutral", {"ParamEyeLOpen": 0, "ParamEyeROpen": 0}),
    ("blink_yaw_left", {"ParamAngleX": -30, "ParamEyeLOpen": 0, "ParamEyeROpen": 0}),
    ("blink_yaw_right", {"ParamAngleX": 30, "ParamEyeLOpen": 0, "ParamEyeROpen": 0}),
    ("mouth_open", {"ParamMouthOpenY": 1}),
)

def run(model3: Path, output: Path, *, size: int = 768) -> dict:
    import pygame
    from pygame.locals import DOUBLEBUF, OPENGL
    import live2d  # live2d-py 1.x exports Model and Cubism APIs at package root
    from OpenGL.GL import glReadPixels, glFinish, GL_RGBA, GL_UNSIGNED_BYTE
    from PIL import Image, ImageChops, ImageStat

    model3 = model3.resolve(strict=True)
    output.mkdir(parents=True, exist_ok=True)
    pygame.init()
    pygame.display.set_mode((size, size), DOUBLEBUF | OPENGL)
    live2d.init()
    live2d.glInit()
    model = live2d.Model()
    try:
        model.LoadModelJson(str(model3))
        model.Resize(size, size)
        # live2d-py 1.0.0 exposes SetAutoBlink/SetAutoBreath.
        # Unrecognized old Enable names silently leave autonomous motions on.
        for name in ("SetAutoBlink", "SetAutoBreath"):
            fun = getattr(model, name, None)
            if callable(fun):
                fun(False)
        # Do not allow unknown parameter identifiers to masquerade as
        # successful animated keyforms. Cubism's setter can be a no-op for
        # an absent parameter, and a blank/static model is not a passed rig.
        available = set(model.GetParamIds())
        required_controls = {"ParamAngleX", "ParamAngleY", "ParamAngleZ",
                             "ParamEyeLOpen", "ParamEyeROpen", "ParamMouthOpenY"}
        missing_controls = sorted(required_controls - available)
        if missing_controls:
            raise RuntimeError(
                "NATIVE_MODEL_MISSING_ANIMATION_CONTROLS: "
                + ", ".join(missing_controls))
        report = {
            "schema": "vtuber/live2d-native-moc3-poses-v1",
            "source": "live2d_py_cubism_native_runtime",
            "model3_json": str(model3),
            "native_pose_rendered": False,
            "vts_application_tracking_verified": False,
            "visual_artistic_quality_verified": False,
            "frames": [], "failures": [],
        }
        neutral = None
        defaults = {
            "ParamAngleX": 0, "ParamAngleY": 0, "ParamAngleZ": 0,
            "ParamEyeLOpen": 1, "ParamEyeROpen": 1, "ParamMouthOpenY": 0,
        }
        for label, params in POSES:
            for key, value in {**defaults, **params}.items():
                # Persist across Model.Update(): SetParamById may otherwise be reset.
                model.SetSaveParamById(key, value, 1)
            live2d.clearBuffer()
            model.Update()
            model.Draw()
            glFinish()
            pixels = glReadPixels(0, 0, size, size, GL_RGBA, GL_UNSIGNED_BYTE)
            img = Image.frombytes("RGBA", (size, size), bytes(pixels))
            img = img.transpose(Image.Transpose.FLIP_TOP_BOTTOM)
            dest = output / f"{label}.png"
            img.save(dest)
            # Real GL targets sometimes render opaque. Use RGB activity too.
            stat = ImageStat.Stat(img.convert("RGB"))
            changed = None
            if neutral is not None:
                changed = ImageChops.difference(img.convert("RGB"), neutral.convert("RGB")).getbbox()
            else:
                neutral = img.copy()
            if max(stat.stddev) < 1.0:
                report["failures"].append({"pose": label, "code": "NATIVE_RENDER_FLAT"})
            if params and changed is None:
                report["failures"].append({"pose": label, "code": "NATIVE_POSE_UNCHANGED"})
            report["frames"].append({
                "pose": label, "image": str(dest), "requested_parameters": params,
                "different_from_neutral": changed is not None if params else None,
                "rgb_stddev": [round(float(v), 4) for v in stat.stddev],
            })
        # Native frame activity alone can pass a severely torn rig.
        # A connected neutral BODY that breaks into large separate regions
        # during tilt/roll is structurally invalid even though pixels changed.
        from tools.vts_native_pose_integrity import inspect_native_pose_frames
        geometry = inspect_native_pose_frames(output)
        report["geometry"] = geometry
        report["native_pose_geometry_passed"] = geometry["geometry_passed"]
        report["failures"].extend(geometry["failures"])
        report["native_pose_rendered"] = len(report["frames"]) == len(POSES)
        report["pose_activity_passed"] = not report["failures"]
        (output / "native_pose_report.json").write_text(
            json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
        return report
    finally:
        live2d.dispose()
        pygame.quit()

def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--model3", type=Path, required=True)
    p.add_argument("--output", type=Path, required=True)
    p.add_argument("--size", type=int, default=768)
    args = p.parse_args()
    if not 256 <= args.size <= 2048:
        raise ValueError("Frame size must be within 256..2048")
    report = run(args.model3, args.output, size=args.size)
    print("NATIVE_POSE_REPORT " + str(args.output / "native_pose_report.json"), flush=True)
    return 0 if report["pose_activity_passed"] else 2

if __name__ == "__main__":
    raise SystemExit(main())
