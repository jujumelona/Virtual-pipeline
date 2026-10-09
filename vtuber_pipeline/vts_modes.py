"""VTube Studio-compatible FREE/PRO artwork briefs and model selection contract.

These are production PLANS, not an unsupported MOC3 writer.  No model download,
GPU allocation, license acceptance or Cubism export happens in this module.
"""
from __future__ import annotations

from dataclasses import asdict
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile
import json

from vtuber_pipeline.prompt_contract import Identity

FRAMES = ("upper", "full")
EDITIONS = ("free", "pro")

# Official Cubism FREE limits, not target part counts or required source image counts.
FREE_BUDGET = {
    "art_mesh_max": 100,
    "part_folders_max": 30,
    "deformers_max": 50,
    "parameters_max": 30,
    "blendshape_parameters_max": 3,
    "art_paths_max": 3,
    "texture_atlas_count_max": 1,
    "texture_atlas_edge_px_max": 2048,
}

MODEL_STACK = (
    {
        "stage": "anime_semantic_layering",
        "name": "See-through V3",
        "source": "https://github.com/shitagaki-lab/see-through",
        "quantized_models": (
            "24yearsold/seethroughv0.0.2_layerdiff3d_nf4",
            "24yearsold/seethroughv0.0.1_marigold_nf4",
        ),
        "anime_parser": "24yearsold/l2d_sam_iter2",
        "max_semantic_layers_reported": 23,
        "license": "Apache-2.0 project; underlying model weights retain Open RAIL conditions",
        "runtime": "requires CUDA capability/precision and output tests; not T4-verified",
    },
    {
        "stage": "precision_masks",
        "name": "SAM2.1 Hiera Large",
        "checkpoint": "sam2.1_hiera_large.pt",
        "model": "facebook/sam2.1-hiera-large",
        "license": "Apache-2.0",
        "runtime": "single chosen SAM2.1 checkpoint; separate from anime parser",
    },
    {
        "stage": "recursive_layers",
        "name": "Qwen-Image-Layered",
        "base": "Qwen/Qwen-Image-Layered",
        "quantized_transformer": "OzzyGT/qwen-image-layered-bnb-4bit-transformer",
        "license": "Apache-2.0",
        "runtime": "transformer only quantized; VAE/text encoders still needed; T4 unverified",
    },
)

STABLE_LAYERS = {
    "adapter": "StabilityLabs/Stable-Layers",
    "adapter_subfolder": "model",
    "enabled_by_default": True,
    "requires_revenue_input": False,
    "license_notice_url": "https://stability.ai/license",
    "commercial_registration_url": "https://stability.ai/community-license",
    "base": "Qwen/Qwen-Image-Layered",
    "license": "Stability AI Community License",
    "conditions": (
        "Community License: free for individual/personal use and eligible small-scale "
        "commercial users with annual revenue below USD 1M. Commercial users must "
        "follow Stability AI registration requirements. Larger commercial use "
        "requires an Enterprise license. No income check or mandatory UI gate. "
        "If distributing the integrated model, follow NOTICE and attribution terms."
    ),
    "inference": {"sampler": "Heun", "steps": 50, "guidance_scale": 1.0,
                  "resolution_long_edge": 640, "layers_per_pass": 4},
    "runtime": "official BF16 inference settings; LoRA+bnb4bit/T4 combination unverified",
}


def _identity_values(identity: Identity) -> str:
    # describe() deliberately excludes outfit for the neutral legacy workflow;
    # do NOT use that legacy neutral-body instruction here.
    if not isinstance(identity, Identity):
        raise TypeError("identity must be an Identity object")
    identity.describe()  # validate key face/hair identity fields
    if not identity.outfit.strip():
        raise ValueError("VTube Studio FREE/PRO prompts require a complete outfit")
    values = {
        "gender/presentation": identity.gender or "adult original anime VTuber",
        "hair_color": identity.hair_color,
        "hairstyle": identity.hairstyle,
        "eyes": identity.eye_color,
        "face": identity.face_description,
        "skin_tone": identity.skin_color or "match face",
        "outfit": identity.outfit,
        "accessories": identity.accessories or "none",
        "palette": identity.palette or "harmonious character palette",
        "unique_details": identity.extra or "preserve the specified identity",
    }
    return "\n".join(f"{k}: {v.strip()}" for k, v in values.items())


def _framing(scope: str) -> str:
    if scope == "upper":
        return (
            "UPPER-BODY: full head, hair, neck, shoulders, forearms and BOTH hands; "
            "down to waist/upper hips. No arbitrary mid-thigh crop. All accessories "
            "and long locks inside frame."
        )
    return (
        "FULL-BODY: complete hair and head ornaments, shoulders, both hands, "
        "upper/lower clothing and BOTH shoes visible with margins on all sides. "
        "Neutral front-view A-pose; separated arms and legs. No cropped anatomy."
    )


def _prompt(identity_text: str, framing: str, filename: str, task: str) -> dict:
    prompt = (
        "ORIGINAL FULLY CLOTHED ADULT ANIME VTUBER\n"
        + identity_text + "\n\n"
        + "OUTPUT EXACT FILE NAME: " + filename + "\n"
        + "ONE image, WIDTH:HEIGHT = 2:3 portrait; use the generator's best "
          "native supported resolution. Do not promise 4K/8K or RGBA support.\n"
        + framing + "\n"
        + task + "\n"
        + "Strict identity consistency, crisp clean anime outlines, symmetric "
          "neutral front-facing pose, open eyes, closed lips, flat-front lighting; "
          "clear outline boundaries for later riggable part extraction. "
          "Fully opaque modest clothing; no exposed torso or intimate anatomy. "
          "Plain contrasting background is fine; alpha transparency is OPTIONAL "
          "for master images. Never draw a grid, multiple poses/views, "
          "additional characters, labels, watermark or checkerboard. "
          "Do NOT require the image generator to supply 100 image files or "
          "Cubism rigging meshes.\n"
    )
    return {"filename": filename, "purpose": "external_image_ai_reference",
            "prompt": prompt, "aspect_ratio": "2:3"}


def build_vts_brief(
    edition: str, scope: str, identity: Identity,
) -> dict:
    """Generate inspectable artwork requests and machine-readable runtime PLAN.

    Stable-Layers is the default Qwen LoRA for both editions without collecting
    income information. No weights are downloaded or LoRAs attached here.
    """
    if edition not in EDITIONS:
        raise ValueError("VTube Studio edition must be free or pro")
    if scope not in FRAMES:
        raise ValueError("scope must be upper or full")
    data = _identity_values(identity)
    frame = _framing(scope)
    images: list[dict] = []
    if edition == "free":
        images.append(_prompt(
            data, frame, f"free_{scope}_master.png",
            "Draw the COMPLETE FINISHED CHARACTER in this ONE frame, ALREADY "
            "WEARING the final hairstyle, outfit, shoes where visible and "
            "all specified accessories. No bald or outfit-free base. "
            "These are NOT separate interchangeable assets. After upload, "
            "the pipeline must infer internal eye/mouth/hair/garment/ornament "
            "layers and occluded pixels for animation. This one master must "
            "not be flattened into one final ArtMesh.",
        ))
    else:
        master = f"pro_{scope}_appearance_master.png"
        images.append(_prompt(
            data, frame, master,
            "Draw the COMPLETE FINISHED original character, wearing hair, "
            "outfit and accessories. This is the fixed IDENTITY LOCK for "
            "separate HIGH-DETAIL / PRO modular images. Save and attach this "
            "same reference to EVERY subsequent generation.",
        ))
        images.append(_prompt(
            data, frame, f"pro_{scope}_base_master.png",
            f"Use the actual attached {master} as identity and geometry reference. "
            "Create the matching permanent adult covered BODY+FACE production "
            "base without detachable hairstyle, fashion garments or accessories. "
            "Use a plain OPAQUE skin-tone seamless production cover (not nude), "
            "keep neck, face, arms and hands visible, match the finished model's "
            "proportions and coordinate origin. No detachable asset included.",
        ))
        images.append(_prompt(
            data, frame, f"pro_{scope}_hair_variant.png",
            f"Use attached {master} as identity and location reference. "
            "Draw ONLY the named hairstyle and attached hair ornaments, "
            "without face or fashion clothes. Keep back/front/side locks "
            "clear for further internal layer subdivision; draw plausible "
            "hidden roots and overlap. This is its OWN separate asset, "
            "not a sprite-sheet of the whole character.",
        ))
        images.append(_prompt(
            data, frame, f"pro_{scope}_outfit_variant.png",
            f"Use attached {master} to draw ONLY the complete garment and "
            "footwear visible in this scope, on matching proportions and "
            "attachment points. No face, hands or hair; draw hidden fabric "
            "for movements. The later pipeline splits sleeves, fabric "
            "panels and movable decorations into rigging layers. No "
            "preordained number of rigging parts.",
        ))
        if identity.accessories.strip():
            images.append(_prompt(
                data, frame, f"pro_{scope}_accessories_variant.png",
                f"Use attached {master} to draw ONLY the specified accessories "
                "at the same relative anchors; omit head/body/hair/clothes. "
                "Retain each accessory identity for subsequent independent "
                "layer extraction and rigging.",
            ))
    qwen_usage = "on_demand_if_quality_insufficient" if edition == "free" else "primary_high_detail_refinement"
    brief = {
        "schema": "vtuber/vts-artwork-brief-v1",
        "edition": edition,
        "scope": scope,
        "status": "plan_only",
        "final_target": "VTube Studio compatible Cubism MOC3, NOT produced by this brief",
        "images": images,
        "image_count": len(images),
        "internal_part_rule": (
            "FREE: a single fixed-look model; never demand separate hair/outfit/accessory uploads"
            if edition == "free"
            else "PRO: separate permanent base, hair, outfit and optional accessory assets"
        ),
        "rigging": {
            "budget": dict(FREE_BUDGET) if edition == "free" else None,
            "target_artmesh_count": None,
            "guaranteed_moc3_export": False,
            "editor_export_required": True,
        },
        "models": {
            "image_generator": "external_large_image_AI_only",
            "stages": [dict(item) for item in MODEL_STACK],
            "qwen_usage": qwen_usage,
            "qwen_quantized_t4_verified": False,
            "see_through_nf4_t4_verified": False,
            "stable_layers": {
                **STABLE_LAYERS,
                "enabled_for_planning": True,
                "default_for_qwen_stage": True,
                "adapter_downloaded": False,
                "adapter_loaded": False,
            },
        },
    }
    return brief


def write_vts_brief_package(brief: dict, destination: str) -> str:
    """Package exact image AI prompts, model decisions and licensing for handoff."""
    if brief.get("schema") != "vtuber/vts-artwork-brief-v1":
        raise ValueError("Invalid VTube Studio brief")
    path = Path(destination)
    path.mkdir(parents=True, exist_ok=True)
    name = f"vts_{brief['edition']}_{brief['scope']}_prompts.zip"
    target = path / name
    temp = target.with_suffix(".tmp")
    with ZipFile(temp, "w", ZIP_DEFLATED) as archive:
        archive.writestr("manifest.json", json.dumps(brief, ensure_ascii=False, indent=2))
        archive.writestr(
            "READ_ME_FIRST.txt",
            "These are EXTERNAL image AI prompts and an UNIMPLEMENTED production "
            "plan. Neither a layered PSD nor a .moc3 is included. "
            "Cubism Editor is still required for actual export. "
            "Stable-Layers is the default Qwen LoRA whenever the Qwen stage "
            "runs. Commercial users must observe Stability AI registration, "
            "NOTICE and Community/Enterprise license conditions; no revenue "
            "check or license selection gate is imposed by this program. "
            "Weights are not bundled with this prompt ZIP.\n",
        )
        archive.writestr("STABILITY_LICENSE_NOTICE.txt", (
            "Stable-Layers (StabilityLabs/Stable-Layers) by Stability AI.\n"
            "This Stability AI Model is licensed under the Stability AI Community License, "
            "Copyright © Stability AI Ltd. All Rights Reserved.\n"
            "Powered by Stability AI\n"
            "License: https://stability.ai/license\n"
            "Commercial registration: https://stability.ai/community-license\n"
            "Adapter source: https://huggingface.co/StabilityLabs/Stable-Layers\n"
            "Individuals and eligible small-scale commercial creators may use it for free; "
            "commercial registration and Enterprise conditions may apply.\n"
        ))
        for item in brief["images"]:
            archive.writestr("prompts/" + item["filename"] + ".txt", item["prompt"])
    temp.replace(target)
    return str(target)
