"""Mandatory real-model Colab compatibility smoke; NO mocks, NO skips.

Run with the same Python minor and pinned dependency versions as the Colab
notebook. On GitHub CPU runners, explicitly select CPU. GPU inference remains
an independently reported requirement, never implied by this smoke.
"""
from __future__ import annotations

import argparse
import importlib.metadata
import pathlib
import sys
import time


def report(stage: str, action):
    start = time.monotonic()
    print(f"[REAL-MODEL] START {stage}", flush=True)
    try:
        result = action()
    except Exception:
        print(f"[REAL-MODEL] FAIL {stage}", flush=True)
        raise
    print(f"[REAL-MODEL] PASS {stage} elapsed={time.monotonic()-start:.2f}s", flush=True)
    return result


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--device", choices=["cpu", "cuda:0"], required=True)
    parser.add_argument("--all-assets", action="store_true")
    args = parser.parse_args()

    import numpy as np
    import torch
    import torchvision
    import cv2
    from PIL import Image

    print(
        f"[REAL-MODEL] Python={sys.version.split()[0]} torch={torch.__version__} "
        f"torchvision={torchvision.__version__} cv2={cv2.__version__} "
        f"device={args.device}",
        flush=True,
    )
    assert importlib.metadata.version("anime-face-detector") == "0.1.0"
    if args.device == "cuda:0":
        assert torch.cuda.is_available(), "CUDA GPU runner is REQUIRED, not emulated"
        print(f"[REAL-MODEL] GPU={torch.cuda.get_device_name(0)}", flush=True)

    from vtuber_pipeline.avatar.face_detector import (
        ANIME_FACE_MODEL_PINS,
        _create_pinned_anime_face_detector,
        _sha256_file,
        resolve_anime_face_model_paths,
    )

    weights = report("pinned YOLO/HRNet downloads and integrity", resolve_anime_face_model_paths)
    assert set(weights) == set(ANIME_FACE_MODEL_PINS)
    for name, location in weights.items():
        path = pathlib.Path(location)
        assert path.is_file() and path.stat().st_size > 0
        assert _sha256_file(path) == ANIME_FACE_MODEL_PINS[name]["sha256"]
        print(
            f"[REAL-MODEL] VERIFIED {name} bytes={path.stat().st_size} "
            f"sha256={ANIME_FACE_MODEL_PINS[name]['sha256']}",
            flush=True,
        )

    # Construct BOTH real networks using actual released weight bytes.
    # This is exactly the previously missing check that hid Unsupported operand 216.
    detector = report(
        "actual YOLOv3 + HRNetV2 strict checkpoint initialization",
        lambda: _create_pinned_anime_face_detector(device=args.device),
    )
    assert detector.face_detector is not None
    assert detector.landmark_detector is not None
    detector.flip_test = False

    # Exercise actual YOLO neural network forward, regardless of detections.
    # A synthetic image is not expected to be recognized as a real face.
    image = np.full((256, 256, 3), 160, dtype=np.uint8)
    raw_boxes = report(
        "real YOLOv3 network forward",
        lambda: detector.face_detector.detect(image),
    )
    assert isinstance(raw_boxes, np.ndarray), type(raw_boxes)
    assert raw_boxes.ndim == 2 and raw_boxes.shape[1] == 5, raw_boxes.shape
    assert np.isfinite(raw_boxes).all()

    # Exercise actual HRNet neural network forward with a supplied face box.
    # This tests 28 scored points without relying on fabricated face detection.
    box = np.array([40, 40, 220, 220, 0.99], dtype=np.float32)
    predictions = report(
        "real HRNet landmark neural network forward",
        lambda: detector(image, boxes=[box]),
    )
    assert len(predictions) == 1, len(predictions)
    landmark = np.asarray(predictions[0]["keypoints"])
    assert landmark.shape == (28, 3), landmark.shape
    assert np.isfinite(landmark).all()
    print(f"[REAL-MODEL] 28 real keypoints shape={landmark.shape}", flush=True)

    if args.all_assets:
        # The same resolver used by Colab checks every real file, not just
        # fake fixtures: TripoSR, u2net, DINO, and MakeHuman.
        from vtuber_pipeline.avatar.reconstruction import resolve_triposr_model
        from vtuber_pipeline.avatar.triposr_runner import (
            DINO_MODEL_ID,
            DINO_MODEL_REVISION,
            _verify_rembg_u2net,
        )
        from vtuber_pipeline.avatar.template_mesh import get_template_path
        from huggingface_hub import hf_hub_download
        import onnxruntime as ort
        import trimesh

        model_dir = pathlib.Path(report("TripoSR model bytes/config", resolve_triposr_model))
        assert (model_dir / "model.ckpt").is_file()
        onnx = report("u2net download and hash", _verify_rembg_u2net)
        def verify_onnx():
            session = ort.InferenceSession(
                onnx, providers=["CPUExecutionProvider"]
            )
            assert session.get_inputs() and session.get_outputs()
        report("u2net actual ONNX runtime initialization", verify_onnx)

        dino = report(
            "pinned DINO configuration",
            lambda: hf_hub_download(
                DINO_MODEL_ID, filename="config.json",
                revision=DINO_MODEL_REVISION,
            ),
        )
        assert pathlib.Path(dino).is_file()
        template = pathlib.Path(report("MakeHuman template", get_template_path))
        scene = report("MakeHuman actual trimesh load", lambda: trimesh.load(template))
        assert scene is not None

    if args.device == "cuda:0":
        assert torch.cuda.memory_allocated(0) > 0, "GPU smoke allocated no CUDA memory"
        print(
            f"[REAL-MODEL] CUDA allocated={torch.cuda.memory_allocated(0)} bytes",
            flush=True,
        )
    print("[REAL-MODEL] PASS all requested real model checks", flush=True)


if __name__ == "__main__":
    main()
