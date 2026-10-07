"""Click CLI for the fail-closed VTuber pipeline."""

import pathlib
import click


@click.group()
def cli():
    """VTuber commercial avatar/accessory pipeline."""
    pass


@cli.command()
@click.option("--image", required=True, type=click.Path(exists=True), help="Input character image")
@click.option("--output", required=True, type=click.Path(), help="Output directory")
@click.option("--profile", default="commercial", show_default=True)
@click.option(
    "--commercial-usage",
    type=click.Choice(["personalNonProfit", "personalProfit", "corporation"]),
    default="corporation",
    show_default=True,
)
def avatar(image, output, profile, commercial_usage):
    """Build one VTuber avatar VRM from an external source image."""
    from vtuber_pipeline.avatar.build import build_avatar

    result = build_avatar(
        image, output,
        {"profile": profile, "commercial_usage": commercial_usage},
    )
    stages = result.get("stages", {})
    stage_names = [
        ("input_gate", "input validation + landmarks"),
        ("reference_reconstruction", "TripoSR reconstruction"),
        ("template_fitting", "canonical template fitting"),
        ("texture_transfer", "texture transfer"),
        ("rig", "humanoid rig"),
        ("expressions", "expressions / visemes"),
        ("gaze", "look-at"),
        ("springbone", "SpringBone"),
        ("vrm_export", "VRM export"),
        ("validator", "strict validation"),
    ]
    for key, label in stage_names:
        stage = stages.get(key)
        if not stage:
            continue
        status = stage.get("status", "unknown")
        if status == "complete":
            click.echo(f"  ✓ {label}")
        else:
            detail = stage.get("error") or stage.get("warning") or status
            click.echo(f"  ✗ {label}: {detail}")

    if result.get("status") != "complete":
        raise click.ClickException(
            str(result.get("failed_reason") or result.get("failed_stages") or "avatar build failed")
        )
    click.echo(f"VRM: {result['vrm_path']}")


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
        "RIGHT_HAND", "LEFT_FOOT", "RIGHT_FOOT", "HIPS",
    ]),
    help=(
        "Accessory anchor. Repeat once per --images item. "
        "If omitted, all items use HEAD_TOP."
    ),
)
@click.option("--output", required=True, type=click.Path(), help="Output directory")
@click.option("--profile", default="commercial", show_default=True)
def accessory(base_vrm, images, anchors, output, profile):
    """Reconstruct and cumulatively attach multiple accessories to one avatar."""
    from vtuber_pipeline.accessory.reconstruction import reconstruct_accessories
    from vtuber_pipeline.accessory.build import AccessoryPipeline

    out = pathlib.Path(output)
    out.mkdir(parents=True, exist_ok=True)
    recon_dir = out / "reconstruction"
    reconstructed = reconstruct_accessories(list(images), str(recon_dir), profile=profile)

    image_list = list(images)
    anchor_list = list(anchors)
    if anchor_list and len(anchor_list) != len(image_list):
        raise click.ClickException(
            "--anchor must be omitted or repeated exactly once per --images item"
        )
    if not anchor_list:
        anchor_list = ["HEAD_TOP"] * len(image_list)

    failures = []
    current_vrm = base_vrm
    completed = 0

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
        build = AccessoryPipeline(
            str(item_dir),
            {"anchor_name": anchor_name},
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


if __name__ == "__main__":
    cli()
