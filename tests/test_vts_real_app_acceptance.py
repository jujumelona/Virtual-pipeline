"""A VTube Studio acceptance claim needs authenticated LIVE desktop telemetry."""
import json
from pathlib import Path
import pytest
from tools.vts_real_app_acceptance import inspect_real_vts


class ScriptedVTS:
    def __init__(self, *, name="Avatar.model3.json", fps=60, found=(True,)*4):
        self.requests = []
        self.name, self.fps, self.found = name, fps, list(found)
        self.calls = 0
    def send(self, payload):
        self.requests.append(json.loads(payload))
    def recv(self, timeout):
        request = self.requests[-1]
        message = request["messageType"]
        if message == "AuthenticationRequest":
            # The live token must never enter the result file.
            assert request["data"]["authenticationToken"] == "secret-token"
            data = {"authenticated": True}
        elif message == "CurrentModelRequest":
            data = {"modelLoaded": True, "live2DModelName": self.name,
                    "modelID": "real-loaded-model", "numberOfLive2DArtmeshes": 33,
                    "numberOfLive2DParameters": 22, "numberOfTextures": 1,
                    "hasPhysicsFile": True}
        elif message == "StatisticsRequest":
            data = {"framerate": self.fps}
        elif message == "FaceFoundRequest":
            data = {"found": self.found[self.calls]}
            self.calls += 1
        else:
            raise AssertionError("Only documented read-only API calls allowed")
        return json.dumps({"requestID": request["requestID"],
                           "messageType": message.replace("Request", "Response"),
                           "data": data})
    def close(self):
        pass


def test_live_desktop_model_and_tracking_evidence_contract(tmp_path):
    conn = ScriptedVTS()
    report = inspect_real_vts(expected_model3="Avatar.model3.json",
        output=tmp_path, token="secret-token", connector=lambda url: conn,
        samples=4, pause=lambda _: None)
    assert report["actual_tracking_sustained_all_samples"]
    assert report["verified_vts_desktop_instance"]
    assert report["actual_artmesh_count"] == 33
    assert [x["messageType"] for x in conn.requests] == [
        "AuthenticationRequest", "CurrentModelRequest", "StatisticsRequest",
        "FaceFoundRequest", "FaceFoundRequest",
        "FaceFoundRequest", "FaceFoundRequest"]
    assert "secret-token" not in (tmp_path / "vts_real_app_report.json").read_text()
    assert report["artistic_quality_verified"] is False


def test_wrong_model_is_blocked(tmp_path):
    with pytest.raises(RuntimeError, match="not running the specified"):
        inspect_real_vts(expected_model3="Expected.model3.json",
            output=tmp_path, token="secret-token",
            connector=lambda url: ScriptedVTS(name="Other.model3.json"),
            pause=lambda _: None)


def test_no_sustained_tracking_is_not_certified(tmp_path):
    with pytest.raises(RuntimeError, match="TRACKING_NOT_SUSTAINED"):
        inspect_real_vts(expected_model3="Avatar.model3.json",
            output=tmp_path, token="secret-token",
            connector=lambda url: ScriptedVTS(found=(True, False, True, True)),
            pause=lambda _: None)
    assert not json.loads((tmp_path / "vts_real_app_report.json").read_text())[
        "actual_tracking_sustained_all_samples"]


def test_nonlocal_vts_api_is_not_contacted(tmp_path):
    with pytest.raises(ValueError, match="localhost"):
        inspect_real_vts(expected_model3="Avatar.model3.json",
            output=tmp_path, token="secret-token",
            endpoint="ws://outside.example.com:8001",
            connector=lambda x: pytest.fail("Should not connect"))


def test_no_auth_token_no_real_vts_acceptance(tmp_path):
    with pytest.raises(ValueError, match="user-authorized"):
        inspect_real_vts(expected_model3="Avatar.model3.json",
            output=tmp_path, token="", connector=lambda x: pytest.fail("no token"))
