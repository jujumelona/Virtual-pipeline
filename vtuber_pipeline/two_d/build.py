"""2D production graph. SDK and official editor boundaries are non-negotiable."""
from __future__ import annotations
from pathlib import Path
import numpy as np
from PIL import Image
from vtuber_pipeline.common.schemas import BuildResult, SourceSet, PartsDocument, Part
from vtuber_pipeline.common.part_taxonomy import z_order

KNOWN = {
    "hair_back": "hair.back", "hair_front": "hair.front",
    "eye_left_white": "eye.left.white", "eye_left_iris": "eye.left.iris",
    "eye_left_lid": "eye.left.lid", "eye_right_white": "eye.right.white",
    "eye_right_iris": "eye.right.iris", "eye_right_lid": "eye.right.lid",
    "brow_left": "eyebrow.left", "brow_right": "eyebrow.right",
    "mouth_closed": "mouth.lip", "mouth_open": "mouth.inner",
    "body": "body", "face": "face", "neck": "neck",
}

def _layers(source: SourceSet, folder: Path) -> PartsDocument | None:
    if not source.user_layers_zip:
        return None
    from .preparation import _load_image, _read_layers
    base = _load_image(Path(source.front_image).read_bytes(), "source")
    supplied = _read_layers(source.user_layers_zip, base.size)
    folder.mkdir(parents=True, exist_ok=True)
    parts = []
    for i, (name, img) in enumerate(supplied):
        identity = KNOWN.get(name.lower(), name.lower().replace("_","."))
        depth = z_order(identity)
        alpha = np.asarray(img.getchannel("A"))
        ys,xs = np.nonzero(alpha > 0)
        if not len(xs):
            continue
        rgba = folder / ("supplied_%03d.png" % i)
        mask = folder / ("supplied_mask_%03d.png" % i)
        img.save(rgba)
        Image.fromarray(alpha, "L").save(mask)
        parts.append(Part(identity, str(rgba), str(mask), None,
                  [int(xs.min()),int(ys.min()),int(xs.max()+1),int(ys.max()+1)],
                  depth, [], "user"))
    if not parts:
        raise ValueError("supplied layers contain no visible pixels")
    return PartsDocument(base.width,base.height,parts,None,"")

def prepare_common_2d(source: SourceSet) -> dict:
    source.validate()
    root = Path(source.output_dir)
    root.mkdir(parents=True,exist_ok=True)
    work = root / "intermediate"
    work.mkdir(exist_ok=True)
    supplied = _layers(source,work/"supplied")
    from vtuber_pipeline.perception.face_landmarks import detect
    landmarks = detect(source.face_image or source.front_image,str(work/"face"))
    complete_layer_ids = {"hair.front", "hair.back", "face",
                          "eye.left.white", "eye.right.white", "mouth.inner"}
    have = {p.semantic_id for p in supplied.parts} if supplied else set()
    if supplied and complete_layer_ids.issubset(have):
        parts = supplied
    else:
        from vtuber_pipeline.perception.anime_alpha import create_person_alpha
        from vtuber_pipeline.perception.semantic_boxes import detect_semantic_parts
        from vtuber_pipeline.perception.sam_parts import segment_parts
        from vtuber_pipeline.perception.layer_split import split_semantic_layers
        from vtuber_pipeline.perception.occlusion_repair import fill_hidden_parts
        alpha=create_person_alpha(source.front_image,str(work/"alpha"))
        boxes=detect_semantic_parts(alpha["rgba_png"],landmarks["landmarks_json"],str(work/"boxes"))
        masks=segment_parts(alpha["rgba_png"],boxes["boxes_json"],
                            alpha["alpha_png"],str(work/"masks"))
        parts=split_semantic_layers(alpha["rgba_png"],masks["index_json"],
                                    landmarks["landmarks_json"],str(work/"parts"))
        parts=fill_hidden_parts(parts,alpha["rgba_png"],str(work/"repair"))
        if supplied:
            names={p.semantic_id:p for p in parts.parts}
            names.update({p.semantic_id:p for p in supplied.parts})
            parts.parts=list(names.values())
    from .layer_export import write_psd_and_ora
    from .mesh2d import generate_meshes
    from .keyforms import build_keyforms
    from .physics2d import build_physics
    from .rig_spec import build_puppet_spec
    parts_json=parts.write(str(work/"parts.json"))
    layers=write_psd_and_ora(parts,str(root))
    parts.psd_path=layers["psd"]
    parts.ora_path=layers["ora"]
    meshes=generate_meshes(parts_json,str(work))
    keys=build_keyforms(meshes["meshes_json"],parts_json,
                        landmarks["landmarks_json"],str(work))
    physics=build_physics(keys["keyforms_json"],parts_json,str(work))
    spec=build_puppet_spec(parts_json,meshes["meshes_json"],keys["keyforms_json"],
                           physics["physics_json"],str(root),str(root/"puppet_spec.json"))
    return {"parts":parts_json,"layers":layers,"meshes":meshes["meshes_json"],
            "keyforms":keys["keyforms_json"],"physics":physics["physics_json"],
            "puppet_spec":spec}

def build_inochi2d(source: SourceSet) -> BuildResult:
    if source.mode!="inochi2d":
        raise ValueError("source mode must be inochi2d")
    art=None
    try:
        art=prepare_common_2d(source)
    except Exception as exc:
        result=BuildResult("inochi2d","failed",None,None,source.output_dir,
                           "2D artwork preparation failed: "+str(exc))
    else:
        try:
            from .inochi_bridge import export_inp
            native=export_inp(art["puppet_spec"],source.output_dir)
            result=BuildResult("inochi2d","complete",native["inp"],
                               native.get("editable") or art["layers"]["psd"],source.output_dir)
        except Exception as exc:
            # Successfully generated real PSD/ORA/mesh/keyforms. A missing or
            # incompatible native INP exporter is PREPARED, never COMPLETE.
            result=BuildResult("inochi2d","prepared",art["layers"]["psd"],
                               art["layers"]["ora"],source.output_dir,
                               "Native INP2 export unavailable: "+str(exc))
    result.write(source.output_dir)
    return result

def build_live2d(source: SourceSet) -> BuildResult:
    if source.mode!="live2d":
        raise ValueError("source mode must be live2d")
    try:
        art=prepare_common_2d(source)
        from .cubism_handoff import create_cubism_package
        handoff=create_cubism_package(art["parts"],art["layers"]["psd"],
                    art["meshes"],art["keyforms"],art["physics"],source.output_dir)
        result=BuildResult("live2d","needs_editor_export",handoff["handoff_zip"],
                           handoff["art_psd"],source.output_dir)
    except Exception as exc:
        result=BuildResult("live2d","failed",None,None,source.output_dir,str(exc))
    result.write(source.output_dir)
    return result
