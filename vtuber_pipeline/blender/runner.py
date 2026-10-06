"""Blender headless subprocess runner for VTuber Pipeline.

This module provides the SubprocessRunner class for executing Blender
scripts in background mode with proper timeout and error handling.
"""

import subprocess
import shutil
import pathlib
from typing import Dict, Any, Optional


def get_blender_path() -> Optional[str]:
    """Get the path to Blender executable.
    
    Checks environment variable BLENDER_PATH first, then searches PATH.
    
    Returns:
        Path to Blender executable or None if not found.
    """
    import os
    
    # Check environment variable first
    env_path = os.environ.get("BLENDER_PATH")
    if env_path and pathlib.Path(env_path).exists():
        return env_path
    
    # Search in PATH
    blender = shutil.which("blender")
    if blender:
        return blender
    
    # Check common installation paths on Windows
    common_paths = [
        pathlib.Path("C:/Program Files/Blender Foundation"),
        pathlib.Path("C:/Program Files/Blender Foundation/Blender 4.2/blender.exe"),
        pathlib.Path("C:/Program Files/Blender Foundation/Blender 4.1/blender.exe"),
        pathlib.Path("C:/Program Files/Blender Foundation/Blender 4.0/blender.exe"),
        pathlib.Path("C:/Program Files/Blender Foundation/Blender 3.6/blender.exe"),
    ]
    
    for path in common_paths:
        if path.exists():
            if path.is_file():
                return str(path)
            # Search for blender.exe in subdirectories
            for exe in path.rglob("blender.exe"):
                return str(exe)
    
    return None


class SubprocessRunner:
    """Runs Blender scripts in headless mode.
    
    Executes Blender with the --background flag and a Python script,
    capturing stdout/stderr and handling timeouts.
    
    Attributes:
        blender_path: Path to Blender executable.
        timeout: Default timeout in seconds.
    """
    
    def __init__(self, blender_path: Optional[str] = None, timeout: int = 300):
        """Initialize the Blender runner.
        
        Args:
            blender_path: Path to Blender executable. If None, auto-detects.
            timeout: Default timeout in seconds for operations.
        """
        self.blender_path = blender_path or get_blender_path()
        self.timeout = timeout
    
    def is_available(self) -> bool:
        """Check if Blender is available.
        
        Returns:
            True if Blender executable exists.
        """
        if self.blender_path is None:
            return False
        return pathlib.Path(self.blender_path).exists()
    
    def run(
        self,
        script_path: str,
        manifest_path: str,
        timeout: Optional[int] = None
    ) -> Dict[str, Any]:
        """Run a Blender script in headless mode.
        
        Executes: blender --background --python <script_path> -- --manifest <manifest_path>
        
        Args:
            script_path: Path to the Python script to run in Blender.
            manifest_path: Path to the manifest JSON file.
            timeout: Timeout in seconds. Uses default if None.
            
        Returns:
            Dictionary with keys: returncode, stdout, stderr, duration
            
        Raises:
            FileNotFoundError: If Blender executable not found.
            subprocess.TimeoutExpired: If the process times out.
            RuntimeError: If Blender returns non-zero exit code.
        """
        if not self.is_available():
            raise FileNotFoundError(
                "Blender executable not found. Install Blender or set BLENDER_PATH environment variable."
            )
        
        import time
        
        actual_timeout = timeout if timeout is not None else self.timeout
        
        cmd = [
            self.blender_path,
            "--background",
            "--python", script_path,
            "--",
            "--manifest", manifest_path
        ]
        
        start_time = time.time()
        
        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=actual_timeout,
                encoding='utf-8',
                errors='replace'
            )
        except subprocess.TimeoutExpired as e:
            raise subprocess.TimeoutExpired(
                cmd, actual_timeout, 
                stdout=e.stdout.decode('utf-8', errors='replace') if e.stdout else "",
                stderr=e.stderr.decode('utf-8', errors='replace') if e.stderr else ""
            )
        
        duration = time.time() - start_time
        
        output = {
            "returncode": result.returncode,
            "stdout": result.stdout,
            "stderr": result.stderr,
            "duration": duration,
            "command": " ".join(cmd)
        }
        
        if result.returncode != 0:
            raise RuntimeError(
                f"Blender exited with code {result.returncode}.\n"
                f"stdout: {result.stdout}\n"
                f"stderr: {result.stderr}"
            )
        
        return output
