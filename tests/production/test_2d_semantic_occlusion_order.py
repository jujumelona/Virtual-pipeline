"""The native 2D rig's draw order must layer the observed eyelid over iris."""
from vtuber_pipeline.common.part_taxonomy import z_order


def test_facial_eye_and_mouth_occlusion_order():
    assert z_order("eye.left.white") < z_order("eye.left.iris") < z_order("eye.left.lid")
    assert z_order("eye.right.white") < z_order("eye.right.iris") < z_order("eye.right.lid")
    assert z_order("mouth.inner") < z_order("mouth.lip")
    assert z_order("face") < z_order("eye.left.iris")
    assert z_order("hair.front.island00") > z_order("eye.left.lid")
    assert z_order("hair.back.island00") < z_order("face")


def test_new_facial_parts_have_distinct_depth_even_if_handed_to_native_sdk():
    names = ["eye.left.white", "eye.left.iris", "eye.left.lid",
             "mouth.inner", "mouth.lip"]
    # The rig exports ascending values as order so no alpha island
    # accidentally overdraws the eyelid or the visible lip.
    depths = [z_order(name) for name in names]
    assert len(set(depths[:3])) == 3
    assert depths[3] < depths[4]
