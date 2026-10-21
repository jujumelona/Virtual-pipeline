"""Public art fixtures must be byte-verifiable, never fake quality."""
from io import BytesIO
import hashlib
import json
from zipfile import ZipFile
import pytest

from tools import vts_open_quality_cases as cases


def _fixture(members):
    buf = BytesIO()
    with ZipFile(buf, "w") as z:
        for path, data in members.items():
            z.writestr(path, data)
    return buf.getvalue()


def _catalog(monkeypatch, data):
    monkeypatch.setattr(cases, "CATALOG", {"test": {
        "url": "https://github.com/tsunehimatoi/psd2live-examples/releases/download/assets-v1/tml-1.0.0.zip",
        "sha256": hashlib.sha256(data).hexdigest(),
        "size": len(data), "license": "CC0-1.0", "purpose": "test"}})


def test_true_case_project_and_native_files_preserved(tmp_path, monkeypatch):
    data = _fixture({
        "case/project/main.psd2live": b"real-editable-format-fixture",
        "case/export/model.model3.json": b"{}",
        "case/export/model.moc3": b"MOC3example",
    })
    _catalog(monkeypatch, data)
    def fake(url, dest):
        dest.write_bytes(data)
    report = cases.fetch_case("test", tmp_path / "public", download=fake)
    assert report["license"] == "CC0-1.0"
    assert len(report["editable_projects"]) == 1
    assert len(report["native_models"]) == 1
    assert not report["runtime_quality_verified"]


def test_modified_external_archive_is_rejected(tmp_path, monkeypatch):
    clean = _fixture({"project/main.psd2live": b"original"})
    modified = _fixture({"project/main.psd2live": b"tampered"})
    _catalog(monkeypatch, clean)
    with pytest.raises(RuntimeError, match="SHA256_MISMATCH"):
        cases.fetch_case("test", tmp_path / "public",
                         download=lambda url, dest: dest.write_bytes(modified))


def test_zip_traversal_is_rejected_even_if_archive_sha_matches(tmp_path, monkeypatch):
    data = _fixture({"../escape.txt": b"bad",
                     "project/main.psd2live": b"original",
                     "export/model.model3.json": b"{}"})
    _catalog(monkeypatch, data)
    with pytest.raises(ValueError, match="UNSAFE_MEMBER"):
        cases.fetch_case("test", tmp_path / "public",
                         download=lambda url, dest: dest.write_bytes(data))
    assert not (tmp_path / "escape.txt").exists()
