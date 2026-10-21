"""Prevent a second, hidden-underpaint-unaware Colab neckline rejection.

The first multiview validator checks the real hidden neck seam. The notebook
MUST reuse its structured neck report, not invoke the old neck/torso visible
overlap function independently.
"""
from __future__ import annotations

import json
import textwrap
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
NOTEBOOK = REPO / "notebooks/VTuber_Finished_AI_ZIP_All_Modes.ipynb"


def notebook_validation_source():
    book = json.loads(NOTEBOOK.read_text(encoding="utf-8"))
    cells = ["".join(c["source"]) for c in book["cells"] if c.get("cell_type") == "code"]
    return next(s for s in cells if "다각도/파츠 원화 사전 검사:" in s)


def test_notebook_reuses_exact_semantic_preflight_neck_report(capsys):
    src = notebook_validation_source()
    assert "SOURCE_QA=prepare_multiview_input(" in src
    assert "skin_joint=SOURCE_QA['parts']['neck']" in src
    assert "require_live2d_body_underpaint(" not in src
    assert "from tools.vts_native_visual_quality import require_live2d_body_underpaint" not in src
    compile(src, str(NOTEBOOK), "exec")

    # Run the actual body post-preflight block rather than accepting a
    # comment-only workaround or duplicating the legacy geometry test.
    start = src.index("    if MODE.startswith('live2d') and ASSET=='body' and not SOURCE_ONLY:\n")
    end = src.index("    if SOURCE_ONLY:\n", start)
    block = textwrap.dedent(src[start:end])
    verified = {
        "status": "EXPLICIT_HIDDEN_NECK_BRIDGE_PRESENT_RIG_VISUAL_REVIEW_REQUIRED",
        "face_neck_overlap_pixels": 0,
        "hidden_neck_overlap_pixels": 20204,
        "hidden_torso_overlap_pixels": 7760,
        "hidden_jaw_overlap_pixels": 10917,
        "editor_review_required": True,
    }
    namespace = {
        "MODE": "live2d_bust_up", "ASSET": "body", "SOURCE_ONLY": False,
        "SOURCE_QA": {"parts": {
            "status": "SEMANTIC_SOURCE_PREFLIGHT_PASS", "neck": verified}},
    }
    exec(compile(block, str(NOTEBOOK), "exec"), namespace)
    assert namespace["skin_joint"] is verified
    assert "목/몸통 원화 회전 연결" in capsys.readouterr().out


def test_failed_semantic_preflight_does_not_become_success():
    src = notebook_validation_source()
    start = src.index("    if MODE.startswith('live2d') and ASSET=='body' and not SOURCE_ONLY:\n")
    end = src.index("    if SOURCE_ONLY:\n", start)
    namespace = {
        "MODE": "live2d_bust_up", "ASSET": "body", "SOURCE_ONLY": False,
        "SOURCE_QA": {"parts": {
            "status": "INVALID", "neck": {"status": "REQUIRES_REGENERATION"}}},
    }
    with pytest.raises(RuntimeError, match="목/몸통 연결 사전 검사 미통과"):
        exec(compile(textwrap.dedent(src[start:end]),
                     str(NOTEBOOK), "exec"), namespace)
