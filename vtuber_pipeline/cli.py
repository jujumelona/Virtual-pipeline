"""Click CLI for the fail-closed VTuber pipeline."""

import math
import pathlib
import click


@click.group()
def cli():
    """VTuber commercial avatar/accessory pipeline."""
    pass


@cli.command()
@click.option("--image", required=True, type=click.Path(exists=True), help="Input character image")
@click.option("--output", required=True, type=click.Path(), help="Output directory")
@click.option("--face-image", type=click.Path(exists=True), help="External close-up face reference")
@click.option("--back-image", type=click.Path(exists=True), help="External full-body rear reference")
@click.option("--left-image", type=click.Path(exists=True), help="Optional observed left reference")
@click.option("--right-image", type=click.Path(exists=True), help="Optional observed right reference")
@click.option("--full-body/--bust-up", default=False, help="Enable full-body input and diagnostics")
@click.option("--texture-size", type=click.Choice(["1024", "2048"]), default="2048")
@click.option(
    "--profile",
    type=click.Choice(["commercial", "production", "development"]),
    default="commercial",
    show_default=True,
)
@click.option(
    "--commercial-usage",
    type=click.Choice(["personalNonProfit", "personalProfit", "corporation"]),
    default="corporation",
    show_default=True,
)
def avatar(image, output, face_image, back_image, left_image, right_image, full_body, texture_size, profile, commercial_usage):
    """Build one VTuber avatar VRM from an external source image."""
    from vtuber_pipeline.avatar.build import build_avatar

    result = build_avatar(
        image, output,
        {
            "profile": profile,
            "commercial_usage": commercial_usage,
            "references": {
                "full_body": full_body,
                "face_image": face_image,
                "back_image": back_image,
                "left_image": left_image,
                "right_image": right_image,
                "texture_size": int(texture_size),
            },
        },
    )
    stages = result.get("stages", {})
    # Render every stage actually emitted by the orchestrator, in execution
    # order. A fixed list silently hid newly added stages (and kept reporting
    # removed InstantMesh stages), making production failure triage unreliable.
    stage_labels = {
        "reference_quality": "external reference diagnostics",
        "person_alpha": "ISNet-IS foreground cutout",
        "input_gate": "input validation + landmarks",
        "relative_depth": "per-observed-view relative depth",
        "reference_reconstruction": "TripoSR reconstruction",
        "licensed_multiview": "observed TripoSR multi-view reconstruction",
        "multiview_alignment": "3D frame registration",
        "template_fitting": "canonical template fitting",
        "surface_refine": "topology-preserving surface refinement",
        "texture_transfer": "source-aware texture transfer",
        "rig": "humanoid rig and hair",
        "expressions": "expressions / visemes",
        "gaze": "look-at",
        "springbone": "SpringBone",
        "vrm_export": "VRM export",
        "blender_vrm_export": "Blender native VRM 1.0 export",
        "validator": "strict validation",
    }
    for key, stage in stages.items():
        if not isinstance(stage, dict):
            click.echo(f"  · {key}: invalid stage report")
            continue
        label = stage_labels.get(key, key)
        status = stage.get("status", "unknown")
        if status == "complete":
            click.echo(f"  ✓ {label}")
        elif status == "cached":
            click.echo(f"  ✓ {label} (verified cached)")
        elif status == "skipped":
            click.echo(f"  · {label} (skipped)")
        else:
            detail = stage.get("error") or stage.get("warning") or status
            click.echo(f"  ✗ {label}: {detail}")

    if result.get("status") != "complete":
        raise click.ClickException(
            str(result.get("failed_reason") or result.get("failed_stages") or "avatar build failed")
        )
    click.echo(f"VRM: {result['vrm_path']}")


@cli.command("inochi2d-prep")
@click.option("--image", required=True, type=click.Path(exists=True))
@click.option("--layers-zip", type=click.Path(exists=True), default=None)
@click.option("--output", required=True, type=click.Path())
@click.option(
    "--commercial-usage",
    type=click.Choice(["personalNonProfit", "personalProfit", "corporation"]),
    default="corporation",
)
def inochi2d_prep(image, layers_zip, output, commercial_usage):
    """Prepare supplied layers for open-source Inochi Creator, not an .inp puppet."""
    from vtuber_pipeline.two_d import prepare_inochi2d_artwork

    try:
        result = prepare_inochi2d_artwork(
            image, output, layers_zip=layers_zip,
            commercial_usage=commercial_usage,
        )
    except (OSError, ValueError) as exc:
        raise click.ClickException(str(exc)) from exc
    click.echo(f"Inochi2D artwork package: {result['package_path']}")
    click.echo("NOT an Inochi2D .inp puppet. Import PSD into Inochi Creator, then rig/export.")


@cli.command("live2d-prep")
@click.option("--image", required=True, type=click.Path(exists=True))
@click.option("--layers-zip", type=click.Path(exists=True), default=None)
@click.option("--output", required=True, type=click.Path())
@click.option(
    "--commercial-usage",
    type=click.Choice(["personalNonProfit", "personalProfit", "corporation"]),
    default="corporation",
)
def live2d_prep(image, layers_zip, output, commercial_usage):
    """Package external artwork for later Live2D Cubism editing; no .moc3 export."""
    from vtuber_pipeline.two_d import prepare_live2d_artwork

    try:
        result = prepare_live2d_artwork(
            image, output, layers_zip=layers_zip,
            commercial_usage=commercial_usage,
        )
    except (OSError, ValueError) as exc:
        raise click.ClickException(str(exc)) from exc

    click.echo(f"2D artwork package: {result['package_path']}")
    if result["status"] == "needs_layering":
        click.echo("Only flattened art supplied: split layers before Cubism rigging.")
    else:
        click.echo("Transparent layers prepared for external Cubism rigging.")
    click.echo("NOT a finished Live2D .moc3 model. NOT ready for VTube Studio.")


@cli.command()
@click.option("--base-vrm", required=True, type=click.Path(exists=True), help="Completed avatar VRM")
@click.option("--images", required=True, multiple=True, type=click.Path(exists=True), help="Accessory source images")
@click.option(
    "--anchor",
    "anchors",
    multiple=True,
    type=click.Choice([
        "HEAD_TOP", "FACE", "LEFT_EAR", "RIGHT_EAR", "NECK", "CHEST",
        "BACK", "LEFT_SHOULDER", "RIGHT_SHOULDER", "LEFT_HAND",
        "RIGHT_HAND", "LEFT_FOOT", "RIGHT_FOOT", "HIPS", "CUSTOM",
    ]),
    help=(
        "Accessory anchor. Repeat once per --images item. "
        "If omitted, all items use HEAD_TOP."
    ),
)
@click.option(
    "--custom-anchor",
    "custom_anchors",
    multiple=True,
    help=(
        "CUSTOM anchor spec: PARENT_BONE,X,Y,Z,TARGET_SIZE. "
        "Repeat once for each --anchor CUSTOM, in the same order."
    ),
)
@click.option("--output", required=True, type=click.Path(), help="Output directory")
@click.option(
    "--profile",
    type=click.Choice(["commercial", "production", "development"]),
    default="commercial",
    show_default=True,
)
def accessory(base_vrm, images, anchors, custom_anchors, output, profile):
    """Reconstruct and cumulatively attach multiple accessories to one avatar."""
    from vtuber_pipeline.accessory.reconstruction import reconstruct_accessories
    from vtuber_pipeline.accessory.build import AccessoryPipeline

    # Validate every slot before invoking expensive GPU reconstruction.
    # Invalid CLI options must fail without downloading or loading models.
    image_list = list(images)
    anchor_list = list(anchors)
    if anchor_list and len(anchor_list) != len(image_list):
        raise click.ClickException(
            "--anchor must be omitted or repeated exactly once per --images item"
        )
    if not anchor_list:
        anchor_list = ["HEAD_TOP"] * len(image_list)

    custom_count = sum(name == "CUSTOM" for name in anchor_list)
    if len(custom_anchors) != custom_count:
        raise click.ClickException(
            "--custom-anchor must be repeated exactly once for each "
            "--anchor CUSTOM"
        )

    parsed_custom_anchors = []
    for raw in custom_anchors:
        parts = [part.strip() for part in raw.split(",")]
        if len(parts) != 5 or not parts[0]:
            raise click.ClickException(
                "--custom-anchor format must be PARENT_BONE,X,Y,Z,TARGET_SIZE"
            )
        try:
            offset = [float(parts[1]), float(parts[2]), float(parts[3])]
            target_size = float(parts[4])
        except ValueError as exc:
            raise click.ClickException(
                "--custom-anchor X,Y,Z,TARGET_SIZE must be numbers"
            ) from exc
        if not all(math.isfinite(value) for value in (*offset, target_size)):
            raise click.ClickException(
                "--custom-anchor X,Y,Z,TARGET_SIZE must be finite numbers"
            )
        if target_size <= 0.0:
            raise click.ClickException(
                "--custom-anchor TARGET_SIZE must be > 0"
            )
        parsed_custom_anchors.append({
            "parent_bone": parts[0],
            "offset": offset,
            "target_size": target_size,
        })

    out = pathlib.Path(output)
    out.mkdir(parents=True, exist_ok=True)
    recon_dir = out / "reconstruction"
    reconstructed = reconstruct_accessories(image_list, str(recon_dir), profile=profile)
    if len(reconstructed) != len(image_list):
        raise click.ClickException(
            "Accessory reconstruction returned the wrong number of results: "
            f"{len(reconstructed)} != {len(image_list)}"
        )

    failures = []
    current_vrm = base_vrm
    completed = 0
    custom_index = 0

    for index, (item, anchor_name) in enumerate(
        zip(reconstructed, anchor_list),
        start=1,
    ):
        if item.get("status") != "complete" or not item.get("mesh"):
            failures.append({
                "image": item.get("image"),
                "error": item.get("error", "reconstruction failed"),
            })
            break

        item_dir = out / f"accessory_{index:03d}"
        custom_anchor = None
        if anchor_name == "CUSTOM":
            custom_anchor = parsed_custom_anchors[custom_index]
            custom_index += 1

        build = AccessoryPipeline(
            str(item_dir),
            {
                "anchor_name": anchor_name,
                "custom_anchor": custom_anchor,
                "bake": True,
            },
        ).build(
            base_vrm=current_vrm,
            accessory_glb=item["mesh"],
        )

        if build.get("status") != "complete":
            failures.append({
                "image": item.get("image"),
                "error": (
                    build.get("failed_stages")
                    or build.get("failed_reason")
                    or build.get("status")
                ),
            })
            break

        current_vrm = build["output_vrm"]
        completed += 1
        click.echo(
            f"  ✓ [{index}/{len(image_list)}] "
            f"{item.get('image')} -> {anchor_name}"
        )

    if failures:
        raise click.ClickException(
            f"Accessory pipeline stopped after {completed} completed item(s): {failures}"
        )

    click.echo(f"VRM: {current_vrm}")


@cli.command("inochi2d")
@click.option("--image", required=True, type=click.Path(exists=True))
@click.option("--layers-zip", type=click.Path(exists=True), default=None)
@click.option("--output", required=True, type=click.Path())
@click.option("--commercial-usage", type=click.Choice(["personalNonProfit","personalProfit","corporation"]), default="corporation")
def inochi2d_full(image, layers_zip, output, commercial_usage):
    """Build a native Inochi2D puppet; reject unsupported native exporters."""
    from vtuber_pipeline.common.schemas import SourceSet
    from vtuber_pipeline.two_d.build import build_inochi2d
    # Direct CLI invocation must be able to build the native executable,
    # without requiring a separate undocumented environment setup command.
    # Restore the user's process environment on completion/error.
    import os
    previous = os.environ.get("VTUBER_INOCHI_AUTO_BUILD")
    os.environ["VTUBER_INOCHI_AUTO_BUILD"] = "1"
    try:
        result=build_inochi2d(SourceSet("inochi2d",image,user_layers_zip=layers_zip,
                                       output_dir=output,commercial_usage=commercial_usage))
    finally:
        if previous is None:
            os.environ.pop("VTUBER_INOCHI_AUTO_BUILD", None)
        else:
            os.environ["VTUBER_INOCHI_AUTO_BUILD"] = previous
    click.echo(__import__("json").dumps(result.__dict__,ensure_ascii=False))
    if result.status!="complete":
        raise click.ClickException(result.error or "No verified INP2 puppet was produced")


@cli.command("live2d")
@click.option("--image", required=True, type=click.Path(exists=True))
@click.option("--layers-zip", type=click.Path(exists=True), default=None)
@click.option("--output", required=True, type=click.Path())
@click.option("--commercial-usage", type=click.Choice(["personalNonProfit","personalProfit","corporation"]), default="corporation")
def live2d_full(image, layers_zip, output, commercial_usage):
    """Prepare layered art and rig data for the official Cubism editor."""
    from vtuber_pipeline.common.schemas import SourceSet
    from vtuber_pipeline.two_d.build import build_live2d
    result=build_live2d(SourceSet("live2d",image,user_layers_zip=layers_zip,
                                 output_dir=output,commercial_usage=commercial_usage))
    click.echo(__import__("json").dumps(result.__dict__,ensure_ascii=False))
    if result.status=="failed":
        raise click.ClickException(result.error or "Live2D art preparation failed")


@cli.command("live2d-import-export")
@click.option("--official-export-dir", required=True, type=click.Path(exists=True,file_okay=False))
@click.option("--output", required=True, type=click.Path())
def live2d_import_export(official_export_dir, output):
    """Collect real MOC3 and all referenced textures/physics from Cubism Editor."""
    from vtuber_pipeline.two_d.cubism_handoff import collect_official_export
    result=collect_official_export(official_export_dir,output)
    click.echo(__import__("json").dumps(result.__dict__,ensure_ascii=False))


if __name__ == "__main__":
    cli()
