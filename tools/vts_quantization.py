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


def patch_nf4_marigold_cpu_offload(source: str) -> str:
    """Make upstream NF4 depth stage obey its existing --cpu_offload switch.

    The pinned source unconditionally moves VAE, UNet and (nonquantized)
    text encoder to CUDA, ignoring --cpu_offload. Replace only the exact
    verified fragment; never modify the upstream checkout in place.
    """
    original = """        marigold_pipe.vae.to(device='cuda')
        marigold_pipe.unet.to(device='cuda')
        # Text encoder may be quantized (from pre-quantized repo) — only move device, not dtype
        if not getattr(marigold_pipe.text_encoder, 'is_quantized', False) and \\
           not getattr(marigold_pipe.text_encoder, 'quantization_method', None):
            marigold_pipe.text_encoder.to(device='cuda')
        if getattr(args, 'group_offload', False):
            marigold_pipe.enable_group_offload('cuda', num_blocks_per_group=1)
"""
    replacement = """        if args.cpu_offload:
            marigold_pipe.enable_model_cpu_offload()
        else:
            marigold_pipe.vae.to(device='cuda')
            marigold_pipe.unet.to(device='cuda')
            # Keep upstream quantization guard for its text encoder.
            if not getattr(marigold_pipe.text_encoder, 'is_quantized', False) and \\
               not getattr(marigold_pipe.text_encoder, 'quantization_method', None):
                marigold_pipe.text_encoder.to(device='cuda')
            if getattr(args, 'group_offload', False):
                marigold_pipe.enable_group_offload('cuda', num_blocks_per_group=1)
"""
    if source.count(original) != 1:
        raise RuntimeError("Pinned See-through NF4 Marigold offload contract changed")
    return source.replace(original, replacement)
