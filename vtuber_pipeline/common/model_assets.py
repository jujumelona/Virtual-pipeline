"""Known model identities and download provenance (hashes measured from actual files)."""
from __future__ import annotations
import hashlib
import json
from pathlib import Path

MODELS = {
    "skytnt_anime_seg_isnet_is": ("skytnt/anime-seg", "Apache-2.0"),
    "florence2_base": ("florence-community/Florence-2-base", "MIT"),
    "sam2_1_hiera_large": ("facebook/sam2.1-hiera-large", "Apache-2.0"),
    "anime_face_yolov3": ("hysts/anime-face-detector-yolov3", "MIT"),
    "anime_face_hrnetv2": ("hysts/anime-face-detector-hrnetv2", "MIT"),
    "flux2_klein_4b": ("black-forest-labs/FLUX.2-klein-4B", "Apache-2.0"),
    "triposr": ("stabilityai/TripoSR", "MIT"),
    "instantmesh_large": ("TencentARC/InstantMesh", "Apache-2.0"),
    "depth_anything_v2_small": ("depth-anything/Depth-Anything-V2-Small-hf", "Apache-2.0"),
}
MODE_ASSETS = {
    # Direct supplied-layer production needs only the real face detector for
    # aligned landmark/keyform extraction; never downloads 4B FLUX / SAM.
    "common_2d_layers": ("anime_face_yolov3", "anime_face_hrnetv2"),
    "common_2d": ("skytnt_anime_seg_isnet_is", "florence2_base", "sam2_1_hiera_large",
                  "anime_face_yolov3", "anime_face_hrnetv2", "flux2_klein_4b"),
    # Do not prefetch restricted InstantMesh checkpoints. The production
    # geometry provider is the MIT-licensed TripoSR for each observed view.
    "3d": ("skytnt_anime_seg_isnet_is", "anime_face_yolov3", "anime_face_hrnetv2",
           "triposr", "depth_anything_v2_small"),
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


def model_pin(model_key: str) -> dict:
    """Read the same immutable pin for downloads and inference."""
    import re
    key = 'anime_segmentation' if model_key == 'skytnt_anime_seg_isnet_is' else model_key
    lock = json.loads((Path(__file__).resolve().parents[2] / 'third_party.lock.json').read_text())
    item = lock['tools'][key]
    revision = item.get('model_revision')
    if not isinstance(revision, str) or not re.fullmatch('[0-9a-f]{40}', revision):
        raise RuntimeError(f'{model_key}: no immutable model revision')
    return {'model_id': item['model_id'], 'revision': revision,
            'allow_patterns': item['download_allow_patterns']}


def resolve_snapshot(model_key: str, cache_dir: str | None = None) -> str:
    """Resolve only the selected model files and record actual byte hashes."""
    import os
    from huggingface_hub import snapshot_download
    pin = model_pin(model_key)
    folder = Path(snapshot_download(repo_id=pin['model_id'], revision=pin['revision'],
                                   allow_patterns=pin['allow_patterns'], cache_dir=cache_dir))
    # Keep generated provenance OUTSIDE the immutable upstream snapshot.
    manifest_root = Path(os.environ.get('VTUBER_MODEL_PROVENANCE',
                                        str(Path.home()/'.cache/vtuber-pipeline/provenance')))
    files = [str(p) for p in folder.rglob('*') if p.is_file()]
    record_artifacts(model_key, files, str(manifest_root/(model_key+'.json')), revision=pin['revision'])
    return str(folder)
