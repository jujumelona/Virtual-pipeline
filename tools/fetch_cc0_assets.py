#!/usr/bin/env python3
"""
MakeHuman CC0 에셋을 다운로드합니다.

MakeHuman 소스코드는 AGPL이지만, 번들된 에셋(메시, 타겟, 텍스처)은 CC0입니다.
이 스크립트는 CC0 에셋만 다운로드합니다.
"""

import requests
import pathlib
import sys

MAKEHUMAN_REPO = "https://raw.githubusercontent.com/makehumancommunity/makehuman/master"

CC0_ASSETS = [
    "makehuman/data/3dobjs/base.obj",
]


def fetch_cc0_assets(output_dir="assets/makehuman_cc0"):
    """MakeHuman CC0 에셋을 다운로드합니다."""
    output_path = pathlib.Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    
    downloaded = []
    failed = []
    
    for asset_path in CC0_ASSETS:
        url = f"{MAKEHUMAN_REPO}/{asset_path}"
        try:
            response = requests.get(url, timeout=30)
            if response.status_code == 200:
                local_path = output_path / pathlib.Path(asset_path).name
                local_path.write_bytes(response.content)
                print(f"Downloaded: {local_path}")
                downloaded.append(str(local_path))
            else:
                print(f"Failed ({response.status_code}): {url}")
                failed.append(url)
        except Exception as e:
            print(f"Error: {url}: {e}")
            failed.append(url)
    
    # LICENSE 파일 생성
    license_text = """# CC0 Assets from MakeHuman

These assets are from the MakeHuman project (https://github.com/makehumancommunity/makehuman).

According to the MakeHuman LICENSE:
- Source code: AGPL-3.0
- Bundled assets (meshes, targets, textures, clothes, poses): CC0 1.0

We only use the CC0 bundled assets, not the AGPL source code.
"""
    (output_path / "LICENSE").write_text(license_text)
    
    return {"downloaded": downloaded, "failed": failed}


def print_download_instructions():
    """수동 다운로드 안내를 출력합니다 (네트워크 없을 때 사용)."""
    print("""
=====================================
MakeHuman CC0 Asset Download Guide
=====================================

URL: https://github.com/makehumancommunity/makehuman
Asset: makehuman/data/3dobjs/base.obj (CC0 licensed)

Or run: python tools/fetch_cc0_assets.py --download
=====================================
""")


if __name__ == "__main__":
    if "--download" in sys.argv or len(sys.argv) == 1:
        result = fetch_cc0_assets()
        if result["downloaded"]:
            print(f"\nSuccessfully downloaded {len(result['downloaded'])} asset(s)")
        if result["failed"]:
            print(f"Failed: {len(result['failed'])} asset(s)")
            print("Run manually: python tools/fetch_cc0_assets.py")
    else:
        print_download_instructions()
