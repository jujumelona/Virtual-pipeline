"""Analytic per-vertex local 2.5D deformation data; no global rotate-only cheats."""
from pathlib import Path
import json
import math
import numpy as np
PARAMS={
 "head.angle_x":(-30,0,30), "head.angle_y":(-20,0,20),
 "head.angle_z":(-30,0,30), "eye.left.open":(0,1,1),
 "eye.right.open":(0,1,1), "eye.x":(-1,0,1), "eye.y":(-1,0,1),
 "brow.left.y":(-1,0,1), "brow.right.y":(-1,0,1),
 "mouth.open":(0,0,1), "mouth.form":(-1,0,1),
 "body.angle_x":(-15,0,15),"body.angle_y":(-15,0,15),
 "body.angle_z":(-15,0,15),"breath":(0,0,1),
}
def _neck_joint_weight(y_coordinates: np.ndarray) -> np.ndarray:
    """Fix lower neck to torso while upper neck follows the head.

    Coordinates are global image-space (increasing Y downward). This is a
    seam-safety deformation, not measured 90-degree profile geometry.
    """
    y = np.asarray(y_coordinates, dtype=float)
    if y.size == 0:
        return np.asarray([], dtype=float)
    span = max(float(np.ptp(y)), 1.0)
    progress = np.clip((y - float(y.min())) / span, 0.0, 1.0)
    smooth = progress * progress * (3.0 - 2.0 * progress)
    return 1.0 - smooth


def _role(part: str) -> str:
    return part.casefold().replace("_", ".").split(".")[0]


def _gaze_drawable(part: str) -> bool:
    tokens = part.casefold().replace("_", ".").split(".")
    return "eye" in tokens and bool(
        {"iris", "irides", "pupil", "highlight", "glint"} & set(tokens)
    )


def _shared_frame(meshes: list, roles: set[str]):
    selected = [np.asarray(m["vertices_xy"], dtype=float)
                for m in meshes if _role(m["semantic_id"]) in roles]
    if not selected:
        return None
    combined = np.concatenate(selected, axis=0)
    return combined.mean(axis=0), np.maximum(combined.max(axis=0) -
                                             combined.min(axis=0), 1.0)


def build_keyforms(meshes_json: str, parts_json: str,
                   face_landmarks_json: str, output_dir: str) -> dict:
    src=json.loads(Path(meshes_json).read_text(encoding="utf-8"))
    # Source landmarks are measured on the same original full-canvas image
    # as the triangulated part. A separate face crop is never projected here.
    part_landmarks = {}
    if Path(parts_json).is_file():
        part_doc = json.loads(Path(parts_json).read_text(encoding="utf-8"))
        part_landmarks = {
            part["semantic_id"]: part.get("landmarks_xy", [])
            for part in part_doc.get("parts", [])
        }
    # All head children share a common movement frame. The same is true
    # for torso and clothing, preventing per-layer translation/stretch drift.
    head_roles = {"head", "face", "eye", "hair", "brow", "eyebrow",
                  "ear", "nose", "mouth", "jaw", "scalp", "neck"}
    body_roles = {"body", "torso", "arm", "shoulder", "forearm", "hand",
                  "cloth", "outfit", "sleeve", "garment", "leg"}
    head_frame = _shared_frame(src["meshes"], head_roles)
    body_frame = _shared_frame(src["meshes"], body_roles)
    entries=[]
    for m in src["meshes"]:
        verts=np.asarray(m["vertices_xy"],dtype=float)
        part=m["semantic_id"]
        center=verts.mean(axis=0)
        observed = np.asarray(part_landmarks.get(part, []), dtype=float)
        pivot_source = "mesh_centroid"
        if observed.size:
            if observed.ndim != 2 or observed.shape[1] != 2 or not np.isfinite(observed).all():
                raise ValueError(f"{part}: nonfinite or invalid aligned source landmarks")
            lower, upper = verts.min(axis=0), verts.max(axis=0)
            # The SAM part boundary need not contain every corner of an eyelid,
            # but an unrelated face crop would be far outside this region.
            margin = np.maximum(6.0, 0.35 * (upper - lower))
            pivot = observed.mean(axis=0)
            if np.all(pivot >= lower - margin) and np.all(pivot <= upper + margin):
                center = np.clip(pivot, lower, upper)
                pivot_source = "observed_hrnet"
        local_span=np.maximum(verts.max(axis=0)-verts.min(axis=0),1)
        deltas={}
        for p,(low,mid,hi) in PARAMS.items():
            role = _role(part)
            if p.startswith("head.") and role not in head_roles:
                continue
            if p.startswith("body.") and role not in body_roles:
                continue
            if p.startswith("eye.left") and "eye.left" not in part: continue
            if p.startswith("eye.right") and "eye.right" not in part: continue
            # Gaze moves only the iris/pupil/highlight, never an entire eye.
            if p in ("eye.x", "eye.y") and not _gaze_drawable(part):
                continue
            if p.startswith("mouth.") and "mouth" not in part: continue
            if p.startswith("brow.left") and "brow.left" not in part: continue
            if p.startswith("brow.right") and "brow.right" not in part: continue
            if p=="breath" and not any(x in part for x in ("body","cloth")): continue
            shared = (head_frame if p.startswith("head.") else
                      body_frame if p.startswith("body.") else None)
            if shared is not None:
                v = verts - shared[0]
                span = shared[1]
            else:
                v = verts - center
                span = local_span
            if p == "body.angle_x":
                # Common torso translation instead of independently stretching
                # each cloth mesh; articulation stays in part-specific physics.
                dx=np.full(len(v),0.13*span[0]);dy=np.zeros(len(v))
            elif p == "body.angle_y":
                dx=np.zeros(len(v));dy=np.full(len(v),0.11*span[1])
            elif p.endswith("angle_x"):
                # Nonuniform deformation varies with vertical extent and part position.
                dx=0.16*span[0]*(1-(v[:,1]/span[1])**2)+0.25*v[:,0]
                dy=-0.07*v[:,0]
            elif p.endswith("angle_y"):
                dx=0.10*v[:,0]*(v[:,1]/span[1])
                dy=-0.25*v[:,1]+0.09*span[1]*(v[:,0]/span[0])**2
            elif p.endswith("angle_z"):
                dx=-v[:,1]
                dy=v[:,0]
            elif p.endswith(".open"):
                dx=np.zeros(len(v))
                dy=v[:,1] if p.startswith("eye.") else v[:,1]*0.65
            elif p.endswith(".form"):
                dx=-v[:,0]*0.25
                dy=v[:,1]*0.10
            elif p=="eye.x": dx=np.full(len(v),0.12*span[0]);dy=np.zeros(len(v))
            elif p=="eye.y": dx=np.zeros(len(v));dy=np.full(len(v),0.12*span[1])
            elif p.endswith(".y"):dx=np.zeros(len(v));dy=np.full(len(v),0.20*span[1])
            elif p=="breath":dx=v[:,0]*0.018;dy=-np.full(len(v),0.012*span[1])
            else:continue
            # The neck is an actual bridge, not a rigid head ornament.
            # Let its top follow the jaw while its lower-most vertices stay
            # rooted at the torso, preventing a cut when the head yaws,
            # pitches or tilts. Final seams still need native pose renders.
            if role == "neck" and p.startswith("head.angle_"):
                influence = _neck_joint_weight(verts[:, 1])
                dx = np.asarray(dx) * influence
                dy = np.asarray(dy) * influence
            # Endpoints need independent offsets: eye.open has default == max.
            high_amount=math.radians(hi-mid) if "angle" in p else hi-mid
            low_amount=math.radians(low-mid) if "angle" in p else low-mid
            plus=np.column_stack((dx,dy))*high_amount
            minus=np.column_stack((dx,dy))*low_amount
            deltas[p]={"min":minus.tolist(),"default":np.zeros_like(plus).tolist(),"max":plus.tolist()}
        entries.append({"semantic_id":part,"deltas":deltas,
                        "pivot_xy":center.tolist(),"pivot_source":pivot_source})
    out=Path(output_dir)/"keyforms.json";out.parent.mkdir(parents=True,exist_ok=True)
    out.write_text(json.dumps({"parameters":{k:list(v) for k,v in PARAMS.items()},
                               "keyforms":entries,
                               "pose_authoring": "shared_anatomical_frame_analytic_preview",
                               "multiview_reference_keyforms_bound": False,
                               "native_cubism_keyforms_verified": False}, indent=2),
                   encoding="utf-8")
    return {"keyforms_json":str(out)}
