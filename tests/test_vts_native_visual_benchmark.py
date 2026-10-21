"""Measured pixel-shape improvement, never a fabricated artistic-quality PASS."""
import json
from pathlib import Path
import pytest
from PIL import Image


def _frame(path, *, shift=0, opaque=False):
    im = Image.new("RGBA", (256, 256),
                   (255, 255, 255, 255) if opaque else (0, 0, 0, 0))
    im.paste((100, 170, 200, 255), (64 + shift, 40, 180 + shift, 218))
    im.save(path)


def _poses(root, *, shift, actual=True):
    root.mkdir()
    for side in ("yaw_left_45", "yaw_right_45"):
        _frame(root / (side + ".png"), shift=shift)
    (root / "native_pose_report.json").write_text(json.dumps({
        "source": ("live2d_py_cubism_native_runtime" if actual else "mock"),
        "native_pose_rendered": True, "pose_activity_passed": True,
    }))
    return root


def _refs(root):
    root.mkdir()
    for side in ("head_three_quarter_L", "head_three_quarter_R"):
        _frame(root / (side + ".png"))
    return root


def test_true_registered_native_pose_improvement(tmp_path):
    from tools.vts_native_visual_benchmark import evaluate_native_visual_change
    reference = _refs(tmp_path / "ref")
    before = _poses(tmp_path / "before", shift=40)
    after = _poses(tmp_path / "after", shift=3)
    report = evaluate_native_visual_change(
        reference, after, tmp_path / "result", previous_native_dir=before)
    assert report["pixel_improvement_verified"]
    assert not report["artistic_quality_verified"]
    assert all(metric["alpha_iou"] > 0.94 for metric
               in report["native_reference_pose_image_comparisons"].values())


def test_visible_regression_is_rejected(tmp_path):
    from tools.vts_native_visual_benchmark import evaluate_native_visual_change
    reference = _refs(tmp_path / "ref")
    before = _poses(tmp_path / "before", shift=2)
    after = _poses(tmp_path / "after", shift=40)
    with pytest.raises(RuntimeError, match="NATIVE_VISUAL_DID_NOT_IMPROVE"):
        evaluate_native_visual_change(
            reference, after, tmp_path / "qa", previous_native_dir=before)
    report = json.loads((tmp_path / "qa" / "native_pixel_quality.json").read_text())
    assert not report["pixel_improvement_verified"]


def test_no_baseline_does_not_claim_better_quality(tmp_path):
    from tools.vts_native_visual_benchmark import evaluate_native_visual_change
    report = evaluate_native_visual_change(
        _refs(tmp_path / "refs"), _poses(tmp_path / "native", shift=2),
        tmp_path / "qa")
    assert not report["pixel_improvement_verified"]
    assert report["relative_comparison"]["head_three_quarter_L"]["measured"]


def test_opaque_background_cannot_pass_alpha_geometry_gate(tmp_path):
    from tools.vts_native_visual_benchmark import compare_transparent_images
    ref, native = tmp_path / "ref.png", tmp_path / "native.png"
    _frame(ref, shift=0)
    _frame(native, opaque=True)
    with pytest.raises(ValueError, match="TRANSPARENCY_REQUIRED"):
        compare_transparent_images(ref, native)


def test_fake_native_render_is_not_accepted(tmp_path):
    from tools.vts_native_visual_benchmark import evaluate_native_visual_change
    with pytest.raises(RuntimeError, match="NATIVE_VISUAL_MOC3_RUNTIME_NOT_VERIFIED"):
        evaluate_native_visual_change(
            _refs(tmp_path / "refs"),
            _poses(tmp_path / "native", shift=0, actual=False),
            tmp_path / "out")
