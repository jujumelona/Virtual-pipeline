"""RGB/8-bit import layers with baked transparency, as Cubism requires."""


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
