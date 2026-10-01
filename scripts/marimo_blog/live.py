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
import sys

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


def trimmed(code: str, names: set[str]) -> str:
    """The code, with import statements that keep only the names in `names`."""
    tree = ast.parse(code)
    body = []
    for node in tree.body:
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            node.names = [a for a in node.names if (a.asname or a.name.split(".")[0]) in names]
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


def live_group(builder, gid: str, group: dict) -> dict:
    s, controls = builder.s, builder.page.controls
    editors = [n for n in group["controls"] if controls[n]["kind"] == "editor"]
    if len(editors) != 1 or len(group["controls"]) != 1:
        raise UnsupportedGroup("one code editor alone is supported in a live group")
    editor = editors[0]
    cells = [i for i in s.order if i in group["cells"]]
    order, names = needed_cells(s, cells, skip={"mo", editor})
    setup = "\n\n".join(trimmed(s.cells[i].code, names) for i in order)
    modules = imported_modules(setup)
    for i in cells:
        modules |= imported_modules(s.cells[i].code)
    return {
        "kind": "live",
        "editor": editor,
        "cells": cells,
        "setup": setup,
        "run": {str(i): s.cells[i].code for i in cells},
        "packages": requirements(modules),
        "pyodide": PYODIDE_VERSION,
    }
