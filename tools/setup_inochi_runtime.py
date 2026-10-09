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
import tempfile

ROOT = Path(__file__).resolve().parents[1]
PROJECT = ROOT / "tools" / "inochi_native"
CACHE = Path(os.environ.get(
    "VTUBER_INOCHI_RUNTIME_DIR", "/content/vtuber_builder/native/inochi",
))


def _run(command: list[str], *, timeout: int, cwd: Path | None = None) -> None:
    """Stream ALL native compiler stdout/stderr to Colab and a durable file.

    No only-last-N-lines excerpts: unresolved symbols often appear hundreds of
    lines before '/usr/bin/cc failed'. Use a file (not a pipe) so the producer
    never deadlocks when notebook output is slow; read it concurrently.
    """
    import signal
    import time

    log_path = CACHE / "logs" / "native_build.log"
    log_path.parent.mkdir(parents=True, exist_ok=True)
    header = "[inochi-sdk] $ " + subprocess.list2cmdline(command)
    print(f"{header}\n[inochi-sdk] complete transcript: {log_path}", flush=True)
    with log_path.open("a", encoding="utf-8") as sink:
        sink.write(header + "\n")
        sink.flush()
        start_offset = sink.tell()
        proc = subprocess.Popen(
            command, cwd=str(cwd) if cwd else None, stdout=sink,
            stderr=subprocess.STDOUT, start_new_session=True,
        )
    cursor = start_offset
    deadline = time.monotonic() + timeout

    def drain() -> None:
        nonlocal cursor
        with log_path.open("r", encoding="utf-8", errors="replace") as stream:
            stream.seek(cursor)
            while True:
                line = stream.readline()
                if not line:
                    break
                print(line, end="" if line.endswith("\n") else "\n", flush=True)
            cursor = stream.tell()

    try:
        while proc.poll() is None:
            drain()
            if time.monotonic() > deadline:
                raise subprocess.TimeoutExpired(command, timeout)
            time.sleep(0.1)
        drain()
    except BaseException:
        if proc.poll() is None:
            try:
                os.killpg(proc.pid, signal.SIGTERM)
            except ProcessLookupError:
                pass
            try:
                proc.wait(timeout=3)
            except subprocess.TimeoutExpired:
                try:
                    os.killpg(proc.pid, signal.SIGKILL)
                except ProcessLookupError:
                    pass
                proc.wait(timeout=10)
        drain()
        raise

    if proc.returncode:
        raise RuntimeError(
            f"Inochi SDK command failed (exit={proc.returncode}): "
            + subprocess.list2cmdline(command)
            + f"\nFull compiler output already shown above and saved in: {log_path}"
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
          "libgl1-mesa-dev", "libglvnd-dev", "libglu1-mesa-dev", "zlib1g-dev"], timeout=900)
    if not all(shutil.which(name) for name in needed) or not _link_dependencies_ready():
        raise RuntimeError("D compiler or SDL2/OpenGL/GLU/zlib link-time dependencies are missing")


def _verify_native_linker() -> None:
    """Exercise the *actual* cc and LDC link steps before compiling the SDK.

    pkg-config alone checks metadata. The Colab failure occurs in the final
    /usr/bin/cc link, which can still lack development symlinks, D runtime,
    architecture-compatible libraries or link symbols.
    """
    with tempfile.TemporaryDirectory(prefix="inochi-link-", dir=CACHE) as folder:
        probe = Path(folder)
        c_source = probe / "link_probe.c"
        c_source.write_text(
            "#include <SDL2/SDL.h>\n"
            "#include <GL/gl.h>\n"
            "#include <GL/glu.h>\n"
            "#include <zlib.h>\n"
            "int main(void) { "
            "return (int)(SDL_Init(0) + (glGetString(GL_VERSION) == 0) "
            "+ (gluErrorString(GL_NO_ERROR) == 0) + (zlibVersion() == 0)); }\n",
            encoding="utf-8",
        )
        _run([
            "cc", str(c_source), "-o", str(probe / "c_link_probe"),
            "-Wl,--no-as-needed", "-lSDL2", "-lGL",
            "-lGLdispatch", "-lGLU", "-lz",
        ], timeout=120, cwd=PROJECT)
        d_source = probe / "link_probe.d"
        d_source.write_text(
            'import std.stdio; void main() { writeln("ldc-link-smoke-ok"); }\n',
            encoding="utf-8",
        )
        _run(["ldc2", str(d_source), "-of=" + str(probe / "d_link_probe"),
              "-L--no-as-needed", "-L-lGL", "-L-lGLdispatch",
              "-v"], timeout=120, cwd=PROJECT)
    print("[inochi-sdk] native C and D linker smoke passed", flush=True)


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
    _verify_native_linker()
    _run(["dub", "build", "--build=release", "--compiler=ldc2",
          "--force", "--verbose"], timeout=1800, cwd=PROJECT)
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
