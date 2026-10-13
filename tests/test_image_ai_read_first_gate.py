"""Read-first gate contract tests; no image inference or image generation."""
from pathlib import Path
from zipfile import ZipFile
import importlib.util
import pytest

FILE = Path(__file__).resolve().parents[1] / "tools/image_ai_read_first_gate.py"
spec = importlib.util.spec_from_file_location("image_ai_gate", FILE)
assert spec and spec.loader
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)


def example(tmp_path):
    path = tmp_path / "live2d_bust_up__body.zip"
    with ZipFile(path, "w") as z:
        for name in m.DOC_NAMES:
            text = "# " + name + "\n"
            if name == "05_OFFICIAL_REFERENCES.md":
                text += "[guide](https://example.com/guide)\n"
            if name == "11_OFFICIAL_IMAGE_EXAMPLES.md":
                text += "![picture](https://example.com/art.png)\n"
            z.writestr(name, text)
    return path


def test_no_generation_before_all_documents_have_gate(tmp_path):
    path = example(tmp_path)
    before = path.read_bytes()
    with pytest.raises(ValueError, match="Missing read-first gate"):
        m.patch(path, write=False)
    assert before == path.read_bytes()


def test_gate_in_all_priority_docs_and_idempotent(tmp_path):
    path = example(tmp_path)
    assert m.patch(path, write=True)
    data = path.read_bytes()
    assert not m.patch(path, write=True)
    assert path.read_bytes() == data
    with ZipFile(path) as z:
        assert z.testzip() is None
        assert len(z.namelist()) == 14
        for name in m.PRIORITY:
            content = z.read(name).decode("utf-8")
            assert content.startswith("# [READ_ALL_BEFORE_IMAGE_GENERATION_V1]")
            assert "이미지 생성·수정 도구를 호출하지 않는다" in content


def test_reference_manifest_and_document_hashes(tmp_path):
    path = example(tmp_path)
    m.patch(path, write=True)
    result = m.manifest(path)
    assert len(result["documents"]) == 14
    assert result["reference_urls"] == [
        "https://example.com/art.png", "https://example.com/guide"]


def test_missing_image_observations_fail_closed(tmp_path):
    path = example(tmp_path)
    m.patch(path, write=True)
    expected = m.manifest(path)
    evidence = {**expected, "references": {}, "conflicts_resolved": True,
                "art_direction": "approved"}
    with pytest.raises(ValueError, match="observations incomplete"):
        m.verify_evidence(path, evidence)
    evidence["references"] = {url: {"status": "unavailable"}
                              for url in expected["reference_urls"]}
    with pytest.raises(ValueError, match="actionable reason"):
        m.verify_evidence(path, evidence)


def test_approved_record_not_misrepresented_as_image_proof(tmp_path):
    path = example(tmp_path)
    m.patch(path, write=True)
    info = m.manifest(path)
    evidence = {**info, "references": {
        u: {"status": "visually_reviewed",
            "observed_details": "visible stylized anime eyes with soft face and complete neck"}
        for u in info["reference_urls"]},
        "conflicts_resolved": True, "art_direction": "broadcast waist-up"}
    assert m.verify_evidence(path, evidence)["status"] == "EVIDENCE_RECORD_COMPLETE_NOT_PIXEL_PROOF"
    evidence["documents"]["00_MASTER_FIRST.md"] = "0" * 64
    with pytest.raises(ValueError, match="14 MD"):
        m.verify_evidence(path, evidence)


def test_invalid_missing_members_is_rejected_without_output(tmp_path):
    path = tmp_path / "live2d_bust_up__body.zip"
    with ZipFile(path, "w") as z:
        z.writestr("00_MASTER_FIRST.md", "text")
    with pytest.raises(ValueError, match="14-MD"):
        m.patch(path, write=True)



def test_existing_psd_template_urls_are_mandatory_visual_references():
    docs = {
        "00_MASTER_FIRST.md": (
            "## [EXISTING_VTUBER_TEMPLATE_SLOTS_V1]\n"
            "[official Boy PSD](https://example.com/templates/boy.psd)\n"
        ),
        "00_READ_FIRST.md": (
            "## [EXISTING_VTUBER_TEMPLATE_SLOTS_V1]\n"
            "[outfit sample](https://example.com/templates/outfit.psd)\n"
        ),
        "05_OFFICIAL_REFERENCES.md": (
            "[official guidance](https://example.com/how-to)\n"
        ),
    }
    urls = m.references(docs)
    assert urls == [
        "https://example.com/how-to",
        "https://example.com/templates/boy.psd",
        "https://example.com/templates/outfit.psd",
    ]



def test_optional_public_reference_outage_with_alternative_visual_observations(tmp_path):
    path = example(tmp_path)
    m.patch(path, write=True)
    info = m.manifest(path)
    first, second = info["reference_urls"]
    evidence = {
        **info,
        "references": {
            first: {"status": "visually_reviewed", "observed_details": "Actual anime eyes, nose, neck and shoulders visibly inspected."},
            second: {"status": "unavailable", "reason": "Download server refused request and file could not be inspected."},
        },
        "conflicts_resolved": True,
        "art_direction": "new original six-head anime vtuber with existing public references",
    }
    with pytest.raises(ValueError, match="fewer than required"):
        m.verify_evidence(path, evidence)
    evidence["references"][second] = {
        "status": "visually_reviewed",
        "observed_details": "Actually observed anime body proportions and independent eye layer chart.",
    }
    assert m.verify_evidence(path, evidence)["visually_reviewed"] == 2


def test_template_registry_does_not_force_user_psd():
    from tools import apply_existing_vtuber_template_slots as slots
    registry = slots.load_registry()
    assert len(registry["templates"]) == 24
    for record in registry["templates"].values():
        assert record["require_uploaded_user_psd"] is False
        assert "original_master" in record["no_user_psd_fallback"]
        assert "user_owned_layered_template_file" not in record["required_source_before_generation"]
