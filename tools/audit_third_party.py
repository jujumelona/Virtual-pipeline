"""Audit pinned third-party source revisions and observed artifact hashes."""

import hashlib
import importlib.metadata
import json
import pathlib
import subprocess
from typing import Any, Dict, Optional


ROOT = pathlib.Path(__file__).resolve().parents[1]
LOCK_PATH = ROOT / "third_party.lock.json"


def compute_artifact_hash(file_path: pathlib.Path) -> Optional[str]:
    """Return the real SHA256 of file bytes, or None when unavailable."""
    if not file_path.is_file():
        return None
    digest = hashlib.sha256()
    with file_path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_lock_file(lock_path: pathlib.Path = LOCK_PATH) -> Dict[str, Any]:
    with lock_path.open(encoding="utf-8") as handle:
        return json.load(handle)


def check_git_revision(path: pathlib.Path, expected: str) -> Dict[str, Any]:
    result = {"expected": expected, "actual": None, "match": False, "path": str(path)}
    if not (path / ".git").exists():
        result["error"] = "git checkout not found"
        return result
    try:
        proc = subprocess.run(
            ["git", "-C", str(path), "rev-parse", "HEAD"],
            capture_output=True, text=True, timeout=30,
        )
    except (FileNotFoundError, subprocess.TimeoutExpired) as exc:
        result["error"] = str(exc)
        return result
    if proc.returncode != 0:
        result["error"] = proc.stderr.strip()
        return result
    result["actual"] = proc.stdout.strip()
    result["match"] = result["actual"] == expected
    return result


def check_package_version(package: str, expected: str) -> Dict[str, Any]:
    result = {"expected": expected, "actual": None, "match": False, "package": package}
    try:
        actual = importlib.metadata.version(package)
    except importlib.metadata.PackageNotFoundError:
        result["error"] = "package not installed"
        return result
    result["actual"] = actual
    result["match"] = actual == expected
    return result


def discover_artifact(name: str, info: Dict[str, Any]) -> Optional[pathlib.Path]:
    """Find concrete downloaded bytes for hash observation; never fake a hash."""
    if name == "triposr":
        candidates = []
        repo = ROOT / info.get("path", "TripoSR")
        candidates.extend([
            repo / "model.ckpt",
            repo / "model.safetensors",
            repo / "weights" / "model.ckpt",
        ])
        hf = pathlib.Path.home() / ".cache" / "huggingface" / "hub" / "models--stabilityai--TripoSR"
        if hf.exists():
            candidates.extend(hf.glob("snapshots/*/model.ckpt"))
            candidates.extend(hf.glob("snapshots/*/*.safetensors"))
        return next((p for p in candidates if pathlib.Path(p).is_file()), None)

    if name == "anime_face_detector":
        candidates = []
        torch_cache = pathlib.Path.home() / ".cache" / "torch" / "hub" / "checkpoints"
        if torch_cache.exists():
            for suffix in ("*.pt", "*.pth", "*.ckpt"):
                candidates.extend(torch_cache.glob(suffix))
        local = ROOT / "models" / "anime_face_detector"
        if local.exists():
            for suffix in ("*.pt", "*.pth", "*.ckpt"):
                candidates.extend(local.glob(suffix))
        return next((p for p in candidates if pathlib.Path(p).is_file()), None)

    if name == "makehuman_cc0":
        candidates = [
            ROOT / "assets" / "makehuman_cc0" / "base.obj",
            pathlib.Path.home() / ".cache" / "vtuber-pipeline" / "makehuman_cc0" / "base.obj",
        ]
        return next((p for p in candidates if p.is_file()), None)

    return None


def audit_tools(lock_path: pathlib.Path = LOCK_PATH) -> Dict[str, Any]:
    """Audit source/package locks and report real observed artifact SHA256 values."""
    lock = load_lock_file(lock_path)
    results: Dict[str, Any] = {}
    for name, info in lock.get("tools", {}).items():
        item: Dict[str, Any] = {
            "license": info.get("license"),
            "commercial_safe": bool(info.get("commercial_safe")),
        }

        if name == "triposr":
            item["source"] = check_git_revision(
                ROOT / info.get("path", "TripoSR"), info["source_commit"]
            )
        elif info.get("package") and info.get("package_version"):
            item["package"] = check_package_version(
                info["package"], info["package_version"]
            )
        else:
            item["source"] = {
                "expected": info.get("source_commit"),
                "match": None,
                "note": "asset is fetched from the pinned commit URL",
            }

        artifact = discover_artifact(name, info)
        observed = compute_artifact_hash(artifact) if artifact else None
        expected = info.get("artifact_sha256")
        item["artifact"] = {
            "path": str(artifact) if artifact else None,
            "expected_sha256": expected,
            "observed_sha256": observed,
            "match": (observed == expected) if expected and observed else None,
            "locked": bool(expected),
        }
        results[name] = item
    return results


def print_audit_report() -> None:
    print("Third-Party Audit")
    print("=" * 40)
    for name, item in audit_tools().items():
        print(name)
        source = item.get("source") or item.get("package")
        if source:
            print("  source/package:", source)
        artifact = item["artifact"]
        print("  artifact:", artifact)
        if artifact["observed_sha256"] and not artifact["locked"]:
            print("  note: real artifact bytes observed but no trusted expected SHA256 is frozen")


if __name__ == "__main__":
    print_audit_report()
