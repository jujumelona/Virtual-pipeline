"""A layered drawing is not a native rigged INP2 model."""
from pathlib import Path
from unittest.mock import patch

from vtuber_pipeline.common.schemas import SourceSet
from vtuber_pipeline.two_d.build import build_inochi2d


def test_native_sdk_missing_preserves_editable_artwork_as_prepared(tmp_path):
    source=tmp_path/"source.png"
    source.write_bytes(b"source bytes for mocked artwork stage")
    psd=tmp_path/"avatar.psd"
    psd.write_bytes(b"8BPS\x00\x01")
    ora=tmp_path/"avatar.ora"
    ora.write_bytes(b"PK\x03\x04")
    spec=tmp_path/"puppet_spec.json"
    spec.write_text('{"parts":[]}',encoding="utf-8")
    prepared={"puppet_spec":str(spec),"layers":{"psd":str(psd),"ora":str(ora)}}
    args=SourceSet("inochi2d",str(source),output_dir=str(tmp_path))
    with patch("vtuber_pipeline.two_d.build.prepare_common_2d",return_value=prepared):
        with patch("vtuber_pipeline.two_d.inochi_bridge.export_inp",
                   side_effect=RuntimeError("native SDK bindings unavailable")):
            result=build_inochi2d(args)
    assert result.status=="prepared"
    assert result.primary_file==str(psd)
    assert result.editable_file==str(ora)
    assert "native SDK bindings unavailable" in result.error
    assert not (tmp_path/"avatar.inp").exists()


def test_missing_artwork_is_failed_not_prepared(tmp_path):
    args=SourceSet("inochi2d",str(tmp_path/"missing.png"),output_dir=str(tmp_path))
    with patch("vtuber_pipeline.two_d.build.prepare_common_2d",
               side_effect=RuntimeError("detector failed")):
        result=build_inochi2d(args)
    assert result.status=="failed"
    assert result.primary_file is None
    assert "detector failed" in result.error
