from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parent))
from _entry import execute

PROMPT = ("Restore only the missing pixels of the specified original anime character layer. "
          "Preserve exact identity, outline, face details, costume colors and alignment. "
          "Extend occluded anatomy naturally. Do not change the visible pixels. No text or background.")

def infer(req):
    from vtuber_pipeline.common.model_assets import resolve_snapshot
    import torch
    import numpy as np
    from PIL import Image
    from vtuber_pipeline.common.schemas import PartsDocument
    from vtuber_pipeline.perception.compose import masked_repair
    doc = PartsDocument.read(req["parts_json"])
    original=Image.open(req["image_path"]).convert("RGB")
    out=Path(req["output_dir"])
    out.mkdir(parents=True,exist_ok=True)
    planned=[]
    for part in doc.parts:
        if not part.hidden_fill_mask_png:
            continue
        mask=Image.open(part.hidden_fill_mask_png).convert("L")
        if mask.getbbox():
            planned.append((part,mask))
    if not planned:
        saved=doc.write(str(out/"repaired_parts.json"))
        return {"parts_json":saved}
    snapshot = resolve_snapshot("flux2_klein_4b")
    from diffusers import Flux2KleinPipeline
    pipe=Flux2KleinPipeline.from_pretrained(snapshot,torch_dtype=(torch.bfloat16 if torch.cuda.is_bf16_supported() else torch.float16))
    pipe.enable_model_cpu_offload()
    for i,(part,mask) in enumerate(planned):
        # Edit reference, then combine ONLY masked pixels into this part.
        edited=pipe(image=original,prompt=PROMPT,num_inference_steps=4,guidance_scale=1.0,
                    height=original.height,width=original.width).images[0].convert("RGB")
        source=np.asarray(Image.open(part.rgba_png).convert("RGBA")).copy()
        generated=np.asarray(edited.resize(original.size))
        m=np.asarray(mask)>0
        source=masked_repair(source, generated, np.asarray(mask))
        dest=out/("repaired_%03d.png"%i)
        Image.fromarray(source,"RGBA").save(dest)
        part.rgba_png=str(dest)
        part.source_stage="sam2.1+flux2-klein-4b"
    saved=doc.write(str(out/"repaired_parts.json"))
    return {"parts_json":saved}

if __name__=="__main__":
    execute(infer)
