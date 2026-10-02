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
def _(go, mo):
    # A callback that raises after a Clear (marimo logs it and runs the cells)
    get_two, set_two = mo.state(go.Figure([go.Scatter(y=[0, 1]), go.Scatter(y=[1, 0])]))

    def on_lvl(v):
        f = get_two()
        f.data[1].y = [v, v]
        set_two(f)

    def clear_two(_):
        f = get_two()
        f.data = f.data[:1]
        set_two(f)

    lvl = mo.ui.slider(1, 3, on_change=on_lvl, label="Level")
    clear_two_btn = mo.ui.button(label="Clear", on_click=clear_two)
    return clear_two_btn, get_two, lvl


@app.cell
def _(clear_two_btn, get_two, lvl, mo):
    mo.vstack([mo.ui.plotly(get_two()), clear_two_btn, lvl])
    return


@app.cell
def _(mo):
    code_n = mo.ui.slider(1, 3, label="Code")
    code_n
    return (code_n,)


@app.cell
def _(code_n, mo):
    # Shown code that a slider changes
    mo.ui.code_editor(value=f"n = {code_n.value}", disabled=True)
    return


@app.cell
def _(mo):
    ra = mo.ui.slider(1, 3, label="A")
    rb = mo.ui.slider(1, 3, label="B")
    mo.hstack([ra, rb])
    return ra, rb


@app.cell
def _(go, mo, ra, rb):
    mo.ui.plotly(go.Figure(go.Bar(y=[ra.value, rb.value])))
    return


@app.cell
def _(go, mo, np, rb):
    # Random draws that only B runs again
    mo.ui.plotly(go.Figure(go.Scatter(y=np.random.normal(size=5) * rb.value)))
    return


@app.cell
def _(mo):
    ea = mo.ui.slider(0, 2, value=1, label="EA")
    eb = mo.ui.slider(0, 2, value=1, label="EB")
    mo.hstack([ea, eb])
    return ea, eb


@app.cell
def _(ea):
    xs = 10 / ea.value
    return (xs,)


@app.cell
def _(eb, go, mo, xs):
    # A cell whose ancestor raises for EA = 0
    mo.ui.plotly(go.Figure(go.Bar(y=[xs * eb.value])))
    return


@app.cell
def _(mo):
    st = mo.ui.slider(0, 2, value=1, label="Stop")
    st
    return (st,)


@app.cell
def _(mo, st):
    mo.stop(st.value < 1)
    sx = st.value * 10
    return (sx,)


@app.cell
def _(go, mo, sx):
    # A cell whose ancestor stops for Stop = 0
    mo.ui.plotly(go.Figure(go.Bar(y=[sx])))
    return


@app.cell
def _(mo, pd):
    mo.ui.table(pd.DataFrame({"x": [1, 2], "y": ["a", "b"]}))
    return


@app.cell
def _(mo):
    mo.ui.dropdown(["a", "b"], value="a", label="Pick")
    return


@app.cell
def _():
    import pandas as pd
    return (pd,)


@app.cell
def _(mo):
    ed2 = mo.ui.code_editor(value="m = 3")
    ed2
    return (ed2,)


@app.cell
def _(ed2):
    _ns2 = {}
    exec(ed2.value, _ns2)
    m = _ns2["m"]
    return (m,)


@app.cell
def _(m, mo):
    # Live code whose output is text (not supported: the blog updates figures only)
    mo.md(f"**m is {m}**")
    return


@app.cell
def _(mo):
    tr = mo.ui.slider(1, 3, label="TR")
    tr
    return (tr,)


@app.cell
def _(go, mo, tr):
    # A toggle whose state the slider builds again
    get_tf, set_tf = mo.state(go.Figure(go.Scatter(y=[tr.value] * 3, mode="markers")))

    def flip(_):
        f = get_tf()
        f.data[0].mode = "lines" if f.data[0].mode == "markers" else "markers"
        set_tf(f)

    flip_btn = mo.ui.button(label="Toggle", on_click=flip)
    return flip_btn, get_tf


@app.cell
def _(flip_btn, get_tf, mo):
    mo.vstack([mo.ui.plotly(get_tf()), flip_btn])
    return


@app.cell
def _(mo):
    fr = mo.ui.slider(1, 3, label="FR")
    fr
    return (fr,)


@app.cell
def _(fr, go, mo):
    # A fixed button whose state the slider builds again
    get_ff, set_ff = mo.state(go.Figure(go.Scatter(y=[fr.value] * 3, mode="markers")))

    def to_lines(_):
        f = get_ff()
        f.data[0].mode = "lines"
        set_ff(f)

    lines_btn = mo.ui.button(label="Lines", on_click=to_lines)
    return get_ff, lines_btn


@app.cell
def _(get_ff, lines_btn, mo):
    mo.vstack([mo.ui.plotly(get_ff()), lines_btn])
    return


@app.cell
def _(mo):
    cr = mo.ui.slider(1, 3, label="CR")
    cr
    return (cr,)


@app.cell
def _(cr, mo):
    # A click counter that the slider resets
    _ = cr.value
    get_c, set_c = mo.state(0)
    return get_c, set_c


@app.cell
def _(get_c, mo, set_c):
    count_btn = mo.ui.button(label="Count", on_click=lambda _: set_c(get_c() + 1))
    return (count_btn,)


@app.cell
def _(count_btn, cr, get_c, mo):
    mo.vstack([count_btn, mo.md(f"Clicks: {get_c()} at s={cr.value}")])
    return


@app.cell
def _(mo):
    # A callback that appends: the page load must not run it
    get_h, set_h = mo.state([0])
    hs = mo.ui.slider(1, 3, on_change=lambda v: set_h(get_h() + [v]), label="Hist")
    return get_h, hs


@app.cell
def _(get_h, go, hs, mo):
    mo.vstack([mo.ui.plotly(go.Figure(go.Bar(y=get_h()))), hs])
    return


if __name__ == "__main__":
    app.run()
