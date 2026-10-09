"""On-demand official Inochi 0.8.7 SDK exporter setup (never during 3D/Live2D).

The stable 0.8.7 SDK still implements mesh deformation parameter bindings,
which are disabled on the upstream 0.9 development branch. Building with
DUB locks the dependency to the exact 0.8.7 release. Do not substitute a
fake .inp file or silently mark model generation as complete on setup failure.
"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
PROJECT = ROOT / "tools" / "inochi_native"
CACHE = Path(os.environ.get(
    "VTUBER_INOCHI_RUNTIME_DIR", "/content/vtuber_builder/native/inochi",
))


def _run(command: list[str], *, timeout: int, cwd: Path | None = None) -> None:
    """Persist complete D compiler output; never discard the actual diagnostics.

    The old check=True call exposed only CalledProcessError(exit=2), making
    source/API mismatches indistinguishable from linker and missing packages.
    """
    log = CACHE / "logs" / "native_build.log"
    log.parent.mkdir(parents=True, exist_ok=True)
    print("[inochi-sdk] " + " ".join(command) + f" · log={log}", flush=True)
    with log.open("a", encoding="utf-8") as stream:
        stream.write("\n$ " + subprocess.list2cmdline(command) + "\n")
        stream.flush()
        try:
            result = subprocess.run(command, timeout=timeout,
                cwd=str(cwd) if cwd else None, stdout=stream,
                stderr=subprocess.STDOUT, check=False)
        except subprocess.TimeoutExpired as exc:
            raise RuntimeError(
                f"Inochi SDK command exceeded {timeout}s; full output: {log}"
            ) from exc
    if result.returncode:
        # Tail is bounded for notebook output, full source error is on disk.
        with log.open("r", encoding="utf-8", errors="replace") as stream:
            from collections import deque
            tail = "".join(deque(stream, maxlen=95))
        raise RuntimeError(
            f"Inochi SDK command failed (exit={result.returncode}): "
            + subprocess.list2cmdline(command)
            + f"\n{tail[-11000:]}\nFull compiler output: {log}"
        )


def _link_dependencies_ready() -> bool:
    """Check the link-time headers/symlinks as well as executables.

    Existing code only looked for ldc2/dub/xvfb-run and skipped SDL2/GL/GLU
    development libraries whenever the compiler was already on PATH.
    """
    if not shutil.which("pkg-config"):
        return False
    try:
        result = subprocess.run(
            ["pkg-config", "--exists", "sdl2", "gl", "glu", "zlib"],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            timeout=20, check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return False
    return result.returncode == 0


def _install_compiler() -> None:
    needed = ("ldc2", "dub", "xvfb-run")
    if all(shutil.which(name) for name in needed) and _link_dependencies_ready():
        return
    if not shutil.which("apt-get"):
        raise RuntimeError(
            "Inochi SDK requires LDC, DUB, SDL2, OpenGL, zlib and Xvfb; no apt-get found")
    prefix = [] if (hasattr(os, "geteuid") and os.geteuid() == 0) else ["sudo"]
    _run([*prefix, "apt-get", "update", "-qq"], timeout=300)
    _run([*prefix, "apt-get", "install", "-y", "--no-install-recommends",
          "ldc", "dub", "xvfb", "pkg-config", "libsdl2-dev",
          "libgl1-mesa-dev", "libglu1-mesa-dev", "zlib1g-dev"], timeout=900)
    if not all(shutil.which(name) for name in needed) or not _link_dependencies_ready():
        raise RuntimeError("D compiler or SDL2/OpenGL/GLU/zlib link-time dependencies are missing")


def ensure_inochi_native_runtime() -> str:
    """Build and verify the real D executable, returning a headless wrapper."""
    CACHE.mkdir(parents=True, exist_ok=True)
    compiler = PROJECT / "dub.sdl"
    sources = sorted((PROJECT / "source").glob("*.d"))
    if not compiler.is_file() or not sources:
        raise RuntimeError("Official Inochi SDK exporter sources are missing")
    dependency_lock = PROJECT / "dub.selections.json"
    if not dependency_lock.is_file():
        raise RuntimeError("Native Inochi SDK DUB dependency lock is missing")
    lock = json.loads(dependency_lock.read_text(encoding="utf-8"))
    if lock.get("versions", {}).get("inochi2d") != "0.8.7":
        raise RuntimeError("Native Inochi SDK must use locked version 0.8.7")
    fingerprint = hashlib.sha256(
        compiler.read_bytes() + dependency_lock.read_bytes()
        + b"".join(src.read_bytes() for src in sources)
        + b"inochi2d-sdk-v0.8.7-full-sdl2"
    ).hexdigest()
    binary = CACHE / "vtuber-inochi-native"
    wrapper = CACHE / "inochi-export"
    marker = CACHE / "ready.json"
    try:
        meta = json.loads(marker.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        meta = {}
    if (meta.get("fingerprint") == fingerprint
            and binary.is_file() and os.access(binary, os.X_OK)
            and wrapper.is_file() and os.access(wrapper, os.X_OK)
            and shutil.which("xvfb-run")):
        os.environ["VTUBER_INOCHI_NATIVE"] = str(wrapper)
        return str(wrapper)

    _install_compiler()
    _run(["ldc2", "--version"], timeout=30, cwd=PROJECT)
    _run(["dub", "--version"], timeout=30, cwd=PROJECT)
    _run(["dub", "build", "--build=release", "--compiler=ldc2",
          "--force"], timeout=1800, cwd=PROJECT)
    built = PROJECT / "vtuber-inochi-native"
    if not built.is_file() or not os.access(built, os.X_OK):
        raise RuntimeError("Official SDK DUB build did not emit a runnable exporter")
    shutil.copy2(built, binary)
    binary.chmod(0o755)
    wrapper.write_text(
        '#!/bin/sh\nexec xvfb-run -a -s "-screen 0 1280x1024x24" '
        + "'" + str(binary) + "'" + ' "$@"\n',
        encoding="utf-8",
    )
    wrapper.chmod(0o755)
    # A successful compilation is not sufficient for INP completeness.
    # The exporter itself validates official inLoadPuppet round-trip and will
    # only mark complete if it bound real deformations and physics.
    marker.write_text(json.dumps({
        "fingerprint": fingerprint,
        "sdk_release": "0.8.7",
        "binary": str(binary),
        "renderer": "SDL2 hidden OpenGL on Xvfb",
    }, indent=2), encoding="utf-8")
    os.environ["VTUBER_INOCHI_NATIVE"] = str(wrapper)
    return str(wrapper)


if __name__ == "__main__":
    print(ensure_inochi_native_runtime(), flush=True)
