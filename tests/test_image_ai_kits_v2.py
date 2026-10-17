"""Published FACE-first source-art contracts (24 ZIPs, no body generation)."""
from zipfile import ZipFile
from tools.audit_24_image_kits import scan, ROOT, MODES, ASSETS, DOCUMENTS, expected_files


def test_all_24_face_first_source_only_zips_pass_semantic_audit():
    result = scan()
    assert result["kits"] == 24 and result["documents"] == 336
    assert result["blockers"] == 0, result["issues"]
    assert len(list(ROOT.glob("*.zip"))) == 24
    assert ASSETS == ("face", "hair", "outfit", "accessory")
    assert not list(ROOT.glob("*__body.zip"))


def test_shipped_artwork_file_names_and_scope_separation():
    for mode in MODES:
        for asset in ASSETS:
            with ZipFile(ROOT / f"{mode}__{asset}.zip") as archive:
                assert archive.testzip() is None
                assert set(archive.namelist()) == DOCUMENTS
                docs = {name: archive.read(name).decode("utf-8")
                        for name in archive.namelist()}
            master = docs["00_MASTER_FIRST.md"]
            output = docs["04_OUTPUT_FILES.md"]
            delivery = docs["00_DELIVERY_AND_RECHECK.md"]
            assert "SOURCE_ART_ONLY_V7" in master
            assert f"{mode}__{asset}__ARTWORK.zip" in delivery
            for image in expected_files(mode, asset):
                assert f"`{image}`" in output and f"`{image}`" in delivery
            assert "part_art/_order.txt" not in output
            assert "isolated_parts/" not in output
            if asset == "face":
                assert "FACE_ONLY_V1" in master
                assert "몸통" in master and "목" in master
                assert "expression_refs/mouth_open.png" in output if mode != "3d" else True
                assert "의상" in docs["03_MODE_RULES.md"]
            elif asset == "outfit":
                assert "OUTFIT_CLOTHED_BODY_V1" in master
                assert "양손" in master and "옷" in master
                assert "expression_refs/" not in output
            else:
                assert "ASSET_ONLY_V1" in master
                assert "expression_refs/" not in output


def test_readme_lists_exactly_new_face_kits():
    index = (ROOT.parent / "README.md").read_text(encoding="utf-8")
    for mode in MODES:
        assert f"zips/{mode}__body.zip" not in index
        for asset in ASSETS:
            assert f"zips/{mode}__{asset}.zip" in index
