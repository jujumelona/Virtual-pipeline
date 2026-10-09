"""Verified, on-demand Blender 4.2 LTS and VRM extension installer.

The 3D editor is not installed during 2D preparation.
"""
from __future__ import annotations
import hashlib
import os
from pathlib import Path
import re
import subprocess
import urllib.request

VERSION = "4.2.23"
ARCHIVE = "blender-4.2.23-linux-x64.tar.xz"
BASE = "https://download.blender.org/release/Blender4.2/"
EXTENSION = "https://github.com/saturday06/VRM-Addon-for-Blender/releases/download/v4.7.2/VRM_Addon_for_Blender-Extension-4_7_2.zip"
EXTENSION_SHA256 = "e85588660bfbb4099910a86803fa87dc8348e65541a4ccdcaf40c538f60027dc"


def published_sha(text: str, filename: str) -> str:
    matches = []
    for line in text.splitlines():
        item = re.fullmatch(r"\s*([0-9a-fA-F]{64})\s+\*?([^\s]+)\s*", line)
        if item and Path(item.group(2)).name == filename:
            matches.append(item.group(1).lower())
    if len(matches) != 1:
        raise ValueError("Expected one exact publisher SHA256 checksum for " + filename)
    return matches[0]


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for part in iter(lambda: stream.read(1048576), b""):
            h.update(part)
    return h.hexdigest()


def verified_download(url: str, path: Path, expected: str, max_bytes: int) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.is_file() and sha256(path) == expected:
        return path
    temp = path.with_suffix(path.suffix + ".part")
    temp.unlink(missing_ok=True)
    total = 0
    h = hashlib.sha256()
    try:
        with urllib.request.urlopen(url, timeout=90) as reply, temp.open("wb") as stream:
            while True:
                part = reply.read(1048576)
                if not part:
                    break
                total += len(part)
                if total > max_bytes:
                    raise RuntimeError("Verified archive exceeded maximum download size")
                stream.write(part)
                h.update(part)
        if not total or h.hexdigest() != expected:
            raise RuntimeError("Publisher archive checksum mismatch: " + url)
        temp.replace(path)
    finally:
        temp.unlink(missing_ok=True)
    return path


def checked_process(args: list[str], *, env: dict | None = None, timeout: int) -> str:
    done = subprocess.run(args, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                          text=True, errors="replace", timeout=timeout, env=env)
    if done.returncode:
        raise RuntimeError("External command failed: " + " ".join(args) + "\n" + done.stdout[-5000:])
    return done.stdout


def ensure_blender_runtime(cache_dir: str) -> str:
    """Install only for 3D and verify the actual import/export operators."""
    configured = os.environ.get("VTUBER_BLENDER_BINARY")
    cache = Path(cache_dir).expanduser().resolve()
    cache.mkdir(parents=True, exist_ok=True)
    executable = (Path(configured).expanduser().resolve() if configured else
                  cache / "blender-4.2.23-linux-x64" / "blender")
    if configured and not executable.is_file():
        raise FileNotFoundError(configured)
    if (os.environ.get("VTUBER_BLENDER_VERIFIED_BINARY") == str(executable)
            and executable.is_file()):
        return str(executable)
    if not executable.is_file():
        with urllib.request.urlopen(BASE + "blender-4.2.23.sha256", timeout=60) as reply:
            digest = published_sha(reply.read(8192).decode("utf-8"), ARCHIVE)
        archive = verified_download(BASE + ARCHIVE, cache / ARCHIVE,
                                    digest, 600 * 1024 * 1024)
        checked_process(["tar", "-xJf", str(archive), "-C", str(cache)], timeout=1200)
    if not executable.is_file():
        raise RuntimeError("Publisher Blender binary is missing")
    addon = verified_download(EXTENSION, cache / "vrm_extension_v4.7.2.zip",
                              EXTENSION_SHA256, 12 * 1024 * 1024)
    env = dict(os.environ)
    env["BLENDER_USER_CONFIG"] = str(cache / "blender-user")
    Path(env["BLENDER_USER_CONFIG"]).mkdir(parents=True, exist_ok=True)
    checked_process([str(executable), "--command", "extension", "install-file",
                     "-r", "user_default", "-e", str(addon)], env=env, timeout=300)
    verify = ("import bpy; "
              "bpy.ops.preferences.addon_enable(module='bl_ext.user_default.vrm'); "
              "bpy.ops.import_scene.vrm.get_rna_type(); "
              "bpy.ops.export_scene.vrm.get_rna_type(); "
              "print('vrm-addon-verified')")
    log = checked_process([str(executable), "--background", "--python-exit-code",
                           "29", "--python-expr", verify], env=env, timeout=180)
    if "vrm-addon-verified" not in log:
        raise RuntimeError("VRM extension import/export operators unavailable")
    os.environ["VTUBER_BLENDER_BINARY"] = str(executable)
    os.environ["BLENDER_USER_CONFIG"] = env["BLENDER_USER_CONFIG"]
    # A configured path is never proof of the official VRM operators.
    # Set readiness only after the exact Blender process has passed the probe.
    os.environ["VTUBER_BLENDER_VERIFIED_BINARY"] = str(executable)
    return str(executable)


def require_blender_runtime_ready() -> str:
    """Generation-only contract: never install or fetch Blender here."""
    executable = os.environ.get("VTUBER_BLENDER_BINARY")
    verified = os.environ.get("VTUBER_BLENDER_VERIFIED_BINARY")
    if not executable or not verified or verified != str(Path(executable).expanduser().resolve()):
        raise RuntimeError("3D Blender/VRM extension must be verified during workflow setup")
    if not Path(executable).is_file():
        raise FileNotFoundError(executable)
    return executable
