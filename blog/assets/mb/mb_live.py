"""A small stand-in for marimo, for the cells that a blog post runs live with Pyodide.

mb.js loads this module, calls configure() with the group's data (setup code, the cells to run as
a list of [cell, code], editor name), and run(code) after each edit. The converter runs the same
module in CPython to check a live group (scripts/marimo_blog/live.py). run() returns JSON: per cell, {"kind": "plotly", "figure",
"config"}, {"kind": "html", "html"} or {"kind": "error", "text"}.
"""

import ast
import html
import json
import sys
import traceback
import types


class Output:
    def __init__(self, kind, **data):
        self.kind = kind
        self.data = data


class _Plotly(Output):
    def __init__(self, figure, config=None, label="", **_):
        super().__init__("plotly", figure=figure, config=config or {})


class _Value:
    """What a cell sees for a UI element: its value."""

    def __init__(self, value):
        self.value = value


def _md(text):
    return Output("html", html=f"<pre>{html.escape(str(text))}</pre>")


def _stack(items, **_):
    return Output("stack", items=list(items))


mo = types.ModuleType("marimo")
mo.md = _md
mo.Html = lambda text: Output("html", html=str(text))
mo.show_code = lambda output=None: output
mo.vstack = _stack
mo.hstack = _stack
mo.ui = types.SimpleNamespace(plotly=_Plotly)
sys.modules.setdefault("marimo", mo)

_spec = {}
_namespace = {}


def run_cell(code, namespace):
    """Run a cell's code; return the value of its last expression (as marimo does)."""
    tree = ast.parse(code)
    last = None
    if tree.body and isinstance(tree.body[-1], ast.Expr):
        last = ast.Expression(tree.body.pop().value)
    exec(compile(tree, "<cell>", "exec"), namespace)
    return eval(compile(last, "<cell>", "eval"), namespace) if last else None


def configure(spec_json):
    _spec.clear()
    _spec.update(json.loads(spec_json))
    _namespace.clear()
    _namespace.update({"mo": mo, "__name__": "__main__"})
    run_cell(_spec["setup"], _namespace)


def _payload(out):
    if isinstance(out, _Plotly):
        figure = out.data["figure"]
        if figure is None:
            # marimo shows an error for mo.ui.plotly(None)
            return {"kind": "error", "text": "mo.ui.plotly needs a Plotly figure, not None"}
        data = json.loads(figure.to_json()) if hasattr(figure, "to_json") else figure
        return {"kind": "plotly", "figure": data, "config": out.data["config"]}
    if isinstance(out, Output) and out.kind == "stack":
        for item in out.data["items"]:
            if isinstance(item, _Plotly):
                return _payload(item)
        return {"kind": "html", "html": ""}
    if isinstance(out, Output):
        return {"kind": "html", "html": out.data.get("html", "")}
    if hasattr(out, "to_json"):
        return {"kind": "plotly", "figure": json.loads(out.to_json()), "config": {}}
    return {"kind": "html", "html": "" if out is None else f"<pre>{html.escape(repr(out))}</pre>"}


def run(code):
    """Run the cells (a list of [cell, code], in marimo's order) with the editor's new code. A cell
    after a cell that raised does not run (as in marimo)."""
    _namespace[_spec["editor"]] = _Value(code)
    results = {}
    failed = False
    for cell, cell_code in _spec["run"]:
        if failed:
            results[cell] = {"kind": "error", "text": "This cell did not run: an earlier cell raised an exception."}
            continue
        try:
            results[cell] = _payload(run_cell(cell_code, _namespace))
        except Exception:
            text = traceback.format_exc(limit=-3)
            results[cell] = {"kind": "error", "text": text.replace('File "<cell>", ', "")}
            failed = True
    return json.dumps(results)
