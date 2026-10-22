"""Stage one of RE:ARCHIVE original-art-first: one genuine transparent PNG master.

Deconstruct the temporary base64-staged RGBA asset into a standardized
See-through input. It is NOT the 4 required separate hair/body/outfit/acc
source ZIPs, and NOT a layered PSD or completed original-avatar rig.
No cropped character part is fabricated from the whole master.
"""
from __future__ import annotations
import argparse,base64,hashlib,io,json
from pathlib import Path
from zipfile import ZipFile,ZIP_DEFLATED
from PIL import Image

TARGET=(1536,2304)
MAX_PIXELS=16_000_000

def create_master(encoded:Path,output:Path)->dict:
    encoded=Path(encoded).resolve(strict=True)
    output=Path(output).resolve()
    if output.exists() and any(output.iterdir()):
        raise ValueError("Output must be new/empty")
    raw=base64.b64decode(encoded.read_text(encoding="ascii").strip(),validate=True)
    if len(raw)>25_000_000:raise ValueError("Excessive original RGBA input size")
    with Image.open(io.BytesIO(raw)) as img:
        img.load()
        if img.format!="PNG" or img.mode!="RGBA":
            raise ValueError("Requires real transparent PNG, not a reference JPG")
        if img.width*img.height>MAX_PIXELS:raise ValueError("Excessively large source")
        source=img.copy()
    bbox=source.getchannel("A").getbbox()
    if not bbox:raise ValueError("Artwork completely transparent")
    lo,hi=source.getchannel("A").getextrema()
    if lo!=0 or hi<240:raise ValueError("Artwork has no meaningful alpha segmentation")
    cut=source.crop(bbox)
    # Keep full human silhouette and hair endings, never rescale if it fits.
    lim=(TARGET[0]-128,TARGET[1]-128)
    s=min(1,lim[0]/cut.width,lim[1]/cut.height)
    if s<1:
        cut=cut.resize((round(cut.width*s),round(cut.height*s)),
                       Image.Resampling.LANCZOS)
    final=Image.new("RGBA",TARGET)
    anchor=((TARGET[0]-cut.width)//2,(TARGET[1]-cut.height)//2)
    final.alpha_composite(cut,anchor)
    assert final.size==TARGET
    assert final.getchannel("A").getextrema()==(0,255)
    output.mkdir(parents=True)
    out=output/"REARCHIVE_SINGLE_ARTWORK_FOR_SEETHROUGH.zip"
    ref=output/"REARCHIVE_TRANSPARENT_ORIGINAL_MASTER.png"
    ref.write_bytes(raw)
    normalized=output/"REARCHIVE_1536x2304_MASTER.png"
    final.save(normalized)
    digest=hashlib.sha256(normalized.read_bytes()).hexdigest()
    status={
       "schema":"rearchive/transparent-original-master-for-seethrough-v1",
       "source_png_sha256":hashlib.sha256(raw).hexdigest(),
       "master_png_sha256":digest,"source_png_size":list(source.size),
       "normalized_png_size":list(final.size),
       "source_alpha_bbox":list(bbox),"normalized_anchor":list(anchor),
       "rescale_ratio":round(s,6),
       "source_art_from_reference":True,
       "single_front_neutral_character":True,
       "real_transparent_background":True,
       "portrait_1536x2304":True,
       "face_style_exactly_original_sheet_4_verified":False,
       "outfit_style_exactly_original_sheet_4_verified":False,
       "parts_really_separated":False,
       "underpainting_completed":False,
       "psd_layers_generated":False,
       "native_rigged_with_this_master":False,
       "ready_for_gpu_see_through":True,
       "status":"ART_MASTER_INPUT_READY_PENDING_SEPARATION_AND_LIVE2D_RIG"
    }
    with ZipFile(out,"w",ZIP_DEFLATED,compresslevel=6) as z:
        z.write(normalized,"outputs/master.png")
        z.write(ref,"references/full_resolution_original.png")
        z.writestr("00_READ_FIRST_KO.txt",
            "RE:ARCHIVE 정면 원화 1장. outputs/master.png 만 See-through에 "
            "입력할 원화로 사용. 레이어를 실제 분리한 PSD가 아니며 "
            "얼굴/의상/헤어/악세사리 4ZIP으로 속여 사용하면 안 됩니다. "
            "분리는 See-through GPU 후 시각/좌표 검수 필수. "
            "현재 기존 CC0 리깅 프로젝트에 이식된 상태가 아닙니다.\n")
        z.writestr("01_SEPARATION_STATUS.json",json.dumps(status,ensure_ascii=False,indent=2))
        if z.testzip() is not None:raise RuntimeError("ZIP integrity broken")
    (output/"INPUT_STATUS.json").write_text(
        json.dumps(status,ensure_ascii=False,indent=2),encoding="utf-8")
    return status

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--rgba-base64",type=Path,required=True)
    p.add_argument("--output",type=Path,required=True)
    args=p.parse_args()
    print(json.dumps(create_master(args.rgba_base64,args.output),
                     ensure_ascii=False,indent=2))
if __name__=="__main__":main()
