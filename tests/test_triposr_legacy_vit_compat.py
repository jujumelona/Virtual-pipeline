"""Regression tests for strict TripoSR ViT checkpoint name conversion."""
import pytest
import torch

from vtuber_pipeline.avatar.triposr_runner import _remap_legacy_triposr_vit_weights


@pytest.mark.parametrize("original,mapped", [
    ("attention.attention.query.weight", "attention.q_proj.weight"),
    ("attention.attention.key.bias", "attention.k_proj.bias"),
    ("attention.attention.value.weight", "attention.v_proj.weight"),
    ("attention.output.dense.weight", "attention.o_proj.weight"),
    ("intermediate.dense.weight", "mlp.fc1.weight"),
    ("output.dense.bias", "mlp.fc2.bias"),
    ("layernorm_before.weight", "layernorm_before.weight"),
])
def test_strict_legacy_vit_parameter_map(original, mapped):
    old = "image_tokenizer.model.encoder.layer.0." + original
    new = "image_tokenizer.model.layers.0." + mapped
    parameter = torch.arange(4, dtype=torch.float32).reshape(2, 2)
    src = {old: parameter, "decoder.weight": torch.ones(1)}
    expected = {new: torch.empty_like(parameter), "decoder.weight": torch.zeros(1)}
    result = _remap_legacy_triposr_vit_weights(src, expected)
    assert set(result) == set(expected)
    assert torch.equal(result[new], parameter)
    assert torch.equal(result["decoder.weight"], src["decoder.weight"])


def test_strict_legacy_vit_rejects_missing_and_wrong_shapes():
    old = "image_tokenizer.model.encoder.layer.0.attention.attention.query.weight"
    new = "image_tokenizer.model.layers.0.attention.q_proj.weight"
    with pytest.raises(RuntimeError, match="architecture mismatch"):
        _remap_legacy_triposr_vit_weights({old: torch.ones(2)}, {
            new: torch.empty(2), "other.weight": torch.empty(1)})
    with pytest.raises(RuntimeError, match="incompatible tensor"):
        _remap_legacy_triposr_vit_weights({old: torch.ones(2)}, {
            new: torch.empty(3)})


def test_strict_legacy_vit_rejects_key_collision():
    old = "image_tokenizer.model.encoder.layer.0.intermediate.dense.weight"
    new = "image_tokenizer.model.layers.0.mlp.fc1.weight"
    with pytest.raises(RuntimeError, match="key collision"):
        _remap_legacy_triposr_vit_weights(
            {old: torch.ones(1), new: torch.ones(1)}, {new: torch.empty(1)})
