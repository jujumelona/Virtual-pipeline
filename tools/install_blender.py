"""Script to detect and install Blender for VTuber Pipeline.

This script detects if Blender is installed and provides installation
instructions if it's not found.
"""

import shutil
import pathlib
import platform


def find_blender() -> pathlib.Path:
    """Try to find Blender installation.
    
    Returns:
        Path to Blender executable, or None if not found.
    """
    # Check PATH
    blender = shutil.which("blender")
    if blender:
        return pathlib.Path(blender)
    
    # Check common installation paths
    system = platform.system()
    
    if system == "Windows":
        common_paths = [
            pathlib.Path("C:/Program Files/Blender Foundation"),
            pathlib.Path("C:/Program Files (x86)/Blender Foundation"),
        ]
        
        for base_path in common_paths:
            if base_path.exists():
                # Find the latest Blender version
                blender_dirs = sorted(base_path.glob("Blender *"), reverse=True)
                for blender_dir in blender_dirs:
                    blender_exe = blender_dir / "blender.exe"
                    if blender_exe.exists():
                        return blender_exe
    
    elif system == "Darwin":  # macOS
        app_path = pathlib.Path("/Applications/Blender.app/Contents/MacOS/Blender")
        if app_path.exists():
            return app_path
    
    elif system == "Linux":
        common_paths = [
            pathlib.Path("/usr/bin/blender"),
            pathlib.Path("/usr/local/bin/blender"),
            pathlib.Path.home() / ".local/bin/blender",
        ]
        
        for path in common_paths:
            if path.exists():
                return path
    
    return None


def print_install_instructions():
    """Print Blender installation instructions."""
    
    system = platform.system()
    
    print("""
=====================================
Blender Installation Guide
=====================================
""")
    
    blender_path = find_blender()
    
    if blender_path:
        print(f"Blender found at: {blender_path}")
        print("\nTo use this Blender installation, set the environment variable:")
        print(f'  Windows: set BLENDER_PATH={blender_path}')
        print(f'  Linux/macOS: export BLENDER_PATH="{blender_path}"')
    else:
        print("Blender not found. Please install it:\n")
        
        if system == "Windows":
            print("Windows Installation:")
            print("  1. Download from: https://www.blender.org/download/")
            print("  2. Run the installer")
            print("  3. Add to PATH or set BLENDER_PATH environment variable")
        
        elif system == "Darwin":
            print("macOS Installation:")
            print("  1. Download from: https://www.blender.org/download/")
            print("  2. Drag to Applications folder")
            print("  3. Set BLENDER_PATH environment variable")
            print("\n  Alternatively, use Homebrew:")
            print("    brew install --cask blender")
        
        elif system == "Linux":
            print("Linux Installation:")
            print("  Ubuntu/Debian: sudo apt install blender")
            print("  Fedora: sudo dnf install blender")
            print("  Arch: sudo pacman -S blender")
            print("\n  Or download from: https://www.blender.org/download/")
    
    print("\nRequired Blender Version: 3.6+")
    print("Recommended Version: 4.0+")
    print("\n=====================================")


if __name__ == "__main__":
    print_install_instructions()
