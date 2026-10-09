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
def test_pro_uses_independent_assets_and_may_exceed_free_budget(identity, scope):
    spec = build_vts_brief("pro", scope, identity)
    names = [image["filename"] for image in spec["images"]]
    assert spec["image_count"] == 5
    assert f"pro_{scope}_appearance_master.png" in names
    assert f"pro_{scope}_base_master.png" in names
    assert f"pro_{scope}_hair_variant.png" in names
    assert f"pro_{scope}_outfit_variant.png" in names
    assert f"pro_{scope}_accessories_variant.png" in names
    assert spec["rigging"]["budget"] is None
    assert spec["rigging"]["editor_export_required"] is True
    assert spec["models"]["qwen_usage"] == "primary_high_detail_refinement"


def test_pro_no_accessories_not_required(identity):
    from dataclasses import replace
    spec = build_vts_brief("pro", "upper", replace(identity, accessories=""))
    assert spec["image_count"] == 4
    assert not any("accessories_variant" in item["filename"] for item in spec["images"])


@pytest.mark.parametrize("edition", ["free", "pro"])
def test_stable_layers_is_default_without_revenue_prompt(identity, edition):
    spec = build_vts_brief(edition, "upper", identity)
    sl = spec["models"]["stable_layers"]
    assert sl["adapter"] == "StabilityLabs/Stable-Layers"
    assert sl["base"] == "Qwen/Qwen-Image-Layered"
    assert sl["adapter_subfolder"] == "model"
    assert sl["default_for_qwen_stage"] is True
    assert sl["enabled_for_planning"] is True
    assert sl["requires_revenue_input"] is False
    assert sl["adapter_downloaded"] is False
    assert sl["adapter_loaded"] is False
    assert "license_acknowledgement" not in sl
    assert spec["models"]["qwen_quantized_t4_verified"] is False


def test_sam_checkpoint_fixed_to_single_large():
    spec = STABLE_LAYERS
    assert spec["inference"]["sampler"] == "Heun"
    assert spec["inference"]["steps"] == 50
    from vtuber_pipeline.vts_modes import MODEL_STACK
    sam = [x for x in MODEL_STACK if x["stage"] == "precision_masks"]
    assert len(sam) == 1
    assert sam[0]["checkpoint"] == "sam2.1_hiera_large.pt"
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
    assert '"stable_layers_enabled_for_planning": true' in result.output
    assert (tmp_path / "vts_free_upper_prompts.zip").is_file()
    assert "NOT a .moc3" in result.output
