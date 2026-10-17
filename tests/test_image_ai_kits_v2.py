"""Twenty-four finished-source instruction ZIPs match Colab's input contract."""
from zipfile import ZipFile
from tools.audit_24_image_kits import scan, ROOT, MODES, ASSETS, DOCUMENTS, expected_files

def test_24_source_only_zips_pass_semantic_audit():
    report=scan()
    assert report["kits"]==24 and report["documents"]==336
    assert report["blockers"]==0, report["issues"]
    assert len(list(ROOT.glob("*.zip")))==24

def test_generator_never_requires_individual_layers():
    for mode in MODES:
        for asset in ASSETS:
            with ZipFile(ROOT/(mode+"__"+asset+".zip")) as z:
                assert z.testzip() is None
                assert set(z.namelist())==DOCUMENTS
                docs={name:z.read(name).decode("utf8") for name in z.namelist()}
            master=docs["00_MASTER_FIRST.md"]
            output=docs["04_OUTPUT_FILES.md"]
            delivery=docs["00_DELIVERY_AND_RECHECK.md"]
            assert "SOURCE_ART_ONLY_V7" in master
            assert "Colab" in master
            assert mode+"__"+asset+"__ARTWORK.zip" in delivery
            for filename in expected_files(mode,asset):
                assert chr(96)+filename+chr(96) in output
                assert chr(96)+filename+chr(96) in delivery
            for obsolete in ("ART_SOURCE_AND_SEPARATION_V3",
                             "GPT_ARTWORK_SEGMENTER_HANDOFF_V5",
                             "MODE_ASSET_SEETHROUGH_V3_ROUTING_V6",
                             "ONE_PART_PER_GENERATION_V1",
                             "See-through V3","SemanticSam","part_art/_order.txt"):
                assert all(obsolete not in d for d in docs.values()), (mode,asset,obsolete)
            if mode=="3d":
                assert "outputs/master.png" not in output
                assert "views/"+asset+"_front.png" in output
            else:
                assert "outputs/master.png" in output
                assert "reference_views/" in output
                if asset=="body":
                    assert "expression_refs/mouth_open.png" in output
                else:
                    assert "expression_refs/" not in output

def test_body_palette_and_asset_pixel_boundaries():
    for mode in MODES:
        with ZipFile(ROOT/(mode+"__body.zip")) as z:
            body=z.read("00_MASTER_FIRST.md").decode("utf8")
        assert "FACE_SKIN_BASE=#F2D4BE" in body
        assert "얼굴·귀·두피·목·어깨·몸통·팔·손 기본색 통일" in body
        assert "머리카락·패션 의상·장신구를 그리지 않는다" in body
        for asset in ("hair","outfit","accessory"):
            with ZipFile(ROOT/(mode+"__"+asset+".zip")) as z:
                d=z.read("00_MASTER_FIRST.md").decode("utf8")
            assert "BODY" in d and "원화" in d

def test_readme_links_all_artwork_kits():
    index=(ROOT.parent/"README.md").read_text(encoding="utf8")
    for mode in MODES:
        for asset in ASSETS:
            assert "zips/"+mode+"__"+asset+".zip" in index
