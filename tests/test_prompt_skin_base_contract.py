"""Generated VTuber base prompts must request a modest, opaque rigging cover."""
from vtuber_pipeline.prompt_contract import Identity, build_prompts


def _identity():
    return Identity(
        hair_color="#F0F0F0",
        hairstyle="long white hair, center bangs",
        eye_color="violet",
        face_description="soft neutral anime face",
        skin_color="#EBC9B8",
    )


def test_2d_generated_prompts_use_skin_not_an_underlayer():
    data = build_prompts("inochi2d", _identity())
    assert data["image_count"] == 21
    prompts = {item["filename"]: item["prompt"] for item in data["images"]}
    master = prompts["front_master.png"]
    assert "smooth scalp without attached hair" in master
    assert "uncovered scalp" in master
    assert "skin" in master.lower()
    assert "#EBC9B8" in master
    for name, prompt in prompts.items():
        assert "PROFESSIONAL FULLY COVERED ADULT ANIME VTUBER" in prompt, name
        assert "opaque" in prompt.lower(), name
        assert "neutral_underlayer:" not in prompt, name
        assert "integrated_default_outfit:" not in prompt, name
    assert "production cover" in prompts["body.png"].lower()


def test_3d_generated_prompts_stay_outfit_free_in_all_views():
    identity = _identity()
    data = build_prompts("3d", identity)
    assert data["image_count"] == 5
    assert "fully covered skin-tone basewear" in data["packaging"].lower()
    for item in data["images"]:
        prompt = item["prompt"]
        assert "#EBC9B8" in prompt
        assert "PROFESSIONAL FULLY COVERED ADULT ANIME VTUBER" in prompt
        assert "same hairstyle" in prompt.lower()
        assert "DEFAULT INTEGRATED COSTUME" not in prompt
        assert "wearing the SAME complete default costume" not in prompt
        assert "neutral_underlayer:" not in prompt


def test_legacy_outfit_field_cannot_leak_into_skin_base():
    identity = Identity(
        hair_color="#F0F0F0",
        hairstyle="long white hair",
        eye_color="violet",
        face_description="adult anime face",
        outfit="LEGACY_OUTFIT_SENTINEL",
        skin_color="#EBC9B8",
    )
    for mode in ("3d", "inochi2d", "live2d"):
        bundle = build_prompts(mode, identity)
        assert "LEGACY_OUTFIT_SENTINEL" not in str(bundle)

def test_all_generated_briefs_prohibit_exposed_torso_and_keep_wardrobe_separate():
    identity = _identity()
    for mode in ("3d", "inochi2d", "live2d"):
        spec = build_prompts(mode, identity)
        for part in spec["images"]:
            prompt = part["prompt"].lower()
            assert "fully covered" in prompt
            assert "opaque" in prompt
            assert "underwear" not in prompt
            assert "{skin_color}" not in prompt
            assert "fashion garments are independent future assets" in prompt
