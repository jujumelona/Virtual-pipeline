"""Unit tests for current VRMC_springBone configuration contracts."""

import json
import pytest


@pytest.mark.parametrize('field,value', [
    ('hitRadius', -0.1), ('stiffness', -1), ('gravityPower', float('nan')),
    ('dragForce', 1.1), ('dragForce', float('inf')),
    ('gravityDir', [0, float('nan'), 0]),
])
def test_builder_rejects_invalid_spring_values_instead_of_silent_clamping(field, value):
    from types import SimpleNamespace
    from vtuber_pipeline.avatar.vrm_builder import create_springbone_extension
    gltf = SimpleNamespace(nodes=[SimpleNamespace(name='hairRoot')])
    with pytest.raises(ValueError, match=field):
        create_springbone_extension(gltf, springs=[{'joints': [{'node': 0, field: value}]}])


def test_builder_uses_official_schema_defaults_when_settings_are_absent():
    from types import SimpleNamespace
    from vtuber_pipeline.avatar.vrm_builder import create_springbone_extension
    gltf = SimpleNamespace(nodes=[SimpleNamespace(name='hairRoot')])
    spring = create_springbone_extension(gltf, springs=[{'joints': [{'node': 0}]}])
    joint = spring['springs'][0]['joints'][0]
    assert joint == dict(node=0, hitRadius=0, stiffness=1, gravityPower=0,
                         gravityDir=[0, -1, 0], dragForce=.5)


def test_builder_preserves_valid_explicit_values_without_normalizing_gravity():
    from types import SimpleNamespace
    from vtuber_pipeline.avatar.vrm_builder import create_springbone_extension
    gltf = SimpleNamespace(nodes=[SimpleNamespace(name='hairRoot')])
    values = dict(node=0, hitRadius=.02, stiffness=2, gravityPower=.1,
                  gravityDir=[0, -2, 0], dragForce=.2)
    result = create_springbone_extension(gltf, springs=[{'joints': [values]}])
    assert result['springs'][0]['joints'][0] == values


@pytest.mark.parametrize('field,value', [('stiffness', float('nan')),
                                        ('hitRadius', float('inf')),
                                        ('gravityDir', [0, float('nan'), 0])])
def test_reimport_validator_rejects_nonfinite_spring_values(field, value):
    from pygltflib import GLTF2, Node
    from vtuber_pipeline.avatar.validator import VRMValidator
    validator = object.__new__(VRMValidator)
    validator.product_contract = False
    validator._gltf = GLTF2(nodes=[Node(name='hairRoot')], extensions={
        'VRMC_springBone': {'specVersion': '1.0', 'springs': [
            {'joints': [{'node': 0, field: value}]}]}})
    assert validator.validate_springbone()['valid'] is False

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


def test_missing_secondary_nodes_is_error(tmp_path):
    from pygltflib import GLTF2, Node

    path = tmp_path / "rig.gltf"
    gltf = GLTF2()
    gltf.nodes = [Node(name="head")]
    gltf.save(str(path))

    result = generate_springbone_config(str(path), str(tmp_path))
    assert result["status"] == "error"
    assert result["springs"] == []
    assert "secondary-bone" in result["error"]


def test_preset_override():
    preset = apply_springbone_preset("hair", {"stiffness": 0.8})
    assert preset["stiffness"] == 0.8
    assert preset["gravity"] == SPRING_BONE_PRESETS["hair"]["gravity"]


def test_unknown_class_uses_hair_default():
    preset = apply_springbone_preset("unknown_class")
    assert preset == SPRING_BONE_PRESETS["hair"]
