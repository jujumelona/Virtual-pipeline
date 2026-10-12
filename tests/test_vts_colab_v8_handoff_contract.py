"""Live2D Colab v8 must call the real artwork builder, not claim fake rigging."""
import ast
import json
from pathlib import Path
import sys
from types import ModuleType
from zipfile import ZipFile

import pytest


NOTEBOOK = Path(__file__).resolve().parents[1] / "notebooks/VTuber_Commercial_Pipeline_Colab_v8.ipynb"


def _load_cells():
    nb = json.loads(NOTEBOOK.read_text(encoding="utf-8"))
    cells = ["".join(cell["source"]) for cell in nb["cells"] if cell["cell_type"] == "code"]
    for code in cells:
        ast.parse(code)
    return cells


def test_colab_live2d_handoff_has_uploaded_inputs_and_real_builder():
    cells = _load_cells()
    combined = "\n".join(cells)
    assert len(cells) >= 9
    for required in (
        "files.upload()", "files.download(", "prepare_large_ai_pack(",
        "make_cubism_handoff(", "psd2live=False", "preserve_supplied_parts=",
        "reference_image=REFERENCE_FILE", "archive.testzip()",
        "preview/pro_body_asset_overlay.png",
    ):
        assert required in combined, required
    assert "실제 시각 품질, 가림 복원, Cubism Editor 동작: 미검증" in combined


def test_pro_reference_same_filename_preserves_both_uploads(tmp_path, monkeypatch):
    """A body PNG with the same name must never overwrite the asset PNG."""
    cell = next(c for c in _load_cells() if "#@title ⑥ 실제 파일 업로드" in c)
    cell = cell.replace('"/content/live2d_handoff"', repr(str(tmp_path)))
    google = ModuleType("google")
    colab = ModuleType("google.colab")
    files = ModuleType("google.colab.files")
    received = iter([{"shared.png": b"asset-pixels"}, {"shared.png": b"body-pixels"}])
    files.upload = lambda: next(received)
    colab.files = files
    google.colab = colab
    monkeypatch.setitem(sys.modules, "google", google)
    monkeypatch.setitem(sys.modules, "google.colab", colab)
    monkeypatch.setitem(sys.modules, "google.colab.files", files)
    state = {"INPUT_KIND": "single_image", "EDITION": "pro", "ASSET": "hair"}
    exec(compile(cell, "cell-6", "exec"), state)
    asset, body = state["INPUT_FILE"], state["REFERENCE_FILE"]
    assert asset != body
    assert asset.read_bytes() == b"asset-pixels"
    assert body.read_bytes() == b"body-pixels"
    assert asset.parent.name == "input" and body.parent.name == "reference"


@pytest.mark.parametrize("missing_mask", [False, True])
def test_colab_live2d_handoff_checks_real_result_zip(tmp_path, monkeypatch, missing_mask):
    cell = next(c for c in _load_cells() if "#@title ⑧ 실제 Live2D PSD 제작" in c)
    importer = ModuleType("tools.vts_ai_pack_import")
    producer = ModuleType("tools.vts_production")
    calls = []

    def prepare(source, destination, *, edition):
        calls.append(("import", source, edition))
        return {"master": destination / "master.png", "psd": destination / "parts.psd"}

    def make(master, dest, **kwargs):
        calls.append(("build", master, kwargs))
        dest.mkdir(parents=True, exist_ok=True)
        zipfile = dest / "result.zip"
        files = [
            "avatar.psd", "README_CUBISM.md", "LIVE2D_ARTWORK_GUIDE.md",
            "QUALITY_REVIEW.md", "preview/composite.png",
            "preview/input_vs_psd_comparison.png",
            "metadata/layer_manifest.json", "metadata/integrity_report.json",
            "source_psd/original.psd", "input_reference/master.png",
            "layers_png/part.png",
        ]
        if not missing_mask:
            files.append("alpha_masks/part.png")
        with ZipFile(zipfile, "w") as z:
            for name in files:
                z.writestr(name, b"fixture")
        return {"package": zipfile}

    importer.prepare_large_ai_pack = prepare
    producer.make_cubism_handoff = make
    monkeypatch.setitem(sys.modules, "tools.vts_ai_pack_import", importer)
    monkeypatch.setitem(sys.modules, "tools.vts_production", producer)
    args = dict(INPUT_KIND="parts_zip", EDITION="free", SCOPE="upper",
                ASSET=None, REFERENCE_FILE=None, INPUT_FILE=tmp_path / "in.zip",
                WORK=tmp_path)
    if missing_mask:
        with pytest.raises(RuntimeError, match="alpha_masks"):
            exec(compile(cell, "cell-8", "exec"), args)
    else:
        exec(compile(cell, "cell-8", "exec"), args)
        assert args["PACKAGE"].is_file()
        assert calls[1][2]["external_psd"] == tmp_path / "imported_artwork" / "parts.psd"
        assert calls[1][2]["preserve_supplied_parts"] is True
        assert calls[1][2]["psd2live"] is False
        assert calls[1][2]["qwen"] is False


@pytest.mark.parametrize("asset", ["hair", "outfit", "accessory"])
def test_pro_detached_asset_skips_see_through_model_preparation(asset, monkeypatch):
    cell = next(c for c in _load_cells() if "#@title ⑦ 의존성 / See-through 준비" in c)
    import subprocess
    calls = []
    monkeypatch.setattr(subprocess, "run", lambda *a, **k: calls.append((a, k)))
    exec(compile(cell, "cell-7", "exec"),
         {"INPUT_KIND": "single_image", "EDITION": "pro", "ASSET": asset})
    assert len(calls) == 1
    assert "psd-tools==1.14.2" in calls[0][0][0]
