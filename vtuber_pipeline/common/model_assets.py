"""Known model identities and download provenance (hashes measured from actual files)."""
from __future__ import annotations
import hashlib
import json
from pathlib import Path

MODELS = {
    "skytnt_anime_seg_isnet_is": ("skytnt/anime-seg", "Apache-2.0"),
    "florence2_base": ("microsoft/Florence-2-base", "MIT"),
    "sam2_1_hiera_tiny": ("facebook/sam2.1-hiera-tiny", "Apache-2.0"),
    "anime_face_yolov3": ("hysts/anime-face-detector-yolov3", "MIT"),
    "anime_face_hrnetv2": ("hysts/anime-face-detector-hrnetv2", "MIT"),
    "flux2_klein_4b": ("black-forest-labs/FLUX.2-klein-4B", "Apache-2.0"),
    "triposr": ("stabilityai/TripoSR", "MIT"),
    "instantmesh_large": ("TencentARC/InstantMesh", "Apache-2.0"),
    "depth_anything_v2_small": ("depth-anything/Depth-Anything-V2-Small-hf", "Apache-2.0"),
}
MODE_ASSETS = {
    "common_2d": ("skytnt_anime_seg_isnet_is", "florence2_base", "sam2_1_hiera_tiny",
                  "anime_face_yolov3", "anime_face_hrnetv2", "flux2_klein_4b"),
    "3d": ("skytnt_anime_seg_isnet_is", "anime_face_yolov3", "anime_face_hrnetv2",
           "triposr", "instantmesh_large", "depth_anything_v2_small"),
}
def sha256_file(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for part in iter(lambda: f.read(1 << 20), b""):
            h.update(part)
    return h.hexdigest()

def record_artifacts(model_key: str, files: list[str], output_json: str, *, revision: str | None = None):
    if model_key not in MODELS:
        raise KeyError(model_key)
    model_id, license_id = MODELS[model_key]
    records = []
    for file in files:
        path = Path(file).resolve()
        if not path.is_file():
            raise FileNotFoundError(path)
        records.append({"path": str(path), "size": path.stat().st_size, "sha256": sha256_file(str(path))})
    if not records:
        raise ValueError("model download contains no verifiable files")
    payload = {"model_key": model_key, "model_id": model_id, "license": license_id,
               "resolved_revision": revision, "files": records}
    out = Path(output_json)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return payload
