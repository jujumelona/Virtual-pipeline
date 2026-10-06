"""Third-party tool lock management for VTuber Pipeline.

This module provides the ThirdPartyLock class for managing pinned versions
and licenses of third-party tools used in the pipeline.
"""

import json
import pathlib
from typing import Dict, Any, Optional, List


class ThirdPartyLock:
    """Manages third-party tool versions and license information.
    
    Reads the third_party.lock.json file and provides methods to query
    tool information, verify pinned revisions, and check licenses.
    
    Attributes:
        lock_file: Path to the lock file.
        lock_data: Parsed lock file data.
    """
    
    _instance: Optional['ThirdPartyLock'] = None
    
    def __init__(self, lock_file: str = "third_party.lock.json"):
        """Initialize the tool lock manager.
        
        Args:
            lock_file: Path to the third_party.lock.json file.
                       Can be relative to project root or absolute.
        """
        self.lock_file = pathlib.Path(lock_file)
        if not self.lock_file.is_absolute():
            # Resolve relative to project root (where pyproject.toml is)
            project_root = pathlib.Path(__file__).parent.parent.parent
            self.lock_file = project_root / lock_file
        
        self.lock_data: Dict[str, Any] = self._load_lock_file()
    
    def _load_lock_file(self) -> Dict[str, Any]:
        """Load and parse the lock file.
        
        Returns:
            Parsed lock file data, or empty dict if file not found.
        """
        if self.lock_file.exists():
            with open(self.lock_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        return {"version": "1.0", "tools": {}}
    
    def get_tool_info(self, tool_name: str) -> Optional[Dict[str, Any]]:
        """Get information about a specific tool.
        
        Args:
            tool_name: Name of the tool (e.g., "TripoSR").
            
        Returns:
            Dictionary with tool info (commit, license, path, etc.)
            or None if tool not found.
        """
        tools = self.lock_data.get("tools", {})
        return tools.get(tool_name)
    
    def get_tool_path(self, name: str) -> pathlib.Path:
        """Get the installed path for a tool.
        
        Args:
            name: Name of the tool.
            
        Returns:
            Path to the tool directory.
            
        Raises:
            KeyError: If tool not found in lock file.
        """
        tool_info = self.get_tool_info(name)
        if tool_info is None:
            raise KeyError(f"Tool '{name}' not found in lock file")
        
        path = tool_info.get("path", "")
        if not path:
            raise KeyError(f"No path defined for tool '{name}'")
        
        # Resolve relative to lock file directory
        if not pathlib.Path(path).is_absolute():
            return self.lock_file.parent / path
        return pathlib.Path(path)
    
    def verify_revision(self, name: str, expected: str) -> bool:
        """Verify that a tool is at the expected revision.
        
        Args:
            name: Name of the tool.
            expected: Expected revision/commit string.
            
        Returns:
            True if the tool is at the expected revision.
            False if tool not found or revision mismatch.
        """
        tool_info = self.get_tool_info(name)
        if tool_info is None:
            return False
        
        actual = tool_info.get("commit", "")
        return actual == expected
    
    def check_licenses(self) -> List[Dict[str, str]]:
        """Check for tools with non-commercial or restrictive licenses.
        
        Returns:
            List of dicts with tool name and license info for tools
            that have non-commercial licenses.
        """
        non_commercial = []
        tools = self.lock_data.get("tools", {})
        
        restrictive_licenses = ["CC-BY-NC", "CC-BY-NC-SA", "non-commercial"]
        
        for name, info in tools.items():
            license_type = info.get("license", "")
            # Check for non-commercial indicators
            if any(nc in license_type.upper() for nc in ["NC", "NON-COMMERCIAL"]):
                non_commercial.append({
                    "name": name,
                    "license": license_type,
                    "license_url": info.get("license_url", "")
                })
        
        return non_commercial
    
    def list_tools(self) -> List[str]:
        """List all tools tracked in the lock file.
        
        Returns:
            List of tool names.
        """
        return list(self.lock_data.get("tools", {}).keys())


def get_toolchain() -> ThirdPartyLock:
    """Get the singleton ThirdPartyLock instance.
    
    Returns:
        The global ThirdPartyLock instance.
    """
    if ThirdPartyLock._instance is None:
        ThirdPartyLock._instance = ThirdPartyLock()
    return ThirdPartyLock._instance
