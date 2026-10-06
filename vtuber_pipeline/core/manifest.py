"""Pipeline manifest for cache-hit checking and stage tracking.

This module provides the PipelineManifest class for tracking the state
of pipeline stages and determining when stages can be skipped due to
cached results.
"""

import hashlib
import json
import pathlib
from typing import Dict, Any, Optional


class PipelineManifest:
    """Manages pipeline manifest for cache-hit checking and stage tracking.
    
    The manifest stores the state of each pipeline stage, including input
    hashes, configuration, and output paths. This enables resumable
    processing and cache optimization.
    
    Attributes:
        output_dir: Directory for manifest and outputs.
        manifest_path: Path to the manifest.json file.
    """
    
    def __init__(self, output_dir: str):
        """Initialize the manifest manager.
        
        Args:
            output_dir: Directory to store manifest and outputs.
        """
        self.output_dir = pathlib.Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.manifest_path = self.output_dir / "manifest.json"
        self._manifest: Dict[str, Any] = self.load()
    
    def load(self) -> Dict[str, Any]:
        """Load existing manifest or return empty dict.
        
        Returns:
            Dictionary containing manifest data.
        """
        if self.manifest_path.exists():
            with open(self.manifest_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        return {"version": "1.0", "stages": {}}
    
    def save(self, manifest: Optional[Dict[str, Any]] = None) -> None:
        """Save manifest to JSON with indent=2.
        
        Args:
            manifest: Manifest dict to save. If None, saves internal state.
        """
        data = manifest if manifest is not None else self._manifest
        with open(self.manifest_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    
    def compute_stage_key(
        self,
        stage_name: str,
        input_hashes: Dict[str, str],
        config: Dict[str, Any],
        code_revision: str,
        tool_revision: str
    ) -> str:
        """Compute a unique SHA256 key for a stage execution.
        
        The key is computed from all inputs that affect the stage output:
        stage name, input hashes, configuration, code revision, and tool revision.
        
        Args:
            stage_name: Name of the pipeline stage.
            input_hashes: Dictionary mapping input names to their SHA256 hashes.
            config: Stage-specific configuration dictionary.
            code_revision: Git revision or version of the pipeline code.
            tool_revision: Version/revision of the third-party tool.
            
        Returns:
            SHA256 hash string uniquely identifying this stage execution.
        """
        # Sort all inputs for deterministic hashing
        hash_input = json.dumps({
            "stage_name": stage_name,
            "input_hashes": dict(sorted(input_hashes.items())),
            "config": dict(sorted(config.items())) if config else {},
            "code_revision": code_revision,
            "tool_revision": tool_revision
        }, sort_keys=True, ensure_ascii=False)
        
        return hashlib.sha256(hash_input.encode('utf-8')).hexdigest()
    
    def is_complete(self, stage_key: str) -> bool:
        """Check if a stage has completed successfully and outputs exist.
        
        Args:
            stage_key: Unique key for the stage execution.
            
        Returns:
            True if the stage is complete and all outputs exist.
        """
        if stage_key not in self._manifest.get("stages", {}):
            return False
        
        stage_data = self._manifest["stages"][stage_key]
        
        # Check status
        if stage_data.get("status") != "complete":
            return False
        
        # Check output files exist
        output_path = stage_data.get("output_path")
        if output_path:
            if not pathlib.Path(output_path).exists():
                return False
        
        return True
    
    def record_stage(
        self,
        stage_key: str,
        contract: Dict[str, Any],
        input_hashes: Optional[Dict[str, str]] = None,
        config: Optional[Dict[str, Any]] = None
    ) -> None:
        """Record a stage execution in the manifest.
        
        Args:
            stage_key: Unique key for the stage execution.
            contract: Contract dict with stage results.
            input_hashes: Optional input hashes for the stage.
            config: Optional configuration for the stage.
        """
        stage_data = {
            "status": contract.get("status", "pending"),
            "stage_name": contract.get("stage_name", "unknown"),
            "output_path": contract.get("output_path", ""),
            "timestamp": self._get_timestamp()
        }
        
        if input_hashes:
            stage_data["input_hashes"] = input_hashes
        if config:
            stage_data["config"] = config
        
        self._manifest["stages"][stage_key] = stage_data
        self.save()
    
    def _get_timestamp(self) -> str:
        """Get current ISO-format timestamp."""
        from datetime import datetime
        return datetime.utcnow().isoformat() + "Z"
    
    def get_stage(self, stage_key: str) -> Optional[Dict[str, Any]]:
        """Get stage data by key.
        
        Args:
            stage_key: Unique key for the stage execution.
            
        Returns:
            Stage data dict or None if not found.
        """
        return self._manifest.get("stages", {}).get(stage_key)
    
    def clear_stage(self, stage_key: str) -> None:
        """Remove a stage from the manifest.
        
        Args:
            stage_key: Unique key for the stage execution.
        """
        if stage_key in self._manifest.get("stages", {}):
            del self._manifest["stages"][stage_key]
            self.save()
