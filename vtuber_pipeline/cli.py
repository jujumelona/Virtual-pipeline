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
    type=click.Choice([
        "HEAD_TOP", "FACE", "LEFT_EAR", "RIGHT_EAR", "NECK", "CHEST",
        "BACK", "LEFT_SHOULDER", "RIGHT_SHOULDER", "LEFT_HAND",
        "RIGHT_HAND", "LEFT_FOOT", "RIGHT_FOOT", "HIPS",
    ]),
    default="HEAD_TOP",
    show_default=True,
)
@click.option("--output", required=True, type=click.Path(), help="Output directory")
@click.option("--profile", default="commercial", show_default=True)
def accessory(base_vrm, images, anchor, output, profile):
    """Reconstruct and independently fit multiple accessories to one avatar."""
    from vtuber_pipeline.accessory.reconstruction import reconstruct_accessories
    from vtuber_pipeline.accessory.build import AccessoryPipeline

    out = pathlib.Path(output)
    out.mkdir(parents=True, exist_ok=True)
    recon_dir = out / "reconstruction"
    reconstructed = reconstruct_accessories(list(images), str(recon_dir), profile=profile)

    failures = []
    completed = []
    for index, item in enumerate(reconstructed):
        if item.get("status") != "complete" or not item.get("mesh"):
            failures.append({"image": item.get("image"), "error": item.get("error", "reconstruction failed")})
            continue
        item_dir = out / f"accessory_{index:03d}"
        build = AccessoryPipeline(str(item_dir), {"anchor_name": anchor}).build(
            base_vrm=base_vrm,
            accessory_glb=item["mesh"],
        )
        if build.get("status") == "complete":
            completed.append(build.get("output_vrm"))
            click.echo(f"  ✓ {item.get('image')} -> {build.get('output_vrm')}")
        else:
            failures.append({
                "image": item.get("image"),
                "error": build.get("failed_stages") or build.get("incomplete_stages") or build.get("status"),
            })

    if failures:
        raise click.ClickException(f"{len(failures)} accessory item(s) failed: {failures}")
    click.echo(f"Completed {len(completed)} accessory variant(s).")


if __name__ == "__main__":
    cli()
