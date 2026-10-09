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
    "ear_left": "ear.left", "ear_right": "ear.right",
    "nose": "nose",
    "hair_left": "hair.side.left", "hair_right": "hair.side.right",
    "outfit_front": "cloth.front", "outfit_back": "cloth.back",
    "outfit_sleeve_left": "cloth.sleeve.left",
    "outfit_sleeve_right": "cloth.sleeve.right",
}

def _layers(source: SourceSet, folder: Path) -> PartsDocument | None:
    if not source.user_layers_zip:
        return None
    from .preparation import _load_image, _read_layers
    base = _load_image(Path(source.front_image).read_bytes(), "source")
    supplied = _read_layers(source.user_layers_zip, base.size)
    from vtuber_pipeline.prompt_contract import LAYER_PARTS, REQUIRED_2D, CANVAS_2D

    provided_names = {name.casefold() for name, _ in supplied}
    vts = source.artwork_profile == "vts_auto"
    missing = sorted(set(REQUIRED_2D) - provided_names)
    if missing and not vts:
        raise ValueError(
            "Provided layered artwork is incomplete; refusing to fall back "
            "to FLUX/SAM automatic generation. Missing semantic PNGs: "
            + ", ".join(missing)
        )
    if not vts and __import__("os").environ.get("VTUBER_2D_STRICT_LAYER_INPUT") == "1":
        from vtuber_pipeline.wardrobe_contract import GARMENT_PARTS
        from vtuber_pipeline.hair_contract import HAIR_PARTS
        base_expected = {name for name, _ in LAYER_PARTS}
        combinations = (
            base_expected,
            base_expected | HAIR_PARTS,
            base_expected | GARMENT_PARTS,
            base_expected | HAIR_PARTS | GARMENT_PARTS,
        )
        if provided_names not in combinations:
            allowed = base_expected | GARMENT_PARTS | HAIR_PARTS
            unexpected = sorted(provided_names - allowed)
            missing_base = sorted(base_expected - provided_names)
            raise ValueError(
                "2D modular artwork requires all 20 permanent body/face "
                "layers and optionally all 4 hair or 4 garment layers; "
                f"missing_base={missing_base}; unexpected={unexpected}; "
                f"observed_count={len(provided_names)}"
            )
        expected = (CANVAS_2D, (CANVAS_2D[0]*2, CANVAS_2D[1]*2))
        if base.size not in expected:
            raise ValueError(
                f"2D master canvas must be one of {expected}, got {base.size}"
            )
    for name, image in supplied:
        alpha = np.asarray(image.getchannel("A"), dtype=np.uint8)
        pixels = int(np.count_nonzero(alpha))
        if not pixels:
            raise ValueError(f"{name}: generated layer is completely transparent")
        if pixels > base.width * base.height * 0.85:
            raise ValueError(
                f"{name}: nearly full-canvas opaque background; "
                "expected one isolated transparent RGBA part"
            )
    if vts and len(supplied) < 2:
        raise ValueError("VTS imported PSD requires at least two separately movable layers")
    folder.mkdir(parents=True, exist_ok=True)
    parts = []
    for i, (name, img) in enumerate(supplied):
        identity = KNOWN.get(name.lower(), name.lower().replace("_","."))
        if vts:
            # Layer labels are extracted from See-through PSD semantics. A
            # legacy neutral-base required-name check cannot apply here.
            if not any(identity == p or identity.startswith(p+".")
                       for p in ("hair", "body", "leg", "shoe", "arm", "head",
                                 "hand", "brow", "sleeve", "accessory",
                                 "ear", "nose", "neck", "cloth", "face",
                                 "eye", "mouth", "eyebrow", "hat", "ornament")):
                raise ValueError("Unclassified VTS PSD layer: " + name)
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
    # The 2D art/part masks live in front_image pixel coordinates.
    # Independently supplied face crops are NOT spatially registered to that
    # image, so their HRNet landmarks must not be used for full-canvas rigging.
    landmarks = detect(source.front_image, str(work / "face"))
    if supplied:
        # User supplied ALL geometrically registered and occlusion-complete
        # layers. Never run alpha, Florence, SAM or FLUX for this path.
        parts = supplied
        print("[2d-layers] Using supplied full-canvas RGBA layers; "
              "FLUX/SAM automatic restoration bypassed", flush=True)
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
    physics=build_physics(keys["keyforms_json"],parts_json,str(work),
                          meshes_json=meshes["meshes_json"])
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
                               "Official Inochi SDK INP export unavailable: "+str(exc))
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
