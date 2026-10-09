"""VRoid/XWear dress-up handoff -- NOT a fake garment skinner.

XWear is a proprietary VRoid Studio outfit file. VRM 1.0 is an avatar
container; a 3D clothing *image* cannot be baked as a rigid accessory.
This adapter safely packages a user-supplied actual XWear and a VRM for
the official fitting editor. It never claims a complete dressed VRM.
"""
from __future__ import annotations
import hashlib
import json
from pathlib import Path
from zipfile import ZipFile, ZIP_DEFLATED


def _digest(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as input_file:
        for chunk in iter(lambda: input_file.read(1024*1024), b""):
            h.update(chunk)
    return h.hexdigest()


def prepare_vroid_dressup(base_vrm: str, outfit_xwear: str,
                          destination: str) -> str:
    from tools.colab_native import _has_vrm_container
    vrm = Path(base_vrm).resolve(strict=True)
    outfit = Path(outfit_xwear).resolve(strict=True)
    output = Path(destination).resolve()
    if vrm == outfit or output in (vrm,outfit):
        raise ValueError("VRM, outfit and handoff output must have different paths")
    if vrm.suffix.casefold() != ".vrm" or not _has_vrm_container(vrm):
        raise ValueError("Base must be an actual VRM 1.0 with humanoid metadata")
    if outfit.suffix.casefold() != ".xwear":
        raise ValueError("Garment requires a REAL .xwear file, not a renamed image/GLB")
    if outfit.stat().st_size < 128 or outfit.stat().st_size > 750*1024*1024:
        raise ValueError("XWear file is empty or exceeds 750 MiB limit")
    if vrm.stat().st_size > 750*1024*1024:
        raise ValueError("VRM file exceeds 750 MiB limit")
    # Do not parse or rewrite VRoid's proprietary binary data. Format-specific
    # compatibility must be checked with its actual importer.
    manifest = {
        "type": "vtuber/wardrobe-handoff-v1",
        "status": "editor_import_required",
        "backend": "VRoid Studio Dress-up / XWear",
        "files": {
            "base_avatar.vrm": {"sha256": _digest(vrm), "bytes":vrm.stat().st_size},
            "costume.xwear": {"sha256": _digest(outfit),
                              "bytes":outfit.stat().st_size},
        },
        "automated_fitting_or_skinning": False,
        "vrm_exported": False,
        "compatibility_verified_in_editor": False,
        "base_may_contain_baked_costume_geometry": True,
        "base_body_mesh_separation_verified": False,
    }
    guide = (
        "This ZIP is a VRoid Studio dress-up INPUT PACKAGE, not a dressed VRM.\n"
        "1. Open VRoid Studio (desktop Windows/macOS) > Dress-up.\n"
        "2. Add Base Model > base_avatar.vrm.\n"
        "3. Add Costume > costume.xwear.\n"
        "4. WARNING: original avatar may contain clothing baked into its\n"
        "   body mesh. It is NOT automatically removed by adding XWear.\n"
        "   Use a covered neutral base or fix/delete interfering geometry.\n"
        "5. Choose fitting strategy: Keep Costume Shape or Conform to Body.\n"
        "6. Inspect skin-mask / delete-hidden-body options; avoid clipping.\n"
        "7. Preview motions at shoulders, elbows, waist, hips and knees.\n"
        "8. Adjust deformation/blend shapes; export VRM 1.0 from VRoid.\n"
        "9. Re-run avatar validation before claiming production success.\n"
        "This repo does NOT auto-rig garments based on four 2D views,\n"
        "and its static-accessory baker explicitly rejects skinned garments.\n"
        "Official usage: https://vroid.pixiv.help/hc/en-us/articles/"
        "38722733769241-Getting-Started-with-the-Dress-up-Feature-"
        "for-those-who-want-to-dress-up-their-characters\n"
    )
    output.parent.mkdir(parents=True,exist_ok=True)
    tmp = output.with_name(output.name+".partial")
    try:
        with ZipFile(tmp,"w",compression=ZIP_DEFLATED,compresslevel=1) as out:
            out.write(vrm, "base_avatar.vrm")
            out.write(outfit, "costume.xwear")
            out.writestr("manifest.json",
                         json.dumps(manifest,ensure_ascii=False,indent=2))
            out.writestr("VRoid_wardrobe_steps.txt",guide)
        tmp.replace(output)
    finally:
        tmp.unlink(missing_ok=True)
    return str(output)
