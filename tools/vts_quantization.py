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


def align_offload_prompt_encoder_device(pipeline, family: str) -> None:
    """Adapt *only* the pinned vendor prompt encoder to Accelerate's device.

    Under enable_model_cpu_offload(), a CLIP model may report CPU *before*
    its forward hook moves its weights to CUDA. Sending tokenizer indices to
    text_encoder.device therefore fails on the second call. Diffusers exposes
    the actual hook execution target via pipeline._execution_device.

    Patch the imported class in this worker process only; leave pinned
    third-party sources and checkpoints intact. Fail closed if vendor code
    no longer has the exact known device expression.
    """
    import inspect
    import textwrap

    targets = {
        "layerdiff": (
            "encode_cropped_prompt_77tokens",
            "device = self.text_encoder.device",
            "device = self._execution_device",
        ),
        "marigold": (
            "encode_empty_text",
            "text_inputs.input_ids.to(self.text_encoder.device)",
            "text_inputs.input_ids.to(self._execution_device)",
        ),
    }
    if family not in targets:
        raise ValueError(f"Unsupported offload encoder family: {family}")
    execution_device = pipeline._execution_device
    if str(execution_device).split(":")[0] != "cuda":
        raise RuntimeError(
            f"{family}: expected CUDA execution device under CPU offload, "
            f"got {execution_device!s}"
        )

    method_name, old_expression, new_expression = targets[family]
    cls = type(pipeline)
    method = getattr(cls, method_name)
    if getattr(method, "_vts_offload_device_patched", False):
        return
    original = inspect.unwrap(method)
    source = textwrap.dedent(inspect.getsource(original))
    if source.count(old_expression) != 1:
        raise RuntimeError(
            f"{family}: pinned upstream encoder device contract changed"
        )
    # Recompile the original decorated vendor method with just one changed
    # device expression, in its original module global namespace.
    namespace = {}
    exec(
        compile(
            source.replace(old_expression, new_expression),
            original.__code__.co_filename,
            "exec",
        ),
        original.__globals__,
        namespace,
    )
    replacement = namespace[method_name]
    replacement._vts_offload_device_patched = True
    setattr(cls, method_name, replacement)
    print(f"[VTS offload] {family} token device follows CUDA execution hook",
          flush=True)
