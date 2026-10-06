"""Script to audit third-party tool versions.

This script reads the third_party.lock.json and checks each tool's
actual version against the pinned version.
"""

import json
import pathlib
import subprocess


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
            tool_result["check_result"] = {"status": "stub", "warning": "Tool path not configured"}
        
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
    print_audit_report()
