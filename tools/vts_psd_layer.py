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
