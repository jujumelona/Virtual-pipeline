"""Local VLM must provide checked correspondences, not phantom model completion."""
from io import BytesIO
import json
from pathlib import Path

import pytest
from PIL import Image

from tools.vts_ai_landmark_pairs import (
    _local_endpoint, _vision_request, create_vision_reference_manifest,
)


def test_remote_image_endpoint_is_refused():
    with pytest.raises(ValueError, match="local"):
        _local_endpoint("https://public-api.example.com/v1/chat/completions")
    assert _local_endpoint("http://127.0.0.1:8000/v1/chat/completions")


class FakeResponse:
    def __init__(self, data):
        self.buffer = BytesIO(json.dumps(data).encode("utf-8"))
    def __enter__(self):
        return self.buffer
    def __exit__(self, *_):
        self.buffer.close()


def _model_reply(confidence=0.9):
    observed = {
        "face_contour": [100, 100], "nose_tip": [140, 125],
        "jaw": [110, 150], "eye_left": [100, 80],
    }
    desired = {n: [p[0]+5, p[1]+5] for n,p in observed.items()}
    return {"choices": [{"message": {"content": json.dumps({
        "confidence": confidence, "observed": observed, "desired": desired,
    })}}]}


def test_reject_low_confidence_vision_correspondences():
    def fake(req, timeout):
        return FakeResponse(_model_reply(0.4))
    with pytest.raises(ValueError, match="Low-confidence"):
        _vision_request(b"a", b"b", model="local-vlm",
                        url="http://localhost:8000/v1/chat/completions",
                        transport=fake)


def test_local_vision_pairs_compile_without_claiming_native_execution(tmp_path):
    ref = tmp_path / "ref"
    native = tmp_path / "moc3"
    ref.mkdir()
    native.mkdir()
    Image.new("RGB", (320, 320)).save(ref / "head_three_quarter_R.png")
    Image.new("RGB", (320, 320)).save(native / "yaw_right_45.png")
    def fake(req, timeout):
        return FakeResponse(_model_reply())
    bindings = {name: "warp:" + name for name in (
        "face_contour", "nose_tip", "jaw", "eye_left")}
    plan, folder = create_vision_reference_manifest(
        ref, native, tmp_path / "compiled", bindings=bindings,
        model="local-vlm",
        endpoint="http://127.0.0.1:8000/v1/chat/completions",
        max_side=320, transport=fake)
    assert len(plan["changes"]) == 4
    assert all(change["key"] == {"ParamAngleX": 45} for change in plan["changes"])
    assert plan["reference_angles_used_as_rig_keyforms"] is False
    assert (folder / "vision_reference_manifest.json").is_file()
    audit = json.loads((folder / "vision_reference_audit.json").read_text())
    assert audit["native_keyforms_applied"] is False
