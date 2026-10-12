"""No-network smoke for the replacement five-mode Colab UI.

Phase 1 should never import/setup any image splitting models, packages
or production engines. Validate syntax + all 20 combinations.
"""
from __future__ import annotations

import ast
import json
from pathlib import Path

from tools.colab_mode_ui import ASSET_KINDS, TOP_MODE_CHOICES, select_mode


def main() -> None:
    nb_path = (Path(__file__).resolve().parents[1] /
               "notebooks/VTuber_Commercial_Pipeline_Colab_v8.ipynb")
    cells = json.loads(nb_path.read_text(encoding="utf-8"))["cells"]
    code = ["".join(c["source"]) for c in cells if c["cell_type"] == "code"]
    assert len(code) >= 9, f"Expected selection and production cells, found {len(code)}"
    assert "TOP_MODE_LABEL" in code[1]
    assert "ASSET_KIND_LABEL" in code[2]
    for i, content in enumerate(code):
        ast.parse(content, filename=f"colab-ui-cell-{i}")
    for mode in TOP_MODE_CHOICES:
        for asset in ASSET_KINDS:
            row = select_mode(mode, asset).as_dict()
            assert row["top_mode"] == mode and row["asset_kind"] == asset
    forbidden = ("tools.vts_setup", "tools.colab_mode_prepare",
                 "See-through", "Qwen", "SAM", "activate_2d_environment",
                 "pip install", "--prepare")
    joined = "\n".join(code[:4])
    assert all(word not in joined for word in forbidden)
    print("[Colab UI smoke] Five modes × four common assets = 20 selections: PASS")
    print("[Colab UI smoke] No splitter installs/inference in four selection cells: PASS")


if __name__ == "__main__":
    main()
