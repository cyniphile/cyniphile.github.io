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
    redrawn: dict[int, str] = field(default_factory=dict)  # cell → group: page load from the group's draws


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
        self._ran: dict[str, list[int]] = {}
        self._random: list[str] = []  # the current group's sliders whose cells draw random numbers
        self._touched: list[str] = []  # the current group's sliders whose event at the default changes the output

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

    def set_default(self, index: int, out: H.Rendered, gid: str) -> None:
        """Show another output at page load: the group's own draws (page.redrawn records it)."""
        self.default[index] = out
        self.page.redrawn[index] = gid
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
            if out is None:
                continue
            for warning in out.warnings:
                self.page.warnings.append(f"cell {cell.index}: {warning}")
            if not out.html.strip():
                continue
            self.default[cell.index] = out
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
            for cell in self.page.cells:  # shown code that events change: an HTML island
                if cell.kind == "code" and cell.index in group["cells"]:
                    cell.kind, cell.rendered = "html", self.default[cell.index]
        self.s.restore(self.base)
        return self.page

    # ---- groups ----

    def frontend_value(self, name: str, index: int):
        """What marimo's frontend sends for a slider position (the index, for steps=[...])."""
        spec = self.page.controls[name]
        return index if spec.get("by_index") else spec["values"][index]

    def other_index(self, name: str) -> int:
        """A slider position different from the default (for probes)."""
        spec = self.page.controls[name]
        last = len(spec["values"]) - 1
        return last if spec["index"] != last else 0

    def probe_value(self, name: str):
        spec = self.page.controls[name]
        if spec["kind"] == "button":
            return 1
        if spec["kind"] == "slider":
            return self.frontend_value(name, self.other_index(name))
        if spec["kind"] == "matrix":
            return _nudged_matrix(spec)
        if spec["kind"] == "editor":
            return spec["value"] + "\n"
        raise ValueError(spec["kind"])

    def ran_cells(self, name: str) -> list[int]:
        """All cells (with or without output) that run again after one event, in topological order."""
        if name not in self._ran:
            self.s.restore(self.base)
            self._ran[name] = self.s.set_value(name, self.probe_value(name), seed=rng.event_seed("probe", name))
            self.s.restore(self.base)
        return self._ran[name]

    def affected(self, name: str) -> set[int]:
        """Cells with output that run again after one event on the control."""
        return {i for i in self.ran_cells(name) if i in self.default}

    def groups(self) -> list[dict]:
        """Controls that change the same cells form a group (marimo state they share shows up as
        shared cells)."""
        names = list(self.page.controls)
        affected = {name: self.affected(name) for name in names}
        parent = {name: name for name in names}

        def find(n):
            while parent[n] != n:
                parent[n] = parent[parent[n]]
                n = parent[n]
            return n

        for a, b in itertools.combinations(names, 2):
            if affected[a] & affected[b]:
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
        except Exception as error:  # noqa: BLE001 - one odd widget must not stop the whole post
            self.page.warnings.append(f"{gid} ({', '.join(group['controls'])}): the conversion failed "
                                      f"({type(error).__name__}: {error}); it stays static")
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
        # Sliders whose cells draw random numbers: the page load and every state run those cells
        # again with the slider event's draws (page_load).
        self._random = [s for s in sliders if self.draws_random(gid, s)]
        self._touched = []
        data = {"kind": "table", "sliders": sliders, "random_sliders": self._random, "cells": cells,
                "states": {}, "buttons": {}, "pools": {}}
        if self._random:
            self.default_from_event(gid, cells)
        # Sliders whose event changes the output also at the default value (a callback): after the
        # reader moves them, the default position shows that, not the page load.
        self._touched = [s for s in sliders if self.event_at_default_changes(gid, s, cells)]
        kinds = {b: self.button_kind(gid, b, sliders, default_state, cells) for b in buttons}
        listers = [b for b in buttons if kinds[b] == "list"]
        targets = {b: self.button_targets(gid, b, sliders, default_state, cells, listers) for b in buttons}
        # What a slider event resets (marimo rebuilds the state): the targets of the buttons whose
        # effect it removes ("cell:number" figures, "cell:cell" whole cells), and their click counts.
        reset_by, reset_buttons = self.slider_resets(gid, sliders, buttons, targets, cells)
        data["reset_by"] = {n: sorted(v) for n, v in reset_by.items()}
        if sliders:
            data["states"] = self.slider_states(gid, sliders, sizes, default_state, cells, data["pools"])
        for name in buttons:
            data["buttons"][name] = self.button_effects(gid, name, kinds[name], sliders, sizes, default_state,
                                                        listers, cells, targets)
            data["buttons"][name]["reset_on"] = sorted(s for s, names in reset_buttons.items() if name in names)
        return data

    def page_load(self, gid: str) -> None:
        """Go to the page load of the group: the first run, then the cells of the random sliders
        run again with the slider event's draws (no callback runs: marimo runs none at page load)."""
        self.s.restore(self.base)
        for name in self._random:
            self.s.run_users(name, seed=rng.event_seed(gid, "slider"))

    def go_to_state(self, gid: str, sliders: list[str], state: tuple) -> None:
        """From the page load: the default events of the sliders in self._touched (a state is what
        the reader sees after moving sliders), then the sliders that are not at their default value."""
        self.page_load(gid)
        for name in self._touched:
            index = self.page.controls[name]["index"]
            self.s.set_value(name, self.frontend_value(name, index), seed=rng.event_seed(gid, "slider"))
        for name, index in zip(sliders, state):
            if index != self.page.controls[name]["index"]:
                self.s.set_value(name, self.frontend_value(name, index), seed=rng.event_seed(gid, "slider"))

    def event_at_default_changes(self, gid: str, name: str, cells: list[int]) -> bool:
        """True when an event at the slider's default value changes the group's cells."""
        self.page_load(gid)
        before = self.snapshot(cells)
        index = self.page.controls[name]["index"]
        self.s.set_value(name, self.frontend_value(name, index), seed=rng.event_seed(gid, "slider"))
        changed = self.snapshot(cells) != before
        self.s.restore(self.base)
        return changed

    def draws_random(self, gid: str, name: str) -> bool:
        """True when the cells that use the slider draw random numbers."""
        self.s.restore(self.base)
        with rng.recording() as recorder:
            self.s.run_users(name, seed=rng.event_seed(gid, "slider"))
        self.s.restore(self.base)
        return bool(recorder.calls)

    def default_from_event(self, gid: str, cells: list[int]) -> None:
        """At page load, show the cells with the draws of the slider events (page_load), so that
        the states, which use those draws, agree with it."""
        self.page_load(gid)
        for index in cells:
            out = self.rendered(index)
            if out is not None and (out.html != self.default[index].html or out.figures != self.default[index].figures
                                    or out.charts != self.default[index].charts):
                self.set_default(index, out, gid)
        self.s.restore(self.base)

    def slider_states(self, gid, sliders, sizes, default_state, cells, pools) -> dict:
        """The effect of each slider combination, so that it is right from any earlier state.

        Figures get operations without a reset (a reset would remove click history that marimo
        keeps): each path that some state changes is set in every state. A cell whose HTML changes
        in some state is replaced in every state."""
        own: dict[tuple, dict] = {}
        paths: dict[tuple[int, int], set] = {}
        replaced: set[int] = set()
        for state in itertools.product(*(range(s) for s in sizes)):
            if state == default_state and not self._touched:
                own[state] = {"cells": {}, "figures": {}}
                continue
            with rng.recording() as recorder:
                self.go_to_state(gid, sliders, state)
                result = {"cells": {}, "figures": {}}
                for index in cells:
                    now, default = self.rendered(index), self.default[index]
                    if now is None:
                        continue
                    if (now.html != default.html or len(now.figures) != len(default.figures)
                            or now.charts != default.charts):
                        result["cells"][index] = cell_payload(now)
                        replaced.add(index)
                        continue
                    for number, (fig_now, fig_default) in enumerate(zip(now.figures, default.figures)):
                        ops = O.set_ops(fig_default["figure"], fig_now["figure"])
                        if ops:
                            result["figures"][(index, number)] = ops
                            paths.setdefault((index, number), set()).update(tuple(op["path"]) for op in ops)
            own[state] = self.use_primitives(result, recorder, pools)
        states, dedupe = {}, {}
        for state, result in own.items():
            effect: dict[str, dict] = {}
            for index in sorted(replaced):
                payload = result["cells"].get(index)
                if payload is None:
                    default = self.default[index]
                    figures = [{**f, "figure": O.apply(f["figure"], result["figures"].get((index, n), []))}
                               for n, f in enumerate(default.figures)]
                    payload = {"html": default.html, "figures": figures, "charts": default.charts}
                effect[str(index)] = {"cell": payload}
            for (index, number), figure_paths in sorted(paths.items()):
                if index in replaced:
                    continue
                default_fig = self.default[index].figures[number]["figure"]
                ops = O.filled_ops(default_fig, result["figures"].get((index, number), []), figure_paths)
                if ops:
                    effect.setdefault(str(index), {"figures": {}})["figures"][str(number)] = ops
            key = _key(*state)
            digest = _digest(effect)
            dedupe.setdefault(digest, key)
            states[key] = effect if dedupe[digest] == key else {"same_as": dedupe[digest]}
        return states

    def snapshot(self, cells: list[int]) -> dict:
        """What the reader sees in the cells: the text and the figures."""
        out = {}
        for i in cells:
            rendered = self.rendered(i)
            out[i] = None if rendered is None else (H.text_of(rendered.html), [f["figure"] for f in rendered.figures])
        return out

    def button_targets(self, gid, name, sliders, default_state, cells, listers) -> set[str]:
        """What a click on the button changes: figures ("cell:number") and whole cells ("cell:cell")."""
        history = tuple((b, 2) for b in listers if b != name)
        targets = set()
        for effect in self.click_sequence(gid, name, sliders, default_state, cells, 2, history):
            for cell, change in effect.items():
                if "cell" in change:
                    targets.add(f"{cell}:cell")
                targets |= {f"{cell}:{n}" for n in change.get("figures", {})}
        return targets

    def slider_resets(self, gid, sliders, buttons, targets, cells):
        """For each slider: the targets that its event resets, and the buttons whose click count it
        resets. A slider resets a button when, after the slider event, the cells are the same with
        and without earlier clicks on the button (after 1 click and after 2 clicks): marimo rebuilt
        the state. Clicks that change nothing (two toggles) tell nothing."""
        reset_by: dict[str, set] = {name: set() for name in sliders}
        reset_buttons: dict[str, set] = {name: set() for name in sliders}
        for name in sliders:
            other = self.frontend_value(name, self.other_index(name))
            self.page_load(gid)
            self.s.set_value(name, other, seed=rng.event_seed(gid, "slider"))
            without = self.snapshot(cells)
            for button in buttons:
                if not targets[button]:
                    continue
                erased = []
                for clicks in (1, 2):
                    self.page_load(gid)
                    before = self.snapshot(cells)
                    for k in range(clicks):
                        self.s.set_value(button, 1, seed=rng.event_seed(gid, button, k))
                    if self.snapshot(cells) == before:
                        continue
                    self.s.set_value(name, other, seed=rng.event_seed(gid, "slider"))
                    erased.append(self.snapshot(cells) == without)
                if erased and all(erased):
                    reset_by[name] |= targets[button]
                    reset_buttons[name].add(button)
        self.s.restore(self.base)
        return reset_by, reset_buttons

    def click_effect(self, name: str, cells: list[int], seed: int) -> dict:
        """One click: figure operations, or a whole new cell when other parts of it change."""
        before = {i: self.rendered(i) for i in cells}
        self.s.set_value(name, 1, seed=seed)
        effect = {}
        for i in cells:
            after, old = self.rendered(i), before[i]
            if after is None or old is None:
                continue
            if after.html != old.html or len(after.figures) != len(old.figures) or after.charts != old.charts:
                effect[str(i)] = {"cell": cell_payload(after)}
                continue
            changes = {}
            for number, (b, a) in enumerate(zip(old.figures, after.figures)):
                fig_ops = O.figure_ops(b["figure"], a["figure"])
                if fig_ops:
                    changes[str(number)] = fig_ops
            if changes:
                effect[str(i)] = {"figures": changes}
        return effect

    def click_sequence(self, gid, name, sliders, state, cells, count, history=()) -> list[dict]:
        """The effects of `count` clicks in a row, from page load at a slider state (after the
        clicks in `history`: (button, number of clicks) pairs)."""
        self.go_to_state(gid, sliders, state)
        for button, clicks in history:
            for k in range(clicks):
                self.s.set_value(button, 1, seed=rng.event_seed(gid, button, k))
        return [self.click_effect(name, cells, seed=rng.event_seed(gid, name, k)) for k in range(count)]

    def button_kind(self, gid, name, sliders, default_state, cells) -> str:
        """"fixed" when each click has the same effect (Clear, Reset), or when only the first
        click changes something (Connect: later clicks do nothing, so the first effect is
        safe to apply again); "list" otherwise: a click appends traces, draws new values or
        toggles."""
        clicks = self.click_sequence(gid, name, sliders, default_state, cells, 3)
        appends = any(op["op"] == "add" for effect in clicks for change in effect.values()
                      for ops in change.get("figures", {}).values() for op in ops)
        if appends:
            return "list"
        if all(c == clicks[0] for c in clicks) or (clicks[1] == {} and clicks[2] == {}):
            return "fixed"
        return "list"

    def button_effects(self, gid, name, kind, sliders, sizes, default_state, listers, cells, targets) -> dict:
        others = [b for b in listers if b != name]
        count = 1 if kind == "list" else 2
        history = tuple((b, 2) for b in others) if kind == "fixed" else ()
        probe = self.click_sequence(gid, name, sliders, default_state, cells, count, history)
        relevant = []  # the sliders that change the effect of this button
        for position, slider in enumerate(sliders):
            other = list(default_state)
            other[position] = (default_state[position] + len(self.page.controls[slider]["values"]) // 2) \
                % len(self.page.controls[slider]["values"])
            if self.click_sequence(gid, name, sliders, tuple(other), cells, count, history) != probe:
                relevant.append(position)
        keyed_states = [s for s in itertools.product(*(range(n) for n in sizes))
                        if all(s[p] == default_state[p] for p in range(len(sizes)) if p not in relevant)]
        keys = [sliders[p] for p in relevant]
        table, dedupe = {}, {}

        def store(key, value):
            digest = _digest(value)
            dedupe.setdefault(digest, key)
            table[key] = value if dedupe[digest] == key else {"same_as": dedupe[digest]}

        if kind == "fixed":
            more = tuple((b, 3) for b in others)
            if self.click_sequence(gid, name, sliders, default_state, cells, 1, more)[0] != probe[0]:
                raise UnsupportedGroup(f"the effect of {name} depends on the earlier clicks")
            for state in keyed_states:
                effect = self.click_sequence(gid, name, sliders, state, cells, 1, history)[0]
                store(_key(*(state[p] for p in relevant)), effect)
            # It resets a list button when it removes that button's traces (truncate, or new data
            # for the whole figure) or replaces its cell.
            cleared = {f"{cell}:{n}" for cell, change in probe[0].items()
                       for n, ops in change.get("figures", {}).items()
                       if any(op["op"] == "truncate" or (op["op"] == "set" and op["path"] == ["data"]) for op in ops)}
            replaced = {cell for cell, change in probe[0].items() if "cell" in change}
            resets = sorted(b for b in listers if targets[b] & cleared
                            or any(t.split(":")[0] in replaced for t in targets[b]))
            return {"kind": "fixed", "keys": keys, "table": table, "resets": resets}

        numbers = _count_numbers(probe[0]) or 1
        pool = max(1, min(MAX_CLICKS, APPEND_BUDGET // (numbers * len(keyed_states))))
        for state in keyed_states:
            store(_key(*(state[p] for p in relevant)),
                  self.click_sequence(gid, name, sliders, state, cells, pool))
        return {"kind": "list", "keys": keys, "pool": pool, "table": table, "targets": sorted(targets[name])}

    # ---- primitives ----

    def use_primitives(self, result, recorder: rng.Recorder, pools: dict):
        """Replace long sampled arrays by a recipe that the browser computes ({"$normal": ...}).
        loc and scale are numbers, or arrays of the full size (numpy broadcasts them here)."""
        recipes = []
        for call in recorder.calls:
            if call.fn != "normal" or call.result is None or call.result.size < PRIMITIVE_MIN_SIZE:
                continue
            z = O.compact(call.z.ravel())
            pool_id = _digest(z)
            pools.setdefault(pool_id, z)

            def full(value):
                value = np.asarray(value, dtype=float)
                return float(value) if value.ndim == 0 else O.compact(np.broadcast_to(value, call.z.shape).ravel())

            recipe = {"$normal": {"loc": full(call.params["loc"]), "scale": full(call.params["scale"]),
                                  "z": pool_id}}
            recipes.append((O.compact(call.result.ravel()), recipe))
        if not recipes:
            return result

        def swap(value):
            if isinstance(value, list) and len(value) >= PRIMITIVE_MIN_SIZE:
                for sample, recipe in recipes:
                    if value == sample:
                        return recipe
            if isinstance(value, dict):
                return {k: swap(v) for k, v in value.items()}
            if isinstance(value, list):
                return [swap(v) for v in value]
            return value

        return swap(result)


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
