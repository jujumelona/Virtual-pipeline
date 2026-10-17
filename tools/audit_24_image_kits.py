"""Audit 18 source-only kits: 2D FACE, 15 scoped 2D, 3D character and accessory."""
from __future__ import annotations
from pathlib import Path
from zipfile import ZipFile
import argparse, json

ROOT=Path(__file__).resolve().parents[1]/"docs/image_ai_kits_v2/zips"
MODES=("live2d_bust_up","live2d_upper","live2d_full","inochi2d_upper","inochi2d_full","3d")
ASSETS=("hair","outfit","accessory")
TARGETS=(("face","face"),)+tuple((m,a) for m in MODES if m!="3d" for a in ASSETS)+(("3d","character"),("3d","accessory"))
DOCUMENTS={
 "00_MASTER_FIRST.md","00_DELIVERY_AND_RECHECK.md","00_READ_FIRST.md",
 "01_COMMON_RULES.md","02_ADVANCED_PARTS.md","03_MODE_RULES.md",
 "04_OUTPUT_FILES.md","05_OFFICIAL_REFERENCES.md",
 "06_ADVANCED_OFFICIAL_COMMUNITY.md","07_REVIEW_BEFORE_FINAL_ZIP.md",
 "08_PRACTICAL_TIPS.md","09_VISUAL_ART_QUALITY.md","10_ANIME_STYLE.md",
 "11_OFFICIAL_IMAGE_EXAMPLES.md"
}
VIEWS={
 "face":("face_front","head_three_quarter_L","head_three_quarter_R","head_profile_L",
         "head_profile_R","head_pitch_up","head_pitch_down","neck_underpaint","face_neck_overlap"),
 "hair":("hair_front","hair_three_quarter_L","hair_three_quarter_R","hair_profile_L",
         "hair_profile_R","hair_back","hair_underlayers","hair_motion_clearance"),
 "outfit":("outfit_front","outfit_three_quarter_L","outfit_three_quarter_R","outfit_profile_L",
           "outfit_profile_R","outfit_back","outfit_inside_seams","outfit_joint_clearance"),
 "accessory":("accessory_front","accessory_three_quarter_L","accessory_three_quarter_R",
              "accessory_profile_L","accessory_profile_R","accessory_back",
              "accessory_attachment_anchor","accessory_occlusion")
}
THREE=("front","front_three_quarter_L","left","back_three_quarter_L",
       "back","back_three_quarter_R","right","front_three_quarter_R","detail_occlusion")
LEGACY=("ART_SOURCE_AND_SEPARATION_V3","GPT_ARTWORK_SEGMENTER_HANDOFF_V5",
        "MODE_ASSET_SEETHROUGH_V3_ROUTING_V6","ONE_PART_PER_GENERATION_V1",
        "See-through V3","SemanticSam","Qwen-Image-Layered",
        "part_art/_order.txt","isolated_parts/")
def expected_files(mode,asset):
    if mode=="face" and asset=="face":
        return (("outputs/master.png",)+tuple("reference_views/"+v+".png" for v in VIEWS["face"])
                +("expression_refs/mouth_closed.png","expression_refs/mouth_open.png"))
    if mode=="3d":
        return tuple("views/"+asset+"_"+v+".png" for v in THREE)
    out=["outputs/master.png"]
    out.extend("reference_views/"+v+".png" for v in VIEWS[asset])
    if asset=="face":out.extend(("expression_refs/mouth_closed.png","expression_refs/mouth_open.png"))
    return tuple(out)
def scan():
    issues=[];inventory=[]
    def fail(kit,name,code,detail=""):
        issues.append({"kit":kit,"document":name,"code":code,"severity":"blocker","excerpt":detail})
    for mode,asset in TARGETS:
            kit="face" if mode=="face" else mode+"__"+asset
            p=ROOT/("face.zip" if mode=="face" else kit+".zip")
            if not p.is_file():
                fail(kit,"","missing_zip");continue
            try:
                with ZipFile(p) as z:
                    names=z.namelist()
                    if len(names)!=14 or set(names)!=DOCUMENTS or z.testzip() is not None:
                        fail(kit,"","bad_zip_structure");continue
                    docs={n:z.read(n).decode("utf-8-sig") for n in names}
            except Exception as exc:
                fail(kit,"","bad_archive",str(exc));continue
            for n,d in docs.items():
                inventory.append({"kit":kit,"document":n,"bytes":len(d.encode())})
                for bad in LEGACY:
                    if bad in d:fail(kit,n,"obsolete_image_ai_segmentation_instruction",bad)
            master=docs["00_MASTER_FIRST.md"]; output=docs["04_OUTPUT_FILES.md"]
            for term in ("SOURCE_ART_ONLY_V7","원화",mode,asset):
                if term not in master:
                    fail(kit,"00_MASTER_FIRST.md","missing_source_only_contract",term)
            if "Colab" not in master:fail(kit,"00_MASTER_FIRST.md","missing_notebook_handoff")
            for expected in expected_files(mode,asset):
                if chr(96)+expected+chr(96) not in output:
                    fail(kit,"04_OUTPUT_FILES.md","required_artwork_png_missing",expected)
            if asset=="face" and ("#F2D4BE" not in master or "몸통" not in master):
                fail(kit,"00_MASTER_FIRST.md","face_scope_or_palette_missing")
            if asset=="face":
                for required in ("PRIMARY MASTER IMAGE PROMPT",
                                 "VTUBER_FACE_ART_QUALITY_V2",
                                 "단순 SVG", "12칸 컨택트시트",
                                 "하나라도 실패"):
                    if required not in master:
                        fail(kit,"00_MASTER_FIRST.md",
                             "missing_professional_vtuber_quality_contract",required)
                for file_name in ("03_MODE_RULES.md","09_VISUAL_ART_QUALITY.md",
                                  "10_ANIME_STYLE.md"):
                    if "전문" not in docs[file_name] and "애니" not in docs[file_name]:
                        fail(kit,file_name,"face_quality_supplement_missing")
            if asset=="character" and ("전신" not in master or "의상" not in master):
                fail(kit,"00_MASTER_FIRST.md","complete_clothed_3d_turnaround_missing")
            if asset=="outfit" and ("옷" not in master or "양손" not in master):
                fail(kit,"00_MASTER_FIRST.md","clothed_torso_hands_missing")
    wanted={"face.zip"} | {m+"__"+a+".zip" for m,a in TARGETS if m!="face"}
    extras={p.name for p in ROOT.glob("*.zip")}-wanted
    for name in sorted(extras):fail(name,"","stale_or_duplicate_published_zip")

    return {"schema":"vtuber/source-art-only-v7","kits":len({x["kit"] for x in inventory}),
            "documents":len(inventory),"blockers":len(issues),"reviews":0,"issues":issues,
            "matrix":[{"kit":("face" if m=="face" else m+"__"+a),
                       "blockers":sum(i["kit"]==("face" if m=="face" else m+"__"+a) for i in issues),
                      "reviews":0} for m,a in TARGETS]}
def main():
    p=argparse.ArgumentParser();p.add_argument("--strict",action="store_true");p.add_argument("--output",type=Path)
    a=p.parse_args();r=scan()
    if a.output:
        a.output.parent.mkdir(parents=True,exist_ok=True)
        a.output.write_text(json.dumps(r,ensure_ascii=False,indent=2),encoding="utf-8")
    print(json.dumps({k:v for k,v in r.items() if k!="issues"},ensure_ascii=False,indent=2))
    if a.strict and (r["blockers"] or r["kits"]!=18 or r["documents"]!=252):
        raise SystemExit("SOURCE_ART_ONLY_18_KIT_CONTRACT_FAIL")
if __name__=="__main__":main()
