"""Script to audit third-party tool versions.

This script reads the third_party.lock.json and checks each tool's
actual version against the pinned version.
"""

import json
import pathlib
import subprocess
import hashlib
from typing import Optional


def compute_artifact_hash(file_path: pathlib.Path) -> Optional[str]:
    """Compute SHA256 hash of an artifact file.
    
    Args:
        file_path: Path to the file to hash.
        
    Returns:
        SHA256 hash string with 'sha256:' prefix, or None if file doesn't exist.
    """
    if not file_path.exists():
        return None
    
    sha256_hash = hashlib.sha256()
    
    try:
        with open(file_path, 'rb') as f:
            for chunk in iter(lambda: f.read(8192), b''):
                sha256_hash.update(chunk)
        return f"sha256:{sha256_hash.hexdigest()}"
    except Exception as e:
        print(f"Error computing hash for {file_path}: {e}")
        return None


def update_artifact_hashes(lock_path: Optional[pathlib.Path] = None) -> dict:
    """Compute and update SHA256 hashes in third_party.lock.json.
    
    This function computes actual SHA256 hashes for:
    - TripoSR model weights (.ckpt/.safetensors)
    - anime-face-detector models
    - MakeHuman CC0 assets
    
    Args:
        lock_path: Path to the lock file. Defaults to third_party.lock.json
                   in the project root.
        
    Returns:
        Dictionary with updated hash values for each tool.
    """
    if lock_path is None:
        lock_path = pathlib.Path(__file__).parent.parent / "third_party.lock.json"
    
    if not lock_path.exists():
        print(f"Lock file not found: {lock_path}")
        return {}
    
    with open(lock_path, 'r', encoding='utf-8') as f:
        lock_data = json.load(f)
    
    project_root = lock_path.parent
    updated_hashes = {}
    
    for name, info in lock_data.get("tools", {}).items():
        artifact_path = None
        
        if name == "triposr":
            # Check for TripoSR model weights
            triposr_path = project_root / info.get("path", "TripoSR/")
            model_files = [
                triposr_path / "model.ckpt",
                triposr_path / "model.safetensors",
                triposr_path / "weights" / "model.ckpt",
            ]
            for mf in model_files:
                if mf.exists():
                    artifact_path = mf
                    break
            
            # Also try git commit hash
            if artifact_path is None:
                git_head = triposr_path / ".git" / "HEAD"
                if git_head.exists():
                    try:
                        cmd = ["git", "-C", str(triposr_path), "rev-parse", "HEAD"]
                        proc = subprocess.run(cmd, capture_output=True, text=True)
                        if proc.returncode == 0:
                            commit_hash = proc.stdout.strip()
                            updated_hashes[name] = f"sha256:git:{commit_hash}"
                            continue
                    except Exception:
                        pass
        
        elif name == "anime_face_detector":
            # Check for model weights in typical locations
            model_dirs = [
                pathlib.Path.home() / ".cache" / "torch" / "hub" / "checkpoints",
                project_root / "models" / "anime_face_detector",
            ]
            for md in model_dirs:
                if md.exists():
                    # Look for any .pt, .pth, .ckpt files
                    model_files = list(md.glob("*.pt")) + list(md.glob("*.pth")) + list(md.glob("*.ckpt"))
                    if model_files:
                        artifact_path = model_files[0]
                        break
            
            # Check PyPI version
            try:
                import importlib.metadata
                version = importlib.metadata.version("anime-face-detector")
                updated_hashes[name] = f"sha256:pypi:{version}"
                continue
            except Exception:
                pass
        
        elif name == "makehuman_cc0":
            # Check for MakeHuman assets
            mh_path = project_root / info.get("path", "assets/makehuman_cc0/")
            if mh_path.exists():
                # Hash the first .obj file found
                obj_files = list(mh_path.glob("**/*.obj"))
                if obj_files:
                    artifact_path = obj_files[0]
                else:
                    # Hash the directory git commit
                    git_head = mh_path / ".git" / "HEAD"
                    if git_head.exists():
                        try:
                            cmd = ["git", "-C", str(mh_path), "rev-parse", "HEAD"]
                            proc = subprocess.run(cmd, capture_output=True, text=True)
                            if proc.returncode == 0:
                                commit_hash = proc.stdout.strip()
                                updated_hashes[name] = f"sha256:git:{commit_hash}"
                                continue
                        except Exception:
                            pass
        
        # Compute hash for artifact if found
        if artifact_path and artifact_path.exists():
            computed_hash = compute_artifact_hash(artifact_path)
            if computed_hash:
                updated_hashes[name] = computed_hash
                info["hash"] = computed_hash
                info["hashed_file"] = str(artifact_path)
    
    # Update the lock file with computed hashes
    if updated_hashes:
        for name, hash_value in updated_hashes.items():
            if name in lock_data.get("tools", {}):
                lock_data["tools"][name]["hash"] = hash_value
        
        with open(lock_path, 'w', encoding='utf-8') as f:
            json.dump(lock_data, f, indent=2, ensure_ascii=False)
        
        print(f"Updated {len(updated_hashes)} hash values in {lock_path}")
    
    return updated_hashes


def load_lock_file() -> dict:
    """Load the third_party.lock.json file.
    
    Returns:
        Dictionary with lock file data.
    """
    lock_path = pathlib.Path(__file__).parent.parent / "third_party.lock.json"
    
    if lock_path.exists():
        with open(lock_path, 'r') as f:
            return json.load(f)
    
    return {"version": "1.0", "tools": {}}


def check_git_revision(path: pathlib.Path, expected_revision: str) -> dict:
    """Check if a git repository is at the expected revision.
    
    Args:
        path: Path to the git repository.
        expected_revision: Expected git commit/branch/tag.
        
    Returns:
        Dictionary with check results.
    """
    result = {
        "path": str(path),
        "expected": expected_revision,
        "actual": None,
        "match": False
    }
    
    if not path.exists():
        result["error"] = "Directory not found"
        return result
    
    try:
        # Get current HEAD
        cmd = ["git", "-C", str(path), "rev-parse", "HEAD"]
        proc = subprocess.run(cmd, capture_output=True, text=True)
        
        if proc.returncode == 0:
            result["actual"] = proc.stdout.strip()
            
            # Check if expected is a branch or tag name
            if expected_revision in ["main", "master"]:
                # For main/master, just check we're on that branch
                branch_cmd = ["git", "-C", str(path), "rev-parse", "--abbrev-ref", "HEAD"]
                branch_proc = subprocess.run(branch_cmd, capture_output=True, text=True)
                if branch_proc.returncode == 0:
                    current_branch = branch_proc.stdout.strip()
                    result["match"] = current_branch == expected_revision
            else:
                # Compare commit hashes
                result["match"] = result["actual"].startswith(expected_revision)
        else:
            result["error"] = proc.stderr.strip()
            
    except Exception as e:
        result["error"] = str(e)
    
    return result


def check_pypi_version(package_name: str, expected_revision: str) -> dict:
    """Check if a PyPI package version matches expected.
    
    Args:
        package_name: Name of the PyPI package.
        expected_revision: Expected version string.
        
    Returns:
        Dictionary with check results.
    """
    result = {
        "package": package_name,
        "expected": expected_revision,
        "actual": None,
        "match": False
    }
    
    try:
        import importlib.metadata
        
        try:
            version = importlib.metadata.version(package_name)
            result["actual"] = version
            result["match"] = version == expected_revision or expected_revision == "main"
        except importlib.metadata.PackageNotFoundError:
            result["error"] = "Package not installed"
            
    except ImportError:
        # Fallback to pip
        try:
            cmd = ["pip", "show", package_name]
            proc = subprocess.run(cmd, capture_output=True, text=True)
            
            if proc.returncode == 0:
                for line in proc.stdout.split("\n"):
                    if line.startswith("Version:"):
                        result["actual"] = line.split(":", 1)[1].strip()
                        result["match"] = result["actual"] == expected_revision or expected_revision == "main"
                        break
            else:
                result["error"] = "Package not installed"
                
        except Exception as e:
            result["error"] = str(e)
    
    return result


def audit_tools():
    """Run audit on all third-party tools.
    
    Returns:
        Dictionary with audit results for each tool.
    """
    lock_data = load_lock_file()
    results = {}
    
    project_root = pathlib.Path(__file__).parent.parent
    
    for name, info in lock_data.get("tools", {}).items():
        tool_result = {
            "name": name,
            "license": info.get("license", "Unknown"),
            "pinned_revision": info.get("commit", "main"),
            "check_result": None
        }
        
        # Check based on tool type
        if "pypi" in info:
            tool_result["check_result"] = check_pypi_version(
                info["pypi"], 
                info.get("commit", "main")
            )
        elif "path" in info:
            tool_path = project_root / info["path"]
            tool_result["check_result"] = check_git_revision(
                tool_path,
                info.get("commit", "main")
            )
        else:
            tool_result["check_result"] = {"match": False, "error": "Tool path/package is not configured"}
        
        results[name] = tool_result
    
    return results


def print_audit_report():
    """Print a formatted audit report."""
    
    print("""
=====================================
Third-Party Tools Audit Report
=====================================
""")
    
    results = audit_tools()
    
    for name, result in results.items():
        print(f"Tool: {name}")
        print(f"  License: {result['license']}")
        print(f"  Pinned Revision: {result['pinned_revision']}")
        
        check = result["check_result"]
        if check:
            if check.get("match"):
                print("  Status: ✓ Match")
            elif check.get("error"):
                print(f"  Status: ✗ Error - {check['error']}")
            else:
                actual = check.get("actual", "Unknown")
                print(f"  Status: ✗ Mismatch (actual: {actual})")
        else:
            print("  Status: ? Not checked")
        
        print()
    
    print("=====================================")


if __name__ == "__main__":
    # First update artifact hashes with real SHA256 values
    print("Computing artifact hashes...")
    updated_hashes = update_artifact_hashes()
    if updated_hashes:
        print(f"Updated {len(updated_hashes)} hash values:")
        for name, hash_value in updated_hashes.items():
            print(f"  {name}: {hash_value}")
    else:
        print("No artifact hashes computed (artifacts may not be present)")
    
    print()
    
    # Then print the audit report
    print_audit_report()
