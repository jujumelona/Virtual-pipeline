"""Offline PSD2Live CLI -> validated native model -> final ZIP contracts."""
from __future__ import annotations

import json
from pathlib import Path
from zipfile import ZipFile

import pytest
from PIL import Image

from tools import vts_psd2live as bridge


def sample_model(dest: Path):
    dest.mkdir(parents=True, exist_ok=True)
    (dest / "avatar.moc3").write_bytes(b"MOC3" + bytes(64))
    Image.new("RGBA", (16, 16), (255, 0, 0, 255)).save(dest / "texture_00.png")
    (dest / "avatar.physics3.json").write_text("{}")
    (dest / "avatar.model3.json").write_text(json.dumps({
        "Version": 3, "FileReferences": {
            "Moc": "avatar.moc3", "Textures": ["texture_00.png"],
            "Physics": "avatar.physics3.json",
        },
    }))
    (dest / "avatar.cmo3").write_bytes(b"CMO3\x00")
    (dest / "avatar.psd2live").write_bytes(b"PK\x03\x04" + b"x" * 32)


def test_official_cli_free_atlas_and_model_bundle(monkeypatch, tmp_path):
    source = tmp_path / "source PSD" / "avatar.psd"
    source.parent.mkdir()
    source.write_bytes(b"8BPS" + bytes(64))
    root = tmp_path / "third party" / "psd2live"
    root.mkdir(parents=True)
    (root / "gradlew").write_text("#!/bin/sh\n")
    monkeypatch.setattr(bridge, "ensure_psd2live", lambda *a, **k: root)
    monkeypatch.setattr(bridge, "_java_env", lambda: {"JAVA_HOME": "/test/jdk21"})
    calls = []

    def execute(command, *, cwd, env, log_path, timeout_seconds):
        calls.append((command, cwd, env, log_path, timeout_seconds))
        assert command[1:3] == ["--no-daemon", "run"]
        assert "--atlas 2048" in command[3]
        assert "'source PSD'" not in command[3]  # quote the whole input path
        assert "'" in command[3]
        assert cwd == root
        assert env["JAVA_HOME"] == "/test/jdk21"
        sample_model(tmp_path / "model")
        Path(log_path).write_text("fake Gradle success")
        return 0

    target = tmp_path / "model"
    result = bridge.run_psd2live(
        source, target, edition="free", runner=execute, timeout_seconds=123)
    assert len(calls) == 1
    assert calls[0][-1] == 123
    assert result["runtime_references_valid"]
    assert result["runtime_execution_verified"] is False
    assert result["cubism_free_editor_limits_verified"] is False
    assert result["atlas_size"] == 2048
    assert len(result["cmo3"]) == 1
    archive = tmp_path / "original.zip"
    with ZipFile(archive, "w") as z:
        z.write(source, "avatar.psd")
    packaged = bridge.package_psd2live(result, archive, tmp_path / "final.zip")
    with ZipFile(packaged) as z:
        names = set(z.namelist())
        assert {"avatar.moc3", "avatar.model3.json", "avatar.physics3.json",
                "texture_00.png", "avatar.cmo3", "avatar.psd2live",
                "source_artwork/original.zip",
                "metadata/psd2live_bridge.json"} <= names
        meta = json.loads(z.read("metadata/psd2live_bridge.json"))
        assert meta["runtime_execution_verified"] is False


def test_missing_texture_rejects_false_success(tmp_path):
    sample_model(tmp_path / "bad")
    (tmp_path / "bad" / "texture_00.png").unlink()
    with pytest.raises(FileNotFoundError, match="missing or unsafe"):
        bridge.validate_psd2live_output(tmp_path / "bad")


def test_fake_moc3_rejects_false_success(tmp_path):
    sample_model(tmp_path / "bad")
    (tmp_path / "bad" / "avatar.moc3").write_bytes(b"FAKE")
    with pytest.raises(ValueError, match="signature"):
        bridge.validate_psd2live_output(tmp_path / "bad")


def test_stale_rigged_model_is_never_accepted(monkeypatch, tmp_path):
    psd = tmp_path / "avatar.psd"
    psd.write_bytes(b"8BPS" + bytes(64))
    sample_model(tmp_path / "output")
    with pytest.raises(RuntimeError, match="PSD2LIVE_OUTPUT_NOT_EMPTY"):
        bridge.run_psd2live(psd, tmp_path / "output", edition="free")


def test_nonzero_external_cli_does_not_yield_model(monkeypatch, tmp_path):
    psd = tmp_path / "avatar.psd"
    psd.write_bytes(b"8BPS" + bytes(64))
    root = tmp_path / "psd2live"
    root.mkdir()
    (root / "gradlew").write_text("stub")
    monkeypatch.setattr(bridge, "ensure_psd2live", lambda *a, **k: root)
    monkeypatch.setattr(bridge, "_java_env", lambda: {})
    with pytest.raises(RuntimeError, match="PSD2LIVE_CLI_FAILED"):
        bridge.run_psd2live(psd, tmp_path / "model", edition="pro",
                            runner=lambda *a, **k: 13)


def test_vendor_label_metadata_does_not_claim_cubism_free_validation(tmp_path):
    sample_model(tmp_path / "full")
    checked = bridge.validate_psd2live_output(tmp_path / "full")
    assert checked["cubism_free_editor_limits_verified"] is False
    assert checked["runtime_execution_verified"] is False


def test_free_character_exports_primary_psd2live_model_zip(monkeypatch, tmp_path):
    """Exercise production orchestration, not only the standalone bridge."""
    from psd_tools import PSDImage
    from psd_tools.api.layers import PixelLayer
    from tools import vts_production

    source = tmp_path / "source.png"
    Image.new("RGBA", (256, 384), (60, 80, 95, 255)).save(source)
    doc = PSDImage.new("RGB", (256, 384))
    face = Image.new("RGBA", (256, 384))
    hair = Image.new("RGBA", (256, 384))
    face.paste((100, 120, 150, 255), (48, 60, 160, 180))
    hair.paste((70, 30, 60, 255), (35, 25, 185, 70))
    PixelLayer.frompil(face, parent=doc, name="face")
    PixelLayer.frompil(hair, parent=doc, name="front hair")
    original = tmp_path / "existing.psd"
    doc.save(original)
    calls = []

    def fake_cli(psd, output, *, edition, third_party):
        calls.append((str(psd), edition))
        assert psd.name == "avatar.psd"
        assert edition == "free"
        sample_model(output)
        return {
            **bridge.validate_psd2live_output(output),
            "backend": "psd2live",
            "license": "GPL-3.0",
            "atlas_size": 2048,
        }
    monkeypatch.setattr(bridge, "run_psd2live", fake_cli)
    output = tmp_path / "final"
    report = vts_production.make_cubism_handoff(
        source, output, edition="free", scope="upper",
        external_psd=original, psd2live=True)
    assert len(calls) == 1
    assert report["state"] == "psd2live_rigged_unverified"
    assert report["moc3_generated"] is True
    assert report["editor_required"] is False
    assert Path(report["artwork_package"]).is_file()
    with ZipFile(report["package"]) as archive:
        names = archive.namelist()
        assert "avatar.model3.json" in names
        assert "avatar.moc3" in names
        assert "texture_00.png" in names
        assert any(name.startswith("source_artwork/") and name.endswith(".zip")
                   for name in names)
        assert "metadata/psd2live_bridge.json" in names


def test_autorig_failure_is_not_reported_as_success(monkeypatch, tmp_path):
    from psd_tools import PSDImage
    from psd_tools.api.layers import PixelLayer
    from tools import vts_production

    source = tmp_path / "source.png"
    Image.new("RGBA", (256, 384), (120, 125, 140, 255)).save(source)
    doc = PSDImage.new("RGB", (256, 384))
    first = Image.new("RGBA", (256, 384), (0, 0, 0, 0))
    second = Image.new("RGBA", (256, 384), (0, 0, 0, 0))
    first.paste((120, 130, 140, 255), (10, 10, 100, 100))
    second.paste((100, 120, 140, 255), (90, 20, 180, 160))
    PixelLayer.frompil(first, parent=doc, name="face")
    PixelLayer.frompil(second, parent=doc, name="hair.front")
    original = tmp_path / "original.psd"
    doc.save(original)

    def fail(*a, **k):
        raise RuntimeError("PSD2LIVE_CLI_FAILED simulated")
    monkeypatch.setattr(bridge, "run_psd2live", fail)
    output = tmp_path / "out"
    with pytest.raises(RuntimeError, match="PSD2LIVE_CLI_FAILED"):
        vts_production.make_cubism_handoff(
            source, output, edition="free", scope="upper",
            external_psd=original, psd2live=True)
    status = json.loads((output / "vts_status.json").read_text())
    assert status["state"] == "failed"
    assert status["moc3_generated"] is False
    assert not (output / "Live2D_PSD2Live_Rigged.zip").exists()
    assert any((output / "artwork").glob("*.zip"))


def test_colab_prepares_psd2live_and_uses_rigged_zip():
    notebook = (Path(__file__).resolve().parents[1] /
                "notebooks/VTuber_Commercial_Pipeline_Colab_v8.ipynb")
    data = json.loads(notebook.read_text(encoding="utf-8"))
    sources = ["".join(cell["source"]) for cell in data["cells"]
               if cell["cell_type"] == "code"]
    import ast
    for code in sources:
        ast.parse(code)
    setup = next(code for code in sources if "psd2live" in code and "--prepare" in code)
    production = next(code for code in sources if "report=make_cubism_handoff(" in code)
    assert "tools.vts_psd2live" in setup
    assert "psd2live=True" in production
    assert 'RESULT_FILE=report["package"]' in production
