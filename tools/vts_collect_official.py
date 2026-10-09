"""Safely ingest genuine native Cubism Editor ZIP after external MOC3 export."""
from __future__ import annotations
from pathlib import Path, PurePosixPath
from zipfile import ZipFile

MAX_ITEM=512*1024*1024
MAX_TOTAL=2*1024*1024*1024

def collect_official_cubism_zip(archive_path: str, output_dir: str) -> str:
    """Return official Live2D export ZIP after validating MOC3 references."""
    src=Path(archive_path)
    if not src.is_file() or src.suffix.lower()!=".zip":
        raise ValueError("Expected official Cubism Editor export ZIP")
    dest=Path(output_dir)
    dest.mkdir(parents=True,exist_ok=True)
    extracted=dest/"unpacked"
    extracted.mkdir(exist_ok=True)
    total=0
    with ZipFile(src) as archive:
        for item in archive.infolist():
            if item.is_dir():continue
            p=PurePosixPath(item.filename.replace("\\","/"))
            if p.is_absolute() or ".." in p.parts or not p.parts:
                raise ValueError("Unsafe Cubism archive path")
            if item.file_size>MAX_ITEM:
                raise ValueError("Oversized Cubism file")
            total+=item.file_size
            if total>MAX_TOTAL:
                raise ValueError("Cubism package exceeds 2GiB")
            if (item.external_attr>>16)&0o170000==0o120000:
                raise ValueError("Archive symlink forbidden")
            target=extracted.joinpath(*p.parts)
            target.parent.mkdir(parents=True,exist_ok=True)
            with archive.open(item) as source,target.open("wb") as out:
                import shutil
                shutil.copyfileobj(source,out,1024*1024)
    from vtuber_pipeline.two_d.cubism_handoff import collect_official_export
    report=collect_official_export(str(extracted),str(dest/"validated"))
    if report.status!="complete":
        raise RuntimeError("Official Cubism export validation did not complete")
    result=dest/"validated"/"live2d_official_export.zip"
    if not result.is_file():
        raise RuntimeError("Validator did not create official export package")
    return str(result)
