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
    if mode == "wardrobe_2d":
        from tools.outfit_variant_pack import build_dressed_2d_assets
        return build_dressed_2d_assets(
            source,request["outfit_png"],folder,neural=True
        )
    if mode in ("live2d","inochi2d"):
        master, layers = convert_2d_sheet_pack(
            source, folder,
            output_scale=2,
            neural=True,
        )
        return {"front":master,"layers":layers}
    if mode == "3d":
        # Reuse ONE GPU model for the sheet's individual views and face.
        from PIL import Image
        from tools.sheet_super_resolution import load_model, upscale_rgba
        from tools.sheet_input_loader import _upscale_to
        model = load_model()
        ai = lambda image,factor: upscale_rgba(image,model,output_scale=factor)
        result = convert_3d_sheet_pack(source,folder,upscaler=ai,neural=True)
        with Image.open(result["face"]) as face:
            sr = _upscale_to(face.convert("RGBA"), (4096,4096),ai,neural=True)
            enhanced = Path(folder)/"face_enhanced.png"
            sr.save(enhanced)
            result["face"] = str(enhanced)
        print("[sheet-sr] 3D views and face aspect-normalized with AI SR; "
              "source viewpoints preserved",flush=True)
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
