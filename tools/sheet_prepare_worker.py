"""Disposable sheet crop + GPU anime SR subprocess (Colab cell ⑤).

Model and CUDA context DIE with this process before face detector, TripoSR
or Blender stages. It never downloads software or checkpoint weights.
"""
from __future__ import annotations

import json
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))

from tools.sheet_input_loader import convert_2d_sheet_pack, convert_3d_sheet_pack


def execute(request: dict) -> dict:
    mode = request["mode"]
    source = request["sheet_zip"]
    folder = str(Path(request["output_dir"]).resolve())
    if mode in ("live2d","inochi2d"):
        master, layers = convert_2d_sheet_pack(
            source, folder,
            output_scale=2,
            neural=True,
        )
        return {"front":master,"layers":layers}
    if mode == "3d":
        result = convert_3d_sheet_pack(source,folder)
        # A larger facial reference can improve eye/skin texture density. Do
        # NOT super-resolve geometry views: TripoSR geometry has fixed inference
        # resolution and hallucinated details may corrupt multiview alignment.
        from PIL import Image
        from tools.sheet_super_resolution import load_model, upscale_rgba
        model = load_model()
        with Image.open(result["face"]) as face:
            sr = upscale_rgba(face.convert("RGBA"),model,output_scale=2)
            enhanced = Path(folder)/"face_enhanced.png"
            sr.save(enhanced)
            result["face"] = str(enhanced)
        print("[sheet-sr] 3D face enhanced; full-body geometry views unchanged",
              flush=True)
        return result
    raise ValueError(f"Unknown sheet generation mode: {mode}")


def main(argv=None):
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--request",required=True)
    parser.add_argument("--result",required=True)
    args = parser.parse_args(argv)
    req = json.loads(Path(args.request).read_text(encoding="utf-8"))
    result = execute(req)
    destination = Path(args.result)
    temp = destination.with_suffix(".tmp")
    temp.write_text(json.dumps(result,ensure_ascii=False,indent=2),
                    encoding="utf-8")
    temp.replace(destination)
    print("[sheet] generated inputs: "+str(result),flush=True)


if __name__ == "__main__":
    main()
