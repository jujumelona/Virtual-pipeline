"""Reproduce the exact Colab 0.1.0 safetensors-vs-torch.load failure.

These tests use actual serialized safetensors tensors and verify BOTH upstream
loader aliases are replaced during construction, without unsafe pickle loading.
"""
from __future__ import annotations

import pickle
import sys
import types

import pytest

# The full CPU discovery suite intentionally excludes the 2+ GB PyTorch
# runtime. These actual-tensor tests run wherever torch+safetensors are
# available; the separate stdlib integration test checks alias rewiring.
torch = pytest.importorskip("torch")
safetensors_torch = pytest.importorskip("safetensors.torch")
save_file = safetensors_torch.save_file

import vtuber_pipeline.avatar.face_detector as face_detector


def _vendor(monkeypatch, create_detector):
    package = types.ModuleType("anime_face_detector")
    package.__path__ = []
    detector = types.ModuleType("anime_face_detector.detector")
    face = types.ModuleType("anime_face_detector._face")
    landmark = types.ModuleType("anime_face_detector._landmark")

    def old_pip_v010_loader(path):
        # Installed 0.1.0 behavior in the reported Colab traceback.
        raise pickle.UnpicklingError(
            "Weights only load failed: Unsupported operand 216"
        )

    detector.hf_hub_download = lambda *a, **k: "old-unpinned-downloader"
    face.load_state_dict_from_path = old_pip_v010_loader
    landmark.load_state_dict_from_path = old_pip_v010_loader
    package.detector = detector
    package._face = face
    package._landmark = landmark
    package.create_detector = create_detector
    for mod in (package, detector, face, landmark):
        monkeypatch.setitem(sys.modules, mod.__name__, mod)
    return detector, face, landmark, old_pip_v010_loader


def test_real_safetensors_loads_for_both_hrnet_and_yolo_without_pickle(
    monkeypatch, tmp_path,
):
    weights = {
        "hysts/anime-face-detector-yolov3": tmp_path / "23bbc708146bcbc1c910f00fe152adbc70d7658d875a0121eaf4ee61d978b2c4",
        "hysts/anime-face-detector-hrnetv2": tmp_path / "e71271376406a743c01528a0460637fcc06e72aeeea583f85007cc72dc8b7a4a",
    }
    save_file({"yolo.weight": torch.tensor([3.0])}, str(weights[
        "hysts/anime-face-detector-yolov3"
    ]))
    save_file({"hrnet.weight": torch.tensor([7.0])}, str(weights[
        "hysts/anime-face-detector-hrnetv2"
    ]))
    # Hugging Face caches store safetensors as extensionless SHA256 blobs.
    # That bypassed the upstream '.safetensors' suffix check as well.
    assert all(not path.suffix for path in weights.values())
    paths = {name: str(path) for name, path in weights.items()}
    monkeypatch.setattr(
        face_detector, "resolve_anime_face_model_paths", lambda: paths,
    )

    observed = {}

    def create_detector(name):
        assert name == "yolov3"
        yolo_path = detector.hf_hub_download(
            "hysts/anime-face-detector-yolov3", "model.safetensors",
        )
        hrnet_path = detector.hf_hub_download(
            "hysts/anime-face-detector-hrnetv2", "model.safetensors",
        )
        observed["yolo"] = face.load_state_dict_from_path(yolo_path)
        observed["hrnet"] = landmark.load_state_dict_from_path(hrnet_path)
        return object()

    detector, face, landmark, old_loader = _vendor(monkeypatch, create_detector)
    old_download = detector.hf_hub_download

    def refuse_pickle(*args, **kwargs):
        raise AssertionError("torch.load must not be used for safetensors")

    monkeypatch.setattr(torch, "load", refuse_pickle)
    model = face_detector._create_pinned_anime_face_detector()
    assert model is not None
    assert float(observed["yolo"]["yolo.weight"][0]) == 3.0
    assert float(observed["hrnet"]["hrnet.weight"][0]) == 7.0
    assert face.load_state_dict_from_path is old_loader
    assert landmark.load_state_dict_from_path is old_loader
    assert detector.hf_hub_download is old_download


def test_nonverified_checkpoint_is_refused_and_vendor_is_restored(
    monkeypatch, tmp_path,
):
    pinned = tmp_path / "pinned.safetensors"
    other = tmp_path / "unverified.safetensors"
    save_file({"w": torch.tensor([1.0])}, str(pinned))
    save_file({"w": torch.tensor([2.0])}, str(other))
    monkeypatch.setattr(face_detector, "resolve_anime_face_model_paths", lambda: {
        "hysts/anime-face-detector-yolov3": str(pinned),
    })

    def create_detector(_name):
        face.load_state_dict_from_path(str(other))

    detector, face, landmark, old_loader = _vendor(monkeypatch, create_detector)
    with pytest.raises(RuntimeError, match="Unverified anime-face checkpoint"):
        face_detector._create_pinned_anime_face_detector()
    assert face.load_state_dict_from_path is old_loader
    assert landmark.load_state_dict_from_path is old_loader


def test_real_checkpoint_code_never_allows_unsafe_pickle_fallback():
    from pathlib import Path

    source = (
        Path(__file__).resolve().parents[2]
        / "vtuber_pipeline/avatar/face_detector.py"
    ).read_text(encoding="utf-8")
    assert 'from safetensors.torch import load_file' in source
    assert "weights_only=False" not in source.replace(
        "do not use unsafe weights_only=False", ""
    )
    assert 'patch.object(face_module, "load_state_dict_from_path"' in source
    assert 'patch.object(landmark_module, "load_state_dict_from_path"' in source
