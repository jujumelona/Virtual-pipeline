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
    import re

    metadata = checked_avatar(path, output_root)
    folder = Path(metadata["path"]).parent.name
    if not re.fullmatch(r"avatar-[A-Za-z0-9_-]{1,32}", folder):
        raise ValueError(f"Unexpected avatar output folder: {folder}")
    return f"/vtuber-download/{folder}/avatar.vrm"


def install_direct_download_route(app, output_root: str | Path) -> None:
    """FastAPI attachment route on the EXISTING Gradio server and Colab port.

    Gradio 6.3's own /gradio_api/file= endpoint responds with
    Content-Disposition: inline for .vrm (MIME model/vrml). This endpoint
    deliberately forces attachment so Chrome actually saves avatar.vrm.
    """
    import re
    from fastapi import HTTPException
    from starlette.responses import FileResponse

    root = Path(output_root).expanduser().resolve(strict=True)

    def download_avatar(folder: str):
        if not re.fullmatch(r"avatar-[A-Za-z0-9_-]{1,32}", folder):
            raise HTTPException(status_code=404, detail="Invalid avatar path")
        try:
            path = root / folder / "avatar.vrm"
            checked_avatar(path, root)
        except (OSError, ValueError):
            raise HTTPException(status_code=404, detail="Valid avatar.vrm not found")
        return FileResponse(
            path,
            media_type="application/octet-stream",
            filename="avatar.vrm",
            content_disposition_type="attachment",
        )

    app.add_api_route(
        "/vtuber-download/{folder}/avatar.vrm",
        download_avatar,
        methods=["GET"],
        include_in_schema=False,
    )
    # Gradio installs a SPA catch-all path. Our route must match BEFORE it,
    # even when registered after demo.launch created the FastAPI app.
    route = app.router.routes.pop()
    app.router.routes.insert(0, route)


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
