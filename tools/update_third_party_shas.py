#!/usr/bin/env python3
"""
third_party.lock.json의 커밋 SHA를 실제 값으로 업데이트합니다.

git ls-remote를 사용하여 각 저장소의 현재 HEAD SHA를 가져옵니다.
"""

import subprocess
import json
import pathlib
import sys

REPOS = {
    "triposr": "https://github.com/VAST-AI-Research/TripoSR",
    "anime_face_detector": "https://github.com/hysts/anime-face-detector",
    "vrm_addon": "https://github.com/saturday06/VRM-Addon-for-Blender",
    "makehuman_cc0": "https://github.com/makehumancommunity/makehuman",
}


def get_commit_sha(repo_url: str) -> str:
    """git ls-remote로 저장소의 HEAD SHA를 가져옵니다."""
    try:
        result = subprocess.run(
            ["git", "ls-remote", repo_url, "HEAD"],
            capture_output=True,
            text=True,
            timeout=30
        )
        if result.returncode == 0 and result.stdout.strip():
            return result.stdout.split()[0]
    except (subprocess.TimeoutExpired, FileNotFoundError, Exception):
        pass
    return None


def update_lock_file(dry_run: bool = False):
    """third_party.lock.json을 실제 SHA로 업데이트합니다."""
    lock_path = pathlib.Path(__file__).parent.parent / "third_party.lock.json"
    
    with open(lock_path, encoding='utf-8') as f:
        lock_data = json.load(f)
    
    tools = lock_data.get("tools", {})
    updated = []
    failed = []
    
    for tool_key, repo_url in REPOS.items():
        if tool_key not in tools:
            print(f"Skipping {tool_key}: not in lock file")
            continue
        print(f"Fetching SHA for {tool_key} ({repo_url})...")
        sha = get_commit_sha(repo_url)
        if sha:
            tools[tool_key]["commit"] = sha
            print(f"  {tool_key}: {sha[:12]}...")
            updated.append(tool_key)
        else:
            print(f"  {tool_key}: failed to fetch SHA")
            failed.append(tool_key)
    
    if not dry_run:
        lock_data["tools"] = tools
        with open(lock_path, "w", encoding='utf-8') as f:
            json.dump(lock_data, f, indent=2, ensure_ascii=False)
        print(f"\nUpdated {len(updated)} SHA(s): {updated}")
    else:
        print(f"\n[DRY RUN] Would update {len(updated)} SHA(s): {updated}")
    
    if failed:
        print(f"Failed: {failed}")
        # Add note to lock file about failed updates
        if not dry_run and "notes" in lock_data:
            lock_data["notes"]["sha_update_failures"] = f"Could not fetch SHA for: {', '.join(failed)}"
            with open(lock_path, "w", encoding='utf-8') as f:
                json.dump(lock_data, f, indent=2, ensure_ascii=False)
    
    return {"updated": updated, "failed": failed}


def main():
    dry_run = "--dry-run" in sys.argv
    tool_filter = None
    for arg in sys.argv[1:]:
        if arg.startswith("--tool="):
            tool_filter = arg.split("=", 1)[1]
    
    if tool_filter:
        # Only update specific tool
        if tool_filter not in REPOS:
            print(f"Unknown tool: {tool_filter}. Available: {list(REPOS.keys())}")
            return
        REPOS_COPY = REPOS.copy()
        REPOS.clear()
        REPOS[tool_filter] = REPOS_COPY[tool_filter]
    
    update_lock_file(dry_run)


if __name__ == "__main__":
    main()
