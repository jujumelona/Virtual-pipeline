"""Mode-scoped prefetch never silently downloads checkpoints for another mode."""
from unittest.mock import patch

from tools import prefetch_model_assets as assets


def test_common_2d_downloads_only_common_2d_models():
    seen=[]
    with patch.object(assets,"run_model_task",side_effect=lambda label,code,timeout: seen.append(label)):
        assets.prefetch_mode("common_2d")
    assert seen==list(assets.MODE_ASSETS["common_2d"])
    assert "triposr" not in seen
    assert "instantmesh_large" not in seen


def test_3d_prefetch_keeps_makehuman_and_nested_reconstruction_dependencies():
    seen=[]
    with patch.object(assets,"run_model_task",side_effect=lambda label,code,timeout: seen.append(label)):
        assets.prefetch_mode("3d")
    assert seen[:len(assets.MODE_ASSETS["3d"])]==list(assets.MODE_ASSETS["3d"])
    assert {"DINO","MakeHuman","u2net"} <= set(seen)
    assert "flux2_klein_4b" not in seen


def test_main_routes_mode_without_download_when_mocked():
    with patch.object(assets,"prefetch_mode") as scoped, patch.object(assets,"prefetch_assets") as legacy:
        assets.main(["--mode","common_2d"])
    scoped.assert_called_once_with("common_2d",timeout=2400)
    legacy.assert_not_called()
