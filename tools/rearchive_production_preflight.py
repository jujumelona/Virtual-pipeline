"""Validate actual RE:ARCHIVE painted assets; never mistake concept art for rig input."""
import argparse, hashlib, io, json
from pathlib import Path, PurePosixPath
from zipfile import ZipFile, ZIP_DEFLATED
from PIL import Image

MAX_TOTAL=700_000_000
MAX_MEMBER=90_000_000
def load_bundle(path):
    with ZipFile(path) as z:
        members=[x for x in z.infolist() if not x.is_dir()]
        if len(members)>350 or sum(x.file_size for x in members)>MAX_TOTAL:
            raise ValueError("ZIP_LIMIT")
        data={}
        for f in members:
            p=PurePosixPath(f.filename)
            if (p.is_absolute() or ".." in p.parts or "\\" in f.filename or
                f.file_size>MAX_MEMBER or f.filename in data or
                ((f.external_attr>>16)&0o170000) in (0o120000,0o060000)):
                raise ValueError("UNSAFE_OR_DUPLICATE_ZIP_MEMBER")
            data[f.filename]=z.read(f)
        return data

def check_png(raw, expected):
    with Image.open(io.BytesIO(raw)) as im:
        im.load()
        if im.format!="PNG" or im.mode!="RGBA" or im.size!=tuple(expected):
            raise ValueError("EXPECT_RGBA_PNG_"+str(expected))
        alpha=im.getchannel("A")
        low,high=alpha.getextrema()
        bbox=alpha.getbbox()
        if low!=0 or high!=255 or not bbox:
            raise ValueError("EXPECT_REAL_ALPHA_AND_PAINT")
        return list(bbox)

def audit(bundle, contract, stage="front"):
    if stage not in ("front","sheets","parts"):
        raise ValueError("BAD_STAGE")
    paths=["art/S01_front_neutral.png"]
    if stage in ("sheets","parts"):
        paths+=["references/S02_left_45.png","references/S03_right_45.png"]
    if stage=="parts":
        paths += [p["path"] for p in contract["parts"] if p["required"]]
    report={"schema":"rearchive/asset-preflight-v2","stage":stage,
            "status":"NOT_READY","found":[],"missing":[],"invalid":[],
            "not_verified":["identity_similarity","underpaint_quality",
                            "true_45_degree_views","editable_rig","camera_tracking"]}
    for path in paths:
        if path not in bundle:
            report["missing"].append(path)
            continue
        try:
            bbox=check_png(bundle[path],contract["canvas"]["artwork_size"])
            report["found"].append({"path":path,"sha256":hashlib.sha256(bundle[path]).hexdigest(),"bbox":bbox})
        except Exception as e:
            report["invalid"].append({"path":path,"error":str(e)})
    if stage in ("sheets","parts") and all(k in bundle for k in paths[:3]):
        if len({hashlib.sha256(bundle[k]).hexdigest() for k in paths[:3]})!=3:
            report["invalid"].append({"path":"references","error":"DUPLICATE_VIEW_PIXELS"})
    if not report["missing"] and not report["invalid"]:
        report["status"]="FILES_VALID_ART_REVIEW_REQUIRED"
    return report

def prepare_seethrough(bundle, report, output):
    if report["stage"]!="front" or report["status"]!="FILES_VALID_ART_REVIEW_REQUIRED":
        raise ValueError("FRONT_NOT_VALID")
    output=Path(output)
    output.parent.mkdir(parents=True,exist_ok=True)
    with ZipFile(output,"w",ZIP_DEFLATED) as z:
        z.writestr("outputs/master.png",bundle["art/S01_front_neutral.png"])
        z.writestr("00_STATUS.json",json.dumps({
            "source":"S01_front_neutral","ready_for_review_only":True,
            "parts_separated":False,"rigged":False},indent=2))
    return output

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--input",type=Path,required=True)
    ap.add_argument("--contract",type=Path,required=True)
    ap.add_argument("--stage",choices=["front","sheets","parts"],default="front")
    ap.add_argument("--report",type=Path,required=True)
    ap.add_argument("--prepare-seethrough-zip",type=Path)
    args=ap.parse_args()
    contract=json.loads(args.contract.read_text(encoding="utf-8"))
    bundle=load_bundle(args.input)
    report=audit(bundle,contract,args.stage)
    args.report.parent.mkdir(parents=True,exist_ok=True)
    args.report.write_text(json.dumps(report,indent=2,ensure_ascii=False)+"\n",encoding="utf-8")
    print(json.dumps({"status":report["status"],"missing":report["missing"][:8],"invalid":report["invalid"][:8]},ensure_ascii=False))
    if report["status"]!="FILES_VALID_ART_REVIEW_REQUIRED":
        raise SystemExit(2)
    if args.prepare_seethrough_zip:
        print(prepare_seethrough(bundle,report,args.prepare_seethrough_zip))
if __name__=="__main__":
    main()
