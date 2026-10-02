"""Check a converted post: replay random reader events on the page data and on the notebook.

For each table group, random event sequences (slider moves, clicks) run on:
- a Python twin of the browser runtime (mb.js tableEvent and mb-core.js applyOps), from the page's
  default output and the group's data;
- the notebook, run by the converter's runner (runner.Session: marimo runs each cell; the runner
  copies marimo's rules for which cells run again), with the event seeds that the converter used.
After each event, each cell of the group must show the same text, figures and charts. Sampler
groups get random matrix values the same way. (Live groups are checked when they are built:
live.check_live.) The page load is compared with a fresh run of the notebook (marimo's App.run).
Each difference becomes a converter warning: the widget would not act as in marimo.

The reference is the runner, not marimo's kernel: where the runner and marimo differ, this check
cannot see it (tests/test_marimo_blog_patterns.py and tests/test_marimo_blog_review.py hold the
marimo behaviors that the runner copies).
"""

from __future__ import annotations

import copy
import random
import re

import numpy as np

from . import html as H
from . import ops as O
from . import rng
from .model import Page
from .runner import Session

SEQUENCES = 2
EVENTS = 15


def follow(table: dict, key: str):
    value = table.get(key)
    while isinstance(value, dict) and "same_as" in value:
        value = table.get(value["same_as"])
    return value


def resolve(value, pools: dict):
    """The twin of mb-core.js resolve, for the group data before emit ({"$normal": ...} only)."""
    if isinstance(value, dict):
        if "$normal" in value:
            recipe = value["$normal"]
            z = np.asarray(pools[recipe["z"]], dtype=float)
            loc = np.asarray(resolve(recipe["loc"], pools), dtype=float)
            scale = np.asarray(resolve(recipe["scale"], pools), dtype=float)
            return (loc + scale * z).tolist()
        return {k: resolve(v, pools) for k, v in value.items()}
    if isinstance(value, list):
        return [resolve(v, pools) for v in value]
    return value


def close(a, b, path="") -> str | None:
    """None when a and b agree (numbers within the converter's rounding), else the first difference."""
    if isinstance(a, dict) and isinstance(b, dict):
        for key in sorted(set(a) | set(b)):
            if key not in a or key not in b:
                return f"{path}/{key}: only in {'the blog' if key in a else 'the notebook'}"
            problem = close(a[key], b[key], f"{path}/{key}")
            if problem:
                return problem
        return None
    if isinstance(a, list) and isinstance(b, list):
        if len(a) != len(b):
            return f"{path}: {len(a)} items in the blog, {len(b)} in the notebook"
        numbers = [v for v in b if isinstance(v, (int, float)) and not isinstance(v, bool)]
        scale = max([abs(v) for v in numbers] + [1e-12]) if numbers else 1.0
        for i, (x, y) in enumerate(zip(a, b)):
            if isinstance(x, (int, float)) and isinstance(y, (int, float)) and not isinstance(x, bool):
                if abs(x - y) > 2e-3 * scale:
                    return f"{path}/{i}: {x} in the blog, {y} in the notebook"
            else:
                problem = close(x, y, f"{path}/{i}")
                if problem:
                    return problem
        return None
    if a != b and not (isinstance(a, (int, float)) and isinstance(b, (int, float))
                       and abs(a - b) <= 2e-3 * max(1.0, abs(b))):
        return f"{path}: {a!r} in the blog, {b!r} in the notebook"
    return None


class Twin:
    """The browser's state for one table group: each cell's HTML, figures and charts, the slider
    positions and the click counts."""

    def __init__(self, page: Page, data: dict):
        self.data = data
        rendered = {c.index: c.rendered for c in page.cells if c.kind == "html" and c.rendered is not None}
        self.cells = [c for c in data["cells"] if c in rendered]
        self.originals = {c: {"html": rendered[c].html, "figures": rendered[c].figures, "charts": rendered[c].charts}
                          for c in self.cells}
        self.defaults = {f"{c}:{n}": copy.deepcopy(f["figure"])
                         for c in self.cells for n, f in enumerate(rendered[c].figures)}
        self.figures: dict[str, dict] = {}
        self.html: dict[int, str] = {}
        self.charts: dict[int, list] = {}
        self.count: dict[int, int] = {}
        for cell in self.cells:
            self.replace(cell, self.originals[cell])
        self.index = {s: page.controls[s]["index"] for s in data["sliders"]}
        self.clicks: dict[str, int] = {}

    def replace(self, cell: int, payload: dict) -> None:
        """mb.js replaceCell (figure entries of the old output stay, as in mb.js)."""
        self.html[cell] = payload["html"]
        self.charts[cell] = copy.deepcopy(payload.get("charts") or [])
        self.count[cell] = len(payload["figures"])
        for n, fig in enumerate(payload["figures"]):
            self.figures[f"{cell}:{n}"] = copy.deepcopy(fig["figure"])

    def shown(self, cell: int) -> tuple[str, list, list]:
        return self.html[cell], [self.figures[f"{cell}:{n}"] for n in range(self.count[cell])], self.charts[cell]

    def apply(self, effect) -> None:
        for cell, change in (effect or {}).items():
            if "cell" in change:
                self.replace(int(cell), resolve(change["cell"], self.data["pools"]))
                continue
            for n, ops in change.get("figures", {}).items():
                key = f"{cell}:{n}"
                if key in self.figures:
                    self.figures[key] = O.apply(self.figures[key], resolve(ops, self.data["pools"]),
                                                self.defaults.get(key))

    def slider(self, name: str, index: int) -> None:
        self.index[name] = index
        for key in self.data["reset_by"].get(name, []):
            cell, part = key.split(":")
            if part == "cell":
                self.replace(int(cell), self.originals[int(cell)])
            elif key in self.figures:
                self.figures[key] = copy.deepcopy(self.defaults[key])
        for button, info in self.data["buttons"].items():
            if name in info.get("reset_on", []):
                self.clicks[button] = 0
        key = ",".join(str(self.index[s]) for s in self.data["sliders"])
        self.apply(follow(self.data["states"], key))

    def click(self, name: str) -> int | None:
        """Apply a click; return the seed number k that the notebook's click must use (None: no click)."""
        info = self.data["buttons"][name]
        entry = follow(info["table"], ",".join(str(self.index[s]) for s in info["keys"]))
        if info["kind"] == "fixed":
            self.apply(entry)
            for button in info.get("resets", []):
                self.clicks[button] = 0
            return 0
        k = self.clicks.get(name, 0)
        if entry is None or k >= len(entry):
            return None
        self.apply(entry[k])
        self.clicks[name] = k + 1
        return k


def _rendered(session: Session, index: int):
    def name_for_id(object_id):
        element = session.element_by_id(object_id)
        return session.name_of(element) if element is not None else None

    html = session.html(index)
    if not html:
        return None
    out = H.render(html, name_for_id)
    figures = [O.compact_figure(O.decode(f["figure"])) for f in out.figures]
    return out, figures


def _frontend(spec: dict, index: int):
    return index if spec.get("by_index") else spec["values"][index]


HASH = re.compile(r"[0-9a-f]{16,}")  # Altair's dataset names: a hash of the data
NUMBER = re.compile(r"[-+]?(\d+\.?\d*|\.\d+)([eE][-+]?\d+)?")


def masked(value):
    """The value with every number replaced (for output whose numbers come from other draws)."""
    if isinstance(value, dict):
        return {masked(k): masked(v) for k, v in value.items()}
    if isinstance(value, list):
        return [masked(v) for v in value]
    if isinstance(value, str):
        return NUMBER.sub("#", HASH.sub("#", value))
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return 0
    return value


def _short(text: str) -> str:
    return text if len(text) <= 80 else text[:77] + "..."


def compare_cell(blog: tuple[str, list, list], notebook: tuple[str, list, list], numbers: bool = True) -> str | None:
    """The first difference between two cell outputs (html, figures, charts): visible text, then
    figures, then charts. numbers=False compares without the numbers."""
    (blog_html, blog_figs, blog_charts), (html, figs, charts) = blog, notebook
    blog_text, text = H.text_of(blog_html), H.text_of(html)
    if not numbers:
        blog_text, text = masked(blog_text), masked(text)
        blog_figs, figs, blog_charts, charts = masked(blog_figs), masked(figs), masked(blog_charts), masked(charts)
    if blog_text != text:
        return f": the text is {_short(blog_text)!r} in the blog, {_short(text)!r} in the notebook"
    if len(blog_figs) != len(figs):
        return f": {len(blog_figs)} figures in the blog, {len(figs)} in the notebook"
    for n, (a, b) in enumerate(zip(blog_figs, figs)):
        problem = close(a, b)
        if problem:
            return f" figure {n}{problem}"
    problem = close(blog_charts, charts)
    return f" charts{problem}" if problem else None


def notebook_cell(session: Session, cell: int) -> tuple[str, list, list] | None:
    result = _rendered(session, cell)
    if result is None:
        return None
    out, figures = result
    return out.html, figures, [O.compact(chart) for chart in out.charts]


def first_difference(session: Session, twin: Twin) -> str | None:
    for cell in twin.cells:
        shown = notebook_cell(session, cell)
        if shown is None:
            return f"cell {cell}: the notebook shows no output"
        problem = compare_cell(twin.shown(cell), shown)
        if problem:
            return f"cell {cell}{problem}"
    return None


def verify_page_load(path, page: Page) -> list[str]:
    """The page load against a fresh run of the notebook (App.run: the page that marimo shows).
    A cell whose page load comes from its group's draws (page.redrawn) is compared without its
    numbers."""
    problems = []
    with Session(path) as session:
        for cell in page.cells:
            if cell.kind != "html" or cell.rendered is None:
                continue
            shown = notebook_cell(session, cell.index)
            if shown is None:
                problems.append(f"page load: cell {cell.index}: the notebook shows no output")
                continue
            blog = (cell.rendered.html, [f["figure"] for f in cell.rendered.figures], cell.rendered.charts)
            problem = compare_cell(blog, shown, numbers=cell.index not in page.redrawn)
            if problem:
                problems.append(f"page load: cell {cell.index}{problem}")
    return problems


def verify_table(path, page: Page, gid: str, data: dict, seed: int) -> list[str]:
    chooser = random.Random(seed)
    controls = data["sliders"] + list(data["buttons"])
    for _ in range(SEQUENCES):
        twin = Twin(page, data)
        with Session(path) as session:
            for name in data.get("random_sliders", []):  # the group's page load (model.Builder.page_load)
                session.run_users(name, seed=rng.event_seed(gid, "slider"))
            problem = first_difference(session, twin)
            if problem:
                return [f"{gid}: at page load: {problem}"]
            events = []
            for _ in range(EVENTS):
                name = chooser.choice(controls)
                if name in data["sliders"]:
                    index = chooser.randrange(len(page.controls[name]["values"]))
                    twin.slider(name, index)
                    session.set_value(name, _frontend(page.controls[name], index),
                                      seed=rng.event_seed(gid, "slider"))
                    events.append(f"{name}={page.controls[name]['values'][index]}")
                else:
                    k = twin.click(name)
                    if k is None:  # the precomputed clicks are used up: no click in either
                        continue
                    session.set_value(name, 1, seed=rng.event_seed(gid, name, k))
                    events.append(f"click {name}")
                problem = first_difference(session, twin)
                if problem:
                    # one difference is enough: the rest would start from a wrong state
                    return [f"{gid}: after {', '.join(events)}: {problem}"]
    return []


def verify_sampler(path, page: Page, gid: str, data: dict, seed: int) -> list[str]:
    problems = []
    chooser = random.Random(seed)
    names = [n for n, spec in page.controls.items() if spec.get("group") == gid]
    current = {n: [[float(v) for v in row] for row in page.controls[n]["value"]] for n in names}
    with Session(path) as session:
        for _ in range(EVENTS):
            name = chooser.choice(names)
            spec = page.controls[name]
            value = current[name]
            i, j = chooser.randrange(len(value)), chooser.randrange(len(value[0]))
            step = spec["step"][i][j] if isinstance(spec.get("step"), list) else (spec.get("step") or 0.1)
            value[i][j] = round(value[i][j] + chooser.randint(-5, 15) * step, 10)
            low = spec["min"][i][j] if isinstance(spec.get("min"), list) else spec.get("min")
            high = spec["max"][i][j] if isinstance(spec.get("max"), list) else spec.get("max")
            if low is not None:
                value[i][j] = max(value[i][j], low)
            if high is not None:
                value[i][j] = min(value[i][j], high)
            if spec.get("symmetric") and len(value) == len(value[0]):
                value[j][i] = value[i][j]
            session.set_value(name, [row[:] for row in value], seed=rng.event_seed(gid))
            out = _rendered(session, data["cell"])
            if out is None:
                continue
            cov = current[data["cov"]["control"]]
            if data["check"] == "raise" and not rng.is_psd(cov):
                if data["error"] is None or H.text_of(out[0].html) != H.text_of(data["error"]["html"]):
                    problems.append(f"{gid}: the error state for covariance {cov} differs from the notebook")
                continue
            mean = (np.asarray(current[data["mean"]["control"]], dtype=float).ravel()
                    if "control" in data["mean"] else np.asarray(data["mean"]["value"], dtype=float))
            samples = np.asarray(data["z"], dtype=float) @ rng.sqrt_factor(cov) + mean
            target = data["target"]
            if "chart" in target:
                datasets = out[0].charts[target["chart"]].get("datasets") or {}
                found = any(isinstance(rows, list) and len(rows) == len(samples)
                            and all(close([row.get(f) for row in rows], samples[:, j].tolist()) is None
                                    for j, f in enumerate(target["fields"]))
                            for rows in datasets.values())
            else:
                fig = out[1][target["figure"]]
                found = all(close(O.get_path(fig, p_), samples[:, j].tolist()) is None
                            for j, p_ in enumerate(target["paths"]))
            if not found:
                problems.append(f"{gid}: for mean {mean.tolist()} and covariance {cov}, the samples differ from the notebook")
    return problems


def verify(path, page: Page, seed: int = 0) -> list[str]:
    """Problems found by the check (empty when the post acts as the notebook does)."""
    checks = [("page load", lambda: verify_page_load(path, page))]
    for number, (gid, data) in enumerate(page.groups.items()):
        if data["kind"] == "table":
            checks.append((gid, lambda gid=gid, data=data, n=number: verify_table(path, page, gid, data, seed + n)))
        elif data["kind"] == "sampler":
            checks.append((gid, lambda gid=gid, data=data, n=number: verify_sampler(path, page, gid, data, seed + n)))
    problems = []
    for name, check in checks:
        try:
            problems += check()
        except Exception as error:  # noqa: BLE001 - a failed check is a warning, not a failed build
            problems.append(f"{name}: the check failed ({type(error).__name__}: {error})")
    return list(dict.fromkeys(problems))
