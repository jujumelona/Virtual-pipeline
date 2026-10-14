"""Test mapping and preservation of existing 14 MD / read-first gates."""
from pathlib import Path
from zipfile import ZipFile
import json
import pytest

from tools import apply_existing_vtuber_template_slots as m


def synthetic_zip(tmp_path):
    path = tmp_path / "live2d_bust_up__body.zip"
    with ZipFile(path, "w") as z:
        for name in m.DOCS:
            if name in ("00_MASTER_FIRST.md", "00_READ_FIRST.md"):
                text = ("# [READ_ALL_BEFORE_IMAGE_GENERATION_V1]\n\n"
                        + m.READ_FIRST_END + f"# {name}\n")
            else:
                text = f"# {name}\n"
            z.writestr(name, text)
        for i in range(14 - len(m.DOCS)):
            z.writestr(f"other_{i}.md", "untouched")
    return path


def test_registry_maps_every_mode_and_asset():
    reg = m.load_registry()
    assert len(reg["templates"]) == 24
    for k, v in reg["templates"].items():
        assert v["source_ids"]
        assert v["required_slots"]
        assert "https://" in m.guidance(reg, k)


def test_existing_psd_and_presets_are_not_falsely_bundled():
    reg = m.load_registry()
    assert "NOT shipped" in reg["distribution_policy"]
    assert reg["sources"]["live2d_sd_guide"]["asset_format"] == "PSD"
    assert reg["sources"]["inochi_aka_psd"]["asset_format"].startswith("PSD")
    assert "3D" in reg["sources"]["vroid_presets"]["asset_format"]
    assert "forearm_L" in reg["templates"]["live2d_bust_up__body"]["required_slots"]
    assert "hand_R" in reg["templates"]["live2d_bust_up__body"]["required_slots"]
    assert "foot_R" in reg["templates"]["live2d_full__body"]["required_slots"]


def test_idempotence_and_read_first_preservation(tmp_path):
    file = synthetic_zip(tmp_path)
    reg = m.load_registry()
    assert m.apply(file, reg, write=True)
    assert not m.apply(file, reg, write=True)
    with ZipFile(file) as z:
        assert len(z.namelist()) == 14
        assert z.testzip() is None
        for name in ("00_READ_FIRST.md", "00_MASTER_FIRST.md"):
            text = z.read(name).decode()
            assert text.startswith("# [READ_ALL_BEFORE_IMAGE_GENERATION_V1]")
            assert text.index(m.READ_FIRST_END) < text.index(m.MARKER)


def test_dry_run_rejects_missing_guidance(tmp_path):
    file = synthetic_zip(tmp_path)
    before = file.read_bytes()
    with pytest.raises(ValueError, match="template slot guidance missing"):
        m.apply(file, m.load_registry(), write=False)
    assert file.read_bytes() == before


def test_partial_stale_sections_are_rejected(tmp_path):
    path = synthetic_zip(tmp_path)
    reg = m.load_registry()
    m.apply(path, reg, write=True)
    with ZipFile(path) as z:
        infos = z.infolist()
        values = {n: z.read(n).decode("utf-8") for n in z.namelist()}
    values["00_READ_FIRST.md"] = values["00_READ_FIRST.md"].replace(
        "슬롯 채우기:", "잘못 바꾼 슬롯:")
    with ZipFile(path, "w") as z:
        for info in infos:
            z.writestr(info, values[info.filename])
    with pytest.raises(ValueError, match="stale/mismatched"):
        m.apply(path, reg, write=True)


@pytest.mark.parametrize("asset", ("hair", "outfit", "accessory"))
def test_independent_asset_does_not_inherit_body_pose_or_missing_hands_gate(asset):
    registry = m.load_registry()
    for mode in m.MODES:
        generated = m.guidance(registry, f"{mode}__{asset}")
        assert "신체 전체를 새로 생성하지 않는다" in generated
        assert "신체·눈 제작을 요구하지 않는다" in generated
        assert "신체·눈·얼굴은 참조만 한다" in generated
        assert "missing required hands/arms" not in generated
        assert "Reject flat gray mannequin" not in generated
        assert "원본 캐릭터 완성 원화 생성" not in generated
        assert "정합 미검증" in generated
        if mode == "3d":
            assert "네이티브 VRM 완성은 약속하지 않는다" in generated
        else:
            assert "독립 PSD·PNG·마스크" in generated


def test_body_template_retains_anatomy_and_hand_validation():
    registry = m.load_registry()
    body = m.guidance(registry, "live2d_bust_up__body")
    assert "missing required hands/arms" in body
    assert "head to upper abdomen/waist" in body
