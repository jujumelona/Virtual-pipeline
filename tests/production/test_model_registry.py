import re


def test_new_models_have_immutable_revisions_and_selective_files():
    from vtuber_pipeline.common.model_assets import model_pin
    for name in ('skytnt_anime_seg_isnet_is','florence2_base','sam2_1_hiera_large','flux2_klein_4b','instantmesh_large','depth_anything_v2_small'):
        pin=model_pin(name)
        assert re.fullmatch('[0-9a-f]{40}',pin['revision'])
        assert pin['allow_patterns']
    assert model_pin('instantmesh_large')['allow_patterns']==['instant_mesh_large.ckpt','diffusion_pytorch_model.bin','README.md']
    assert 'isnetis.onnx' not in model_pin('skytnt_anime_seg_isnet_is')['allow_patterns']


def test_common_2d_sam_download_and_worker_identity_use_large(monkeypatch, tmp_path):
    import json
    from pathlib import Path
    from vtuber_pipeline.common.model_assets import MODE_ASSETS, model_pin
    from vtuber_pipeline.perception import _worker
    assert "sam2_1_hiera_large" in MODE_ASSETS["common_2d"]
    observed = []
    def stage(**kwargs):
        observed.append(json.loads(Path(kwargs["request_json"]).read_text())["model_identity"])
        return {"status": "complete"}
    monkeypatch.setattr(_worker, "run_stage", stage)
    _worker.invoke("sam", {}, str(tmp_path))
    assert observed == [model_pin("sam2_1_hiera_large")]
    assert observed[0]["revision"] == "665f8e2ad61cf5f53d65644ff27c8ee525124610"
    assert observed[0]["allow_patterns"] == ["sam2.1_hiera_large.pt", "sam2.1_hiera_l.yaml", "README.md"]
