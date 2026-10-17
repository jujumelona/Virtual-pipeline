"""Eighteen source-art packages: one 2D FACE, 15 other 2D assets and 2 3D kits."""
from zipfile import ZipFile
from tools.audit_24_image_kits import scan, ROOT, MODES, ASSETS, TARGETS, DOCUMENTS, expected_files


def test_18_source_only_zips_pass_semantic_audit():
    result=scan()
    assert result["kits"] == 18 and result["documents"] == 252
    assert result["blockers"] == 0, result["issues"]
    assert len(list(ROOT.glob("*.zip"))) == 18
    assert ASSETS == ("hair","outfit","accessory")
    assert not list(ROOT.glob("*__body.zip"))
    assert not list(ROOT.glob("*__face.zip"))


def test_shared_face_and_scoped_artwork_instructions():
    for mode,asset in TARGETS:
        name="face" if mode=="face" else mode+"__"+asset
        with ZipFile(ROOT/(name+".zip")) as archive:
            assert archive.testzip() is None
            assert set(archive.namelist()) == DOCUMENTS
            docs={n:archive.read(n).decode("utf-8") for n in archive.namelist()}
        master=docs["00_MASTER_FIRST.md"]
        output=docs["04_OUTPUT_FILES.md"]
        delivery=docs["00_DELIVERY_AND_RECHECK.md"]
        assert "SOURCE_ART_ONLY_V7" in master
        assert name+"__ARTWORK.zip" in delivery
        for filename in expected_files(mode,asset):
            assert "`"+filename+"`" in output
            assert "`"+filename+"`" in delivery
        assert "isolated_parts/" not in output
        if mode=="face":
            assert "공통 FACE" in master
            assert "FACE_ONLY_V1" in master
            assert "expression_refs/mouth_open.png" in output
            assert "PRIMARY MASTER IMAGE PROMPT" in master
            assert "VTUBER_FACE_ART_QUALITY_V2" in master
            assert "12칸 컨택트시트" in master
            assert "고품질 애니 VTuber FACE 원화 필수" in master
            assert "하나라도 실패" in master
            assert "실제로 이 품질이 합격하기 전에는" in master
            assert "원시 도형 얼굴 금지" in docs["09_VISUAL_ART_QUALITY.md"]
            assert "90도" in docs["06_ADVANCED_OFFICIAL_COMMUNITY.md"] or "90°" in docs["06_ADVANCED_OFFICIAL_COMMUNITY.md"]
            assert "views/face_front.png" in output
            for framing in ("Live2D 방송 바스트업 / FACE", "Live2D 상반신 / FACE"):
                assert framing not in master
        elif asset=="character":
            assert "3D_COMPLETE_CHARACTER_FROM_2D_V1" in master
            assert "전신" in master and "옷" in master
        elif asset=="outfit":
            assert "OUTFIT_CLOTHED_BODY_V1" in master
            assert "양손" in master and "옷" in master
        else:
            assert "ASSET_ONLY_V1" in master


def test_readme_lists_shared_face_once_and_18_other_kits():
    index=(ROOT.parent/"README.md").read_text(encoding="utf-8")
    assert index.count("(zips/face.zip)") == 6  # one standalone link + five links to the SAME FACE ZIP
    for mode in MODES:
        assert f"zips/{mode}__face.zip" not in index
        assert f"zips/{mode}__body.zip" not in index
        allowed=("character","accessory") if mode=="3d" else ASSETS
        for asset in allowed:
            assert f"zips/{mode}__{asset}.zip" in index
    assert "FACE 열의 다섯 링크는 모두 동일한" in index
    assert "완성 캐릭터에 얼굴 포함" in index
    assert "zips/3d__hair.zip" not in index
    assert "zips/3d__outfit.zip" not in index
