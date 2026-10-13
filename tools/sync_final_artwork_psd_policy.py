"""Synchronize final PSD handoff language across canonical 20 2D instruction ZIPs."""
from __future__ import annotations
import argparse
from pathlib import Path
from zipfile import ZipFile
import os
import tempfile

KIT=Path(__file__).resolve().parents[1]/"docs/image_ai_kits_v2"
MODES=("live2d_bust_up","live2d_upper","live2d_full","inochi2d_upper","inochi2d_full")
ASSETS=("body","hair","outfit","accessory")
OLD="이미지 AI 대신 PSD/리깅을 요구하지 않는다."
NEW=("중간 PNG 구조 검사의 PASS를 최종 납품으로 오인하지 않는다. "
     "Live2D/Inochi2D 최종 결과 원화 ZIP에는 실제 편집 가능한 다층 PSD와 "
     "각 파츠의 알파 마스크가 필수이며, Cubism/Inochi Creator 네이티브 리깅 "
     "및 모션 자동 완성은 요구하지 않는다.")

def update_one(path:Path,write:bool)->bool:
    with ZipFile(path) as archive:
        infos=archive.infolist()
        if len(infos)!=14 or len(set(i.filename for i in infos))!=14 or archive.testzip():
            raise ValueError("Corrupt 14 MD ZIP: "+path.name)
        data={i.filename:archive.read(i.filename).decode("utf-8") for i in infos}
    name="04_OUTPUT_FILES.md"
    contents=data[name]
    if OLD in contents:
        if not write:raise ValueError("Legacy handoff still in "+path.name)
        # Only replace contract prose. Preserve the embedded Python validator
        # unchanged so downstream CLI validation stays executable.
        data[name]=contents.replace(OLD,NEW)
    elif NEW not in contents:
        raise ValueError("Final PSD policy absent: "+path.name)
    else:
        return False
    temp=None
    try:
        with tempfile.NamedTemporaryFile(dir=path.parent,suffix=".zip",prefix="psd-handoff-",delete=False) as handle:
            temp=Path(handle.name)
        with ZipFile(temp,"w") as archive:
            for i in infos:archive.writestr(i,data[i.filename].encode("utf-8"))
        with ZipFile(temp) as archive:
            if archive.testzip() is not None or archive.namelist()!=list(data):
                raise ValueError("Repack damaged "+path.name)
        os.replace(temp,path)
        temp=None
    finally:
        if temp:temp.unlink(missing_ok=True)
    return True

def main():
    parser=argparse.ArgumentParser()
    group=parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--check",action="store_true")
    group.add_argument("--write",action="store_true")
    args=parser.parse_args()
    source=(KIT/"source/ARTWORK_LAYER_ORDER_CONTRACT.md").read_text(encoding="utf-8")
    if NEW not in source or OLD in source:
        raise ValueError("Canonical final-PSD source contract not updated")
    n=0
    for mode in MODES:
        for asset in ASSETS:
            n+=int(update_one(KIT/"zips"/f"{mode}__{asset}.zip",args.write))
    print(f"PASS: 20 final PSD handoff briefs, updated={n}")
if __name__=="__main__":main()
