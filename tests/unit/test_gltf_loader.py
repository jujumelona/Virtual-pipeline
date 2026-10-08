"""Tests for suffix-independent glTF/GLB/VRM loading."""

import pathlib


def test_load_gltf_detects_binary_vrm_by_magic(tmp_path):
    import trimesh

    from vtuber_pipeline.core.gltf import load_gltf

    glb = tmp_path / "mesh.glb"
    vrm = tmp_path / "mesh.vrm"
    trimesh.creation.box().export(glb)
    glb.replace(vrm)

    loaded = load_gltf(vrm)
    assert loaded.binary_blob() is not None
    assert loaded.meshes
    assert loaded.nodes


def test_load_gltf_keeps_json_gltf_path(tmp_path):
    from pygltflib import Asset, GLTF2

    from vtuber_pipeline.core.gltf import load_gltf

    path = tmp_path / "plain.gltf"
    GLTF2(asset=Asset(version="2.0")).save(str(path))

    loaded = load_gltf(path)
    assert loaded.asset.version == "2.0"
    assert loaded.binary_blob() is None
