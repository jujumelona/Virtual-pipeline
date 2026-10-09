"""CPU integration smoke for the *real* pinned converted Florence checkpoint.

Unlike an import-only test, this downloads exact model weights, verifies that
the native architecture loads the weights and performs generation/box parsing.
No TensorFlow, GPU or user photo is required.
"""
from __future__ import annotations
import json
import os
from pathlib import Path

os.environ["USE_TF"] = "0"
os.environ["USE_FLAX"] = "0"


def run():
    import torch
    from PIL import Image, ImageDraw
    from transformers import AutoProcessor, Florence2ForConditionalGeneration
    from vtuber_pipeline.common.model_assets import model_pin, resolve_snapshot

    pin = model_pin("florence2_base")
    assert pin["model_id"] == "florence-community/Florence-2-base", pin
    assert pin["revision"] == "0ae188f8620727704bcffa9292a0fdb92f127480", pin
    path = resolve_snapshot("florence2_base")
    model, info = Florence2ForConditionalGeneration.from_pretrained(
        path, trust_remote_code=False, output_loading_info=True,
    )
    assert len(info.get("missing_keys", [])) <= 16, info.get("missing_keys", [])[:40]
    assert len(info.get("unexpected_keys", [])) <= 16, info.get("unexpected_keys", [])[:40]
    assert not info.get("error_msgs"), info["error_msgs"]
    model.eval()
    processor = AutoProcessor.from_pretrained(path, trust_remote_code=False)
    image = Image.new("RGB", (256, 256), (240, 239, 242))
    d = ImageDraw.Draw(image)
    d.ellipse((72, 35, 178, 158), fill=(60, 69, 122))
    d.rectangle((55, 146, 207, 255), fill=(10, 31, 82))
    report = {}
    for prompt in ("<OD>", "<OPEN_VOCABULARY_DETECTION>hair"):
        task = "<OPEN_VOCABULARY_DETECTION>" if prompt.startswith(
            "<OPEN_VOCABULARY_DETECTION>"
        ) else "<OD>"
        inputs = processor(text=prompt, images=image, return_tensors="pt")
        with torch.inference_mode():
            tokens = model.generate(
                **inputs, max_new_tokens=64, num_beams=1, do_sample=False
            )
        decoded = processor.batch_decode(tokens, skip_special_tokens=False)[0]
        parsed = processor.post_process_generation(
            decoded, task=task, image_size=image.size
        )
        assert isinstance(parsed, dict) and task in parsed, parsed
        report[task] = {
            "returned_keys": list(parsed[task]),
            "decoded_characters": len(decoded),
        }
    print(json.dumps({
        "REAL_NATIVE_FLORENCE_WEIGHTS": "PASS",
        "revision": pin["revision"],
        "tests": report,
    }, indent=2), flush=True)


if __name__ == "__main__":
    run()
