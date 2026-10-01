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
   - Controls that change the same cells form a group.
   - Slider states (reactive `.value` sliders and `on_change` sliders, all combinations of a
     group): each state sets every figure path that some state changes (no reset: marimo can keep
     the click history of a figure). A cell whose HTML changes in some state is replaced in every
     state. A slider that rebuilds a figure (marimo runs its state cell again) resets that figure
     and the click counts of its buttons (`reset_by`, `reset_on`).
   - Buttons: three clicks in a row decide the kind. "fixed": each click has the same effect, or
     only the first click changes something (Clear, Reset, Connect). "list": a click appends traces,
     draws new values or toggles; the effects are stored per click (a pool, default 20 clicks).
     Both are stored per value of the sliders that change them. A fixed button that truncates a
     list button's figure resets that button's click count. A click that changes text replaces
     the cell.
   - `steps=[...]` sliders send the step index, as marimo's frontend does.
   - A cell that raises shows the error (as marimo does); its dependents show that they did not run.
   - The global numpy RNG is reseeded before each simulated event (seed from the event kind and the
     click number), so the results are deterministic and the same draws repeat across slider states.
     A group with random draws shows at page load the state from the same draws.
5. **Random-sampling primitives** where states are continuous or too large: during the conversion,
   `np.random.normal` and `np.random.multivariate_normal` are wrapped. The converter finds their
   results in the output (Plotly arrays, Vega datasets) and stores the standard-normal draws once;
   the browser computes `loc + scale·z` and `mean + z·F(cov)` (same Jacobi eigen factor in Python
   and JS, numpy's PSD check and error text). Used for the 2-D matrix widget (continuous) and the
   mean/variance histogram (5,050 states × 5,000 samples).
6. **Live code editor**: the editor runs the reader's code with Pyodide (core + numpy + plotly from
   PyPI), loaded when the reader clicks into the editor. The converter ships the code of all cells
   that marimo runs again after an edit (with or without output, in marimo's order) and of the cells
   they need (imports trimmed to the used names; marimo imports removed: the stand-in `mb_live.py`
   gives `mo`). At conversion time it runs the same stand-in in CPython with the default code: the
   result must equal marimo's output.
7. **Data**: each island's default state is inline (renders at once). The other states are in
   `widgets/<island>.json`, fetched when the island comes near the viewport. Floats are written with
   5 significant digits; Plotly templates are stored once per page.
8. **Runtime** (written once, shared): `blog/assets/mb/mb.js` and `mb.css`, a project resource
   (`blog/_quarto.yml`) served at `/blog/assets/mb/`; the post writes `/assets/mb/...` and Quarto
   makes it relative to the blog. It draws figures, applies precomputed ops, runs the primitives, and loads
   plotly.js, vega-embed and Pyodide on demand. Control styles copy marimo's measured styles.

## Supported and not supported

Supported marimo features: `mo.md`, `mo.vstack`/`hstack`, `mo.Html`, `mo.show_code`, `mo.ui.plotly`
(static), Altair charts (also `mo.ui.altair_chart`, without its selection), `mo.ui.slider` (also with
`steps`), `mo.ui.button`, `mo.state`, `mo.ui.matrix` (up to 4×4, when its value feeds
`np.random.multivariate_normal` directly), `mo.ui.code_editor` (with live Python). A control that the
converter cannot make interactive keeps its default value: the page shows it disabled, with a link to
the live notebook, and the converter prints a warning. Other marimo elements keep their content,
without interaction (with a warning). Limits: 6,000 slider combinations per group; a sampled array
becomes a browser recipe only for `np.random.normal`.

## Known differences from marimo

- Random samples come from fixed draws: the same samples at each visit; a "New Sample" button stops
  after its pool (default 20 clicks) until "Clear".
- Text uses the blog's fonts. Controls copy marimo's look.
- The code editor is a plain text area (no syntax colors) and needs a Python download on first run.

## Verification (after each conversion)

`verify.py` replays random reader events (slider moves, clicks, matrix edits) on a Python twin of
the browser runtime and on a fresh marimo session, with the converter's event seeds, and compares
every figure after each event. A difference is a converter warning. This also finds notebooks that
keep state outside `mo.state` (a list that a callback changes): the converter's fast restore cannot
undo such state. `--no-verify` skips the check.

## Testing

pytest for the converter (HTML transpiling, state simulation on the fixture notebooks
`tests/fixtures/marimo/{mini,patterns}`, ops, primitives against numpy, the self-check);
`tests/test_marimo_blog_js.py` runs `mb-core.js` in node against the Python twins; browser checks
with chrome-devtools against the live marimo page (desktop and 390 px).
