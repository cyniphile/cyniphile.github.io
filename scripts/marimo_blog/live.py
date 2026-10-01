"""Live groups: a code editor. The browser runs the affected cells again with Pyodide.

The reader's code can be anything, so only Python can run it. The converter ships the code of the
cells that the affected cells need (topological order; import statements keep only the names
that are used, so unused heavy packages are not loaded) and the packages to install. In the
browser, a small stand-in for marimo (blog/assets/mb/mb_live.py) gives the cells `mo` and
the editor's value; Pyodide loads when the reader first edits the code.
"""

from __future__ import annotations

import ast
import importlib.metadata
import importlib.util
import json
import sys
from pathlib import Path

import numpy as np

from . import ops as O
from .model import UnsupportedGroup

PYODIDE_VERSION = "314.0.7"
# Packages that Pyodide builds itself (micropip takes Pyodide's version; do not pin them).
PYODIDE_PACKAGES = {"numpy", "scipy", "pandas", "matplotlib", "scikit-learn", "sympy", "networkx", "pillow",
                    "statsmodels", "shapely", "pyarrow", "altair", "jsonschema", "narwhals"}


def needed_cells(session, cells: list[int], skip: set[str]) -> tuple[list[int], set[str]]:
    """The cells (topological order) that define what the given cells read, and the names read."""
    names = set().union(*(session.cells[i].refs for i in cells)) - skip
    include: set[int] = set()
    while True:
        new = {session.definer[n] for n in names if n in session.definer} - include - set(cells)
        if not new:
            break
        include |= new
        names |= set().union(*(session.cells[i].refs for i in new)) - skip
    return [i for i in session.order if i in include], names


def used_names(code: str) -> set[str]:
    """The names that the code reads or calls (not counting its import statements)."""
    names = set()
    for node in ast.walk(ast.parse(code)):
        if isinstance(node, ast.Name):
            names.add(node.id)
    return names


def trimmed(code: str, used: set[str]) -> str:
    """The code, with import statements that keep only the names that the shipped code uses
    (so that an unused heavy package is not loaded in the browser). marimo imports go: the
    browser's stand-in for marimo gives the cells `mo`."""
    tree = ast.parse(code)
    body = []
    for node in tree.body:
        if isinstance(node, ast.ImportFrom) and (node.module or "").split(".")[0] == "marimo":
            continue
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            node.names = [a for a in node.names if (a.asname or a.name.split(".")[0]) in used
                          and not (isinstance(node, ast.Import) and a.name.split(".")[0] == "marimo")]
            if not node.names:
                continue
        body.append(node)
    tree.body = body
    return ast.unparse(tree)


def imported_modules(code: str) -> set[str]:
    modules = set()
    for node in ast.walk(ast.parse(code)):
        if isinstance(node, ast.Import):
            modules |= {a.name.split(".")[0] for a in node.names}
        elif isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
            modules.add(node.module.split(".")[0])
    return modules


def requirements(modules: set[str]) -> list[str]:
    """micropip requirements for the imported modules (pinned to the build's version, except the
    packages that Pyodide builds)."""
    dists = importlib.metadata.packages_distributions()
    reqs = set()
    for module in sorted(modules):
        if module in sys.stdlib_module_names or module == "marimo":
            continue
        for dist in dists.get(module, [module]):
            name = dist.lower()
            if name in PYODIDE_PACKAGES:
                reqs.add(name)
            else:
                try:
                    reqs.add(f"{name}=={importlib.metadata.version(dist)}")
                except importlib.metadata.PackageNotFoundError:
                    reqs.add(name)
    return sorted(reqs)


MB_LIVE = Path(__file__).resolve().parents[2] / "blog" / "assets" / "mb" / "mb_live.py"


def load_mb_live():
    """The browser's stand-in for marimo (blog/assets/mb/mb_live.py), loaded in CPython."""
    spec = importlib.util.spec_from_file_location("mb_live_check", MB_LIVE)
    if spec is None or spec.loader is None:
        raise ImportError(f"cannot load {MB_LIVE}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def live_group(builder, gid: str, group: dict) -> dict:
    s, controls = builder.s, builder.page.controls
    editors = [n for n in group["controls"] if controls[n]["kind"] == "editor"]
    if len(editors) != 1 or len(group["controls"]) != 1:
        raise UnsupportedGroup("one code editor alone is supported in a live group")
    editor = editors[0]
    # Every cell that marimo runs again after an edit, with or without output, in topological order
    ran = builder.ran_cells(editor)
    order, _ = needed_cells(s, ran, skip={"mo", editor})
    used = set()
    for i in [*order, *ran]:
        used |= used_names(s.cells[i].code)
    setup = "\n\n".join(trimmed(s.cells[i].code, used) for i in order)
    modules = imported_modules(setup)
    for i in ran:
        modules |= imported_modules(s.cells[i].code)
    data = {
        "kind": "live",
        "editor": editor,
        "cells": [i for i in ran if i in group["cells"]],
        "setup": setup,
        "run": [[str(i), s.cells[i].code] for i in ran],  # a list: the order matters
        "packages": requirements(modules),
        "pyodide": PYODIDE_VERSION,
    }
    check_live(builder, data, controls[editor]["value"])
    return data


def check_live(builder, data: dict, code: str) -> None:
    """Run the live group as the browser will (mb_live.py), in CPython, with the editor's default
    code. It must run without errors and give the figures that marimo shows."""
    mb_live = load_mb_live()
    random_state = np.random.get_state()
    real_marimo = sys.modules.get("marimo")
    sys.modules["marimo"] = mb_live.mo  # as in the browser: `import marimo` gives the stand-in
    try:
        mb_live.configure(json.dumps(data))
        results = json.loads(mb_live.run(code))
    except Exception as error:  # noqa: BLE001
        raise UnsupportedGroup(f"the live code does not run in the browser's stand-in for marimo "
                               f"({type(error).__name__}: {error})") from error
    finally:
        sys.modules["marimo"] = real_marimo
        np.random.set_state(random_state)
    for cell in data["cells"]:
        out = results.get(str(cell)) or {}
        if out.get("kind") == "error":
            raise UnsupportedGroup(f"cell {cell} fails in the browser's stand-in for marimo: {out.get('text')}")
        default = builder.default.get(cell)
        if default is None:
            continue
        if default.figures:
            live = O.compact_figure(O.decode(out["figure"])) if out.get("kind") == "plotly" else None
            if live != default.figures[0]["figure"]:
                builder.page.warnings.append(f"cell {cell}: the live code gives another figure than marimo at "
                                             f"page load (check the browser's stand-in for marimo)")
