"""GPU-free contracts for VTube Studio Cubism FREE/PRO artwork generation."""
import json
import zipfile

import pytest
from click.testing import CliRunner

from vtuber_pipeline.cli import cli
from vtuber_pipeline.prompt_contract import Identity
from vtuber_pipeline.vts_modes import (
    FREE_BUDGET,
    STABLE_LAYERS,
    build_vts_brief,
    write_vts_brief_package,
)


@pytest.fixture
def identity():
    return Identity(
        hair_color="#FFFFFF",
        hairstyle="White medium-length layered hair with ahoge",
        eye_color="Violet eyes",
        face_description="Androgynous anime adult with gentle face",
        outfit="Black and lavender layered high-neck outfit, modest opaque base",
        gender="androgynous adult",
        accessories="metal hair clip, small pendant",
        palette="#FFFFFF #A78BFA #20202A",
        skin_color="#EAC4B0",
    )


@pytest.mark.parametrize("scope", ["upper", "full"])
def test_free_always_one_finished_character_no_unclothed_base(identity, scope):
    spec = build_vts_brief("free", scope, identity)
    assert spec["status"] == "plan_only"
    assert spec["image_count"] == 1
    assert len(spec["images"]) == 1
    img = spec["images"][0]
    assert img["filename"] == f"free_{scope}_master.png"
    assert "WEARING the final hairstyle, outfit" in img["prompt"]
    assert "accessories" in img["prompt"].lower()
    assert "bald" in img["prompt"].lower()
    assert "ONE image" in img["prompt"]
    assert spec["rigging"]["budget"]["art_mesh_max"] == 100
    assert spec["rigging"]["guaranteed_moc3_export"] is False


@pytest.mark.parametrize("scope", ["upper", "full"])
@pytest.mark.parametrize("asset", ["body", "hair", "outfit", "accessory"])
def test_pro_independent_asset_request(identity, scope, asset):
    spec = build_vts_brief("pro", scope, identity, asset_kind=asset)
    assert spec["image_count"] == 1
    assert spec["asset_kind"] == asset
    assert spec["rigging"]["budget"] is None
    assert spec["rigging"]["editor_export_required"] is True
    assert spec["models"]["qwen_usage"] == (
        "optional_detached_asset_only" if asset in ("outfit", "accessory") else "disabled")
    assert spec["images"][0]["filename"].startswith(f"pro_{scope}_")


def test_pro_body_has_no_outfit_or_accessory_requirement(identity):
    from dataclasses import replace
    spec = build_vts_brief("pro", "upper",
                           replace(identity, accessories="", outfit=""), asset_kind="body")
    assert spec["image_count"] == 1
    assert "base_master" in spec["images"][0]["filename"]
    with pytest.raises(ValueError, match="asset_kind"):
        build_vts_brief("pro", "upper", identity)


@pytest.mark.parametrize("edition", ["free", "pro"])
def test_stable_layers_is_default_without_revenue_prompt(identity, edition):
    spec = build_vts_brief(edition, "upper", identity,
                           asset_kind="body" if edition == "pro" else None)
    sl = spec["models"]["stable_layers"]
    assert sl["adapter"] == "StabilityLabs/Stable-Layers"
    assert sl["base"] == "Qwen/Qwen-Image-Layered"
    assert sl["adapter_subfolder"] == "model"
    assert sl["default_for_qwen_stage"] is True
    assert sl["enabled_for_planning"] is False
    assert sl["requires_revenue_input"] is False
    assert sl["adapter_downloaded"] is False
    assert sl["adapter_loaded"] is False
    assert "license_acknowledgement" not in sl
    assert spec["models"]["qwen_quantized_t4_verified"] is False


def test_sam_descriptor_matches_executable_pinned_model():
    spec = STABLE_LAYERS
    assert spec["inference"]["sampler"] == "Heun"
    assert spec["inference"]["steps"] == 50
    from vtuber_pipeline.vts_modes import MODEL_STACK
    sam = [x for x in MODEL_STACK if x["stage"] == "precision_masks"]
    assert len(sam) == 1
    from vtuber_pipeline.common.model_assets import model_pin
    assert sam[0]["checkpoint"] == "sam2.1_hiera_large.pt"
    assert sam[0]["model"] == model_pin("sam2_1_hiera_large")["model_id"]
    assert sam[0]["execution_status"] == "optional_plan_not_connected_to_vts_handoff"
    assert FREE_BUDGET["art_mesh_max"] == 100


def test_bundle_contains_license_notice_and_no_weight_file(identity, tmp_path):
    spec = build_vts_brief("free", "upper", identity)
    pkg = write_vts_brief_package(spec, str(tmp_path))
    with zipfile.ZipFile(pkg) as z:
        names = z.namelist()
        assert "manifest.json" in names
        assert "STABILITY_LICENSE_NOTICE.txt" in names
        assert "prompts/free_upper_master.png.txt" in names
        assert not any(name.endswith((".safetensors", ".bin", ".gguf")) for name in names)
        notice = z.read("STABILITY_LICENSE_NOTICE.txt").decode("utf-8")
        assert "Powered by Stability AI" in notice
        assert "stability.ai/license" in notice
        assert "Community" in notice
        parsed = json.loads(z.read("manifest.json"))
        assert parsed["models"]["stable_layers"]["default_for_qwen_stage"] is True
        assert parsed["models"]["qwen_usage"] == "disabled"


def test_invalid_scope_and_missing_outfit_rejected(identity):
    from dataclasses import replace
    with pytest.raises(ValueError):
        build_vts_brief("free", "side", identity)
    with pytest.raises(ValueError, match="complete outfit"):
        build_vts_brief("free", "upper", replace(identity, outfit=" "))


def test_cli_no_license_gate_and_outputs_zip(identity, tmp_path):
    result = CliRunner().invoke(cli, [
        "vts-prompts", "--edition", "free", "--scope", "upper",
        "--hair-color", identity.hair_color,
        "--hairstyle", identity.hairstyle,
        "--eyes", identity.eye_color,
        "--face", identity.face_description,
        "--outfit", identity.outfit,
        "--accessories", identity.accessories,
        "--output", str(tmp_path),
    ])
    assert result.exit_code == 0, result.output
    assert '"status": "plan_only"' in result.output
    assert '"stable_layers_enabled_for_planning": false' in result.output
    assert (tmp_path / "vts_free_upper_prompts.zip").is_file()
    assert "NOT a .moc3" in result.output

@pytest.mark.parametrize('scope', ['upper', 'full'])
@pytest.mark.parametrize('asset', ['hair', 'outfit', 'accessory'])
def test_detached_prompt_has_no_character_pose_or_clothing_instruction(identity, scope, asset):
    image = build_vts_brief('pro', scope, identity, asset_kind=asset)['images'][0]
    assert 'open eyes, closed lips' not in image['prompt']
    assert 'Fully opaque modest clothing' not in image['prompt']
    assert 'reference canvas' in image['prompt']
    assert image['aspect_ratio_source'] == 'project_composition_not_model_requirement'

@pytest.mark.parametrize('scope', ['upper', 'full'])
@pytest.mark.parametrize('edition,asset', [('free', None), ('pro', 'body'),
    ('pro', 'hair'), ('pro', 'outfit'), ('pro', 'accessory')])
def test_all_ten_briefs_distinguish_native_generation_and_model_processing(identity, scope, edition, asset):
    brief = build_vts_brief(edition, scope, identity, asset_kind=asset)
    contract = brief['models']['image_processing']
    assert contract['see_through']['canvas'] == [1280, 1280]
    assert contract['stable_layers']['max_side'] == 640
    assert contract['stable_layers']['dimension_multiple'] == 16
    assert contract['upscale_before_decomposition'] is False
    assert brief['images'][0]['native_generation_settings_verified'] is False

@pytest.mark.parametrize("edition,asset,expected", [
    ("free", None, False), ("pro", "body", False),
    ("pro", "hair", False), ("pro", "outfit", True),
    ("pro", "accessory", True),
])
def test_qwen_plans_match_real_mode_gate(identity, edition, asset, expected):
    spec = build_vts_brief(edition, "upper", identity, asset_kind=asset)
    assert spec["models"]["stable_layers"]["enabled_for_planning"] is expected
    assert (spec["models"]["qwen_usage"] == "optional_detached_asset_only") is expected
    assert ("recursive_layers" in {x["stage"] for x in spec["models"]["stages"]}) is expected

