"""CPU contracts for BF16-incompatible GPUs; no inference-quality claim."""
import sys
import types

from tools.vts_quantization import set_4bit_compute_dtype


def test_serialized_bf16_compute_is_overridden_without_requantizing(monkeypatch):
    class Linear4bit:
        def __init__(self):
            self.compute_dtype = 'bf16'
            self.compute_type_is_set = False
            self.weight = object()
    monkeypatch.setitem(sys.modules, 'bitsandbytes', types.SimpleNamespace(
        nn=types.SimpleNamespace(Linear4bit=Linear4bit)))
    quantized = Linear4bit()
    ordinary = types.SimpleNamespace(compute_dtype='untouched')
    weight = quantized.weight
    model = types.SimpleNamespace(modules=lambda: iter([ordinary, quantized]))
    assert set_4bit_compute_dtype(model, 'fp16') == 1
    assert quantized.compute_dtype == 'fp16'
    assert quantized.compute_type_is_set is True
    assert quantized.weight is weight
    assert ordinary.compute_dtype == 'untouched'
