"""End-to-end: the marimo patterns that the second converter review found
(tests/fixtures/marimo/review). Each pattern has its own controls, so it is its own group.

After the conversion, verify.py compares the page load with a fresh run of the notebook and replays
random events on the page data and on the notebook: a group without a warning acts as the notebook
does for those events. The tests below also check the form that each pattern takes.
"""

import copy
import json
import re
import shutil
from pathlib import Path

import pytest

import marimo_to_blog
from marimo_blog import ops as O
from marimo_blog import verify as V

FIXTURE = Path(__file__).parent / "fixtures" / "marimo" / "review"


@pytest.fixture(scope="module")
def converted(tmp_path_factory):
    post = tmp_path_factory.mktemp("review")
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


def gid_of(converted, control):
    return converted[3]["controls"][control]["group"]


def cell_html(effect, cell):
    return effect[str(cell)]["cell"]["html"]


def test_only_the_expected_warnings(converted):
    _, page, _, _, _ = converted
    expected = ["no blog version of <marimo-table>", "no blog version of <marimo-dropdown>",
                "(ed2): cell", f"differs from the notebook: {gid_of(converted, 'hs')}: after hs="]
    assert len(page.warnings) == len(expected), page.warnings
    for text in expected:
        assert sum(text in w for w in page.warnings) == 1, (text, page.warnings)


def test_callback_error_after_clear_converts_and_agrees(converted):
    # The callback raises once Clear removed its trace; verify replays this and finds no difference.
    group = group_of(converted, "lvl")
    assert group["buttons"]["clear_two_btn"]["kind"] == "fixed"


def test_shown_code_that_a_slider_changes_is_an_island(converted):
    _, _, qmd, _, _ = converted
    group = group_of(converted, "code_n")
    (cell,) = group["cells"]
    assert f'<div class="mb-cell" data-cell="{cell}"><pre class="mb-code">n = 1</pre></div>' in qmd
    assert "n = 3" in cell_html(group["states"]["2"], cell)


def test_random_cell_of_one_slider_stays_when_another_slider_moves(converted):
    _, page, _, model, _ = converted
    group = group_of(converted, "ra")
    _, scatter = group["cells"]
    assert group["random_sliders"] == ["rb"] and scatter in page.redrawn
    # A moved: the state sets the scatter (B's states change it) to the draws of the page load
    page_load = model["cells"][str(scatter)]["figures"][0]["figure"]
    ops = V.follow(group["states"], "2,0")[str(scatter)]["figures"]["0"]
    assert O.apply(page_load, ops) == page_load


def test_ancestor_error_blocks_the_cell_for_every_value_of_the_other_slider(converted):
    states = group_of(converted, "ea")["states"]
    (cell,) = group_of(converted, "ea")["cells"]
    for key in ("0,0", "0,1", "0,2"):
        assert "An ancestor raised an exception (ZeroDivisionError)" in cell_html(V.follow(states, key), cell)


def test_stopped_ancestor_blocks_the_cell(converted):
    group = group_of(converted, "st")
    (cell,) = group["cells"]
    assert "ancestor was stopped with `mo.stop`" in cell_html(V.follow(group["states"], "0"), cell)


def test_inputs_without_blog_version_show_a_note(converted):
    _, _, qmd, model, _ = converted
    assert '<div class="mb-unsupported" data-element="table">' in qmd and "<td>b</td>" in qmd
    assert re.search(r'data-element="dropdown"><span class="mb-unsupported-label">Pick</span>'
                     r'<span class="mb-unsupported-value">a</span>', qmd)


def test_live_code_with_text_output_stays_static(converted):
    _, _, _, model, _ = converted
    assert "group" not in model["controls"]["ed2"]


def test_slider_that_rebuilds_the_state_resets_a_toggle(converted):
    group = group_of(converted, "tr")
    (cell,) = group["cells"]
    assert group["reset_by"] == {"tr": [f"{cell}:0"]}
    assert group["buttons"]["flip_btn"]["kind"] == "list" and group["buttons"]["flip_btn"]["reset_on"] == ["tr"]


def test_slider_that_rebuilds_the_state_resets_a_fixed_button(converted):
    group = group_of(converted, "fr")
    (cell,) = group["cells"]
    assert group["reset_by"] == {"fr": [f"{cell}:0"]} and group["buttons"]["lines_btn"]["kind"] == "fixed"


def test_slider_that_rebuilds_the_state_resets_a_text_counter(converted):
    group = group_of(converted, "cr")
    (cell,) = group["cells"]
    assert group["reset_by"] == {"cr": [f"{cell}:cell"]}
    assert group["buttons"]["count_btn"]["reset_on"] == ["cr"]


def test_page_load_runs_no_callback(converted):
    _, _, _, model, _ = converted
    (cell,) = group_of(converted, "hs")["cells"]
    assert model["cells"][str(cell)]["figures"][0]["figure"]["data"][0]["y"] == [0]


# ---- the check finds wrong page data ----

def test_verify_finds_wrong_text_and_a_missing_error(converted):
    post, page, _, _, _ = converted
    path = post / "notebook.py"
    gid = page.controls["count_btn"]["group"]
    broken = copy.deepcopy(page.groups[gid])
    for clicks in broken["buttons"]["count_btn"]["table"].values():
        for effect in clicks if isinstance(clicks, list) else []:
            for change in effect.values():
                change["cell"]["html"] = re.sub(r"Clicks: \d+", "Clicks: 0", change["cell"]["html"])
    assert "the text is" in V.verify_table(path, page, gid, broken, seed=1)[0]

    gid = page.controls["ea"]["group"]
    broken = copy.deepcopy(page.groups[gid])
    (cell,) = broken["cells"]
    for key in ("0,0", "0,1", "0,2"):
        broken["states"][key] = {}  # the plot stays: no error
    problems = []
    for seed in range(5):  # random sequences: some move EA to 0
        problems += V.verify_table(path, page, gid, broken, seed=seed)
    assert any(f"cell {cell}: the text is" in p for p in problems)


def test_verify_finds_a_wrong_page_load(converted):
    post, page, _, _, _ = converted
    broken = copy.deepcopy(page)
    (cell,) = broken.groups[broken.controls["hs"]["group"]]["cells"]
    out = next(c.rendered for c in broken.cells if c.index == cell)
    out.figures[0]["figure"]["layout"]["title"] = {"text": "v=1"}
    assert f"page load: cell {cell} figure 0/layout/title: only in the blog" in V.verify_page_load(
        post / "notebook.py", broken)


def test_verify_reports_a_failed_check_as_a_warning(converted):
    post, page, _, _, _ = converted
    broken = copy.deepcopy(page)
    gid = broken.controls["tr"]["group"]
    broken.groups = {gid: broken.groups[gid]}
    del broken.groups[gid]["reset_by"]
    assert any(p.startswith(f"{gid}: the check failed (KeyError") for p in V.verify(post / "notebook.py", broken))
