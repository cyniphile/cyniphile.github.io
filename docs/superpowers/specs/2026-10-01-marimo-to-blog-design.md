# marimo → blog converter (design)

Date: 2026-10-01. Status: owner direction, replaces the Observable JS widgets (Tasks 9–11 of the
2026-09-28 plan). Owner words: "for the matric input and code editor dont just make a one time fix,
made a dedicated transpilation script for these widgets so future posts can be easily made blog
ready. (obv same for current ploty). The matric thing was really nice because you could scroll (even
on mible1) to change values and see matrix."

## Goal

The author writes a post as a marimo notebook (`blog/<slug>/notebook.py`) and runs one command. The
command writes a static Quarto post (`blog/<slug>/index.qmd` + `blog/<slug>/widgets/*.json`) whose
widgets look and act like the marimo originals, with no Python in the browser, except the code
editor, which loads Python only when the reader runs code. No per-post JavaScript.

## Architecture

1. **Run the notebook with marimo itself** (`app.run()`; marimo 0.25.0 pinned). This gives each
   cell's output (HTML with marimo custom elements) and the definitions (UI objects, state getters).
   `Cell.run(**refs)` re-runs one cell in about 0.02 s.
2. **Prose**: cells that are only `mo.md(<string literal>)` become Markdown in the `.qmd` (Quarto
   renders math with KaTeX). Other cells with output become raw HTML islands.
3. **Transpile the output HTML**: each marimo element maps to a blog element with the same look:
   `marimo-plotly` → Plotly div (figure JSON); `marimo-button`, `marimo-slider`, `marimo-matrix`,
   `marimo-code-editor` → blog controls; `marimo-mime-renderer` (Vega-Lite) → vega-embed div;
   `marimo-tex` → KaTeX markup; marimo flex layout HTML stays as it is.
4. **Precompute interaction states with marimo's own semantics** (finite state spaces):
   - Reactive slider (cells use `.value`): for each value, set it (`_update`) and re-run the
     dependent cells in topological order (this also resets state cells, as marimo does).
   - Callback slider (`on_change` + `mo.state`): for each value, or each combination for sliders
     that share state, call `_update` and re-render the display cells.
   - Buttons (`on_click` + `mo.state`): simulate clicks and record each click's effect as ops:
     append traces, truncate traces, restyle all traces, relayout, or replace a figure.
   - The global numpy RNG is reseeded before each simulated event (seed from the event kind and the
     click number), so the results are deterministic and the same draws repeat across slider states.
5. **Random-sampling primitives** where states are continuous or too large: during the conversion,
   `np.random.normal` and `np.random.multivariate_normal` are wrapped. The converter finds their
   results in the output (Plotly arrays, Vega datasets) and stores the standard-normal draws once;
   the browser computes `loc + scale·z` and `mean + z·F(cov)` (same Jacobi eigen factor in Python
   and JS, numpy's PSD check and error text). Used for the 2-D matrix widget (continuous) and the
   mean/variance histogram (5,050 states × 5,000 samples).
6. **Live code editor**: the editor runs the reader's code with Pyodide (core + numpy + plotly from
   PyPI), loaded on first edit. The converter ships the source of the cells that the run needs.
7. **Data**: each island's default state is inline (renders at once). The other states are in
   `widgets/<island>.json`, fetched when the island comes near the viewport. Floats are written with
   5 significant digits; Plotly templates are stored once per page.
8. **Runtime** (written once, shared): `blog/assets/mb/mb.js` and `mb.css`, a project resource
   (`blog/_quarto.yml`) served at `/blog/assets/mb/`; the post writes `/assets/mb/...` and Quarto
   makes it relative to the blog. It draws figures, applies precomputed ops, runs the primitives, and loads
   plotly.js, vega-embed and Pyodide on demand. Control styles copy marimo's measured styles.

## Supported and not supported

Supported marimo features: `mo.md`, `mo.vstack`/`hstack`, `mo.Html`, `mo.show_code`, `mo.ui.plotly`
(static), Altair charts, `mo.ui.slider`, `mo.ui.button`, `mo.state`, `mo.ui.matrix` (when its value
feeds `np.random.multivariate_normal` directly), `mo.ui.code_editor` (with live Python). Any other
interactive output is written as its default static state with a warning from the converter, and
the post links to the live marimo notebook.

## Known differences from marimo

- Random samples come from fixed draws: the same samples at each visit; a "New Sample" button stops
  after its pool (default 20 clicks) until "Clear".
- Text uses the blog's fonts. Controls copy marimo's look.
- The code editor is a plain text area (no syntax colors) and needs a Python download on first run.

## Testing

pytest for the converter (HTML transpiling, state simulation on small fixture notebooks, ops diff,
primitives against numpy); `node --test` for the runtime (ops, primitives, matrix input math);
browser checks with chrome-devtools against the live marimo page (desktop and 390 px).
