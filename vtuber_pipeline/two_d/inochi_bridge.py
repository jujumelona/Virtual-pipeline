"""Official Inochi SDK export boundary and independently parsed INP1 integrity.

The stable, animated 0.8.7 SDK writes INP1; the upstream development SDK
writes INP2 but currently has deformation binding code disabled. Never rename
JSON or artwork to .inp, and do not report success without SDK round-trip,
bound deformations and native secondary physics.
"""
from __future__ import annotations
import json
import os
from pathlib import Path
import struct
import subprocess

INP1_MAGIC = b"TRNSRTS\x00"
INP2_MAGIC = b"TRNSRTS2"


def inspect_native_inp(path: str) -> dict:
    """Parse official Inochi 0.8 INP1 payload/texture section, not file extension."""
    file = Path(path)
    raw = file.read_bytes()
    if len(raw) < 32 or raw[:8] not in (INP1_MAGIC, INP2_MAGIC):
        raise ValueError("Inochi native INP header missing")
    if raw[:8] == INP2_MAGIC:
        # Upstream 0.9's public deformation binding implementation is
        # disabled. A magic-only INP2 check cannot demonstrate animation,
        # so refuse an unparsed version until the native SDK proves both
        # structure and functioning keyframes across reimport.
        raise ValueError("INP2 native deformation/physics validation is unavailable")
    length = struct.unpack_from(">I", raw, 8)[0]
    offset = 12 + length
    if length < 32 or offset + 12 > len(raw):
        raise ValueError("Inochi native INP1 JSON section truncated")
    try:
        payload = json.loads(raw[12:offset].decode("utf-8"))
    except (UnicodeError, json.JSONDecodeError) as exc:
        raise ValueError("Inochi native INP1 JSON payload invalid") from exc
    if raw[offset:offset + 8] != b"TEX_SECT":
        raise ValueError("Inochi native INP1 texture section absent")
    count = struct.unpack_from(">I", raw, offset + 8)[0]
    if not 1 <= count <= 512:
        raise ValueError("Inochi native texture count invalid")
    offset += 12
    for _ in range(count):
        if offset + 5 > len(raw):
            raise ValueError("Inochi native texture payload truncated")
        size = struct.unpack_from(">I", raw, offset)[0]
        encoding = raw[offset + 4]
        offset += 5
        if size < 8 or size > 128 * 1024 * 1024 or encoding not in (0, 1, 2):
            raise ValueError("Inochi native texture payload invalid")
        if offset + size > len(raw):
            raise ValueError("Inochi native texture exceeds file")
        offset += size
    # Official SDK may append EXT_SECT; no opaque trailing garbage allowed.
    if offset < len(raw) and raw[offset:offset + 8] != b"EXT_SECT":
        raise ValueError("Unexpected trailing Inochi native INP payload")
    params = payload.get("param")
    nodes = payload.get("nodes")
    if not isinstance(params, list) or not isinstance(nodes, dict):
        raise ValueError("Inochi native parameters/nodes missing")
    binding_count = sum(
        len(p.get("bindings", []))
        for p in params if isinstance(p, dict) and isinstance(p.get("bindings"), list)
    )
    node_types = []
    def visit(node, depth=0):
        if not isinstance(node, dict) or depth > 256:
            raise ValueError("Inochi native node tree invalid")
        node_types.append(node.get("type"))
        children = node.get("children", [])
        if not isinstance(children, list):
            raise ValueError("Inochi native node children invalid")
        for child in children:
            visit(child, depth + 1)
    visit(nodes)
    if binding_count < 1 or "Part" not in node_types or "SimplePhysics" not in node_types:
        raise ValueError("Inochi native INP has no keyed parts and physical driver")
    return {"format": "INP1", "file_size": len(raw),
            "textures": count, "binding_count": binding_count,
            "part_count": node_types.count("Part"),
            "physics_drivers": node_types.count("SimplePhysics")}


def export_inp(puppet_spec_json: str, output_dir: str) -> dict:
    source = Path(puppet_spec_json).resolve()
    if not source.is_file():
        raise FileNotFoundError(source)
    spec = json.loads(source.read_text(encoding="utf-8"))
    required = ("textures", "parts", "mesh", "parameters", "keyforms",
                "physics", "draw_order")
    if any(key not in spec for key in required):
        raise ValueError("missing Inochi puppet spec keys")
    if not spec["mesh"] or not spec["parameters"]:
        raise ValueError("no mesh/parameter data to rig")
    output = Path(output_dir).resolve()
    output.mkdir(parents=True, exist_ok=True)
    native = os.getenv("VTUBER_INOCHI_NATIVE")
    if (not native or not Path(native).is_file()) and os.getenv("VTUBER_INOCHI_AUTO_BUILD") == "1":
        from tools.setup_inochi_runtime import ensure_inochi_native_runtime
        native = ensure_inochi_native_runtime()
    if not native or not Path(native).is_file():
        raise RuntimeError(
            "Native Inochi SDK exporter unavailable. Choose Inochi2D in "
            "Colab first or enable VTUBER_INOCHI_AUTO_BUILD=1 for the CLI. "
            "Do not label intermediate PSD/ORA as finished native puppet."
        )
    target = output / "avatar.inp"
    report = output / "native_export_report.json"
    for path in (target, report):
        path.unlink(missing_ok=True)
    log_path = output / "inochi_native.log"
    with log_path.open("w", encoding="utf-8") as log:
        proc = subprocess.run([native, str(source), str(target), str(report)],
                              stdout=log, stderr=subprocess.STDOUT, timeout=900)
    if proc.returncode:
        raise RuntimeError("native Inochi SDK exporter failed (exit="
                           + str(proc.returncode) + "); see " + str(log_path))
    if not report.is_file():
        raise RuntimeError("Inochi SDK exporter did not provide a validation report")
    evidence = json.loads(report.read_text(encoding="utf-8"))
    if (evidence.get("sdk_native_write") is not True
            or evidence.get("sdk_roundtrip_read") is not True
            or int(evidence.get("sdk_reimport_binding_count", 0)) < 1
            or int(evidence.get("bound_keyforms_count", 0)) < 1
            or int(evidence.get("mesh_vertices_count", 0)) < 3
            or int(evidence.get("physics_bindings_count", 0)) < 1):
        target.unlink(missing_ok=True)
        raise RuntimeError("native INP has no verified mesh/physics/deformation bindings")
    if not target.is_file() or target.stat().st_size < 128:
        raise RuntimeError("native exporter did not emit a complete model")
    try:
        parsed = inspect_native_inp(str(target))
        if parsed["format"] != evidence.get("inp_format"):
            raise ValueError("official SDK version and INP file encoding mismatch")
        if parsed["format"] == "INP1" and (
            parsed["binding_count"] < 1 or parsed["physics_drivers"] < 1
        ):
            raise ValueError("Inochi native file lost bound animation/physics")
    except Exception:
        target.unlink(missing_ok=True)
        raise
    return {"inp": str(target), "editable": str(source),
            "native_report": str(report), "native_format": parsed["format"]}
