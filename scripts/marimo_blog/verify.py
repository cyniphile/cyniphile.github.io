"""Check a converted post against marimo: replay random reader events on both.

For each table group, random event sequences (slider moves, clicks) run on:
- a Python twin of the browser runtime (mb.js tableEvent and mb-core.js applyOps), from the page's
  default figures and the group's data;
- a fresh marimo session (the notebook itself), with the event seeds that the converter used.
After each event, each figure of the group's cells must agree. Sampler groups get random matrix
values the same way. (Live groups are checked when they are built: live.check_live.) Each
difference becomes a converter warning: the widget would not act as in marimo.
"""

from __future__ import annotations

import copy
import random

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
                return f"{path}/{key}: only in {'the blog' if key in a else 'marimo'}"
            problem = close(a[key], b[key], f"{path}/{key}")
            if problem:
                return problem
        return None
    if isinstance(a, list) and isinstance(b, list):
        if len(a) != len(b):
            return f"{path}: {len(a)} items in the blog, {len(b)} in marimo"
        numbers = [v for v in b if isinstance(v, (int, float)) and not isinstance(v, bool)]
        scale = max([abs(v) for v in numbers] + [1e-12]) if numbers else 1.0
        for i, (x, y) in enumerate(zip(a, b)):
            if isinstance(x, (int, float)) and isinstance(y, (int, float)) and not isinstance(x, bool):
                if abs(x - y) > 2e-3 * scale:
                    return f"{path}/{i}: {x} in the blog, {y} in marimo"
            else:
                problem = close(x, y, f"{path}/{i}")
                if problem:
                    return problem
        return None
    if a != b and not (isinstance(a, (int, float)) and isinstance(b, (int, float))
                       and abs(a - b) <= 2e-3 * max(1.0, abs(b))):
        return f"{path}: {a!r} in the blog, {b!r} in marimo"
    return None


class Twin:
    """The browser's state for one table group: figures, slider positions, click counts."""

    def __init__(self, page: Page, data: dict):
        self.data = data
        self.controls = page.controls
        rendered = {c.index: c.rendered for c in page.cells if c.kind == "html" and c.rendered is not None}
        self.defaults = {f"{cell}:{n}": copy.deepcopy(fig["figure"])
                         for cell in data["cells"] for n, fig in enumerate(rendered[cell].figures)}
        self.figures = copy.deepcopy(self.defaults)
        self.index = {s: self.controls[s]["index"] for s in data["sliders"]}
        self.clicks: dict[str, int] = {}

    def apply(self, effect) -> None:
        for cell, change in (effect or {}).items():
            if "cell" in change:
                payload = resolve(change["cell"], self.data["pools"])
                for n, fig in enumerate(payload["figures"]):
                    self.figures[f"{cell}:{n}"] = fig["figure"]
                continue
            for n, ops in change.get("figures", {}).items():
                key = f"{cell}:{n}"
                self.figures[key] = O.apply(self.figures[key], resolve(ops, self.data["pools"]), self.defaults[key])

    def slider(self, name: str, index: int) -> None:
        self.index[name] = index
        for key in self.data["reset_by"].get(name, []):
            self.figures[key] = copy.deepcopy(self.defaults[key])
        for button, info in self.data["buttons"].items():
            if name in info.get("reset_on", []):
                self.clicks[button] = 0
        key = ",".join(str(self.index[s]) for s in self.data["sliders"])
        self.apply(follow(self.data["states"], key))

    def click(self, name: str) -> int | None:
        """Apply a click; return the seed number k that marimo's click must use (None: no click)."""
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


def first_difference(session: Session, twin: Twin, cells: list[int]) -> str | None:
    for cell in cells:
        result = _rendered(session, cell)
        if result is None:
            continue
        for n, fig in enumerate(result[1]):
            problem = close(twin.figures.get(f"{cell}:{n}"), fig)
            if problem:
                return f"cell {cell} figure {n}{problem}"
    return None


def verify_table(path, page: Page, gid: str, data: dict, seed: int) -> list[str]:
    problems = []
    chooser = random.Random(seed)
    controls = data["sliders"] + list(data["buttons"])
    for _ in range(SEQUENCES):
        twin = Twin(page, data)
        with Session(path) as session:
            for name in data["sliders"]:  # the page's default, as the converter makes it
                spec = page.controls[name]
                session.set_value(name, _frontend(spec, spec["index"]), seed=rng.event_seed(gid, "slider"))
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
                problem = first_difference(session, twin, data["cells"])
                if problem:
                    problems.append(f"{gid}: after {', '.join(events)}: {problem}")
                    break  # the rest of the sequence would start from a wrong state
    return problems


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
                    problems.append(f"{gid}: the error state for covariance {cov} differs from marimo")
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
                problems.append(f"{gid}: for mean {mean.tolist()} and covariance {cov}, the samples differ from marimo")
    return problems


def verify(path, page: Page, seed: int = 0) -> list[str]:
    """Problems found by replaying random events (empty when the post acts as in marimo)."""
    problems = []
    for number, (gid, data) in enumerate(page.groups.items()):
        if data["kind"] == "table":
            problems += verify_table(path, page, gid, data, seed + number)
        elif data["kind"] == "sampler":
            problems += verify_sampler(path, page, gid, data, seed + number)
    return problems
