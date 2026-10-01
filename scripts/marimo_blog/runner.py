"""Run a marimo notebook with marimo, and simulate reader events the way marimo does.

marimo gives each cell's output and definitions (App.run) and runs one cell again with given
references (Cell.run, about 0.02 s). A reader event is simulated with the UI element's own
_update method, which calls its on_click / on_change callbacks. Then the cells that use the element
or a state that a callback set run again in topological order, with their descendants. The cell
that defines the element is not run again (marimo does the same).
"""

from __future__ import annotations

import contextlib
import copy
import html
import importlib.util
import os
import weakref
from dataclasses import dataclass
from pathlib import Path

import marimo as mo
import numpy as np
from marimo._output.formatters.formatters import register_formatters
from marimo._plugins.ui._core.ui_element import UIElement
from marimo._runtime import state as marimo_state

from . import rng

# Without marimo's formatters (its kernel registers them), Altair charts come out as Altair's own
# HTML; with them, as a Vega-Lite spec that the converter can read.
register_formatters()


@dataclass(frozen=True)
class CellInfo:
    index: int
    cell_id: str
    code: str
    hide_code: bool
    refs: frozenset[str]
    defs: frozenset[str]


def load_app(path: Path):
    """Import a notebook file and return its marimo App."""
    spec = importlib.util.spec_from_file_location(f"mb_notebook_{abs(hash(str(path)))}", path)
    if spec is None or spec.loader is None:
        raise ImportError(f"cannot load {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.app


def topological_order(cells: list[CellInfo]) -> list[int]:
    """Cell indexes so that each cell comes after the cells that define its references."""
    definer = {name: c.index for c in cells for name in c.defs}
    deps = {c.index: {definer[r] for r in c.refs if r in definer and definer[r] != c.index} for c in cells}
    order, done = [], set()
    while len(order) < len(cells):
        ready = [i for i in sorted(deps) if i not in done and deps[i] <= done]
        if not ready:
            raise ValueError("the notebook has a cycle between cells")
        order.extend(ready)
        done.update(ready)
    return order


class CellError:
    """The output of a cell that raised during a simulated event (marimo shows the error)."""

    def __init__(self, message: str):
        self.message = message
        self.text = f'<pre class="mb-error">{html.escape(message)}</pre>'


def output_html(output) -> str | None:
    """The HTML that marimo shows for a cell output (None when the cell has no output)."""
    if output is None:
        return None
    return output.text if hasattr(output, "text") else mo.as_html(output).text


class Session:
    """One notebook run. Holds the current definitions and outputs, and simulates events."""

    def __init__(self, path, seed: int = 0):
        self.path = Path(path).resolve()
        # weak references in lists: marimo UI elements cannot be hashed
        self._state_refs: list[weakref.ref] = []
        self._element_refs: list[weakref.ref] = []
        self._used_states: set[int] = set()  # ids of the states that events used since the last checkpoint
        self._used_elements: set[int] = set()
        self._exit = contextlib.ExitStack()
        self._exit.enter_context(rng.controlled(seed))
        self._exit.enter_context(self._tracking())
        try:
            self.app = load_app(self.path)
            data = list(self.app._cell_manager.cell_data())
            self.cells = [
                CellInfo(i, d.cell_id, d.code, bool(d.config.hide_code),
                         frozenset(d.cell._cell.refs), frozenset(d.cell._cell.defs))
                for i, d in enumerate(data)
            ]
            self._cell_objects = [d.cell for d in data]
            self.order = topological_order(self.cells)
            with self._in_notebook_dir():
                outputs, defs = self.app.run()
        except BaseException:
            self.close()
            raise
        if len(outputs) != len(self.cells):
            self.close()
            raise ValueError(f"{len(outputs)} outputs for {len(self.cells)} cells")
        self.outputs = list(outputs)
        self.defs = dict(defs)
        self.definer = {name: c.index for c in self.cells for name in c.defs}

    # ---- context ----

    def close(self) -> None:
        self._exit.close()

    def __enter__(self):
        return self

    def __exit__(self, *_exc):
        self.close()

    @contextlib.contextmanager
    def _in_notebook_dir(self):
        old = os.getcwd()
        os.chdir(self.path.parent)
        try:
            yield
        finally:
            os.chdir(old)

    @property
    def states(self) -> list:
        return [s for s in (r() for r in self._state_refs) if s is not None]

    @property
    def elements(self) -> list:
        return [e for e in (r() for r in self._element_refs) if e is not None]

    @contextlib.contextmanager
    def _tracking(self):
        """Keep weak references to every State and UI element that the notebook creates."""
        state_refs, element_refs = self._state_refs, self._element_refs
        state_init, element_init = marimo_state.State.__init__, UIElement.__init__

        def track_state(self, *args, **kwargs):
            state_init(self, *args, **kwargs)
            state_refs.append(weakref.ref(self))

        def track_element(self, *args, **kwargs):
            element_init(self, *args, **kwargs)
            element_refs.append(weakref.ref(self))

        setattr(marimo_state.State, "__init__", track_state)
        setattr(UIElement, "__init__", track_element)
        try:
            yield
        finally:
            setattr(marimo_state.State, "__init__", state_init)
            setattr(UIElement, "__init__", element_init)

    @contextlib.contextmanager
    def watch_states(self):
        """Yield (set, used): the ids of the State objects set, and of those read or set, inside
        the block. A callback can change a value in place after it reads it."""
        changed: set[int] = set()
        used = self._used_states
        original_set, original_get = marimo_state.SetFunctor.__call__, marimo_state.State.__call__

        def recording_set(self, update):
            changed.add(id(self._state))
            used.add(id(self._state))
            return original_set(self, update)

        def recording_get(self):
            used.add(id(self))
            return original_get(self)

        setattr(marimo_state.SetFunctor, "__call__", recording_set)
        setattr(marimo_state.State, "__call__", recording_get)
        try:
            yield changed
        finally:
            setattr(marimo_state.SetFunctor, "__call__", original_set)
            setattr(marimo_state.State, "__call__", original_get)

    # ---- checkpoints ----

    def checkpoint(self):
        """Everything needed to go back to this point: definitions, outputs, state and UI values."""
        states = {id(s): (s, copy.deepcopy(s._value)) for s in self.states}
        elements = {id(e): (e, copy.deepcopy(e._value)) for e in self.elements}
        self._used_states.clear()
        self._used_elements.clear()
        return dict(self.defs), list(self.outputs), states, elements, np.random.get_state()

    def restore(self, point) -> None:
        """Go back to a checkpoint. Only the states and UI values that events used are copied back."""
        defs, outputs, states, elements, random_state = point
        self.defs, self.outputs = dict(defs), list(outputs)
        for key in self._used_states:
            if key in states:
                state, value = states[key]
                state._value = copy.deepcopy(value)
        for key in self._used_elements:
            if key in elements:
                element, value = elements[key]
                element._value = copy.deepcopy(value)
        self._used_states.clear()
        self._used_elements.clear()
        np.random.set_state(random_state)

    # ---- graph ----

    def html(self, index: int) -> str | None:
        return output_html(self.outputs[index])

    def users(self, names: set[str]) -> set[int]:
        """Cells that read any of the names (not the cells that define them)."""
        return {c.index for c in self.cells if c.refs & names and not (c.defs & names)}

    def name_of(self, obj) -> str | None:
        """The notebook variable that holds this object, if any."""
        for name, value in self.defs.items():
            if value is obj:
                return name
        return None

    def element_by_id(self, object_id: str):
        for element in self.elements:
            if getattr(element, "_id", None) == object_id:
                return element
        return None

    # ---- events ----

    def rerun(self, names: set[str]) -> list[int]:
        """Run again the cells that use the names, then their descendants. Return the cells run.

        As in marimo, a cell that raises shows the error, and the cells that depend on it do not
        run (they show that an ancestor raised)."""
        dirty, failed, ran = set(names), set(), []
        with self._in_notebook_dir():
            for index in self.order:
                cell = self.cells[index]
                if not (cell.refs & dirty) or (cell.defs & names):
                    continue
                ran.append(index)
                dirty |= cell.defs
                if cell.refs & failed:
                    self.outputs[index] = CellError("This cell did not run: a cell that it uses raised an exception.")
                    failed |= cell.defs
                    continue
                refs = {r: self.defs[r] for r in cell.refs if r in self.defs}
                try:
                    output, defs = self._cell_objects[index].run(**refs)
                except Exception as error:  # noqa: BLE001 - marimo shows any exception in the cell
                    self.outputs[index] = CellError(f"{type(error).__name__}: {error}")
                    failed |= cell.defs
                    continue
                self.outputs[index] = output
                self.defs.update(defs)
        return ran

    def set_value(self, name: str, value, seed: int | None = None) -> list[int]:
        """Simulate a reader event: the frontend sends `value` for the UI element `name`.

        For a button, any value except 0 is a click. Return the cells that ran again.
        """
        element = self.defs[name]
        if seed is not None:
            np.random.seed(seed)
        self._used_elements.add(id(element))
        with self.watch_states() as changed:
            element._update(value)
            getters = {n for n, v in self.defs.items() if isinstance(v, marimo_state.State) and id(v) in changed}
            return self.rerun({name} | getters)
