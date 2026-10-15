"""Semantic inventory is a QA report, not a false automatic-split certificate."""
from tools.vts_part_separation_contract import (
    BODY_REQUIRED, audit_part_separation, classify_name,
)


def test_complete_bustup_body_label_set_counts_each_anatomical_role():
    names = [
        "face", "neck", "torso", "nose", "mouth.open",
    ]
    for side in ("left", "right"):
        names += [
            "eye." + side + ".white",
            "eye." + side + ".iris",
            "eye." + side + ".upper.lash",
            "eyebrow." + side,
            "arm." + side + ".upper",
            "arm." + side + ".forearm",
            "hand." + side,
        ]
    audit = audit_part_separation(names, asset="body", scope="upper")
    assert audit["named_role_requirements_met"], audit["missing_or_unproven_roles"]
    assert set(audit["observed_named_roles"]) >= set(BODY_REQUIRED)
    assert audit["geometry_or_underpaint_verified"] is False


def test_sam19_eyes_does_not_count_as_white_iris_and_lash():
    names = ["face", "neck", "torso", "nose", "mouth", "eyes",
             "eye.left", "eye.right", "handwear", "topwear"]
    audit = audit_part_separation(names, asset="body", scope="upper")
    assert not audit["named_role_requirements_met"]
    for role in ("eye_left_white", "eye_left_iris", "eye_left_upper_lash",
                 "eye_right_white", "eye_right_iris", "eye_right_upper_lash"):
        assert role in audit["missing_or_unproven_roles"]
    assert "eyes" in audit["ambiguous_whole_eye_layers"]


def test_character_side_labels_not_screen_side_invented():
    assert "eye_left_iris" in classify_name("eye.left.iris")
    assert not any(x.startswith("eye_left") for x in classify_name("eye.image_left"))


def test_full_scope_requires_leg_pieces_but_upper_does_not():
    names = ["face", "torso"]
    upper = audit_part_separation(names, asset="body", scope="upper")
    full = audit_part_separation(names, asset="body", scope="full")
    assert "thigh_left" not in upper["required_semantic_roles"]
    assert "thigh_left" in full["required_semantic_roles"]
    assert len(full["required_semantic_roles"]) > len(upper["required_semantic_roles"])


def test_modular_assets_are_scoped_to_their_own_parts():
    hair = audit_part_separation(["hair.front", "hair.back"], asset="hair", scope="upper")
    outfit = audit_part_separation(["outfit.front", "outfit.sleeve.left"],
                                   asset="outfit", scope="upper")
    assert hair["named_role_requirements_met"]
    assert outfit["named_role_requirements_met"]
    assert "eye_left_iris" not in hair["required_semantic_roles"]
