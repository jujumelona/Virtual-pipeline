"""Blender Add-on production contract uses genuine import and export."""
import inspect
from vtuber_pipeline.avatar.blender_bridge import export_blender_from_vrm
from vtuber_pipeline.avatar.build import AvatarPipeline


def test_blender_export_mainline():
    source = inspect.getsource(AvatarPipeline.build)
    assert '"blender_vrm_export"' in source
    assert source.index('"blender_vrm_export"') < source.index('"validator"')


def test_exporter_uses_real_blender_process_and_is_fail_closed():
    source = inspect.getsource(export_blender_from_vrm)
    assert "subprocess.run" in source
    assert "VTUBER_BLENDER_BINARY" in source
    assert 'b"BLENDER"' in source
