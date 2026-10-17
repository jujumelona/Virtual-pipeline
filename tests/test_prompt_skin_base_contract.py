"""Legacy external generator now emits face/neck only, never a BODY reference."""
from vtuber_pipeline.prompt_contract import Identity, build_prompts


def identity():
    return Identity(hair_color="#F0F0F0", hairstyle="long white hair",
                    eye_color="orange", face_description="adult round anime face",
                    skin_color="#EBC9B8")


def test_2d_face_only_brief_has_no_body_parts():
    for mode in ("live2d", "inochi2d"):
        data = build_prompts(mode, identity())
        prompts = {x["filename"]: x["prompt"] for x in data["images"]}
        assert data["image_count"] == 16
        assert "front_master.png" in prompts
        assert "face.png" in prompts and "neck.png" in prompts
        assert "body.png" not in prompts
        assert "arm_left.png" not in prompts and "hand_left.png" not in prompts
        assert "#EBC9B8" in prompts["front_master.png"]
        for prompt in prompts.values():
            assert "FACE ASSET ONLY" in prompt
            assert "No shoulders, arms, hands, torso" in prompt
            assert "OUTFIT" in prompt


def test_3d_references_are_head_only_not_native_vrm():
    data = build_prompts("3d", identity())
    assert data["image_count"] == 5
    assert "not a riggable VRM input" in data["packaging"]
    for view in data["images"]:
        assert "FACE ASSET ONLY" in view["prompt"]
        assert "#EBC9B8" in view["prompt"]


def test_legacy_outfit_field_cannot_become_body_prompt():
    value = Identity(hair_color="white", hairstyle="medium", eye_color="orange",
                     face_description="adult anime", outfit="LEGACY_OUTFIT_SENTINEL",
                     skin_color="#F2D4BE")
    for mode in ("live2d", "inochi2d", "3d"):
        bundle = build_prompts(mode, value)
        assert "LEGACY_OUTFIT_SENTINEL" not in str(bundle)
        assert "body.png" not in str(bundle)
