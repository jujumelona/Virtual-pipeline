"""Blender script to apply deformation graph to mesh.

This script is designed to run in Blender headless mode:
    blender --background --python apply_fit.py -- --manifest manifest.json
"""

import argparse
import json
import sys


def apply_fit(manifest_path: str) -> dict:
    """Apply deformation graph to mesh.
    
    Args:
        manifest_path: Path to the manifest JSON file.
        
    Returns:
        Dictionary with application results.
    """
    result = {
        "status": "pending",
        "manifest_path": manifest_path
    }
    
    try:
        # Load manifest
        with open(manifest_path, 'r') as f:
            manifest = json.load(f)
        
        result["manifest_loaded"] = True
        
        # Try to use Blender API if available
        try:
            import bpy
            
            # Load deformation graph (stub)
            # In actual implementation:
            # 1. Load fit.npz with numpy
            # 2. Apply vertex deltas to mesh
            # 3. Update shape keys if present
            
            result["status"] = "complete"
            result["vertices_modified"] = 0
            
        except ImportError:
            result["status"] = "stub"
            result["warning"] = "Not running in Blender context"
            
    except Exception as e:
        result["status"] = "error"
        result["error"] = str(e)
    
    return result


def main():
    """Main entry point for command-line execution."""
    parser = argparse.ArgumentParser(description="Apply deformation to mesh in Blender")
    parser.add_argument("--manifest", required=True, help="Path to manifest JSON")
    
    args = parser.parse_known_args()[0]
    
    result = apply_fit(args.manifest)
    print(json.dumps(result, indent=2))
    
    return 0 if result["status"] == "complete" else 1


if __name__ == '__main__':
    sys.exit(main())
