"""Local VLM artistic anomaly triage over *real* native MOC3 pose frames.

A language/vision model diagnoses likely *visible* defects, while native
geometry tools determine safe edits. Never trust model-generated code, Warp
IDs, file paths, success claims, or new art pixels. Real VTS review is still
required for broadcasting quality.
"""
from __future__ import annotations

import argparse
import base64
import json
from pathlib import Path
import urllib.request

from tools.vts_ai_landmark_pairs import _local_endpoint, _normalized_image
from tools.vts_native_visual_benchmark import PAIRS, _native_evidence
from tools.vts_native_repair_plan import quality_repair_plan

KNOWN = {
    "face_identity_drift", "facial_asymmetry", "eye_deformation",
    "mouth_shape", "neck_seam", "hair_gap", "outfit_gap",
    "mesh_collapse", "occlusion_order", "texture_detail_loss",
}
ROUTES = {
    "face_identity_drift": "source_art_regenerate",
    "facial_asymmetry": "vts_reference_keyform_author",
    "eye_deformation": "eye_art_and_keyforms",
    "mouth_shape": "mouth_art_and_keyforms",
    "neck_seam": "source_underpaint_and_mesh",
    "hair_gap": "source_underpaint_and_mesh",
    "outfit_gap": "source_underpaint_and_mesh",
    "mesh_collapse": "vts_modern_mesh_refiner",
    "occlusion_order": "native_draw_order_and_mask_review",
    "texture_detail_loss": "source_art_and_atlas_review",
}

PROMPT = """Compare TWO actual images of the SAME character, at the SAME angle:
image 1 original desired hand-authored three-quarter reference;
image 2 native PSD2Live MOC3 render, not an AI-proposed or simulated result.
Return JSON only: {"issues":[{"category":"...","severity":"low|medium|high",
"explanation":"short visual evidence", "region_xyxy":[0,0,1,1]}],
"reference_and_render_same_identity":true|false}.
Categories allowed: face_identity_drift, facial_asymmetry, eye_deformation,
mouth_shape, neck_seam, hair_gap, outfit_gap, mesh_collapse,
occlusion_order, texture_detail_loss.
region_xyxy is normalized to the displayed image, four finite
coordinates within 0..1, left<right and top<bottom. Do not invent
details or report unseen objects. Empty issues is not proof of premium
quality. Do not emit files, code, commands or tool calls."""


def _part(payload: bytes) -> dict:
    return {"type": "image_url", "image_url": {
        "url": "data:image/png;base64," + base64.b64encode(payload).decode("ascii")}}


def observe_visual_defects(reference: Path, native: Path, *, model: str,
                           endpoint: str, transport=None) -> dict:
    url = _local_endpoint(endpoint)
    if not isinstance(model, str) or not model or len(model) > 256:
        raise ValueError("Real localhost image-capable model is required")
    ref, _ = _normalized_image(reference, (768, 768))
    rendered, _ = _normalized_image(native, (768, 768))
    req = urllib.request.Request(url, method="POST",
        headers={"Content-Type": "application/json"},
        data=json.dumps({
            "model": model, "temperature": 0,
            "messages": [{"role": "user", "content": [
                {"type": "text", "text": PROMPT}, _part(ref), _part(rendered)]}],
        }).encode("utf-8"))
    open_req = transport or urllib.request.urlopen
    with open_req(req, timeout=120) as response:
        reply = json.loads(response.read(8_000_000).decode("utf-8"))
    content = reply["choices"][0]["message"]["content"]
    if not isinstance(content, str):
        raise ValueError("VLM visual review is not JSON text")
    body = json.loads(content)
    if not isinstance(body, dict) or not isinstance(body.get("issues"), list):
        raise ValueError("VLM review must provide issue list")
    if not isinstance(body.get("reference_and_render_same_identity"), bool):
        raise ValueError("VLM review must explicitly assess identity")
    if len(body["issues"]) > 16:
        raise ValueError("Excessive VLM visual issue proposals")
    safe = []
    for issue in body["issues"]:
        if not isinstance(issue, dict) or issue.get("category") not in KNOWN:
            raise ValueError("Unknown VLM issue category")
        if issue.get("severity") not in {"low", "medium", "high"}:
            raise ValueError("Invalid VLM severity")
        why = issue.get("explanation")
        rect = issue.get("region_xyxy")
        if not isinstance(why, str) or not 5 <= len(why) <= 350:
            raise ValueError("VLM visual explanation missing")
        if not isinstance(rect, list) or len(rect) != 4 or not all(
            type(x) in (int, float) and 0 <= x <= 1 for x in rect):
            raise ValueError("VLM visual bounding box invalid")
        if not (rect[0] < rect[2] and rect[1] < rect[3]):
            raise ValueError("VLM visual region degenerate")
        safe.append({
            "category": issue["category"],
            "severity": issue["severity"],
            "explanation": why, "region_xyxy": rect,
            "proposed_tool": ROUTES[issue["category"]],
            "tool_executed": False,
            "corrected_visual_quality_verified": False,
        })
    return {"same_identity_assessed": body["reference_and_render_same_identity"],
            "issues": safe}


def review_real_native_poses(reference_dir: Path, native_dir: Path,
                             output: Path, *, model: str, endpoint: str,
                             observer=None) -> dict:
    native_dir = Path(native_dir)
    _native_evidence(native_dir)
    reference_dir = Path(reference_dir)
    worker = observer or observe_visual_defects
    output = Path(output)
    output.mkdir(parents=True, exist_ok=True)
    results = {}
    for view, frame in PAIRS.items():
        ref = reference_dir / (view + ".png")
        actual = native_dir / (frame + ".png")
        if not ref.is_file() or not actual.is_file():
            raise FileNotFoundError("Real 3/4 source and native screenshots required")
        results[view] = worker(ref, actual, model=model, endpoint=endpoint)
    issues = [dict(issue, view=view) for view, review in results.items()
              for issue in review["issues"]]
    verdict = {
        "schema": "vtuber/localhost-vision-native-art-critique-v1",
        "origin": "local-image-vlm-real-MOC3-references",
        "source_native_report": str(native_dir / "native_pose_report.json"),
        "views": results, "issues": issues,
        "proposed_actions": sorted(set(i["proposed_tool"] for i in issues)),
        "all_proposed_fixes_executed": False,
        "aesthetic_premium_quality_verified": False,
        "vtube_studio_tracking_verified": False,
    }
    (output / "visual_critique.json").write_text(
        json.dumps(verdict, ensure_ascii=False, indent=2), encoding="utf-8")
    return verdict


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--reference-dir", type=Path, required=True)
    p.add_argument("--native-dir", type=Path, required=True)
    p.add_argument("--output", type=Path, required=True)
    p.add_argument("--model", required=True)
    p.add_argument("--endpoint", default="http://127.0.0.1:8000/v1/chat/completions")
    args = p.parse_args()
    print(json.dumps(review_real_native_poses(
        args.reference_dir, args.native_dir, args.output,
        model=args.model, endpoint=args.endpoint), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
