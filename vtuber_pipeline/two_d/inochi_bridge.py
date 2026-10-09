"""Native Inochi SDK launcher; refuse inert/renamed/non-rigged INP2 assets."""
from __future__ import annotations
import json
import os
from pathlib import Path
import subprocess

SDK_INP1_MAGIC=b"TRNSRTS\\x00"\nSDK_INP2_MAGIC=b"TRNSRTS2"

def export_inp(puppet_spec_json: str, output_dir: str) -> dict:
    source=Path(puppet_spec_json).resolve()
    if not source.is_file():raise FileNotFoundError(source)
    spec=json.loads(source.read_text(encoding="utf-8"))
    required=("textures","parts","mesh","parameters","keyforms","physics","draw_order")
    if any(key not in spec for key in required):
        raise ValueError("missing Inochi puppet spec keys")
    if not spec["mesh"] or not spec["parameters"]:
        raise ValueError("no mesh/parameter data to rig")
    output=Path(output_dir).resolve()
    output.mkdir(parents=True,exist_ok=True)
    native=os.getenv("VTUBER_INOCHI_NATIVE")
    if not native or not Path(native).is_file():
        raise RuntimeError(
          "Inochi2D requires a built D SDK exporter at VTUBER_INOCHI_NATIVE. "
          "Current SDK 0.9 upstream has disabled parameter deformation bindings; "
          "cannot silently emit a nonanimated .inp model."
        )
    target=output/"avatar.inp"
    report=output/"native_export_report.json"
    for path in (target,report):
        path.unlink(missing_ok=True)
    with (output/"inochi_native.log").open("w",encoding="utf-8") as log:
        proc=subprocess.run([native,str(source),str(target),str(report)],
                            stdout=log,stderr=subprocess.STDOUT,timeout=900)
    if proc.returncode:
        raise RuntimeError("native Inochi exporter failed exit="+str(proc.returncode))
    if not report.is_file():
        raise RuntimeError("Inochi SDK exporter did not provide a validation report")
    evidence=json.loads(report.read_text(encoding="utf-8"))
    if (evidence.get("sdk_native_write") is not True or\n        evidence.get("sdk_roundtrip_read") is not True or\n        evidence.get("sdk_reimport_binding_count", 0) < 1 or
        int(evidence.get("bound_keyforms_count",0))<1 or
        int(evidence.get("mesh_vertices_count",0))<3 or
        int(evidence.get("physics_bindings_count",0))<1):
        target.unlink(missing_ok=True)
        raise RuntimeError("native INP2 is not a functional rig: "
                           "mesh/keyforms/secondary physics must be serialized and bound")
    if not target.is_file() or target.stat().st_size<128:\n        target.unlink(missing_ok=True)\n        raise RuntimeError("native exporter did not emit a usable INP file")\n    reported_format = evidence.get("inp_format")\n    expected_magic = {"INP1": SDK_INP1_MAGIC, "INP2": SDK_INP2_MAGIC}.get(reported_format)\n    if expected_magic is None or target.open("rb").read(8) != expected_magic:
        target.unlink(missing_ok=True)
        raise RuntimeError("native SDK file format disagrees with its reported INP version")
    return {"inp":str(target),"editable":str(source),"native_report":str(report),\n            "inp_format": reported_format, "sdk_version": evidence.get("sdk_version")}
