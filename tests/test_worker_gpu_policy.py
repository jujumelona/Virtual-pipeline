import sys
from types import SimpleNamespace
import pytest


def test_production_requires_gpu_before_model_load(monkeypatch):
    from tools.model_workers._entry import require_cuda
    monkeypatch.setenv('VTUBER_REQUIRE_CUDA', '1')
    monkeypatch.setitem(sys.modules, 'torch', SimpleNamespace(cuda=SimpleNamespace(is_available=lambda: False)))
    with pytest.raises(RuntimeError, match='CUDA GPU'):
        require_cuda()


def test_available_cuda_and_explicit_cpu_validation_are_allowed(monkeypatch):
    from tools.model_workers._entry import require_cuda
    monkeypatch.setenv('VTUBER_REQUIRE_CUDA', '1')
    monkeypatch.setitem(sys.modules, 'torch', SimpleNamespace(cuda=SimpleNamespace(is_available=lambda: True)))
    require_cuda()
    monkeypatch.delenv('VTUBER_REQUIRE_CUDA')
    monkeypatch.setitem(sys.modules, 'torch', SimpleNamespace(cuda=SimpleNamespace(is_available=lambda: False)))
    require_cuda()
