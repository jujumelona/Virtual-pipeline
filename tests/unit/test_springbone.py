"""Unit tests for current VRMC_springBone configuration contracts."""

import json

from vtuber_pipeline.avatar.springbone import (
    SPRING_BONE_PRESETS,
    apply_springbone_preset,
    classify_springbone_chains,
    generate_springbone_config,
)


def _write_hair_gltf(path):
    from pygltflib import GLTF2, Node

    gltf = GLTF2()
    gltf.nodes = [
        Node(name="hairRoot", children=[1]),
        Node(name="hairMid", children=[2]),
        Node(name="hairTip"),
    ]
    gltf.save(str(path))


def test_presets_use_current_field_names():
    for name, preset in SPRING_BONE_PRESETS.items():
        assert "stiffness" in preset, name
        assert "stiffiness" not in preset, name
        for field in ("stiffness", "gravity", "drag", "hit_radius"):
            assert field in preset, (name, field)


def test_classify_uses_actual_secondary_node_names():
    chains = classify_springbone_chains(
        mesh_path="unused.glb",
        skeleton={"names": ["head", "hairRoot", "hairMid", "hairTip"]},
    )
    hair = next(chain for chain in chains if chain["name"] == "hair")
    assert [joint["node"] for joint in hair["joints"]] == [
        "hairRoot", "hairMid", "hairTip"
    ]
    assert "jointEdges" not in hair
    assert "stiffiness" not in json.dumps(hair)


def test_generate_config_from_real_gltf_nodes(tmp_path):
    mesh_path = tmp_path / "rig.gltf"
    _write_hair_gltf(mesh_path)

    result = generate_springbone_config(str(mesh_path), str(tmp_path))
    assert result["status"] == "complete"
    assert result["specVersion"] == "1.0"
    assert result["springs"]

    hair = next(s for s in result["springs"] if s["name"] == "hair")
    assert len(hair["joints"]) == 3
    for joint in hair["joints"]:
        assert "stiffness" in joint
        assert "gravityDir" in joint
        assert "dragForce" in joint
        assert "stiffiness" not in joint

    persisted = json.loads((tmp_path / "springbone.json").read_text())
    assert persisted["status"] == "complete"


def test_missing_secondary_nodes_is_not_fake_complete(tmp_path):
    from pygltflib import GLTF2, Node

    path = tmp_path / "rig.gltf"
    gltf = GLTF2()
    gltf.nodes = [Node(name="head")]
    gltf.save(str(path))

    result = generate_springbone_config(str(path), str(tmp_path))
    assert result["status"] == "partial"
    assert result["springs"] == []


def test_preset_override():
    preset = apply_springbone_preset("hair", {"stiffness": 0.8})
    assert preset["stiffness"] == 0.8
    assert preset["gravity"] == SPRING_BONE_PRESETS["hair"]["gravity"]


def test_unknown_class_uses_hair_default():
    preset = apply_springbone_preset("unknown_class")
    assert preset == SPRING_BONE_PRESETS["hair"]
