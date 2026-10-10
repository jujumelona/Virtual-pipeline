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


class _FakeTokenIndices:
    def __init__(self, device="cpu"):
        self.device = device

    def to(self, device):
        return _FakeTokenIndices(str(device))


class _FakeOffloadTextEncoder:
    device = "cpu"  # reported before Accelerate's pre-forward hook fires
    def __call__(self, ids):
        # Simulate hook moving weights onto CUDA without fixing CPU input IDs.
        if ids.device != "cuda:0":
            raise RuntimeError("Expected all tensors to be on the same device")
        return ids.device


class _FakeLayerDiffOffload:
    _execution_device = "cuda:0"

    def __init__(self):
        self.text_encoder = _FakeOffloadTextEncoder()

    def encode_cropped_prompt_77tokens(self, indices):
        device = self.text_encoder.device
        return self.text_encoder(indices.to(device))


class _FakeMarigoldOffload:
    _execution_device = "cuda:0"

    def __init__(self):
        self.text_encoder = _FakeOffloadTextEncoder()
        self.text_inputs = types.SimpleNamespace(
            input_ids=_FakeTokenIndices()
        )

    def encode_empty_text(self):
        text_inputs = self.text_inputs
        text_input_ids = text_inputs.input_ids.to(self.text_encoder.device)
        return self.text_encoder(text_input_ids)


def test_layerdiff_offload_both_head_and_body_prompt_batches_use_cuda():
    import pytest
    from tools.vts_quantization import align_offload_prompt_encoder_device

    pipeline = _FakeLayerDiffOffload()
    with pytest.raises(RuntimeError, match="same device"):
        pipeline.encode_cropped_prompt_77tokens(_FakeTokenIndices())
    align_offload_prompt_encoder_device(pipeline, "layerdiff")
    assert pipeline.encode_cropped_prompt_77tokens(_FakeTokenIndices()) == "cuda:0"
    # A later call (head tags, after the CLIP hooks have moved the models)
    # must also send token indices to the CUDA execution device.
    assert pipeline.encode_cropped_prompt_77tokens(_FakeTokenIndices()) == "cuda:0"
    align_offload_prompt_encoder_device(pipeline, "layerdiff")  # idempotent


def test_marigold_cpu_offload_empty_prompt_uses_cuda_execution_device():
    import pytest
    from tools.vts_quantization import align_offload_prompt_encoder_device

    pipeline = _FakeMarigoldOffload()
    with pytest.raises(RuntimeError, match="same device"):
        pipeline.encode_empty_text()
    align_offload_prompt_encoder_device(pipeline, "marigold")
    assert pipeline.encode_empty_text() == "cuda:0"


def test_device_fix_fails_closed_for_unknown_upstream_encoder():
    import pytest
    from tools.vts_quantization import align_offload_prompt_encoder_device

    with pytest.raises(ValueError, match="Unsupported"):
        align_offload_prompt_encoder_device(_FakeLayerDiffOffload(), "unknown")

    class ChangedEncoder:
        _execution_device = "cuda:0"

        def encode_empty_text(self):
            return 1

    with pytest.raises(RuntimeError, match="contract changed"):
        align_offload_prompt_encoder_device(ChangedEncoder(), "marigold")
