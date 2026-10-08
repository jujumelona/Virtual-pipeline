from pathlib import Path
import pytest

from vtuber_pipeline.avatar.commercial_dependency_guard import (
    RUNTIME_SOURCES, require_commercial_compatible_upstream
)


def _sample_source(tmp_path, content="import torch"):
    for name in RUNTIME_SOURCES:
        file = tmp_path / name
        file.parent.mkdir(parents=True, exist_ok=True)
        file.write_text(content)
    return tmp_path


def test_nvidia_renderer_detected_even_without_zero123(tmp_path):
    source = _sample_source(tmp_path)
    (source / "src/models/lrm_mesh.py").write_text("import nvdiffrast.torch as dr")
    with pytest.raises(RuntimeError, match="license-cleared"):
        require_commercial_compatible_upstream(source)


def test_nested_proprietary_license_overrides_root_apache_claim(tmp_path):
    source = _sample_source(tmp_path)
    (source / "src/models/renderer/utils/renderer.py").write_text(
        "SPDX-License-Identifier: LicenseRef-NvidiaProprietary"
    )
    with pytest.raises(RuntimeError, match="renderer.py"):
        require_commercial_compatible_upstream(source)


def test_missing_source_cannot_prove_license_compatibility(tmp_path):
    source = _sample_source(tmp_path)
    (source / RUNTIME_SOURCES[0]).unlink()
    with pytest.raises(RuntimeError, match="missing source evidence"):
        require_commercial_compatible_upstream(source)


def test_safe_dummy_source_passes_only_source_pattern_check(tmp_path):
    source = _sample_source(tmp_path)
    result = require_commercial_compatible_upstream(source)
    assert result["restricted_sources_found"] is False
    assert result["source_license_gate"] == "review-required"
