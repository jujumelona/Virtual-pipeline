"""Optional SkinTokens skin-only adapter, retaining the canonical VRM rig.

Runs upstream's real demo.py --use_skeleton --use_transfer in a separate
environment; ONLY transplants validated JOINTS_0/WEIGHTS_0 arrays into the
original GLB. Upstream geometry, textures, node layout and expression metadata
are never promoted to the broadcast asset.
"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys

import numpy as np
from pygltflib import GLTF2

SOURCE_SHA = "273b691d35989d71cd17ff2895fdc735097b92d1"
CHECKPOINT = "experiments/articulation_xl_quantization_256_token_4/grpo_1400.ckpt"
SKIN_VAE = "experiments/skin_vae_2_10_32768/last.ckpt"
# From the upstream README, not a measurement of free memory during a run.
MIN_TOTAL_VRAM_BYTES = 14 * (1024 ** 3)

_DTYPES = {5121: np.dtype("u1"), 5123: np.dtype("<u2"),
           5125: np.dtype("<u4"), 5126: np.dtype("<f4")}
_COMPONENTS = {"SCALAR": 1, "VEC2": 2, "VEC3": 3, "VEC4": 4, "MAT4": 16}


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(4 * 1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def _read(gltf: GLTF2, attr: int) -> np.ndarray:
    accessor = gltf.accessors[attr]
    if accessor.sparse is not None:
        raise ValueError("SkinTokens bridge does not support sparse accessors")
    if accessor.bufferView is None or accessor.componentType not in _DTYPES:
        raise ValueError("Unsupported glTF accessor encoding")
    view = gltf.bufferViews[accessor.bufferView]
    if view.buffer != 0:
        raise ValueError("Only single-buffer GLB is supported")
    dt = _DTYPES[accessor.componentType]
    cols = _COMPONENTS.get(accessor.type)
    if cols is None:
        raise ValueError("Unsupported glTF accessor shape")
    stride = view.byteStride or (dt.itemsize * cols)
    if stride < dt.itemsize * cols:
        raise ValueError("Invalid accessor stride")
    start = (view.byteOffset or 0) + (accessor.byteOffset or 0)
    blob = gltf.binary_blob()
    end = start + (accessor.count - 1) * stride + dt.itemsize * cols
    if accessor.count < 1 or end > len(blob):
        raise ValueError("Accessor points outside GLB")
    array = np.ndarray(
        (accessor.count, cols), dtype=dt, buffer=blob,
        offset=start, strides=(stride, dt.itemsize),
    ).copy()
    if accessor.normalized and accessor.componentType != 5126:
        maximum = float(np.iinfo(dt).max)
        array = array.astype(np.float64) / maximum
    return array


def _primitive(gltf: GLTF2):
    if not gltf.meshes or len(gltf.meshes) != 1:
        raise ValueError("Expected one avatar mesh")
    if len(gltf.meshes[0].primitives) != 1:
        raise ValueError("Expected one avatar primitive")
    primitive = gltf.meshes[0].primitives[0]
    if not gltf.skins or len(gltf.skins) != 1:
        raise ValueError("Expected one complete skeleton")
    return primitive, gltf.skins[0]


def graft_weights(baseline_file: str, candidate_file: str, output_file: str) -> dict:
    """Validate then graft upstream skin weights; preserve baseline glTF bytes."""
    base = GLTF2().load_binary(str(baseline_file))
    pred = GLTF2().load_binary(str(candidate_file))
    src, source_skin = _primitive(base)
    dst, predicted_skin = _primitive(pred)

    base_xyz = _read(base, src.attributes.POSITION)
    pred_xyz = _read(pred, dst.attributes.POSITION)
    if (base_xyz.shape != pred_xyz.shape
            or not np.isfinite(pred_xyz).all()
            or not np.allclose(base_xyz, pred_xyz, rtol=0, atol=1e-5)):
        raise ValueError("SkinTokens changed vertex topology/order/positions")

    if src.attributes.TEXCOORD_0 is not None:
        if dst.attributes.TEXCOORD_0 is None:
            raise ValueError("SkinTokens discarded UV mapping")
        uv = _read(base, src.attributes.TEXCOORD_0)
        pred_uv = _read(pred, dst.attributes.TEXCOORD_0)
        if uv.shape != pred_uv.shape or not np.allclose(uv, pred_uv, atol=1e-5, rtol=0):
            raise ValueError("SkinTokens reordered or changed texture coordinates")

    base_names = [base.nodes[index].name for index in source_skin.joints]
    other_names = [pred.nodes[index].name for index in predicted_skin.joints]
    if (any(not n for n in base_names + other_names)
            or len(set(base_names)) != len(base_names)
            or len(set(other_names)) != len(other_names)):
        raise ValueError("Ambiguous or unnamed skeleton joints")
    if not set(other_names).issubset(set(base_names)):
        raise ValueError("SkinTokens produced joints outside canonical VRM skeleton")
    # The source remains the canonical joint hierarchy and rest transforms.
    lookup = {name: i for i, name in enumerate(base_names)}
    # Skin weights are only portable between identical rest-pose bind
    # transforms. The upstream GLB may rename or rescale bones on export;
    # matching names alone cannot establish compatible animation.
    if (source_skin.inverseBindMatrices is None
            or predicted_skin.inverseBindMatrices is None):
        raise ValueError("SkinTokens skin lacks inverse-bind rest matrices")
    baseline_rest = _read(base, source_skin.inverseBindMatrices)
    candidate_rest = _read(pred, predicted_skin.inverseBindMatrices)
    if (baseline_rest.shape != (len(base_names), 16)
            or candidate_rest.shape != (len(other_names), 16)
            or not np.isfinite(candidate_rest).all()):
        raise ValueError("SkinTokens inverse-bind matrices invalid")
    for candidate_index, name in enumerate(other_names):
        if not np.allclose(candidate_rest[candidate_index],
                           baseline_rest[lookup[name]], rtol=1e-5, atol=1e-5):
            raise ValueError("SkinTokens changed rest-pose bind matrix for " + name)

    weights = _read(pred, dst.attributes.WEIGHTS_0).astype(np.float64)
    joints = _read(pred, dst.attributes.JOINTS_0)
    if (weights.shape != (len(base_xyz), 4)
            or joints.shape != weights.shape
            or not np.issubdtype(joints.dtype, np.integer)):
        raise ValueError("SkinTokens produced invalid 4-influence skin")
    if (not np.isfinite(weights).all() or (weights < 0).any()
            or (weights > 1.0001).any()):
        raise ValueError("SkinTokens skin contains invalid weights")
    row_sums = weights.sum(axis=1)
    if np.any(row_sums < 0.99) or np.any(row_sums > 1.01):
        raise ValueError("SkinTokens weights are not normalized")
    if np.any(joints >= len(other_names)):
        raise ValueError("SkinTokens joints refer outside their skin palette")
    remap = np.array([lookup[n] for n in other_names], dtype=np.uint16)
    index_data = remap[joints.astype(np.int64)]
    # Preserve already-normalized source rows byte-for-byte. In particular
    # Blender body-only grafts must not perturb protected facial/hair weights
    # merely because float32 summation differs from one by one ULP.
    weight_data = weights.astype("<f4")
    needs_normalizing = np.abs(row_sums - 1.0) > 1e-6
    weight_data[needs_normalizing] = (
        weights[needs_normalizing] / row_sums[needs_normalizing, None]
    ).astype("<f4")

    # Independently authored hair strands must remain bound to head/hair bones,
    # or the downstream SpringBone chain would animate detached hair.
    extras = base.meshes[0].extras or {}
    if "hairVertexStart" in extras:
        start = int(extras["hairVertexStart"])
        if not 0 < start < len(base_xyz):
            raise ValueError("Invalid source hair partition")
        permitted = np.array(
            [n == "head" or n.startswith("hair") for n in base_names],
            dtype=bool,
        )
        hair_total = (weight_data[start:] *
                      permitted[index_data[start:]]).sum(axis=1)
        if np.any(hair_total < 0.90):
            raise ValueError("SkinTokens removed head/hair skin for hair strands")

    if (src.attributes.JOINTS_0 is None or src.attributes.WEIGHTS_0 is None
            or base.accessors[src.attributes.JOINTS_0].componentType != 5123
            or base.accessors[src.attributes.WEIGHTS_0].componentType != 5126):
        raise ValueError("Canonical GLB skin encoding changed")
    binary = bytearray(base.binary_blob())
    for attr_idx, payload in (
        (src.attributes.JOINTS_0, index_data.astype("<u2").tobytes()),
        (src.attributes.WEIGHTS_0, weight_data.tobytes()),
    ):
        accessor = base.accessors[attr_idx]
        view = base.bufferViews[accessor.bufferView]
        if view.byteStride is not None:
            raise ValueError("Cannot graft into interleaved skin accessors")
        start = (view.byteOffset or 0) + (accessor.byteOffset or 0)
        expected = accessor.count * 4 * _DTYPES[accessor.componentType].itemsize
        if len(payload) != expected or start + expected > len(binary):
            raise ValueError("Canonical skin buffer bounds do not match")
        binary[start:start + expected] = payload

    target = Path(output_file)
    target.parent.mkdir(parents=True, exist_ok=True)
    base.set_binary_blob(bytes(binary))
    base.save_binary(str(target))
    verified = GLTF2().load_binary(str(target))
    if not np.allclose(_read(verified, verified.meshes[0].primitives[0].attributes.WEIGHTS_0),
                       weight_data, atol=1e-6):
        target.unlink(missing_ok=True)
        raise RuntimeError("Saved SkinTokens weights did not round-trip")
    return {"status": "complete", "rigged_mesh": str(target),
            "output_path": str(target), "vertices": len(base_xyz),
            "model": "VAST-AI-Research/SkinTokens", "skin_only": True}


def check_gpu_compatibility(identity: dict) -> dict:
    """Reject T4/CPU explicitly: upstream TokenRig hardcodes BF16 + FA2."""
    probe = (
        "import json, torch; "
        "assert torch.cuda.is_available(), 'SkinTokens requires an NVIDIA GPU'; "
        "p=torch.cuda.get_device_properties(0); "
        "free,total=torch.cuda.mem_get_info(0); "
        "print(json.dumps({'device':p.name,'major':p.major,'minor':p.minor,"
        "'total_bytes':total,'free_bytes':free,"
        "'bf16':bool(torch.cuda.is_bf16_supported())}))"
    )
    result = subprocess.run(
        [identity["python"], "-c", probe],
        cwd=identity["repo"], capture_output=True, text=True, timeout=90,
    )
    if result.returncode:
        raise RuntimeError("SkinTokens CUDA probe failed: " + result.stderr[-1000:])
    properties = json.loads(result.stdout.strip().splitlines()[-1])
    if (properties["major"] < 8 or not properties["bf16"]):
        raise RuntimeError(
            "SkinTokens upstream requires BF16 and FlashAttention-2 (Ampere+). "
            f"Unsupported GPU: {properties['device']} sm{properties['major']}{properties['minor']}; "
            "Colab T4 uses sm75. Select canonical rigging on T4."
        )
    if properties["total_bytes"] < MIN_TOTAL_VRAM_BYTES:
        raise RuntimeError("SkinTokens GPU has less than 14 GiB total VRAM")
    if properties["free_bytes"] < MIN_TOTAL_VRAM_BYTES:
        raise RuntimeError("SkinTokens needs at least 14 GiB free GPU memory")
    return properties


def runtime_identity() -> dict:
    """Fail closed until the exact upstream source and checkpoint are present."""
    repo = Path(os.environ.get("VTUBER_SKINTOKENS_DIR", "")).expanduser()
    if not str(os.environ.get("VTUBER_SKINTOKENS_DIR", "")).strip():
        raise RuntimeError("VTUBER_SKINTOKENS_DIR is required for SkinTokens")
    if not (repo / "demo.py").is_file():
        raise RuntimeError("SkinTokens demo.py is missing")
    revision = subprocess.run(
        ["git", "-C", str(repo), "rev-parse", "HEAD"],
        capture_output=True, text=True, timeout=20, check=True,
    ).stdout.strip()
    if revision != SOURCE_SHA:
        raise RuntimeError(f"SkinTokens source revision mismatch: {revision}")
    for name in (CHECKPOINT, SKIN_VAE):
        if not (repo / name).is_file():
            raise RuntimeError("SkinTokens model is not installed: " + name)
    python = os.environ.get("VTUBER_SKINTOKENS_PYTHON") or str(repo / ".venv/bin/python")
    if not Path(python).is_file():
        raise RuntimeError("SkinTokens isolated Python missing: " + python)
    # Checkpoint checksum is included in the stage cache identity. Changing
    # weights can never silently reuse an inference result.
    return {"repo": str(repo.resolve()), "python": str(Path(python).resolve()),
            "revision": revision, "model_sha256": _sha256(repo / CHECKPOINT),
            "skin_vae_sha256": _sha256(repo / SKIN_VAE)}


def run_skintokens_skin_only(baseline_file: str, output_dir: str,
                            *, timeout: int = 2400, identity: dict | None = None) -> dict:
    """Launch real TokenRig in isolated env; validate and graft its skin only."""
    if not Path(baseline_file).is_file():
        raise FileNotFoundError(baseline_file)
    identity = runtime_identity() if identity is None else identity
    gpu = check_gpu_compatibility(identity)
    root = Path(output_dir)
    root.mkdir(parents=True, exist_ok=True)
    candidate = root / "skintokens_candidate.glb"
    final = root / "skintokens_skin.glb"
    log_path = root / "skintokens.log"
    candidate.unlink(missing_ok=True)
    final.unlink(missing_ok=True)
    command = [identity["python"], "-u", str(Path(identity["repo"]) / "demo.py"),
               "--input", str(Path(baseline_file).resolve()),
               "--output", str(candidate.resolve()), "--use_skeleton", "--use_transfer"]
    # Do not run the experimental model in the parent Colab process. Its
    # upstream CLI also launches and cleans up the bpy_server subprocess.
    with log_path.open("w", encoding="utf-8") as log:
        try:
            status = subprocess.run(
                command, cwd=identity["repo"], stdout=log,
                stderr=subprocess.STDOUT, timeout=timeout, check=False,
            )
        except subprocess.TimeoutExpired as exc:
            raise RuntimeError(f"SkinTokens inference timeout; log={log_path}") from exc
    if status.returncode != 0 or not candidate.is_file() or candidate.stat().st_size == 0:
        raise RuntimeError(f"SkinTokens inference failed; log={log_path}")
    result = graft_weights(baseline_file, str(candidate), str(final))
    result["gpu"] = gpu
    result["source_revision"] = identity["revision"]
    result["checkpoint_sha256"] = identity["model_sha256"]
    result["log_path"] = str(log_path)
    report = root / "skintokens_report.json"
    report.write_text(json.dumps(result, indent=2), encoding="utf-8")
    result["report_json"] = str(report)
    return result
