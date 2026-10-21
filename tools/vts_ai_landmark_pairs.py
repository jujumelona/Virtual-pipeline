"""Obtain reference/native facial correspondences from a local vision model.

This adapter uses an OpenAI-compatible *local* image endpoint for observation;
it does not trust model-proposed tool calls, warp IDs or unbounded geometry.
The derived points must still pass vts_reference_keyform_author validation.
"""
from __future__ import annotations

import argparse
import base64
from io import BytesIO
import json
from pathlib import Path
import urllib.parse
import urllib.request
from PIL import Image, ImageOps

from tools.vts_reference_keyform_author import (
    REQUIRED_SHAPE, compile_native_reference_edits,
)

VIEW_NATIVE = {
    "head_three_quarter_L": "yaw_left.png",
    "head_three_quarter_R": "yaw_right.png",
}

PROMPT = """Return JSON only, without code fences. Analyze TWO images:
image 1 is the CURRENT native Live2D pose; image 2 is the DESIRED
same-character 3/4 reference drawing.
Report the same physical landmark in each image. Pixel coordinates are
measured from top-left on the displayed square canvas, x right, y down.
The four required names are:
face_contour: outermost near-side cheek contour at eye height;
nose_tip: center of nose's furthest projected contour;
jaw: lowest point of jaw/visible chin;
eye_left: center of the character's LEFT eye (not viewer left).
If one feature is occluded or cannot be located reliably, return
confidence <= 0.5 rather than guessing. No mirror-only approximations.
Response schema:
{"confidence":0.0, "observed":{"face_contour":[x,y],"nose_tip":[x,y],
"jaw":[x,y],"eye_left":[x,y]},
"desired":{"face_contour":[x,y],"nose_tip":[x,y],
"jaw":[x,y],"eye_left":[x,y]}}
No suggestions, commentary, HTML, YAML, or tools.
"""


def _local_endpoint(url: str) -> str:
    parts = urllib.parse.urlsplit(url)
    if (parts.scheme != "http" or parts.hostname not in
            ("localhost", "127.0.0.1", "::1") or
            parts.path != "/v1/chat/completions"):
        raise ValueError("Image data may only be sent to a local compatible VLM endpoint")
    if parts.username or parts.password or parts.query or parts.fragment:
        raise ValueError("Unexpected endpoint components")
    return url


def _normalized_image(path: Path, size: tuple[int, int]) -> tuple[bytes, dict]:
    """Letterbox, not independent x/y stretching; keep provenance for review."""
    path = Path(path).resolve(strict=True)
    with Image.open(path) as source:
        source.load()
        original = list(source.size)
        rgb = ImageOps.contain(source.convert("RGB"), size, Image.Resampling.LANCZOS)
    composed = Image.new("RGB", size, (255, 255, 255))
    x = (size[0] - rgb.width) // 2
    y = (size[1] - rgb.height) // 2
    composed.paste(rgb, (x, y))
    stream = BytesIO()
    composed.save(stream, format="PNG")
    return stream.getvalue(), {"source": str(path), "source_size": original,
                               "normalized_canvas": list(size),
                               "paste_xy": [x, y], "resized": original != list(size)}


def _vision_request(native: bytes, desired: bytes, *, model: str,
                    url: str, timeout: int = 120, transport=None) -> dict:
    if not model or len(model) > 256:
        raise ValueError("A concrete local image-capable model is required")
    endpoint = _local_endpoint(url)
    def image_part(content):
        return {"type": "image_url", "image_url": {"url":
            "data:image/png;base64," + base64.b64encode(content).decode("ascii")}}
    body = json.dumps({
        "model": model, "temperature": 0,
        "messages": [{"role": "user", "content": [
            {"type": "text", "text": PROMPT},
            image_part(native), image_part(desired),
        ]}],
    }).encode("utf-8")
    request = urllib.request.Request(endpoint, body, method="POST",
                                     headers={"Content-Type": "application/json"})
    opener = transport or urllib.request.urlopen
    with opener(request, timeout=timeout) as response:
        result = json.loads(response.read(8_000_000).decode("utf-8"))
    content = result["choices"][0]["message"]["content"]
    if not isinstance(content, str):
        raise ValueError("Vision model did not return JSON text")
    parsed = json.loads(content)
    if not isinstance(parsed, dict):
        raise ValueError("Vision response must be a JSON object")
    confidence = parsed.get("confidence")
    if (isinstance(confidence, bool) or not isinstance(confidence, (int, float))
            or not 0.8 <= confidence <= 1.0):
        raise ValueError("Low-confidence or invalid vision correspondences")
    if not (isinstance(parsed.get("observed"), dict)
            and isinstance(parsed.get("desired"), dict)):
        raise ValueError("Vision response missing landmark dictionaries")
    if not REQUIRED_SHAPE <= set(parsed["observed"]) or not REQUIRED_SHAPE <= set(parsed["desired"]):
        raise ValueError("Vision response missing silhouette, nose, jaw, eye")
    return parsed


def create_vision_reference_manifest(reference_dir: Path, native_dir: Path,
                                     output: Path, *, bindings: dict,
                                     model: str, endpoint: str,
                                     max_side: int = 768,
                                     transport=None) -> tuple[dict, Path]:
    """Pair real pose images and reference poses, ask local VLM for landmarks."""
    if not 256 <= max_side <= 1024:
        raise ValueError("Invalid reference canvas")
    output = Path(output).resolve()
    if output.exists() and any(output.iterdir()):
        raise ValueError("AI observation output must be a fresh directory")
    output.mkdir(parents=True, exist_ok=True)
    view_root = output / "reference_views"
    pose_root = output / "native_poses"
    view_root.mkdir()
    pose_root.mkdir()
    poses = []
    audit = []
    for view, native_name in VIEW_NATIVE.items():
        ref = Path(reference_dir) / (view + ".png")
        actual = Path(native_dir) / native_name
        if not ref.is_file() or not actual.is_file():
            continue
        ref_data, ref_metadata = _normalized_image(ref, (max_side, max_side))
        pose_data, pose_metadata = _normalized_image(actual, (max_side, max_side))
        (view_root / (view + ".png")).write_bytes(ref_data)
        (pose_root / (view + ".png")).write_bytes(pose_data)
        observed = _vision_request(pose_data, ref_data, model=model,
                                   url=endpoint, transport=transport)
        angle = -30 if view.endswith("_L") else 30
        poses.append({"view": view, "angle_x": angle,
                      "observed": observed["observed"],
                      "desired": observed["desired"]})
        audit.append({"view": view, "model": model, "confidence": observed["confidence"],
                      "reference_registration": ref_metadata,
                      "native_registration": pose_metadata})
    if not poses:
        raise ValueError("No valid reference/native yaw image pairs were found")
    manifest = {"canvas": [max_side, max_side],
                "warp_bindings": bindings, "poses": poses}
    compiled = compile_native_reference_edits(manifest, output)
    (output / "vision_reference_manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    (output / "vision_reference_audit.json").write_text(
        json.dumps({"observations": audit, "rendered_model_geometry_verified": False,
                    "native_keyforms_applied": False}, ensure_ascii=False, indent=2),
        encoding="utf-8")
    (output / "native_reference_plan.json").write_text(
        json.dumps(compiled, ensure_ascii=False, indent=2), encoding="utf-8")
    return compiled, output


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--reference-dir", type=Path, required=True)
    parser.add_argument("--native-dir", type=Path, required=True)
    parser.add_argument("--bindings", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--model", required=True)
    parser.add_argument("--endpoint", default="http://127.0.0.1:8000/v1/chat/completions")
    args = parser.parse_args()
    bindings = json.loads(args.bindings.read_text(encoding="utf-8"))
    plan, root = create_vision_reference_manifest(
        args.reference_dir, args.native_dir, args.output, bindings=bindings,
        model=args.model, endpoint=args.endpoint)
    print(json.dumps({"planned_warps": len(plan["changes"]),
                      "manifest": str(root / "vision_reference_manifest.json"),
                      "executed": False}, ensure_ascii=False))


if __name__ == "__main__":
    main()
