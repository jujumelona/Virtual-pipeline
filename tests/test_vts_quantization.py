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


def test_keep_official_bf16_on_native_hardware_and_fp16_on_t4():
    from tools.vts_quantization import select_compute_dtype
    for capability, expected in [((7, 5), 'fp16'), ((8, 0), 'bf16'), ((9, 0), 'bf16')]:
        torch = types.SimpleNamespace(float16='fp16', bfloat16='bf16', cuda=types.SimpleNamespace(
            is_available=lambda: True, get_device_capability=lambda: capability))
        assert select_compute_dtype(torch) == expected
