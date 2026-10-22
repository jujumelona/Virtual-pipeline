"""Source audit: real case fixture required, no claimed model after inventory."""
from pathlib import Path
import json
import pytest
from tools import vts_cc0_source_layer_audit as audit

def test_roles_are_hints_only():
    assert audit.classify("eyeWhite-L")=="eyes"
    assert audit.classify("left sleeve big")=="cloth"
    assert audit.classify("bottomwear")=="cloth"
    assert audit.classify("neckwear")=="cloth"
    assert audit.classify("headwear 1")=="hair"
    assert audit.classify("back_hair")=="hair"
    assert audit.classify("unlabeled")=="other"

def test_nonexistent_case_dir_rejected(tmp_path):
    with pytest.raises(FileNotFoundError):
        audit.inspect_case("hiakari-inori",tmp_path/"out",
                           case_dir=tmp_path/"missing")

def test_real_local_inventory_never_claims_retargeted(tmp_path,monkeypatch):
    case=tmp_path/"case";case.mkdir()
    for p in ["hiakari_inori_layers_v3.psd",
              "hiakari_inori_layers_v3.psd2live",
              "hiakari_inori_layers_v3.model3.json"]:
        (case/p).write_bytes(b"actual-case-fixture")
    monkeypatch.setattr(audit,"summarize_psd",lambda p:{
        "psd":str(p),"canvas":[2048,3072],
        "independent_raster_layer_count":41,
        "role_counts_from_names_NOT_semantic_proof":{"eyes":8},
        "layers":[{"name":"irides-l"}]})
    r=audit.inspect_case("hiakari-inori",tmp_path/"report",case_dir=case)
    assert r["actual_psd_inventory"]["independent_raster_layer_count"]==41
    assert not r["real_psd2live_layer_ids_verified"]
    assert not r["native_rig_retargeted"]
    assert not r["edit_ready"]
    assert not r["download_report"]["archive_sha256_verified_this_run"]
    assert json.loads((tmp_path/"report"/"source_layer_audit.json").read_text())["mapping_status"]=="SOURCE_LAYER_INVENTORY_ONLY"
