import marimo

__generated_with = "0.25.0"
app = marimo.App()


@app.cell
def _():
    import marimo as mo
    import numpy as np
    import plotly.graph_objects as go
    return go, mo, np


@app.cell
def _(mo):
    # A slider with steps: marimo's frontend value is the index into the steps
    steps = mo.ui.slider(steps=[0.1, 0.5, 1.0], value=0.5, label=r"Scale $\ell$")
    steps
    return (steps,)


@app.cell
def _(go, mo, steps):
    mo.ui.plotly(go.Figure(go.Bar(y=[steps.value]), layout=dict(title=f"s={steps.value}")))
    return


@app.cell
def _(go, mo, np):
    # Buttons whose clicks differ: new draws each time, and a switch
    get_rs, set_rs = mo.state(go.Figure(go.Scatter(y=[0.0, 0.0, 0.0], mode="markers")))

    def resample(_):
        f = get_rs()
        f.data[0].y = np.random.normal(size=3)
        set_rs(f)

    def toggle(_):
        f = get_rs()
        f.data[0].mode = "lines" if f.data[0].mode == "markers" else "markers"
        set_rs(f)

    resample_btn = mo.ui.button(label="Resample", on_click=resample)
    toggle_btn = mo.ui.button(label="Toggle", on_click=toggle)
    return get_rs, resample_btn, toggle_btn


@app.cell
def _(get_rs, mo, resample_btn, toggle_btn):
    mo.vstack([mo.ui.plotly(get_rs()), mo.hstack([resample_btn, toggle_btn])])
    return


@app.cell
def _(go, mo, np):
    # A slider (on_change) that changes a figure with click history; a Reset that reads the slider
    get_cb, set_cb = mo.state(go.Figure(go.Scatter(y=[0, 1])))

    def on_level(v):
        f = get_cb()
        f.update_layout(title=f"v={v}")
        set_cb(f)

    def add_cb(_):
        f = get_cb()
        f.add_trace(go.Scatter(y=np.random.normal(size=3)))
        set_cb(f)

    level = mo.ui.slider(1, 3, on_change=on_level, label="Level")
    add_btn = mo.ui.button(label="New Sample", on_click=add_cb, kind="success")

    def reset_cb(_):
        f = get_cb()
        f.data = []
        f.add_trace(go.Scatter(y=[level.value * 10] * 3))
        set_cb(f)

    reset_btn = mo.ui.button(label="Reset", on_click=reset_cb, kind="danger")
    return add_btn, get_cb, level, reset_btn


@app.cell
def _(add_btn, get_cb, level, mo, reset_btn):
    mo.vstack([mo.ui.plotly(get_cb()), mo.hstack([add_btn, reset_btn]), level])
    return


@app.cell
def _(mo):
    size = mo.ui.slider(0, 3, label="Size")
    size
    return (size,)


@app.cell
def _(go, mo, size):
    # The text of the cell changes with the slider, not only its figure
    mo.vstack([mo.md("**too big**" if size.value >= 2 else "small"), mo.ui.plotly(go.Figure(go.Bar(y=[size.value])))])
    return


@app.cell
def _(mo):
    # A click that changes text, not a figure
    get_n, set_n = mo.state(0)
    counter = mo.ui.button(label="Count", on_click=lambda _: set_n(get_n() + 1))
    return counter, get_n


@app.cell
def _(counter, get_n, mo):
    mo.vstack([counter, mo.md(f"Clicks: {get_n()}")])
    return


@app.cell
def _(mo):
    divisor = mo.ui.slider(0, 2, value=1, label="Divisor")
    divisor
    return (divisor,)


@app.cell
def _(divisor, go, mo):
    # This cell raises for the value 0 (marimo shows the error in the cell)
    mo.ui.plotly(go.Figure(go.Bar(y=[10 / divisor.value])))
    return


@app.cell
def _(mo):
    editor = mo.ui.code_editor(value="n = 3")
    editor
    return (editor,)


@app.cell
def _(TAU, go, mo, n):
    # The display cell is above the cell that computes its data
    mo.ui.plotly(go.Figure(go.Scatter(y=[TAU * i for i in range(n)])))
    return


@app.cell
def _(editor):
    _ns = {}
    exec(editor.value, _ns)
    n = _ns["n"]
    return (n,)


@app.cell
def _():
    # An import that only its own cell uses
    import math
    TAU = math.tau
    return (TAU,)


if __name__ == "__main__":
    app.run()
