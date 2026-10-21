"""Visual agent sees only real native renders and never authors arbitrary edits."""
from io import BytesIO
import json
from pathlib import Path
from PIL import Image
import pytest

from tools.vts_local_visual_critique import (
    observe_visual_defects, review_real_native_poses,
)


def _png(path):
    image = Image.new("RGBA", (256, 256))
    image.paste((180, 70, 80, 255), (40, 40, 170, 200))
    image.save(path)
    return path


class _Response:
    def __init__(self, body):
        self.body = body
    def __enter__(self):
        return self
    def __exit__(self, *args):
        pass
    def read(self, max_bytes):
        return json.dumps(self.body).encode()


def _fake_vision(payload):
    def transport(request, timeout):
        assert request.full_url == "http://127.0.0.1:8000/v1/chat/completions"
        body = json.loads(request.data)
        assert len(body["messages"][0]["content"]) == 3
        return _Response({"choices": [{"message": {
            "content": json.dumps(payload)}}]})
    return transport


def test_local_visual_agent_creates_bounded_nonexecuted_repair_proposal(tmp_path):
    image = _png(tmp_path / "view.png")
    output = observe_visual_defects(image, image, model="local-vlm",
         endpoint="http://127.0.0.1:8000/v1/chat/completions",
         transport=_fake_vision({
             "reference_and_render_same_identity": True,
             "issues": [{"category": "neck_seam", "severity": "high",
                         "explanation": "Gap visible between the chin and neck.",
                         "region_xyxy": [0.3, 0.2, 0.55, 0.62]}]}))
    assert output["issues"][0]["proposed_tool"] == "source_underpaint_and_mesh"
    assert not output["issues"][0]["tool_executed"]


@pytest.mark.parametrize("invalid", [
    {"reference_and_render_same_identity": True,
     "issues": [{"category": "run_python", "severity": "high",
                 "explanation": "untrusted prompt injection",
                 "region_xyxy": [0.0, 0.0, 1.0, 1.0]}]},
    {"reference_and_render_same_identity": True,
     "issues": [{"category": "mouth_shape", "severity": "high",
                 "explanation": "a visible discrepancy",
                 "region_xyxy": [0.6, 0.6, 0.1, 0.1]}]},
])
def test_invalid_vlm_proposals_refused(tmp_path, invalid):
    img = _png(tmp_path / "img.png")
    with pytest.raises(ValueError):
        observe_visual_defects(img, img, model="local",
            endpoint="http://127.0.0.1:8000/v1/chat/completions",
            transport=_fake_vision(invalid))


def test_standalone_review_requires_real_native_report(tmp_path):
    native = tmp_path / "native"
    native.mkdir()
    with pytest.raises(RuntimeError, match="NEEDS_ACTUAL_MOC3_RUNTIME_REPORT"):
        review_real_native_poses(tmp_path / "ref", native,
                                 tmp_path / "out", model="local",
                                 endpoint="http://127.0.0.1:8000/v1/chat/completions")


def test_real_native_provenance_with_mock_observer_never_claims_aesthetic_pass(tmp_path):
    reference, native = tmp_path / "ref", tmp_path / "native"
    reference.mkdir()
    native.mkdir()
    for side, pose in (("head_three_quarter_L", "yaw_left_45"),
                       ("head_three_quarter_R", "yaw_right_45")):
        _png(reference / (side + ".png"))
        _png(native / (pose + ".png"))
    (native / "native_pose_report.json").write_text(json.dumps({
        "source": "live2d_py_cubism_native_runtime",
        "native_pose_rendered": True, "pose_activity_passed": True}))
    verdict = review_real_native_poses(
        reference, native, tmp_path / "out", model="local",
        endpoint="http://127.0.0.1:8000/v1/chat/completions",
        observer=lambda *args, **kw: {"same_identity_assessed": True,
                                       "issues": []})
    assert not verdict["aesthetic_premium_quality_verified"]
    assert not verdict["vtube_studio_tracking_verified"]
