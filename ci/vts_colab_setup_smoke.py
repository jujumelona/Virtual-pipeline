"""Offline smoke test for the real Colab Live2D preparation cell.

Run with: python -m ci.vts_colab_setup_smoke
No model downloads, GPU, pytest, or PSD2Live installation required.
"""
from __future__ import annotations

import ast
import json
import os
from pathlib import Path
from types import SimpleNamespace
import sys


def main() -> None:
    notebook = (Path(__file__).resolve().parents[1] /
                "notebooks/VTuber_Commercial_Pipeline_Colab_v8.ipynb")
    cells = json.loads(notebook.read_text(encoding="utf-8"))["cells"]
    code_cells = ["".join(cell["source"]) for cell in cells
                  if cell.get("cell_type") == "code"]
    for index, source in enumerate(code_cells):
        try:
            ast.parse(source)
        except SyntaxError as exc:
            raise AssertionError(f"Notebook code cell {index} is invalid") from exc

    setup = next((source for source in code_cells
                  if source.startswith("#@title ⑦ AI 모델")), None)
    assert setup is not None, "Live2D preparation cell not found"
    tree = ast.parse(setup)
    branch = next((node for node in tree.body
                   if isinstance(node, ast.If)
                   and "live2d_free" in ast.unparse(node.test)
                   and "LIVE2D_INPUT_KIND" in ast.unparse(node.test)), None)
    assert branch is not None, "Live2D preparation branches not found"
    isolated = compile(ast.fix_missing_locations(
        ast.Module(body=[branch], type_ignores=[])), str(notebook), "exec")

    for input_kind in ("ai_asset_zip", "master_image"):
        commands = []

        def record(command, timeout):
            assert timeout > 0
            commands.append(command)

        namespace = {
            "scope": "live2d_free",
            "LIVE2D_INPUT_KIND": input_kind,
            "LIVE2D_EDITION": "free",
            "LIVE2D_PRO_ASSET": "body",
            "LIVE2D_USE_QWEN": False,
            "USAGE": "personalNonProfit",
            "repo": Path("/content/Virtual-pipeline"),
            "pathlib": __import__("pathlib"),
            "sys": sys,
            "os": SimpleNamespace(environ={}, pathsep=os.pathsep),
            "run": record,
        }
        # Intentionally do not define 'Path' in this namespace. ⑦ must
        # resolve every name itself, without relying on later notebook cells.
        exec(isolated, namespace)
        cli = [command for command in commands
               if "tools.vts_psd2live" in command]
        assert len(cli) == 1, f"{input_kind}: expected one PSD2Live setup"
        assert "/content/vtuber_builder/third_party" in cli[0]
        print(f"[Colab smoke] {input_kind}: PASS")
    print(f"[Colab smoke] {len(code_cells)} notebook code cells parse: PASS")


if __name__ == "__main__":
    main()
