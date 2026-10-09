"""Adapt serialized bitsandbytes math dtype without changing NF4 weights."""


def set_4bit_compute_dtype(model, dtype):
    # torch_dtype only controls unquantized modules. Pre-quantized snapshots
    # retain their own Linear4bit compute_dtype, including BF16 on a T4.
    # Run before the first forward/cache_tag_embeds, after from_pretrained.
    import bitsandbytes as bnb
    changed = 0
    for module in model.modules():
        if isinstance(module, bnb.nn.Linear4bit):
            module.compute_dtype = dtype
            module.compute_type_is_set = True
            changed += 1
    if changed:
        print(f"[VTS NF4] {changed} quantized linear modules: compute_dtype={dtype}", flush=True)
    return changed


def select_compute_dtype(torch):
    # Turing may expose emulated BF16; require native Ampere-or-newer math.
    if torch.cuda.is_available() and torch.cuda.get_device_capability()[0] >= 8:
        return torch.bfloat16
    return torch.float16
