"""SHA-pinned public CC0 PSD2Live character fixtures for real art-quality reviews.

The cases are from tsunehimatoi/psd2live-examples and retain their native PSD,
editable project, real .model3/.moc3, texture and physics. NOT bundled here.
This module does not claim any case passes commercial broadcast QA.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path, PurePosixPath
import stat
import urllib.request
from zipfile import ZipFile

CATALOG = {
    "kirishima-mio": {
        "url": "https://github.com/tsunehimatoi/psd2live-examples/releases/download/assets-v2/kirishima-mio-1.0.0.zip",
        "sha256": "ce09667ec781f05df5ff9a41451299f6090d5b0ab207d1c575ae2f8a7be84390",
        "size": 86393193, "license": "CC0-1.0",
        "purpose": "AI-generated full-body layer registration, neck/hair seam repairs",
    },
    "hiakari-inori": {
        "url": "https://github.com/tsunehimatoi/psd2live-examples/releases/download/assets-v2/hiakari-inori-1.0.0.zip",
        "sha256": "71a2b25b75763d50d1d2bcd72f683915c0138a583ede8fa4bcdc895e00778f64",
        "size": 659714165, "license": "CC0-1.0",
        "purpose": "AI-authored parts, cloth, tail, sleeve/physics simulation",
    },
    "star_lan": {
        "url": "https://github.com/tsunehimatoi/psd2live-examples/releases/download/assets-v1/star_lan-1.0.0.zip",
        "sha256": "9485008ffd52c165dbdcf6ec8dd035d882bbd0dfdc54404c65bf3230453b52fe",
        "size": 97431002, "license": "CC0-1.0",
        "purpose": "joint, multi-texture and AI assisted authoring",
    },
    "ds": {
        "url": "https://github.com/tsunehimatoi/psd2live-examples/releases/download/assets-v1/ds-1.0.0.zip",
        "sha256": "c3f97b6e6ee62ad706667aab5fd765a1603eb4a86a21ec7f62853626aab22eb3",
        "size": 9120777, "license": "CC0-1.0",
        "purpose": "small full-character physics and motion example",
    },
}


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as fh:
        while block := fh.read(1 << 20):
            digest.update(block)
    return digest.hexdigest()


def fetch_case(case: str, output: Path, *, download=None) -> dict:
    """Only known signed archives, no path traversal or stale artifact acceptance."""
    if case not in CATALOG:
        raise ValueError("Unknown CC0 quality case")
    spec = CATALOG[case]
    output = Path(output).resolve()
    if output.exists() and any(output.iterdir()):
        raise ValueError("Case destination must be fresh")
    output.mkdir(parents=True, exist_ok=True)
    archive = output / (case + ".zip")
    if download is None:
        def download(url: str, path: Path):
            request = urllib.request.Request(url, headers={"User-Agent": "Virtual-pipeline-quality-fixture/1"})
            with urllib.request.urlopen(request, timeout=300) as response, path.open("xb") as sink:
                while block := response.read(1 << 20):
                    sink.write(block)
    download(spec["url"], archive)
    actual_sha = _sha256(archive)
    if archive.stat().st_size != spec["size"] or actual_sha != spec["sha256"]:
        archive.unlink(missing_ok=True)
        raise RuntimeError("PUBLIC_QUALITY_CASE_SHA256_MISMATCH: refuse unverified art")
    target = output / "case"
    target.mkdir()
    with ZipFile(archive) as z:
        regular = [entry for entry in z.infolist() if not entry.is_dir()]
        if len(regular) > 2500:
            raise ValueError("PUBLIC_QUALITY_CASE_TOO_MANY_MEMBERS")
        total = sum(i.file_size for i in regular)
        if total > 3 * 1024**3:
            raise ValueError("PUBLIC_QUALITY_CASE_TOO_LARGE_UNCOMPRESSED")
        names = set()
        for item in regular:
            name = item.filename
            parts = PurePosixPath(name)
            mode = (item.external_attr >> 16) & 0o170000
            if (name in names or parts.is_absolute() or ".." in parts.parts
                    or "\\" in name or mode == stat.S_IFLNK or
                    not name or parts.parts[0] == "__MACOSX"):
                raise ValueError("PUBLIC_QUALITY_CASE_UNSAFE_MEMBER")
            names.add(name)
        for item in regular:
            path = target.joinpath(*PurePosixPath(item.filename).parts)
            path.parent.mkdir(parents=True, exist_ok=True)
            with z.open(item) as stream, path.open("xb") as sink:
                while data := stream.read(1 << 20):
                    sink.write(data)
    models = sorted(target.rglob("*.model3.json"))
    projects = sorted(target.rglob("*.psd2live"))
    report = {
        "schema": "vtuber/public-quality-reference-case-v1",
        "case": case, "license": spec["license"],
        "purpose": spec["purpose"],
        "source_archive_url": spec["url"],
        "validated_archive_sha256": actual_sha,
        "source_artifact_dir": str(target),
        "editable_projects": [str(path) for path in projects],
        "native_models": [str(path) for path in models],
        "runtime_quality_verified": False,
        "reference_character_artistic_quality_verified": False,
    }
    (output / "case_report.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    if not models or not projects:
        raise RuntimeError("PUBLIC_QUALITY_CASE_NO_REAL_MODEL_OR_EDITABLE_PROJECT")
    return report


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--case", required=True, choices=sorted(CATALOG))
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(fetch_case(args.case, args.output), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
