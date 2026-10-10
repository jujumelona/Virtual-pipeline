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


def new_import_psd(size):
    from psd_tools import PSDImage
    from psd_tools.constants import Resource
    from psd_tools.psd.image_resources import ImageResource

    # RGBA here means Photoshop RGB color mode with four stored channels:
    # R/G/B plus native layer transparency. PSD files remain RGB/8-bit/sRGB.
    # Creating a three-channel 'RGB' document forces psd-tools 1.14.2 to
    # convert each RGBA layer to RGB and emit an extra user layer mask,
    # leading to fragile private channel mutation during export.
    psd = PSDImage.new("RGBA", size, depth=8)
    if psd.color_mode.name != "RGB" or psd.pil_mode != "RGBA":
        raise RuntimeError("psd-tools native RGBA/RGB transparency contract changed")
    profile = srgb_profile_bytes()
    psd.image_resources[Resource.ICC_PROFILE] = ImageResource(
        key=Resource.ICC_PROFILE, data=profile)
    return psd


def create_import_layer(image, parent, *, name, top=0, left=0):
    from psd_tools.api.layers import PixelLayer
    from psd_tools.constants import ChannelID

    rgba = image.convert("RGBA")
    layer = PixelLayer.frompil(rgba, parent=parent, name=name, top=top, left=left)
    # psd-tools 1.14.2 creates an extra USER_LAYER_MASK even when
    # the parent is RGBA-capable. Remove that duplicate; alpha is already
    # written as TRANSPARENCY_MASK by PixelLayer.frompil.
    if layer.mask is not None:
        layer.remove_mask()
    channel_ids = {info.id for info in layer._record.channel_info}
    if ChannelID.TRANSPARENCY_MASK not in channel_ids:
        raise RuntimeError("Pinned psd-tools writer has no native transparency channel")
    if layer.mask is not None:
        raise RuntimeError("PSD still has a separate unapplied user mask")
    return layer


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
            marshal.dumps(create_import_layer.__code__)).hexdigest(),
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
    import numpy as np
    from PIL import Image
    from tools.vts_artwork_export import _write_psd

    report = {**psd_runtime_identity(), "tested_alpha_values": 256}
    if diagnostics_dir is not None:
        diagnostics_dir = Path(diagnostics_dir)
        diagnostics_dir.mkdir(parents=True, exist_ok=True)
    workspace = (nullcontext(str(diagnostics_dir)) if diagnostics_dir is not None
                 else TemporaryDirectory(prefix="vts-psd-preflight-"))
    rgba = np.empty((4, 256, 4), dtype=np.uint8)
    rgba[..., :3] = (127, 90, 180)
    rgba[..., 3] = np.arange(256, dtype=np.uint8)
    rgba[1, :, :3] = (0, 128, 255)
    rgba[2, :, :3] = (255, 255, 255)
    rgba[3, :, :3] = (1, 2, 3)
    try:
        with workspace as scratch:
            _write_psd([{"name": "hair.front.0.000", "image": Image.fromarray(rgba),
                         "depth": 0}], Path(scratch) / "probe.psd", free=False)
    except Exception as exc:
        raise RuntimeError(
            f"PSD_RUNTIME_PREFLIGHT failed before inference: {exc}; "
            f"loaded_codec={report['psd_tools_version']} "
            f"path={report['psd_tools_path']} writer={report['writer_sha256']}; "
            "update the checkout and restart the Python process before retrying; "
            "completed See-through PSDs can be reused via generated_psd"
        ) from exc
    report.update(state="PASS", rgba_byte_exact=True)
    return report
