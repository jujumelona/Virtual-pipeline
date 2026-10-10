"""RGB/8-bit import layers with baked transparency, as Cubism requires."""



def validate_srgb_profile(data):
    """Refuse silently retagging an embedded profile while retaining RGB bytes."""
    if not data:
        return
    from io import BytesIO
    from PIL import ImageCms
    try:
        profile = ImageCms.ImageCmsProfile(BytesIO(data))
        description = ImageCms.getProfileDescription(profile).lower()
    except (OSError, ValueError, ImageCms.PyCMSError) as exc:
        raise ValueError("Invalid input ICC profile; convert artwork to sRGB") from exc
    if "srgb" not in description or profile.profile.xcolor_space.strip() != "RGB":
        raise ValueError("Convert the input artwork to sRGB before production; "
                         "refusing to silently reinterpret a different ICC color space")


def srgb_profile_bytes():
    from PIL import ImageCms
    return ImageCms.ImageCmsProfile(ImageCms.createProfile("sRGB")).tobytes()


def new_import_psd(size, *, checkpoint=None):
    from psd_tools import PSDImage
    from psd_tools.constants import Resource
    from psd_tools.psd.image_resources import ImageResource

    # RGBA here means Photoshop RGB color mode with four stored channels:
    # R/G/B plus native layer transparency. PSD files remain RGB/8-bit/sRGB.
    # Creating a three-channel 'RGB' document forces psd-tools 1.14.2 to
    # convert each RGBA layer to RGB and emit an extra user layer mask,
    # leading to fragile private channel mutation during export.
    if checkpoint:
        checkpoint('native_document_create')
    psd = PSDImage.new("RGBA", size, depth=8)
    if psd.color_mode.name != "RGB" or psd.pil_mode != "RGBA":
        raise RuntimeError("psd-tools native RGBA/RGB transparency contract changed")
    if checkpoint:
        checkpoint('srgb_profile_create')
    profile = srgb_profile_bytes()
    if checkpoint:
        checkpoint('srgb_profile_attach')
    psd.image_resources[Resource.ICC_PROFILE] = ImageResource(
        key=Resource.ICC_PROFILE, data=profile)
    return psd


def create_import_layer(image, parent, *, name, top=0, left=0, checkpoint=None):
    from psd_tools.api.layers import PixelLayer
    from psd_tools.constants import ChannelID

    rgba = image.convert("RGBA")
    if checkpoint:
        checkpoint('native_layer_encode', name=name)
    layer = PixelLayer.frompil(rgba, parent=parent, name=name, top=top, left=left)
    # psd-tools 1.14.2 creates an extra USER_LAYER_MASK even when
    # the parent is RGBA-capable. Remove that duplicate; alpha is already
    # written as TRANSPARENCY_MASK by PixelLayer.frompil.
    if layer.mask is not None:
        if checkpoint:
            checkpoint('duplicate_mask_remove', name=name)
        layer.remove_mask()
    channel_ids = {info.id for info in layer._record.channel_info}
    if ChannelID.TRANSPARENCY_MASK not in channel_ids:
        raise RuntimeError("Pinned psd-tools writer has no native transparency channel")
    if layer.mask is not None:
        raise RuntimeError("PSD still has a separate unapplied user mask")
    return layer


def save_import_psd(psd, target, *, checkpoint=None):
    """Write controlled Normal-only import layers without float compositing.

    PSDImage.save() automatically invokes the general compositor, even for
    a four-row codec probe. Our generated layers have no effects/masks and
    use Normal/Pass Through only, so Pillow can build the merged preview with
    bounded 8-bit buffers. Serialize through the format writer after setting
    that preview explicitly; do not mark the tree clean or discard layers.
    """
    from PIL import Image
    from psd_tools.constants import BlendMode
    if psd.color_mode.name != "RGB" or psd.depth != 8 or psd.channels != 4:
        raise ValueError("Bounded PSD writer requires RGB/8-bit with transparency")
    if checkpoint:
        checkpoint('preview_create')
    preview = Image.new("RGBA", psd.size)
    for layer in psd.descendants():  # PSD stores bottom-to-top.
        allowed = (BlendMode.PASS_THROUGH, BlendMode.NORMAL) if layer.is_group() else (BlendMode.NORMAL,)
        if (layer.blend_mode not in allowed or layer.opacity != 255 or layer.mask is not None
                or layer.clipping or layer.has_effects() or layer.has_vector_mask()):
            raise ValueError("Bounded PSD writer cannot flatten unsupported attributes: " + layer.name)
        if layer.is_group() or not layer.is_visible():
            continue
        if checkpoint:
            checkpoint('preview_layer_decode', name=layer.name)
        tile = layer.topil(apply_icc=False)
        if tile is None:
            raise ValueError("Generated PSD layer has no raster: " + layer.name)
        if checkpoint:
            checkpoint('preview_layer_composite', name=layer.name)
        preview.alpha_composite(tile.convert("RGBA"), (layer.left, layer.top))
    # PSD merged image RGB is stored over white; its transparency is a
    # separate channel. Layer RGB/A remain straight and byte-exact.
    matte = Image.new("RGBA", psd.size, (255, 255, 255, 255))
    matte.alpha_composite(preview)
    bands = (*matte.convert("RGB").split(), preview.getchannel("A"))
    if checkpoint:
        checkpoint('merged_image_encode')
    psd._record.image_data.set_data([band.tobytes() for band in bands], psd._record.header)
    # PSD format: a negative layer count identifies the first merged alpha
    # as transparency, rather than an unrelated saved alpha selection.
    info = psd._record.layer_and_mask_information.layer_info
    if info is None or info.layer_count == 0:
        raise ValueError("Bounded PSD writer requires actual layer records")
    info.layer_count = -abs(info.layer_count)
    if checkpoint:
        checkpoint('psd_records_write')
    with open(target, "wb") as stream:
        psd._record.write(stream)


def psd_runtime_identity():
    """Identify loaded code, not merely packages installed on disk."""
    import hashlib
    import marshal
    from pathlib import Path
    import subprocess
    import sys
    import numpy
    import PIL
    import psd_tools
    try:
        commit = subprocess.run(
            ["git", "rev-parse", "HEAD"], cwd=Path(__file__).resolve().parents[1],
            capture_output=True, text=True, timeout=5, check=True).stdout.strip()
    except (OSError, subprocess.SubprocessError):
        commit = "unavailable"
    return {
        "git_commit": commit, "python": sys.version, "python_executable": sys.executable,
        "pillow_version": PIL.__version__, "numpy_version": numpy.__version__,
        "psd_tools_version": psd_tools.__version__,
        "psd_tools_path": str(Path(psd_tools.__file__).resolve()),
        "writer_sha256": hashlib.sha256(
            marshal.dumps(new_import_psd.__code__) +
            marshal.dumps(create_import_layer.__code__) +
            marshal.dumps(save_import_psd.__code__)).hexdigest(),
    }


def verify_import_psd_runtime(*, diagnostics_dir=None):
    """Exercise the loaded writer/reader before paying for model inference.

    Installing a package does not replace modules already imported by a
    notebook kernel. Record the loaded codec and writer, and test actual
    serialized bytes, including hidden RGB and very low alpha values.
    Never cache this result across calls in a mutable notebook runtime.
    """
    from contextlib import nullcontext
    from pathlib import Path
    from tempfile import TemporaryDirectory
    import json
    import os
    import sys
    import time
    from tools.vts_handoff_process import _save
    if diagnostics_dir is not None:
        diagnostics_dir = Path(diagnostics_dir)
        diagnostics_dir.mkdir(parents=True, exist_ok=True)
    workspace = (nullcontext(str(diagnostics_dir)) if diagnostics_dir is not None
                 else TemporaryDirectory(prefix="vts-psd-preflight-"))
    # Commit evidence BEFORE imports, runtime identification and the probe.
    # The previous order emitted versions only after _write_psd returned.
    with workspace as scratch:
        scratch = Path(scratch)
        def step(operation, **details):
            event = {'event': 'PSD_RUNTIME_START', 'operation': operation,
                     'python_executable': sys.executable, 'pid': os.getpid(),
                     'time': time.time(), **details}
            with (scratch / 'runtime.steps.jsonl').open('a', encoding='utf-8') as stream:
                stream.write(json.dumps(event) + '\n')
                stream.flush()
                os.fsync(stream.fileno())
            print('[VTS] PSD_RUNTIME_START: ' + json.dumps(event), flush=True)
        _save(scratch / 'runtime.json', {'state': 'running', 'python_executable': sys.executable})
        step('native_imports')
        import numpy as np
        from PIL import Image
        from tools.vts_artwork_export import _write_psd
        step('runtime_identity')
        report = {**psd_runtime_identity(), 'tested_alpha_values': 256, 'state': 'running'}
        _save(scratch / 'runtime.json', report)
        print('[VTS] PSD_RUNTIME_IDENTITY: ' + json.dumps(report), flush=True)
        return _verify_import_psd_probe(scratch, report, step, np, Image, _write_psd)


def _verify_import_psd_probe(scratch, report, step, np, Image, _write_psd):
    from tools.vts_handoff_process import _save
    step('build_alpha_probe')
    rgba = np.empty((4, 256, 4), dtype=np.uint8)
    rgba[..., :3] = (127, 90, 180)
    rgba[..., 3] = np.arange(256, dtype=np.uint8)
    rgba[1, :, :3] = (0, 128, 255)
    rgba[2, :, :3] = (255, 255, 255)
    rgba[3, :, :3] = (1, 2, 3)
    try:
        step('write_alpha_probe')
        _write_psd([{"name": "hair.front.0.000", "image": Image.fromarray(rgba),
                     "depth": 0}], scratch / "probe.psd", free=False)
    except Exception as exc:
        _save(scratch / 'runtime.json', {**report, 'state': 'FAIL', 'error': str(exc)})
        raise RuntimeError(
            f"PSD_RUNTIME_PREFLIGHT failed before inference: {exc}; "
            f"loaded_codec={report['psd_tools_version']} "
            f"path={report['psd_tools_path']} writer={report['writer_sha256']}; "
            "update the checkout and restart the Python process before retrying; "
            "completed See-through PSDs can be reused via generated_psd"
        ) from exc
    report.update(state="PASS", rgba_byte_exact=True)
    _save(scratch / 'runtime.json', report)
    return report
