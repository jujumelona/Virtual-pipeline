"""Mandatory real-model Colab compatibility smoke; NO mocks, NO skips.

Run with the same Python minor and pinned dependency versions as the Colab
notebook. On GitHub CPU runners, explicitly select CPU. GPU inference remains
an independently reported requirement, never implied by this smoke.
"""
from __future__ import annotations

import argparse
import importlib.metadata
import os
import pathlib
import subprocess
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
    parser.add_argument("--triposr-load", action="store_true")
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

        if args.triposr_load:
            # The official pinned TripoSR checkout is a mandatory prerequisite.
            # Exercise actual OmegaConf, DINO ViT config, checkpoint loading,
            # and model construction, not just downloaded model.sha256.
            from vtuber_pipeline.avatar.reconstruction import TRIPOSR_PINNED_COMMIT
            from vtuber_pipeline.avatar.triposr_runner import _install_hf_revision_guard
            from vtuber_pipeline.avatar.marching_cubes_backend import (
                install_triposr_marching_cubes,
            )

            repo = pathlib.Path(
                os.environ.get("TRIPOSR_DIR", "/tmp/vtuber-ci-triposr")
            ).resolve()
            result = subprocess.run(
                ["git", "-C", str(repo), "rev-parse", "HEAD"],
                check=True, capture_output=True, text=True, timeout=20,
            )
            actual_commit = result.stdout.strip()
            assert actual_commit == TRIPOSR_PINNED_COMMIT, (
                actual_commit, TRIPOSR_PINNED_COMMIT
            )
            # Crucial: production executes upstream run.py via runpy,
            # unlike direct imports done by the old model-only CI path.
            # This failed on Colab with ModuleNotFoundError: tsr.
            def verify_real_subprocess_import():
                runner = (
                    pathlib.Path(__file__).resolve().parents[1]
                    / "vtuber_pipeline/avatar/triposr_runner.py"
                )
                command = [
                    sys.executable, "-u", str(runner), str(repo / "run.py"),
                    "--no-remove-bg", "--help",
                ]
                env = os.environ.copy()
                env.pop("VTUBER_REQUIRE_CUDA", None)
                result = subprocess.run(
                    command, cwd=str(repo), env=env, text=True,
                    capture_output=True, timeout=120,
                )
                if result.returncode != 0:
                    raise RuntimeError(
                        f"Production TripoSR wrapper exited {result.returncode}:\\n"
                        f"{result.stdout}\\n{result.stderr}"
                    )
                assert "usage:" in result.stdout.lower(), result.stdout
                assert "[TripoSR] source import root:" in result.stdout
                return result

            report(
                "real pinned TripoSR production runner CLI subprocess tsr import",
                verify_real_subprocess_import,
            )
            sys.path.insert(0, str(repo))
            install_triposr_marching_cubes()
            _install_hf_revision_guard()
            from tsr.system import TSR

            # Release the other large networks before allocating TSR's params.
            import gc
            del detector
            gc.collect()

            def load_actual_triposr():
                model = TSR.from_pretrained(
                    str(model_dir), config_name="config.yaml",
                    weight_name="model.ckpt",
                )
                model.to(args.device)
                assert model.backbone is not None
                assert model.image_tokenizer is not None
                assert model.decoder is not None
                return model

            triposr = report(
                "real TripoSR backbone and checkpoint initialization",
                load_actual_triposr,
            )
            print(
                "[REAL-MODEL] TripoSR checkpoint strict loading PASS",
                flush=True,
            )
            # Execute the actual TripoSR DINO -> transformer -> triplane
            # compute graph even on a CPU-only GitHub runner. Loading a
            # checkpoint alone misses shape/device/attention failures.
            if args.device == "cpu":
                torch.set_num_threads(min(4, os.cpu_count() or 1))
            rgb = Image.new("RGB", (128, 128), (160, 160, 160))
            with torch.inference_mode():
                codes = report(
                    f"real TripoSR {args.device} neural forward",
                    lambda: triposr([rgb], device=args.device),
                )
            assert codes.numel() > 0 and torch.isfinite(codes).all()
            print(
                f"[REAL-MODEL] TripoSR scene codes shape={tuple(codes.shape)}",
                flush=True,
            )
            del codes
            del triposr
            gc.collect()

            # The prior smoke called TSR directly, bypassing CLI bootstrap,
            # mesh extraction and export. Exercise the exact production wrapper
            # with a real image from the immutable upstream checkout.
            import tempfile

            def run_actual_cli_mesh():
                sample = repo / "examples" / "police_woman.png"
                assert sample.is_file(), sample
                with tempfile.TemporaryDirectory(prefix="vtuber-real-cli-") as folder:
                    out = pathlib.Path(folder)
                    (out / "0").mkdir()
                    command = [
                        sys.executable, "-u", str(
                            pathlib.Path(__file__).resolve().parents[1]
                            / "vtuber_pipeline/avatar/triposr_runner.py"
                        ),
                        str(repo / "run.py"), str(sample),
                        "--output-dir", str(out),
                        "--pretrained-model-name-or-path", str(model_dir),
                        "--no-remove-bg",
                        "--mc-resolution", "32",
                        "--chunk-size", "2048",
                        "--device", args.device,
                    ]
                    env = os.environ.copy()
                    if args.device == "cuda:0":
                        env["VTUBER_REQUIRE_CUDA"] = "1"
                    else:
                        env.pop("VTUBER_REQUIRE_CUDA", None)
                    proc = subprocess.run(
                        command, cwd=str(repo), env=env,
                        capture_output=True, text=True, timeout=360,
                    )
                    if proc.returncode != 0:
                        raise RuntimeError(
                            f"Actual production CLI failed (exit={proc.returncode}):\\n"
                            f"{proc.stdout}\\n{proc.stderr}"
                        )
                    mesh = out / "0" / "mesh.obj"
                    assert mesh.is_file() and mesh.stat().st_size > 0, (
                        f"Missing produced OBJ mesh. stdout={proc.stdout} "
                        f"stderr={proc.stderr}"
                    )
                    loaded_mesh = trimesh.load(mesh, process=False)
                    assert len(loaded_mesh.vertices) > 0
                    assert len(loaded_mesh.faces) > 0
                    print(
                        f"[REAL-MODEL] Produced OBJ bytes={mesh.stat().st_size} "
                        f"vertices={len(loaded_mesh.vertices)} "
                        f"faces={len(loaded_mesh.faces)}",
                        flush=True,
                    )

                    # Downstream rigid fit used to fail in Colab AFTER a
                    # successful real TripoSR mesh. Exercise the actual
                    # pinned MakeHuman template against this actual OBJ with
                    # 28 deterministic pixel landmarks. This verifies the
                    # numeric fitting graph, not facial-semantic correctness.
                    from vtuber_pipeline.avatar.template_fitting import fit_template
                    from PIL import Image as PILImage

                    width, height = PILImage.open(sample).size
                    pixel_landmarks = [
                        [
                            0.5 * width + 0.055 * width * float(np.cos(i * 2 * np.pi / 28)),
                            0.30 * height + 0.065 * height * float(np.sin(i * 2 * np.pi / 28)),
                        ]
                        for i in range(28)
                    ]
                    fitting = report(
                        "real MakeHuman to TripoSR OBJ rigid/nonrigid template fitting",
                        lambda: fit_template(
                            str(template), pixel_landmarks,
                            str(out / "template_fit"),
                            reference_mesh_path=str(mesh),
                        ),
                    )
                    if fitting["status"] != "complete":
                        raise RuntimeError(f"Real production template fitting failed: {fitting}")
                    fitted = pathlib.Path(fitting["fitted_mesh"])
                    assert fitted.is_file() and fitted.stat().st_size > 0
                    fitted_mesh = trimesh.load(fitted, force="mesh")
                    assert len(fitted_mesh.vertices) > 0
                    assert np.isfinite(fitted_mesh.vertices).all()
                    assert fitting.get("sparse_solve_success") is True
                    assert fitting["rigid_selected_energy"] <= fitting["rigid_initial_energy"] + 1e-10
                    print(
                        "[REAL-MODEL] Fitted canonical GLB "
                        f"vertices={len(fitted_mesh.vertices)} "
                        f"rigid_converged={fitting['converged']} "
                        f"mesh_bytes={fitted.stat().st_size}",
                        flush=True,
                    )

            report(
                "real production TripoSR subprocess full mesh extraction/export",
                run_actual_cli_mesh,
            )

    if args.device == "cuda:0":
        assert torch.cuda.memory_allocated(0) > 0, "GPU smoke allocated no CUDA memory"
        print(
            f"[REAL-MODEL] CUDA allocated={torch.cuda.memory_allocated(0)} bytes",
            flush=True,
        )
    print("[REAL-MODEL] PASS all requested real model checks", flush=True)


if __name__ == "__main__":
    main()
