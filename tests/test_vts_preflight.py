"""Validate public request and worker boundaries before any expensive model call."""
from pathlib import Path
import sys
from types import SimpleNamespace
import pytest
from PIL import Image
from tools import vts_production as production


@pytest.mark.parametrize("layers,passes", [(1, 8), (11, 8), (6, -1), (6, 13)])
def test_bad_recursion_budget_rejected_before_decomposition(tmp_path, monkeypatch, layers, passes):
    master = tmp_path / "master.png"
    Image.new("RGBA", (256, 384)).save(master)
    monkeypatch.setattr(production, "run_see_through",
                        lambda *a, **kw: pytest.fail("invalid request reached model inference"))
    with pytest.raises(ValueError, match="Qwen"):
        production.make_cubism_handoff(master, tmp_path / "out", edition="free", scope="upper",
                                       qwen_layers=layers, qwen_passes=passes)
    assert not (tmp_path / "out").exists()


def test_see_through_relative_paths_survive_worker_cwd(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    source = Path("master.png"); Image.new("RGBA", (256, 384)).save(source)
    repo = Path("see")
    scripts = repo / "inference/scripts"; scripts.mkdir(parents=True)
    script = scripts / "inference_psd_quantized.py"
    script.write_text("# " + "torch.bfloat16 " * 8 + '''
import argparse
from pathlib import Path
p=argparse.ArgumentParser(); p.add_argument('--srcp'); p.add_argument('--save_dir')
a, _=p.parse_known_args()
assert Path(a.srcp).is_file()
folder=Path(a.save_dir); folder.mkdir(parents=True, exist_ok=True)
(folder/(Path(a.srcp).stem+'.psd')).write_bytes(b'8BPS CPU wrapper fixture')
print('CPU wrapper fixture completed')
''')
    monkeypatch.setitem(sys.modules, "torch", SimpleNamespace(cuda=SimpleNamespace(
        is_available=lambda: True, get_device_capability=lambda *a: (7, 5))))
    monkeypatch.setattr(production, "_safe_refine_psd", lambda src, **kw: src)
    result = production.run_see_through(source, Path("out"), third_party=repo, timeout=20)
    assert result.is_absolute() and result.is_file()
    assert result.read_bytes().startswith(b"8BPS")
    assert (Path("out") / "see_through_full.log").read_text().strip() == "CPU wrapper fixture completed"
