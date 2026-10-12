"""CPU-only regression for artwork-first Live2D API and CLI defaults."""
import ast
from pathlib import Path

SOURCE = Path(__file__).resolve().parents[1] / "tools" / "vts_production.py"


def test_make_cubism_handoff_defaults_to_editable_psd_not_rigging():
    tree = ast.parse(SOURCE.read_text(encoding="utf-8"))
    func = next(node for node in tree.body
                if isinstance(node, ast.FunctionDef) and node.name == "make_cubism_handoff")
    args = func.args.kwonlyargs
    defaults = dict(zip((a.arg for a in args), func.args.kw_defaults))
    assert isinstance(defaults["psd2live"], ast.Constant)
    assert defaults["psd2live"].value is False


def test_cli_requires_explicit_psd2live_opt_in():
    text = SOURCE.read_text(encoding="utf-8")
    assert 'default=False, help="Opt in to third-party PSD2Live CLI; default PSD-only"' in text
    assert 'dest="psd2live", action="store_false"' in text
    assert 'psd2live=args.psd2live' in text
