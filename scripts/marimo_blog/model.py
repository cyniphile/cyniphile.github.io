"""Build the page model: each cell's default output, and the precomputed effects of reader events.

Controls that change the same cells (or that one cell defines) form a group. A group is one of:

- "table": sliders and buttons. Each combination of slider values is simulated (marimo semantics,
  see runner.Session), and the effect on each changed figure is stored as operations. "New Sample"
  style buttons (their click appends traces) get a list of operations per click, for each slider
  combination that changes them. Other buttons get one fixed list of operations.
- "sampler": matrix inputs whose value feeds np.random.multivariate_normal directly. The browser
  computes the samples from the recorded standard-normal draws (rng.py, mb-core.js).
- "live": a code editor; the browser runs the cells again with Pyodide (live.py).

A group that the converter cannot handle keeps its default output, with a warning.
"""

from __future__ import annotations

import ast
import hashlib
import itertools
import json
import textwrap
from dataclasses import dataclass, field

import numpy as np

from . import html as H
from . import ops as O
from . import rng
from .runner import Session

MAX_STATES = 6000
APPEND_BUDGET = 200_000  # most numbers stored for the appended traces of one button
MAX_CLICKS = 20
PRIMITIVE_MIN_SIZE = 500  # arrays at least this long that a sampler produced are computed in the browser


@dataclass
class CellOut:
    index: int
    kind: str  # "markdown", "code" or "html"
    markdown: str | None = None
    code: str | None = None
    rendered: H.Rendered | None = None


@dataclass
class Page:
    cells: list[CellOut]
    controls: dict[str, dict]
    groups: dict[str, dict] = field(default_factory=dict)
    warnings: list[str] = field(default_factory=list)


def markdown_of(code: str) -> str | None:
    """The text of a cell that is only mo.md(<string literal>), dedented like marimo does."""
    try:
        tree = ast.parse(code)
    except SyntaxError:
        return None
    if len(tree.body) != 1 or not isinstance(tree.body[0], ast.Expr):
        return None
    call = tree.body[0].value
    if not (isinstance(call, ast.Call) and isinstance(call.func, ast.Attribute) and call.func.attr == "md"
            and isinstance(call.func.value, ast.Name) and call.func.value.id == "mo"
            and len(call.args) == 1 and not call.keywords
            and isinstance(call.args[0], ast.Constant) and isinstance(call.args[0].value, str)):
        return None
    return textwrap.dedent(call.args[0].value).strip()


def _key(*indexes) -> str:
    return ",".join(str(i) for i in indexes)


def _digest(obj) -> str:
    return hashlib.sha256(json.dumps(obj, sort_keys=True).encode()).hexdigest()[:16]


class Builder:
    def __init__(self, session: Session):
        self.s = session
        self.page = Page(cells=[], controls={})
        self.base = session.checkpoint()
        self.default: dict[int, H.Rendered] = {}
        self._affected: dict[str, set[int]] = {}
        self._appender: dict[str, bool] = {}

    # ---- rendering ----

    def name_for_id(self, object_id: str) -> str | None:
        element = self.s.element_by_id(object_id)
        return self.s.name_of(element) if element is not None else None

    def rendered(self, index: int) -> H.Rendered | None:
        html = self.s.html(index)
        if not html:
            return None
        out = H.render(html, self.name_for_id)
        for fig in out.figures:
            fig["figure"] = O.compact_figure(O.decode(fig["figure"]))
            fig["config"] = O.compact(fig["config"])
        out.charts = [O.compact(chart) for chart in out.charts]
        return out

    def set_default(self, index: int, out: H.Rendered) -> None:
        """Show another output at page load (a group can need the default from its own draws)."""
        self.default[index] = out
        for cell in self.page.cells:
            if cell.index == index:
                cell.rendered = out

    def figures(self, index: int) -> list[dict]:
        out = self.rendered(index)
        return [f["figure"] for f in out.figures] if out else []

    # ---- page ----

    def build(self) -> Page:
        for cell in self.s.cells:
            text = markdown_of(cell.code)
            if text is not None:
                self.page.cells.append(CellOut(cell.index, "markdown", markdown=text))
                continue
            out = self.rendered(cell.index)
            if out is None or (not out.html.strip() and out.code is None):
                continue
            self.default[cell.index] = out
            for warning in out.warnings:
                self.page.warnings.append(f"cell {cell.index}: {warning}")
            if out.code is not None:
                self.page.cells.append(CellOut(cell.index, "code", code=out.code))
                continue
            self.page.cells.append(CellOut(cell.index, "html", rendered=out))
            for spec in out.controls:
                if spec["name"]:
                    self.page.controls[spec["name"]] = {**spec, "cell": cell.index}
        for number, group in enumerate(self.groups()):
            gid = f"g{number + 1}"
            data = self.build_group(gid, group)
            if data is None:
                continue
            self.page.groups[gid] = data
            for name in group["controls"]:
                self.page.controls[name]["group"] = gid
        self.s.restore(self.base)
        return self.page

    # ---- groups ----

    def probe_value(self, name: str):
        spec = self.page.controls[name]
        if spec["kind"] == "button":
            return 1
        if spec["kind"] == "slider":
            values, index = spec["values"], spec["index"]
            return values[-1] if index != len(values) - 1 else values[0]
        if spec["kind"] == "matrix":
            return _nudged_matrix(spec)
        if spec["kind"] == "editor":
            return spec["value"] + "\n"
        raise ValueError(spec["kind"])

    def affected(self, name: str) -> set[int]:
        """Cells with output that run again after one event on the control."""
        if name not in self._affected:
            self.s.restore(self.base)
            ran = self.s.set_value(name, self.probe_value(name), seed=rng.event_seed("probe", name))
            self._affected[name] = {i for i in ran if i in self.default}
            self.s.restore(self.base)
        return self._affected[name]

    def groups(self) -> list[dict]:
        names = list(self.page.controls)
        affected = {name: self.affected(name) for name in names}
        definer = {name: self.s.definer.get(name) for name in names}
        parent = {name: name for name in names}

        def find(n):
            while parent[n] != n:
                parent[n] = parent[parent[n]]
                n = parent[n]
            return n

        for a, b in itertools.combinations(names, 2):
            if affected[a] & affected[b] or (definer[a] is not None and definer[a] == definer[b]):
                parent[find(a)] = find(b)
        groups: dict[str, dict] = {}
        for name in names:
            root = find(name)
            group = groups.setdefault(root, {"controls": [], "cells": set()})
            group["controls"].append(name)
            group["cells"] |= affected[name]
        return [g for g in groups.values() if g["cells"]]

    def build_group(self, gid: str, group: dict) -> dict | None:
        kinds = {self.page.controls[n]["kind"] for n in group["controls"]}
        try:
            if "editor" in kinds:
                from .live import live_group
                return live_group(self, gid, group)
            if "matrix" in kinds:
                from .sampler import sampler_group
                return sampler_group(self, gid, group)
            return self.table_group(gid, group)
        except UnsupportedGroup as problem:
            self.page.warnings.append(f"{gid} ({', '.join(group['controls'])}): {problem}; it stays static")
            return None
        finally:
            self.s.restore(self.base)

    # ---- table groups ----

    def table_group(self, gid: str, group: dict) -> dict:
        controls = self.page.controls
        sliders = [n for n in group["controls"] if controls[n]["kind"] == "slider"]
        buttons = [n for n in group["controls"] if controls[n]["kind"] == "button"]
        sizes = [len(controls[n]["values"]) for n in sliders]
        states = int(np.prod(sizes)) if sizes else 1
        if states > MAX_STATES:
            raise UnsupportedGroup(f"{states} slider combinations (the limit is {MAX_STATES})")
        default_state = tuple(controls[n]["index"] for n in sliders)
        cells = sorted(group["cells"])
        data = {"kind": "table", "sliders": sliders, "cells": cells, "states": {}, "buttons": {}, "pools": {}}
        # Figures ("cell:number") that a slider event resets, so that their click history goes.
        data["reset_by"] = {n: sorted(v) for n, v in self.figures_reset_by_sliders(sliders, buttons, cells).items()}

        # Slider states: for each figure that differs from the default, reset + changes.
        dedupe: dict[str, str] = {}
        touched: dict[str, set] = {}
        for state in itertools.product(*(range(s) for s in sizes)):
            if state == default_state:
                continue
            with rng.recording() as recorder:
                self.go_to_state(gid, sliders, state)
                effect = self.state_effect(cells)
            for cell, change in effect.items():
                touched.setdefault(cell, set()).update(change.get("figures", {}).keys())
                if "cell" in change:
                    touched.setdefault(cell, set()).add("cell")
            effect = self.use_primitives(effect, recorder, data["pools"])
            key = _key(*state)
            digest = _digest(effect)
            dedupe.setdefault(digest, key)
            data["states"][key] = effect if dedupe[digest] == key else {"same_as": dedupe[digest]}
        if sliders:
            # Back at the default values: reset what the other states change.
            data["states"][_key(*default_state)] = {
                cell: ({"cell": cell_payload(self.default[int(cell)])} if "cell" in keys
                       else {"figures": {n: [{"op": "reset"}] for n in sorted(keys)}})
                for cell, keys in touched.items()
            }

        # Buttons.
        for name in buttons:
            data["buttons"][name] = self.button_effects(gid, name, sliders, sizes, default_state, buttons, cells)
            if data["buttons"][name]["kind"] == "append":
                targets = data["buttons"][name]["targets"]
                data["buttons"][name]["reset_on"] = sorted(
                    s for s, figs in data["reset_by"].items() if set(figs) & set(targets))
        return data

    def go_to_state(self, gid: str, sliders: list[str], state: tuple) -> None:
        self.s.restore(self.base)
        for name, index in zip(sliders, state):
            spec = self.page.controls[name]
            if index != spec["index"]:
                self.s.set_value(name, spec["values"][index], seed=rng.event_seed(gid, "slider"))

    def state_effect(self, cells: list[int]) -> dict:
        """Per cell: for each figure that differs from the default, reset + changes; or a whole new
        cell when its HTML differs."""
        effect = {}
        for index in cells:
            now, default = self.rendered(index), self.default[index]
            if now is None:
                continue
            if now.html != default.html or len(now.figures) != len(default.figures):
                effect[str(index)] = {"cell": cell_payload(now)}
                continue
            figure_ops = {}
            for number, (fig_now, fig_default) in enumerate(zip(now.figures, default.figures)):
                if fig_now["figure"] != fig_default["figure"]:
                    figure_ops[str(number)] = O.reset_ops(fig_default["figure"], fig_now["figure"])
            if figure_ops:
                effect[str(index)] = {"figures": figure_ops}
        return effect

    def figures_reset_by_sliders(self, sliders, buttons, cells) -> dict[str, set]:
        """For each slider: the figures ("cell:number") that its event resets (click history is lost)."""
        appenders = [b for b in buttons if self.is_appender(b)]
        result: dict[str, set] = {}
        for name in sliders:
            spec = self.page.controls[name]
            result[name] = set()
            if not appenders:
                continue
            self.s.restore(self.base)
            for b in appenders:
                self.s.set_value(b, 1, seed=1)
                self.s.set_value(b, 1, seed=2)
            before = {i: self.figures(i) for i in cells}
            other = spec["values"][-1] if spec["index"] != len(spec["values"]) - 1 else spec["values"][0]
            self.s.set_value(name, other, seed=3)
            for i in cells:
                after = self.figures(i)
                for number, (b_fig, a_fig) in enumerate(zip(before[i], after)):
                    if len(a_fig.get("data", [])) < len(b_fig.get("data", [])):
                        result[name].add(f"{i}:{number}")
        self.s.restore(self.base)
        return result

    def is_appender(self, name: str) -> bool:
        """True when a click on the button appends traces to a figure ("New Sample")."""
        if name not in self._appender:
            cells = self.affected(name)
            before = {i: self.figures(i) for i in cells}
            self.s.set_value(name, 1, seed=1)
            self._appender[name] = any(len(a.get("data", [])) > len(b.get("data", []))
                                       for i in cells for b, a in zip(before[i], self.figures(i)))
            self.s.restore(self.base)
        return self._appender[name]

    def click_ops(self, name: str, cells: list[int], seed: int) -> dict:
        before = {i: self.figures(i) for i in cells}
        self.s.set_value(name, 1, seed=seed)
        effect = {}
        for i in cells:
            changes = {}
            for number, (b, a) in enumerate(zip(before[i], self.figures(i))):
                fig_ops = O.figure_ops(b, a)
                if fig_ops:
                    changes[str(number)] = fig_ops
            if changes:
                effect[str(i)] = {"figures": changes}
        return effect

    def button_effects(self, gid, name, sliders, sizes, default_state, buttons, cells) -> dict:
        if not self.is_appender(name):
            # A fixed effect: the same operations after 2 and after 3 appended samples.
            appenders = [b for b in buttons if b != name and self.is_appender(b)]
            effects = []
            for clicks in (2, 3):
                self.s.restore(self.base)
                for k in range(clicks):
                    for b in appenders:
                        self.s.set_value(b, 1, seed=rng.event_seed(gid, b, k))
                effects.append(self.click_ops(name, cells, seed=rng.event_seed(gid, name)))
            if effects[0] != effects[1]:
                raise UnsupportedGroup(f"the effect of {name} depends on the earlier clicks")
            resets = any(op["op"] == "truncate" for cell in effects[0].values()
                         for fig_ops in cell.get("figures", {}).values() for op in fig_ops)
            return {"kind": "fixed", "ops": effects[0], "resets": resets}

        # An appending button: a list of click effects, per slider state that changes them.
        def clicks_for(state: tuple, count: int) -> list[dict]:
            self.go_to_state(gid, sliders, state)
            return [self.click_ops(name, cells, seed=rng.event_seed(gid, name, k)) for k in range(count)]

        probe = clicks_for(default_state, 1)
        numbers = _count_numbers(probe[0]) or 1
        relevant = []  # sliders that change the appended traces
        for position, slider in enumerate(sliders):
            spec = self.page.controls[slider]
            other = list(default_state)
            other[position] = (spec["index"] + len(spec["values"]) // 2) % len(spec["values"])
            if clicks_for(tuple(other), 1) != probe:
                relevant.append(position)
        keyed_states = [s for s in itertools.product(*(range(n) for n in sizes))
                        if all(s[p] == default_state[p] for p in range(len(sizes)) if p not in relevant)]
        pool = max(1, min(MAX_CLICKS, APPEND_BUDGET // (numbers * len(keyed_states))))
        table, dedupe = {}, {}
        for state in keyed_states:
            effects = clicks_for(state, pool)
            key = _key(*(state[p] for p in relevant))
            digest = _digest(effects)
            dedupe.setdefault(digest, key)
            table[key] = effects if dedupe[digest] == key else {"same_as": dedupe[digest]}
        targets = sorted({f"{cell}:{number}" for cell, change in probe[0].items()
                          for number in change.get("figures", {})})
        return {"kind": "append", "keys": [sliders[p] for p in relevant], "pool": pool, "clicks": table,
                "targets": targets}

    # ---- primitives ----

    def use_primitives(self, effect: dict, recorder: rng.Recorder, pools: dict) -> dict:
        """Replace long sampled arrays by a recipe that the browser computes ({"$normal": ...})."""
        recipes = []
        for call in recorder.calls:
            if call.fn != "normal" or call.result is None or call.result.size < PRIMITIVE_MIN_SIZE:
                continue
            z = O.compact(call.z.ravel())
            pool_id = _digest(z)
            pools.setdefault(pool_id, z)
            recipe = {"$normal": {"loc": O.compact(call.params["loc"]), "scale": O.compact(call.params["scale"]),
                                  "z": pool_id}}
            recipes.append((O.compact(call.result.ravel()), recipe))
        if not recipes:
            return effect

        def swap(value):
            if isinstance(value, list) and len(value) >= PRIMITIVE_MIN_SIZE:
                for result, recipe in recipes:
                    if value == result:
                        return recipe
            if isinstance(value, dict):
                return {k: swap(v) for k, v in value.items()}
            if isinstance(value, list):
                return [swap(v) for v in value]
            return value

        return swap(effect)


class UnsupportedGroup(Exception):
    pass


def cell_payload(out: H.Rendered) -> dict:
    return {"html": out.html, "figures": out.figures, "charts": out.charts}


def _count_numbers(obj) -> int:
    if isinstance(obj, dict):
        return sum(_count_numbers(v) for v in obj.values())
    if isinstance(obj, list):
        return sum(_count_numbers(v) for v in obj)
    return 1 if isinstance(obj, (int, float)) and not isinstance(obj, bool) else 0


def _nudged_matrix(spec: dict):
    value = [list(map(float, row)) for row in spec["value"]]
    step = spec["step"][0][0] if isinstance(spec.get("step"), list) else (spec.get("step") or 0.1)
    value[0][0] = round(value[0][0] + step, 10)
    return value


def build(session: Session) -> Page:
    return Builder(session).build()
