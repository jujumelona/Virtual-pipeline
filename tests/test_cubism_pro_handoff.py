"""Cubism PRO handoff must preserve real source art and never claim rigging."""
import json
import struct
from zipfile import ZipFile

import pytest

from tools.vts_cubism_pro import build_cubism_pro_handoff
from tools.rebuild_cubism_pro_zips import transform_zip


def _psd(width=1536, height=2304):
    # Valid minimal PSD header; intentionally no layer data (never art-certified).
    return b"8BPS" + struct.pack(">H", 1) + bytes(6) + struct.pack(
        ">HIIHH", 4, height, width, 8, 3
    )


def test_pro_bundle_preserves_psd_source_art_and_correct_status(tmp_path):
    source = tmp_path / "artwork.zip"
    with ZipFile(source, "w") as archive:
        archive.writestr("avatar.psd", _psd())
        archive.writestr("preview/composite.png", b"real-image-placeholder")
        archive.writestr("qa/source.json", '{"approved":false}')
    output = tmp_path / "pro.zip"
    result = build_cubism_pro_handoff(source, output, frame="upper")
    assert result["editor_required"]
    assert not result["moc3_generated"]
    assert not result["native_runtime_verified"]
    with ZipFile(output) as archive:
        assert archive.testzip() is None
        assert archive.read("avatar.psd") == _psd()
        assert archive.read("artwork/preview/composite.png") == b"real-image-placeholder"
        assert archive.read("artwork/qa/source.json") == b'{"approved":false}'
        plan = json.loads(archive.read("cubism_pro/rig_transfer_plan.json"))
        assert plan["template_applied"] is False
        assert plan["psd_header"]["width"] == 1536
        assert plan["psd_header"]["layer_structure_verified"] is False
        assert plan["source_artwork_members"] == [
            "preview/composite.png", "qa/source.json"
        ]
        assert not any(x.endswith((".moc3", ".cmo3")) for x in archive.namelist())


def test_pro_bundle_prefers_avatar_psd_and_preserves_other_psd(tmp_path):
    source = tmp_path / "source.zip"
    with ZipFile(source, "w") as archive:
        archive.writestr("source_psd/old.psd", _psd(1000, 1000))
        archive.writestr("avatar.psd", _psd(1536, 2304))
    output = tmp_path / "pro.zip"
    build_cubism_pro_handoff(source, output)
    with ZipFile(output) as archive:
        assert archive.read("avatar.psd") == _psd(1536, 2304)
        assert archive.read("artwork/source_psd/old.psd") == _psd(1000, 1000)


def test_pro_rejects_ambiguous_psds_and_bogus_files(tmp_path):
    source = tmp_path / "source.zip"
    with ZipFile(source, "w") as archive:
        archive.writestr("other1.psd", _psd())
        archive.writestr("other2.psd", _psd())
    with pytest.raises(ValueError, match="AMBIGUOUS_PSD"):
        build_cubism_pro_handoff(source, tmp_path / "pro.zip")
    assert not (tmp_path / "pro.zip").exists()
    with ZipFile(source, "w") as archive:
        archive.writestr("avatar.psd", b"FAKE" + bytes(64))
    with pytest.raises(ValueError, match="PSD_HEADER_INVALID"):
        build_cubism_pro_handoff(source, tmp_path / "bad.zip")


def test_pro_rejects_duplicate_and_path_traversal(tmp_path):
    source = tmp_path / "source.zip"
    with ZipFile(source, "w") as archive:
        archive.writestr("avatar.psd", _psd())
        archive.writestr("../escape.png", b"bad")
    with pytest.raises(ValueError, match="UNSAFE_ZIP_MEMBER"):
        build_cubism_pro_handoff(source, tmp_path / "out.zip")


def test_template_script_idempotent_and_keeps_14_files(tmp_path):
    source = tmp_path / "live2d_upper__hair.zip"
    with ZipFile(source, "w") as archive:
        for i, name in enumerate((
            "00_MASTER_FIRST.md", "00_DELIVERY_AND_RECHECK.md",
            "00_READ_FIRST.md", "01_COMMON_RULES.md", "02_ADVANCED_PARTS.md",
            "03_MODE_RULES.md", "04_OUTPUT_FILES.md",
            "05_OFFICIAL_REFERENCES.md", "06_ADVANCED_OFFICIAL_COMMUNITY.md",
            "07_REVIEW_BEFORE_FINAL_ZIP.md", "08_PRACTICAL_TIPS.md",
            "09_VISUAL_ART_QUALITY.md", "10_ANIME_STYLE.md",
            "11_OFFICIAL_IMAGE_EXAMPLES.md",
        )):
            archive.writestr(name, "【SEE_THROUGH_ONLY_2D_V1】\n"
                                     + f"original_{i}\n")
    assert transform_zip(source)
    first = source.read_bytes()
    assert not transform_zip(source), "second ZIP build must be byte-for-byte stable"
    assert source.read_bytes() == first
    with ZipFile(source) as archive:
        assert archive.testzip() is None
        assert len(archive.namelist()) == 14
        assert "CUBISM_PRO_TEMPLATE_FIRST_V1" in archive.read("00_MASTER_FIRST.md").decode()
        assert b"original_0" in archive.read("00_MASTER_FIRST.md")
