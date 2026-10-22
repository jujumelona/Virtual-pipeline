"""Read-only proof from the ACTUAL VTube Studio desktop application.

Default localhost VTube Studio WebSocket is ws://127.0.0.1:8001. Token is
obtained through VTS's explicit user permission popup and never logged.
Native rendering in CI cannot substitute for VTS loaded-model/tracker proof.
"""
from __future__ import annotations

import argparse
import json
import math
import os
from pathlib import Path
import time
from urllib.parse import urlsplit
import uuid


def _envelope(action: str, data: dict | None = None) -> dict:
    result = {"apiName": "VTubeStudioPublicAPI", "apiVersion": "1.0",
              "requestID": str(uuid.uuid4()), "messageType": action}
    if data is not None:
        result["data"] = data
    return result


def _local_ws(endpoint: str):
    url = urlsplit(endpoint)
    if url.scheme != "ws" or url.hostname not in ("127.0.0.1", "localhost", "::1") \
            or url.path not in ("", "/") or url.query or url.username \
            or url.password or url.fragment or not url.port:
        raise ValueError("VTube Studio inspection only connects to localhost WS")
    return endpoint


def _ask(connection, action: str, data: dict | None = None) -> dict:
    request = _envelope(action, data)
    connection.send(json.dumps(request))
    msg = json.loads(connection.recv(timeout=12))
    if msg.get("requestID") != request["requestID"]:
        raise RuntimeError("VTS response mismatched requestID")
    if msg.get("messageType") == "APIError":
        raise RuntimeError("VTS API refused " + action + ": " +
                           str((msg.get("data") or {}).get("message", "unknown")))
    if msg.get("messageType") != action.replace("Request", "Response"):
        raise RuntimeError("VTS unexpected message type for " + action)
    value = msg.get("data")
    if not isinstance(value, dict):
        raise RuntimeError("VTS response has no structured data")
    return value


def inspect_real_vts(*, expected_model3: str, output: Path,
                     endpoint: str = "ws://127.0.0.1:8001",
                     token: str, connector=None, samples: int = 4,
                     pause=None) -> dict:
    """Only active VTS instance counts. Tracks actual faceFound and model data."""
    if not isinstance(expected_model3, str) or not expected_model3.endswith(".model3.json"):
        raise ValueError("Require exact exported *.model3.json filename")
    if not 2 <= samples <= 12:
        raise ValueError("Require 2..12 real VTS samples")
    if not token:
        raise ValueError("Pass user-authorized VTS API token via environment")
    _local_ws(endpoint)
    from contextlib import closing
    if connector is None:
        from websockets.sync.client import connect
        connector = lambda uri: connect(uri, open_timeout=10, close_timeout=5)
    output = Path(output)
    output.mkdir(parents=True, exist_ok=True)
    with closing(connector(endpoint)) as connection:
        auth = _ask(connection, "AuthenticationRequest", {
            "pluginName": "Virtual Pipeline QA",
            "pluginDeveloper": "Virtual Pipeline",
            "authenticationToken": token,
        })
        if auth.get("authenticated") is not True:
            raise RuntimeError("VTS did not authenticate the QA session")
        model = _ask(connection, "CurrentModelRequest")
        if not model.get("modelLoaded") or model.get("live2DModelName") != expected_model3:
            raise RuntimeError("VTS is not running the specified model3.json")
        if model.get("numberOfLive2DArtmeshes", 0) < 2:
            raise RuntimeError("VTS model has too few real ArtMeshes")
        stats = _ask(connection, "StatisticsRequest")
        if not isinstance(stats.get("framerate"), (int, float)) \
                or not math.isfinite(stats["framerate"]) or stats["framerate"] <= 0:
            raise RuntimeError("VTS is not rendering frames")
        face = []
        for i in range(samples):
            found = _ask(connection, "FaceFoundRequest").get("found")
            if type(found) is not bool:
                raise RuntimeError("VTS tracking sensor report missing")
            face.append(found)
            if i != samples - 1:
                (pause or time.sleep)(0.5)
    report = {
        "schema": "vtuber/vts-real-running-app-acceptance-v1",
        "verified_vts_desktop_instance": True,
        "model3_name": model["live2DModelName"],
        "vts_model_id": model.get("modelID"),
        "actual_artmesh_count": model["numberOfLive2DArtmeshes"],
        "actual_parameter_count": model.get("numberOfLive2DParameters"),
        "actual_texture_pages": model.get("numberOfTextures"),
        "has_physics_file": model.get("hasPhysicsFile"),
        "vts_render_fps": stats["framerate"],
        "face_found_samples": face,
        "actual_tracking_face_detected": any(face),
        "actual_tracking_sustained_all_samples": all(face),
        "actual_parameter_motion_verified": False,
        "artistic_quality_verified": False,
        "ninety_degree_profile_verified": False,
        "read_only": True,
    }
    target = output / "vts_real_app_report.json"
    target.write_text(json.dumps(report, ensure_ascii=False, indent=2),
                      encoding="utf-8")
    if not all(face):
        raise RuntimeError("VTS_FACE_TRACKING_NOT_SUSTAINED: " + str(target))
    return report


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--expected-model3", required=True,
                        help="Filename matching loaded model in VTS, not a fake local preview")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--endpoint", default="ws://127.0.0.1:8001")
    parser.add_argument("--samples", type=int, default=4)
    args = parser.parse_args()
    token = os.environ.get("VTS_API_AUTH_TOKEN", "")
    result = inspect_real_vts(
        expected_model3=args.expected_model3, output=args.output,
        endpoint=args.endpoint, token=token, samples=args.samples)
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
