"""Configuration and license management for VTuber Pipeline."""

from typing import Dict


BLOCKED_PACKAGES: Dict[str, str] = {
    'instantmesh': 'runtime path uses nvdiffrast',
    'nvdiffrast': 'public license restricts non-NVIDIA use',
    'stable-fast-3d': 'community license has commercial conditions',
}


def check_commercial_profile(package_name: str) -> None:
    """Raise ValueError if package_name is blocked under the commercial profile.
    
    Args:
        package_name: Name of the package to check.
        
    Raises:
        ValueError: If the package is blocked for commercial use.
    """
    if package_name in BLOCKED_PACKAGES:
        raise ValueError(f"{package_name} is blocked: {BLOCKED_PACKAGES[package_name]}")
