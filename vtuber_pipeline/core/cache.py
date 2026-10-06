"""Pipeline caching module for VTuber Pipeline."""

# Google Drive 캐시 지원: Google Drive가 마운트된 경우 cache_dir을 드라이브 경로로 설정하세요.

import hashlib
import json
import pathlib
from typing import Dict, Any


class PipelineCache:
    """Cache manager for pipeline state and intermediate results.
    
    This class provides functionality to save and load pipeline state
    for resumable processing. Future versions may support Google Drive
    as a cache backend for cloud-based caching.
    """
    
    def __init__(self, cache_dir: str):
        """Initialize the cache manager.
        
        Args:
            cache_dir: Directory to store cache files.
        """
        self.cache_dir = pathlib.Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
    
    def save_state(self, stage: str, data: Dict[str, Any]) -> None:
        """Save pipeline state for a specific stage.
        
        Args:
            stage: Name of the pipeline stage.
            data: State data to save.
        """
        json_path = self.cache_dir / f"{stage}.json"
        sha256_path = self.cache_dir / f"{stage}.sha256"
        
        # Save JSON
        serialized = json.dumps(data, ensure_ascii=False, indent=2)
        json_path.write_text(serialized, encoding='utf-8')
        
        # Compute and save SHA256 checksum
        checksum = hashlib.sha256(serialized.encode('utf-8')).hexdigest()
        sha256_path.write_text(checksum, encoding='utf-8')
    
    def load_state(self, stage: str) -> Dict[str, Any]:
        """Load pipeline state for a specific stage.
        
        Args:
            stage: Name of the pipeline stage.
            
        Returns:
            Dictionary containing the stage state.
            
        Raises:
            ValueError: If checksum verification fails.
        """
        json_path = self.cache_dir / f"{stage}.json"
        sha256_path = self.cache_dir / f"{stage}.sha256"
        
        # Load JSON
        serialized = json_path.read_text(encoding='utf-8')
        data = json.loads(serialized)
        
        # Verify checksum
        if sha256_path.exists():
            expected_checksum = sha256_path.read_text(encoding='utf-8').strip()
            actual_checksum = hashlib.sha256(serialized.encode('utf-8')).hexdigest()
            if expected_checksum != actual_checksum:
                raise ValueError(
                    f"Checksum mismatch for stage '{stage}': "
                    f"expected {expected_checksum}, got {actual_checksum}"
                )
        
        return data
    
    def compute_checksum(self, path: str) -> str:
        """Compute a SHA256 checksum for a file.
        
        Args:
            path: Path to the file.
            
        Returns:
            SHA256 checksum string for the file.
        """
        sha256_hash = hashlib.sha256()
        with open(path, 'rb') as f:
            for chunk in iter(lambda: f.read(8192), b''):
                sha256_hash.update(chunk)
        return sha256_hash.hexdigest()
