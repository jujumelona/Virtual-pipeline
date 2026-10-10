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

    psd = PSDImage.new("RGB", size, depth=8)
    profile = srgb_profile_bytes()
    psd.image_resources[Resource.ICC_PROFILE] = ImageResource(
        key=Resource.ICC_PROFILE, data=profile)
    return psd


def create_import_layer(image, parent, *, name, top=0, left=0):
    from psd_tools.api.layers import PixelLayer
    from psd_tools.constants import ChannelID

    rgba = image.convert("RGBA")
    layer = PixelLayer.frompil(rgba, parent=parent, name=name, top=top, left=left)
    # psd-tools 1.14.2 converts RGBA to the RGB document mode and stores
    # alpha in a USER_LAYER_MASK. Cubism's stable import instructions require
    # that mask be applied. Put alpha in the actual TRANSPARENCY_MASK channel
    # and remove the separate mask; preserve RGB and straight-alpha bytes.
    if layer.mask is not None:
        layer.remove_mask()
    for index, info in enumerate(layer._record.channel_info):
        if info.id == ChannelID.TRANSPARENCY_MASK:
            channel = layer._channels[index]
            channel.set_data(rgba.getchannel("A").tobytes(), rgba.width, rgba.height,
                             depth=8, version=layer._psd._record.header.version)
            info.length = channel._length
            layer._psd._mark_updated()
            return layer
    raise RuntimeError("Pinned psd-tools writer has no transparency channel")
