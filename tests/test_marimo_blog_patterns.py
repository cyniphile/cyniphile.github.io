"""End-to-end: the marimo patterns that the converter review found (tests/fixtures/marimo/patterns).

The converter replays random events against marimo after each conversion (verify.py); a post
without warnings acts as in marimo for those events. The tests below also check the form that each
pattern takes.
"""

import json
import re
import shutil
import sys
from pathlib import Path

import pytest

import marimo_to_blog
from marimo_blog import live
from marimo_blog import model as M
from marimo_blog.runner import Session

FIXTURE = Path(__file__).parent / "fixtures" / "marimo" / "patterns"


@pytest.fixture(scope="module")
def converted(tmp_path_factory):
    post = tmp_path_factory.mktemp("patterns")
    for name in ("notebook.py", "post.yml"):
        shutil.copy(FIXTURE / name, post / name)
    page = marimo_to_blog.convert(post)
    qmd = (post / "index.qmd").read_text()
    model = json.loads(re.search(r'id="mb-model">(.*?)</script>', qmd).group(1).replace("<\\/", "</"))
    groups = {gid: json.loads((post / info["src"]).read_text()) for gid, info in model["groups"].items()}
    return post, page, qmd, model, groups


def group_of(converted, control):
    _, _, _, model, groups = converted
    return groups[model["controls"][control]["group"]]


def first_change(effect):
    (change,) = effect.values()
    return change


def test_no_warnings_and_marimo_agrees(converted):
    _, page, qmd, _, _ = converted
    assert page.warnings == []  # includes the replay of random events against marimo
    assert "resources:\n- data.csv\n- widgets/*.json" in qmd  # post.yml resources are kept


def test_steps_slider_uses_the_index(converted):
    _, _, _, model, _ = converted
    spec = model["controls"]["steps"]
    assert (spec["values"], spec["index"], spec["by_index"]) == ([0.1, 0.5, 1.0], 1, True)
    # mb-math, not math: Quarto's KaTeX script must not see label spans (mb.js renders them)
    assert spec["label_html"] == 'Scale <span class="mb-math inline">\\ell</span>'
    assert set(group_of(converted, "steps")["states"]) == {"0", "1", "2"}


def test_buttons_whose_clicks_differ_are_lists(converted):
    buttons = group_of(converted, "toggle_btn")["buttons"]
    assert buttons["resample_btn"]["kind"] == "list" and buttons["toggle_btn"]["kind"] == "list"
    # one trace: the change is for that trace only (a path operation, not "restyle every trace")
    ops = [first_change(e)["figures"]["0"][0] for e in buttons["toggle_btn"]["table"][""][:3]]
    assert [(op["path"], op["value"]) for op in ops] == [(["data", 0, "mode"], m) for m in ("lines", "markers", "lines")]


def test_slider_keeps_click_history_and_button_reads_slider(converted):
    group = group_of(converted, "level")
    assert group["reset_by"] == {"level": []}
    for effect in group["states"].values():
        if "same_as" not in effect:
            assert all(op["op"] != "reset" for op in first_change(effect)["figures"]["0"])
    reset = group["buttons"]["reset_btn"]
    assert reset["kind"] == "fixed" and reset["keys"] == ["level"] and len(reset["table"]) == 3
    # Reset replaces all traces (set ["data"]): the "New Sample" pool starts again
    assert reset["resets"] == ["add_btn"]


def test_page_load_runs_no_callback(converted):
    _, _, _, model, _ = converted
    (cell,) = group_of(converted, "level")["cells"]
    assert "title" not in model["cells"][str(cell)]["figures"][0]["figure"].get("layout", {})


def test_slider_that_changes_text_replaces_the_cell_in_every_state(converted):
    states = group_of(converted, "size")["states"]
    assert all("cell" in first_change(e) for e in states.values() if "same_as" not in e)


def test_click_that_changes_text(converted):
    counter = group_of(converted, "counter")["buttons"]["counter"]
    assert counter["kind"] == "list"
    assert "Clicks: 2" in first_change(counter["table"][""][1])["cell"]["html"]


def test_cell_error_is_shown_as_in_marimo(converted):
    state = first_change(group_of(converted, "divisor")["states"]["0"])
    assert "ZeroDivisionError" in state["cell"]["html"]


def test_live_cells_run_in_marimo_order_with_their_imports(converted):
    group = group_of(converted, "editor")
    order = [run[0] for run in group["run"]]
    code = {run[0]: run[1] for run in group["run"]}
    assert "exec(editor.value" in code[order[0]] and "mo.ui.plotly" in code[order[1]]
    assert "import math" in group["setup"] and "TAU = math.tau" in group["setup"]
    assert "marimo" not in group["setup"]  # the browser's stand-in gives `mo`


def test_live_check_finds_another_figure():
    with Session(FIXTURE / "notebook.py") as session:
        builder = M.Builder(session)
        page = builder.build()
        gid = page.controls["editor"]["group"]
        assert not page.warnings
        live.check_live(builder, page.groups[gid], "n = 2")  # not the editor's default code
        assert any("another figure" in w for w in page.warnings)
    assert "marimo" in sys.modules and sys.modules["marimo"].__name__ == "marimo"
