"""Verified Colab avatar.vrm delivery handoff between the Gradio server and kernel.

The UI runs in a separate Python process. Only the notebook kernel can invoke
google.colab.files.download(). Never interpret a Gradio download component as a
browser delivery acknowledgement.
"""
from __future__ import annotations

import hashlib
import json
import os
import shutil
from pathlib import Path
import uuid


def _digest(path: Path) -> str:
    sha = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            sha.update(chunk)
    return sha.hexdigest()


def checked_avatar(path: str | Path, output_root: str | Path) -> dict:
    file = Path(path).expanduser().resolve(strict=True)
    root = Path(output_root).expanduser().resolve(strict=True)
    if not file.is_relative_to(root) or file.name != "avatar.vrm":
        raise ValueError(f"Auto-download requires avatar.vrm inside output root: {file}")
    if not file.is_file() or file.stat().st_size < 20:
        raise ValueError(f"Avatar VRM is missing or too short: {file}")
    with file.open("rb") as handle:
        if handle.read(4) != b"glTF":
            raise ValueError(f"Avatar VRM does not have a GLB/VRM header: {file}")
    return {
        "id": uuid.uuid4().hex,
        "filename": "avatar.vrm",
        "path": str(file),
        "size": file.stat().st_size,
        "sha256": _digest(file),
    }


def save_latest_avatar(path: str | Path, output_root: str | Path, destination: str | Path) -> Path:
    """Provide a stable Colab Files-sidebar path, without moving the original."""
    metadata = checked_avatar(path, output_root)
    source = Path(metadata["path"])
    final = Path(destination).expanduser().absolute()
    final.parent.mkdir(parents=True, exist_ok=True)
    pending = final.with_name(f".{final.name}.{uuid.uuid4().hex}.pending")
    try:
        shutil.copyfile(source, pending)
        if pending.stat().st_size != metadata["size"] or _digest(pending) != metadata["sha256"]:
            raise RuntimeError("Latest VRM copy failed checksum verification")
        os.replace(pending, final)
    finally:
        pending.unlink(missing_ok=True)
    return final


def gradio_file_route(path: str | Path, output_root: str | Path) -> str:
    """URL path for the current Gradio server's directly downloadable file."""
    from urllib.parse import quote

    metadata = checked_avatar(path, output_root)
    return "/gradio_api/file=" + quote(metadata["path"], safe="/")


def publish_avatar_download(
    path: str | Path,
    output_root: str | Path,
    queue_dir: str | Path,
) -> Path:
    """Publish only a completed, file-verified avatar, atomically."""
    metadata = checked_avatar(path, output_root)
    queue = Path(queue_dir).expanduser().resolve()
    queue.mkdir(parents=True, exist_ok=True)
    final = queue / f"request-{metadata['id']}.json"
    temporary = queue / f".{metadata['id']}.tmp"
    try:
        temporary.write_text(json.dumps(metadata, ensure_ascii=False), encoding="utf-8")
        os.replace(temporary, final)
    finally:
        temporary.unlink(missing_ok=True)
    return final


def consume_avatar_downloads(queue_dir: str | Path, output_root: str | Path, download) -> list[dict]:
    """Start browser downloads for pending events, once each.

    Return outcome records. 'requested' means Colab accepted the call, NOT
    confirmed that the browser saved the bytes on the user's computer.
    """
    queue = Path(queue_dir)
    if not queue.is_dir():
        return []
    outcomes = []
    for request in sorted(queue.glob("request-*.json")):
        try:
            metadata = json.loads(request.read_text(encoding="utf-8"))
            path = metadata["path"]
            actual = checked_avatar(path, output_root)
            if (
                actual["sha256"] != metadata["sha256"]
                or actual["size"] != metadata["size"]
                or metadata.get("filename") != "avatar.vrm"
            ):
                raise RuntimeError("VRM changed since successful validation")
            download(str(actual["path"]))
            outcome = {"id": metadata["id"], "status": "requested", "filename": "avatar.vrm"}
        except Exception as exc:
            outcome = {
                "id": request.stem.removeprefix("request-"),
                "status": "error",
                "detail": f"{type(exc).__name__}: {exc}",
            }
        acknowledged = queue / f"receipt-{outcome['id']}.json"
        temporary = queue / f".receipt-{outcome['id']}.tmp"
        try:
            temporary.write_text(json.dumps(outcome, ensure_ascii=False), encoding="utf-8")
            os.replace(temporary, acknowledged)
            request.unlink(missing_ok=True)
        finally:
            temporary.unlink(missing_ok=True)
        outcomes.append(outcome)
    return outcomes
