import marimo

__generated_with = "0.25.0"
app = marimo.App()


@app.cell
def _():
    import altair as alt
    import marimo as mo
    import numpy as np
    import pandas as pd
    import plotly.graph_objects as go
    return alt, go, mo, np, pd


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    # Mini notebook

    Some math: $x^2$.
    """)
    return


@app.cell
def _(go, mo):
    mo.ui.plotly(go.Figure(go.Scatter(x=[1, 2, 3], y=[3, 1, 2])))
    return


@app.cell
def _(mo):
    size = mo.ui.slider(start=1, stop=4, value=2, label="Size")
    size
    return (size,)


@app.cell
def _(go, mo, size):
    mo.ui.plotly(go.Figure(go.Bar(x=["a"], y=[size.value]), layout=dict(title=f"size={size.value}")))
    return


@app.cell
def _(go, mo, np):
    get_fig, set_fig = mo.state(go.Figure(go.Scatter(mode="markers")))

    def add(_):
        fig = get_fig()
        fig.add_trace(go.Scatter(y=np.random.normal(size=5)))
        set_fig(fig)

    def clear(_):
        fig = get_fig()
        fig.data = fig.data[:1]
        set_fig(fig)

    new = mo.ui.button(label="New Sample", on_click=add, kind="success")
    reset = mo.ui.button(label="Clear", on_click=clear, kind="danger")
    return get_fig, new, reset


@app.cell
def _(get_fig, mo, new, reset):
    mo.vstack([mo.ui.plotly(get_fig()), mo.hstack([new, reset])])
    return


@app.cell
def _(mo, np):
    mat = mo.ui.matrix(np.eye(2), symmetric=True, step=0.1, min_value=0)
    return (mat,)


@app.cell
def _(alt, mat, mo, np, pd):
    try:
        xs = np.random.multivariate_normal([0, 0], np.asarray(mat.value), 50, check_valid="raise")
        note = ""
    except ValueError as e:
        xs = np.zeros((50, 2))
        note = mo.md(f"Error: {e}")
    chart = alt.Chart(pd.DataFrame({"x": xs[:, 0], "y": xs[:, 1]})).mark_point().encode(x="x", y="y")
    mo.vstack([mat, chart, note])
    return


@app.cell
def _(mo):
    editor = mo.ui.code_editor(value="y = [1, 2, 3]")
    editor
    return (editor,)


@app.cell
def _(editor, go, mo):
    _ns = {}
    exec(editor.value, _ns)
    mo.ui.plotly(go.Figure(go.Scatter(y=_ns.get("y", []))))
    return


if __name__ == "__main__":
    app.run()
