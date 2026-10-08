"""Produce real multilayer OpenRaster and PSD files with full-canvas RGBA pixels."""
from pathlib import Path
from io import BytesIO
import json
import zipfile
from xml.etree import ElementTree as ET

def write_psd_and_ora(parts, output_dir: str) -> dict:
    from PIL import Image
    from psd_tools import PSDImage
    out=Path(output_dir)
    out.mkdir(parents=True,exist_ok=True)
    layers=sorted(parts.parts,key=lambda p:p.z_order,reverse=True)
    if not layers:
        raise ValueError("no actual parts to export")
    psd=PSDImage.new("RGB",(parts.width,parts.height),depth=8)
    stack=ET.Element("image",{"version":"0.0.3","w":str(parts.width),
                              "h":str(parts.height),"name":"VTuber separated artwork"})
    node=ET.SubElement(stack,"stack")
    images=[]
    for i,p in enumerate(layers):
        im=Image.open(p.rgba_png).convert("RGBA")
        if im.size!=(parts.width,parts.height):
            raise ValueError("PSD part must use original full canvas")
        ET.SubElement(node,"layer",{"name":p.semantic_id,"src":"data/layer_%03d.png"%i,
                      "opacity":"1.0","visibility":"visible","composite-op":"svg:src-over","x":"0","y":"0"})
        buf=BytesIO()
        im.save(buf,format="PNG")
        images.append(buf.getvalue())
    # psd-tools appends layers bottom-to-top; ORA lists top-to-bottom.
    for p in reversed(layers):
        psd.create_pixel_layer(Image.open(p.rgba_png).convert("RGBA"),
                               name=p.semantic_id, top=0, left=0)
    psd_path=out/"avatar.psd"
    psd.save(str(psd_path))
    # Validate real PSD format, not renamed bitmap.
    if psd_path.read_bytes()[:4]!=b"8BPS":
        raise RuntimeError("layer writer did not emit a native PSD")
    if len(PSDImage.open(str(psd_path)))!=len(layers):
        raise RuntimeError("PSD layer count differs from source parts")
    merged=Image.new("RGBA",(parts.width,parts.height))
    for p in reversed(layers):
        merged.alpha_composite(Image.open(p.rgba_png).convert("RGBA"))
    ora_path=out/"avatar.ora"
    with zipfile.ZipFile(ora_path,"w") as bundle:
        bundle.writestr("mimetype","image/openraster",compress_type=zipfile.ZIP_STORED)
        bundle.writestr("stack.xml",ET.tostring(stack,encoding="utf-8"))
        b=BytesIO()
        merged.save(b,"PNG")
        bundle.writestr("mergedimage.png",b.getvalue())
        merged.thumbnail((256,256))
        b=BytesIO()
        merged.save(b,"PNG")
        bundle.writestr("Thumbnails/thumbnail.png",b.getvalue())
        for i,data in enumerate(images):
            bundle.writestr("data/layer_%03d.png"%i,data)
    manifest=out/"layers.json"
    manifest.write_text(json.dumps({"width":parts.width,"height":parts.height,
                        "parts":[p.__dict__ for p in layers]},ensure_ascii=False,indent=2),encoding="utf-8")
    return {"psd":str(psd_path),"ora":str(ora_path),"layers_json":str(manifest)}
