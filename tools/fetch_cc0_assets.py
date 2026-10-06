"""Script to fetch CC0 assets from MakeHuman.

This script prints manual download instructions for MakeHuman CC0 assets
since automated downloads require user interaction with the MakeHuman
community website.
"""

import pathlib


def print_download_instructions():
    """Print instructions for manually downloading CC0 assets."""
    
    print("""
=====================================
MakeHuman CC0 Asset Download Guide
=====================================

This pipeline uses MakeHuman CC0 assets as the canonical VTuber template.
Due to license requirements, these assets must be downloaded manually.

REQUIRED ASSETS
---------------

1. MakeHuman Community Assets
   URL: http://www.makehumancommunity.org/
   
   Navigate to the Downloads section and download:
   - Base mesh (MHX2 or native format)
   - Human body targets
   - Clothing proxies (optional)
   
2. Asset Directories
--------------------
   
   Create the following directory structure:
   
   assets/makehuman_cc0/
   ├── base_mesh.blend      # Base human mesh
   ├── targets/             # Morph targets
   └── clothes/             # Optional clothing proxies

3. License Information
----------------------
   
   All MakeHuman assets are CC0 (Creative Commons Zero):
   - No attribution required (but appreciated)
   - Free for commercial use
   - Can be modified and redistributed
   
   License URL: https://creativecommons.org/publicdomain/zero/1.0/

4. Alternative: Custom Template
-------------------------------
   
   If you prefer to use your own template mesh:
   
   1. Create a human mesh with VRM-compatible topology
   2. Ensure 22+ humanoid bones are present
   3. Create shape keys for required expressions
   4. Place in assets/canonical_vtuber/template.glb

5. Verification
---------------
   
   After placing assets, verify with:
   
   python -c "from pathlib import Path; print(Path('assets/makehuman_cc0').exists())"

=====================================
""")


if __name__ == "__main__":
    print_download_instructions()
