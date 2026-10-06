"""Script to detect and install VRM Add-on for Blender.

This script detects if the VRM Add-on is installed in Blender and
provides installation instructions if it's not found.
"""

import pathlib
import platform


def find_blender_addons_dir() -> pathlib.Path:
    """Find the Blender addons directory.
    
    Returns:
        Path to Blender addons directory, or None if not found.
    """
    system = platform.system()
    
    if system == "Windows":
        # Windows: %APPDATA%\\Blender Foundation\\Blender\\{version}\\scripts\\addons
        appdata = pathlib.Path.home() / "AppData" / "Roaming"
        blender_base = appdata / "Blender Foundation"
        if blender_base.exists():
            # Find the latest Blender version
            version_dirs = sorted(blender_base.glob("Blender/*"), reverse=True)
            for version_dir in version_dirs:
                addons_dir = version_dir / "scripts" / "addons"
                if addons_dir.exists():
                    return addons_dir
    
    elif system == "Darwin":  # macOS
        # macOS: ~/Library/Application Support/Blender/{version}/scripts/addons
        support = pathlib.Path.home() / "Library" / "Application Support" / "Blender"
        if support.exists():
            version_dirs = sorted(support.glob("*"), reverse=True)
            for version_dir in version_dirs:
                addons_dir = version_dir / "scripts" / "addons"
                if addons_dir.exists():
                    return addons_dir
    
    elif system == "Linux":
        # Linux: ~/.config/blender/{version}/scripts/addons
        config = pathlib.Path.home() / ".config" / "blender"
        if config.exists():
            version_dirs = sorted(config.glob("*"), reverse=True)
            for version_dir in version_dirs:
                addons_dir = version_dir / "scripts" / "addons"
                if addons_dir.exists():
                    return addons_dir
    
    return None


def check_vrm_addon() -> bool:
    """Check if VRM Add-on is installed.
    
    Returns:
        True if VRM Add-on is found.
    """
    addons_dir = find_blender_addons_dir()
    
    if addons_dir and addons_dir.exists():
        # Look for VRM addon directory
        vrm_addon = addons_dir / "io_scene_vrm"
        return vrm_addon.exists()
    
    return False


def print_install_instructions():
    """Print VRM Add-on installation instructions."""
    
    print("""
=====================================
VRM Add-on for Blender Installation
=====================================
""")
    
    addons_dir = find_blender_addons_dir()
    
    if check_vrm_addon():
        print("VRM Add-on is installed.")
        if addons_dir:
            print(f"Location: {addons_dir / 'io_scene_vrm'}")
    else:
        print("VRM Add-on not found.\n")
        
        print("Installation Steps:")
        print("  1. Download from: https://github.com/saturday06/VRM-Addon-for-Blender")
        print("  2. Extract the ZIP file")
        print("  3. In Blender, go to Edit > Preferences > Add-ons")
        print("  4. Click 'Install...' and select the extracted ZIP")
        print("  5. Enable the add-on by checking the box")
        
        if addons_dir:
            print(f"\n  Expected installation directory: {addons_dir}")
        else:
            print("\n  Blender addons directory not found. Please install Blender first.")
        
        print("\n  Alternative: Manual installation")
        print("  Copy the 'io_scene_vrm' folder to your Blender addons directory")
    
    print("""
Required VRM Add-on Version: 2.x (for VRM 1.0 support)
License: MIT

VRM Add-on GitHub: https://github.com/saturday06/VRM-Addon-for-Blender
VRM Specification: https://github.com/vrm-c/vrm-specification

=====================================""")


if __name__ == "__main__":
    print_install_instructions()
