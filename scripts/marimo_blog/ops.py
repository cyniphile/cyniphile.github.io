"""Figure JSON helpers: decode, make small, and describe changes as operations.

Operations on one figure (the runtime applies them, then calls Plotly.react):
  {"op": "reset"}                         back to the figure's default (page load) state
  {"op": "set", "path": [...], "value": v} set the value at a path of keys and list indexes
  {"op": "del", "path": [...]}            remove the key at a path
  {"op": "add", "traces": [...]}          append traces
  {"op": "truncate", "n": k}              keep the first k traces
  {"op": "restyle_all", "style": {...}}   set the same attributes on every trace
"""

from __future__ import annotations

import base64
import math

import numpy as np

SIGNIFICANT = 5


def decode(obj):
    """Replace Plotly's binary arrays ({"dtype", "bdata", "shape"}) with plain lists."""
    if isinstance(obj, dict):
        if "bdata" in obj and "dtype" in obj:
            array = np.frombuffer(base64.b64decode(obj["bdata"]), dtype=np.dtype(obj["dtype"]))
            shape = obj.get("shape")
            if shape:
                array = array.reshape([int(s) for s in str(shape).split(",")])
            return array.tolist()
        return {k: decode(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [decode(v) for v in obj]
    return obj


def round_number(x: float, significant: int = SIGNIFICANT) -> float | int:
    if not math.isfinite(x) or x == 0:
        return x
    rounded = float(f"{x:.{significant}g}")
    return int(rounded) if rounded.is_integer() and abs(rounded) < 2**53 else rounded


def _is_number(v) -> bool:
    return isinstance(v, (int, float, np.integer, np.floating)) and not isinstance(v, (bool, np.bool_))


def _numeric_array(obj) -> bool:
    """A list of numbers, or a list of lists of numbers (a heatmap's z)."""
    if not isinstance(obj, (list, tuple)) or not obj:
        return False
    if all(_is_number(v) for v in obj):
        return True
    return all(isinstance(row, (list, tuple)) and row and all(_is_number(v) for v in row) for row in obj)


def _round_array(obj, significant: int):
    """Round every value to the same absolute precision: `significant` digits of the largest value.
    (Values far below the largest one, such as 1e-15 next to 1, become 0.)"""
    values = [float(v) for row in obj for v in (row if isinstance(row, (list, tuple)) else [row])]
    finite = [abs(v) for v in values if math.isfinite(v)]
    largest = max(finite) if finite else 0.0
    decimals = significant - 1 - math.floor(math.log10(largest)) if largest > 0 else 0

    def one(v):
        v = float(v)
        if not math.isfinite(v):
            return None
        r = round(v, decimals)
        return int(r) if r.is_integer() and abs(r) < 2**53 else r

    return [[one(v) for v in row] if isinstance(row, (list, tuple)) else one(row) for row in obj]


def compact(obj, significant: int = SIGNIFICANT, relative: bool = True):
    """Plain JSON with floats rounded (numpy values converted). Single numbers keep `significant`
    digits. Number arrays keep `significant` digits of their largest value when `relative` (use
    relative=False for figures with a log axis, where small values matter)."""
    if isinstance(obj, np.ndarray):
        obj = obj.tolist()
    if isinstance(obj, dict):
        return {str(k): compact(v, significant, relative) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        if relative and _numeric_array(obj):
            return _round_array(obj, significant)
        return [compact(v, significant, relative) for v in obj]
    if isinstance(obj, (bool, np.bool_)):
        return bool(obj)
    if isinstance(obj, (int, np.integer)):
        return int(obj)
    if isinstance(obj, (float, np.floating)):
        value = float(obj)
        return round_number(value, significant) if math.isfinite(value) else None
    return obj


def has_log_axis(figure: dict) -> bool:
    layout = figure.get("layout") or {}
    return any(isinstance(v, dict) and v.get("type") == "log" for k, v in layout.items()
               if k.startswith(("xaxis", "yaxis", "zaxis")) or k == "scene")


def compact_figure(figure: dict) -> dict:
    return compact(figure, relative=not has_log_axis(figure))


def set_ops(before, after, path: tuple = ()) -> list[dict]:
    """Operations that change `before` into `after` (lists of the same length are compared item
    by item when their items are objects; other lists are set as a whole)."""
    if before == after:
        return []
    if isinstance(before, dict) and isinstance(after, dict):
        ops = []
        for key in before:
            if key not in after:
                ops.append({"op": "del", "path": [*path, key]})
        for key, value in after.items():
            if key not in before:
                ops.append({"op": "set", "path": [*path, key], "value": value})
            else:
                ops.extend(set_ops(before[key], value, (*path, key)))
        return ops
    if (isinstance(before, list) and isinstance(after, list) and len(before) == len(after)
            and all(isinstance(v, dict) for v in before + after)):
        ops = []
        for i, (b, a) in enumerate(zip(before, after)):
            ops.extend(set_ops(b, a, (*path, i)))
        return ops
    return [{"op": "set", "path": list(path), "value": after}]


def _same_style_change(per_trace: list[list[dict]]) -> dict | None:
    """If every trace got exactly the same top-level attribute sets, return them."""
    if not per_trace or not all(per_trace):
        return None
    first = per_trace[0]
    if any(op["op"] != "set" or len(op["path"]) != 1 for op in first):
        return None
    style = {op["path"][0]: op["value"] for op in first}
    for ops in per_trace[1:]:
        if any(o["op"] != "set" or len(o["path"]) != 1 for o in ops):
            return None
        if {o["path"][0]: o["value"] for o in ops} != style:
            return None
    return style


def figure_ops(before: dict, after: dict) -> list[dict]:
    """Operations that change one figure into another, for a click (relative to the current state)."""
    data_b, data_a = before.get("data", []), after.get("data", [])
    ops: list[dict] = []
    if data_a != data_b:
        if len(data_a) > len(data_b) and data_a[: len(data_b)] == data_b:
            ops.append({"op": "add", "traces": data_a[len(data_b):]})
        elif len(data_a) < len(data_b) and data_b[: len(data_a)] == data_a:
            ops.append({"op": "truncate", "n": len(data_a)})
        elif len(data_a) == len(data_b):
            per_trace = [set_ops(b, a) for b, a in zip(data_b, data_a)]
            style = _same_style_change(per_trace)
            if style is not None:
                ops.append({"op": "restyle_all", "style": style})
            else:
                for i, trace_ops in enumerate(per_trace):
                    ops.extend({**o, "path": ["data", i, *o["path"]]} for o in trace_ops)
        else:
            ops.append({"op": "set", "path": ["data"], "value": data_a})
    ops.extend(set_ops(before.get("layout", {}), after.get("layout", {}), ("layout",)))
    for key in sorted(set(before) | set(after)):
        if key not in ("data", "layout"):
            ops.extend(set_ops(before.get(key), after.get(key), (key,)) if key in before and key in after
                       else [{"op": "set", "path": [key], "value": after[key]}] if key in after
                       else [{"op": "del", "path": [key]}])
    return ops


def reset_ops(default: dict, state: dict) -> list[dict]:
    """Operations that show `state`, from any current state: reset, then change the default."""
    changes = set_ops(default, state)
    return [{"op": "reset"}, *changes]


_MISSING = object()


def get_path(obj, path):
    """The value at a path of keys and list indexes, or _MISSING."""
    for key in path:
        if isinstance(obj, dict) and key in obj:
            obj = obj[key]
        elif isinstance(obj, list) and isinstance(key, int) and 0 <= key < len(obj):
            obj = obj[key]
        else:
            return _MISSING
    return obj


def filled_ops(default: dict, own: list[dict], paths: set[tuple]) -> list[dict]:
    """A slider state's operations that work from any earlier state, with no reset (a reset would
    remove the click history that marimo keeps): every path that some state changes gets its
    value in this state. The default value where this state does not change the path, first and
    parents before children, then this state's own operations."""
    own_paths = {tuple(op["path"]) for op in own}
    fillers = []
    for path in sorted(paths, key=len):
        if path in own_paths:
            continue
        value = get_path(default, path)
        fillers.append({"op": "del", "path": list(path)} if value is _MISSING
                       else {"op": "set", "path": list(path), "value": value})
    return fillers + own


def apply(figure: dict, ops: list[dict], default: dict | None = None) -> dict:
    """Apply operations to a figure (the Python twin of mb-core.js applyOps).

    A set makes missing parent objects; a del of a missing value does nothing."""
    import copy

    fig = copy.deepcopy(figure)
    for op in ops:
        kind = op["op"]
        if kind == "reset":
            fig = copy.deepcopy(default if default is not None else figure)
        elif kind in ("set", "del"):
            target = fig
            for key in op["path"][:-1]:
                if isinstance(target, dict) and target.get(key) is None:
                    if kind == "del":
                        target = None
                        break
                    target[key] = {}
                target = target[key]
            if target is None:
                continue
            last = op["path"][-1]
            if kind == "set":
                if isinstance(target, list) and last == len(target):
                    target.append(copy.deepcopy(op["value"]))
                else:
                    target[last] = copy.deepcopy(op["value"])
            elif isinstance(target, list):
                if isinstance(last, int) and last < len(target):
                    del target[last]
            else:
                target.pop(last, None)
        elif kind == "add":
            fig.setdefault("data", []).extend(copy.deepcopy(op["traces"]))
        elif kind == "truncate":
            fig["data"] = fig.get("data", [])[: op["n"]]
        elif kind == "restyle_all":
            for trace in fig.get("data", []):
                trace.update(copy.deepcopy(op["style"]))
        else:
            raise ValueError(f"unknown operation {kind}")
    return fig
