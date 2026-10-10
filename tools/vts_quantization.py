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
    """Keep the pinned custom Marigold on its supported NF4 GPU/group offload.

    The vendor MarigoldDepthPipeline has no model_cpu_offload_seq, so calling
    enable_model_cpu_offload would fail after the lengthy LayerDiff stage.
    Retain the pinned GPU/group-offload path and report that explicitly.
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
    replacement = original.replace(
        "        marigold_pipe.vae.to(device='cuda')",
        "        if args.cpu_offload:\n"
        "            print('[VTS] Marigold NF4: GPU/group offload (custom pipeline lacks native CPU offload)', flush=True)\n"
        "        marigold_pipe.vae.to(device='cuda')",
    )
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


def align_offload_image_devices(pipeline, family: str) -> None:
    """Align pinned vendor VAE/UNet inference with real CUDA execution.

    Accelerate's CPU component offload makes module.device report CPU between
    calls, even though its forward hooks move parameters onto CUDA. Upstream
    manually constructs VAE inputs, scheduler tensors and latents on those
    stale reported devices. This patch is confined to the transient worker.
    Vendor source is checked before each replacement and never overwritten.
    """
    import inspect
    import textwrap
    import torch

    def patch_function(function, replacements, name):
        original = inspect.unwrap(function)
        source = textwrap.dedent(inspect.getsource(original))
        for before, after in replacements:
            if source.count(before) == 0:
                raise RuntimeError(f"{name}: offload source contract changed: {before}")
            source = source.replace(before, after)
        namespace = {}
        exec(
            compile(source, original.__code__.co_filename, "exec"),
            original.__globals__,
            namespace,
        )
        return namespace[original.__name__]

    target_device = pipeline._execution_device
    if str(target_device).split(":")[0] != "cuda":
        raise RuntimeError(
            f"{family}: expected CUDA offload execution, got {target_device!s}"
        )
    cls = type(pipeline)
    if family == "layerdiff":
        source_call = getattr(cls, "__call__")
        if not getattr(source_call, "_vts_image_device_patched", False):
            patched = patch_function(
                source_call,
                [
                    ("self.unet.device", "self._execution_device"),
                    ("self.vae.device", "self._execution_device"),
                    ("self.trans_vae.device", "self._execution_device"),
                ],
                "layerdiff.__call__",
            )
            patched._vts_image_device_patched = True
            setattr(cls, "__call__", patched)

        call_globals = inspect.unwrap(source_call).__globals__
        old_vae_encode = call_globals["vae_encode"]
        if not getattr(old_vae_encode, "_vts_image_device_patched", False):
            patched = patch_function(
                old_vae_encode,
                [("device=vae.device", "device=torch.device('cuda', torch.cuda.current_device())")],
                "layerdiff.vae_encode",
            )
            patched._vts_image_device_patched = True
            call_globals["vae_encode"] = patched
    elif family == "marigold":
        # Marigold defines its own device property based on unet.device, which
        # is CPU between offloaded forwards; never recurse via _execution_device.
        original_device_property = getattr(cls, "device")
        if not getattr(cls, "_vts_device_property_patched", False):
            if not isinstance(original_device_property, property):
                raise RuntimeError("marigold.device property contract changed")
            original_getter = inspect.getsource(original_device_property.fget)
            if "return self.unet.device" not in original_getter:
                raise RuntimeError("marigold.device getter contract changed")
            cls.device = property(
                lambda self: torch.device("cuda", torch.cuda.current_device())
            )
            cls._vts_device_property_patched = True

        for method_name, replacements in (
            ("__call__", [
                ("self.vae.device", "self._execution_device"),
                ("vae.device", "self._execution_device"),
            ]),
            ("encode_rgb", [
                ("self.vae.device", "self._execution_device"),
            ]),
            ("decode_depth", [
                ("self.vae.device", "self._execution_device"),
            ]),
        ):
            method = getattr(cls, method_name)
            if getattr(method, "_vts_image_device_patched", False):
                continue
            # A single method often contains several uses of the same property.
            # Avoid replacing a suffix of an already rewritten expression.
            patched = patch_function(method, replacements, f"marigold.{method_name}")
            patched._vts_image_device_patched = True
            setattr(cls, method_name, patched)

        call_globals = inspect.unwrap(getattr(cls, "__call__")).__globals__
        old_encode_list = call_globals["encode_argb_list"]
        if not getattr(old_encode_list, "_vts_image_device_patched", False):
            patched = patch_function(
                old_encode_list,
                [("device=vae.device", "device=torch.device('cuda', torch.cuda.current_device())")],
                "marigold.encode_argb_list",
            )
            patched._vts_image_device_patched = True
            call_globals["encode_argb_list"] = patched
    else:
        raise ValueError(f"Unsupported offload image family: {family}")
    print(f"[VTS offload] {family} VAE/UNet inputs use CUDA execution device", flush=True)


def align_offloaded_transparent_decoder(pipeline) -> None:
    """Fix the pinned see-through decoder bypassing its parent's CPU offload hook.

    The vendor calls trans_vae.decoder directly; its nested UNet1024 remains
    on CPU while sd_vae.decode() produces CUDA pixels. Activate only that
    nested network *after* the SD VAE has decoded a frame, so the decoder
    is not resident during the expensive 30-step diffusion loop.
    """
    import inspect
    import textwrap

    decoder = pipeline.trans_vae.decoder
    cls = type(decoder)
    method = cls.estimate_single_pass
    if getattr(method, "_vts_offload_patched", False):
        return

    original = inspect.unwrap(method)
    source = textwrap.dedent(inspect.getsource(original))
    anchor = "    y = self.model(pixel, latent)"
    if source.count(anchor) != 1:
        raise RuntimeError("Pinned TransparentVAE decoder placement contract changed")
    source = source.replace(
        anchor,
        "    self.model.to(device=pixel.device, dtype=pixel.dtype)\n" + anchor,
    )
    namespace = {}
    exec(
        compile(source, original.__code__.co_filename, "exec"),
        original.__globals__,
        namespace,
    )
    replacement = namespace[original.__name__]
    replacement._vts_offload_patched = True
    cls.estimate_single_pass = replacement
    print("[VTS offload] transparent decoder activates after SD VAE decode",
          flush=True)
