// The blog widget runtime for posts converted from marimo notebooks (scripts/marimo_to_blog.py).
// It draws the figures, charts and controls, and applies the precomputed effects of reader events.
// Pure parts: mb-core.js. Python in the browser (code editors only): Pyodide + mb_live.py.
import * as core from "./mb-core.js";

const MODEL = JSON.parse(document.getElementById("mb-model").textContent);
const RUNTIME = new URL(".", import.meta.url).href;
const tables = { templates: MODEL.templates, arrays: {}, pools: {} };
const figures = new Map(); // "cell:n" → { div, fig, config }
const defaults = new Map(); // "cell:n" → the figure at page load
const charts = new Map(); // "cell:n" → Promise of a Vega view
const originals = new Map(); // cell → { html, figures, charts } at page load
const groupData = new Map(); // gid → Promise of the group's data
const groupState = new Map(); // gid → { index, clicks, values, error, queue }

// ---- libraries ----

// The converter picks the smallest Plotly bundle for the page's trace types (MODEL.plotlyBundle).
// Live code can make any trace type: loadPlotly(true) loads the full bundle when one is missing.
const BUNDLE_TYPES = {
  basic: ["bar", "pie", "scatter"],
  cartesian: ["bar", "box", "contour", "heatmap", "histogram", "histogram2d", "histogram2dcontour",
    "image", "pie", "scatter", "scatterternary", "violin"],
};
let plotlyPromise, plotlyBundle;
function plotlyUrl(bundle) {
  return `https://cdn.plot.ly/plotly-${bundle === "full" ? "" : `${bundle}-`}${MODEL.plotly}.min.js`;
}
function loadPlotly(types = []) {
  const bundle = MODEL.plotlyBundle || "full";
  const missing = bundle !== "full" && types.some((t) => !BUNDLE_TYPES[bundle].includes(t));
  if (missing && plotlyBundle !== "full") {
    plotlyBundle = "full";
    plotlyPromise = (plotlyPromise || Promise.resolve()).then(() => import(plotlyUrl("full"))).then(() => window.Plotly);
  }
  if (!plotlyPromise) {
    plotlyBundle = bundle;
    plotlyPromise = import(plotlyUrl(bundle)).then(() => window.Plotly);
  }
  return plotlyPromise;
}

function loadScript(src) {
  return new Promise((resolve, reject) => {
    const script = document.createElement("script");
    script.src = src;
    script.onload = resolve;
    script.onerror = () => reject(new Error(`cannot load ${src}`));
    document.head.append(script);
  });
}

let vegaPromise;
function loadVega() {
  vegaPromise ??= (async () => {
    await loadScript("https://cdn.jsdelivr.net/npm/vega@6");
    await loadScript("https://cdn.jsdelivr.net/npm/vega-lite@6");
    await loadScript("https://cdn.jsdelivr.net/npm/vega-embed@7");
    return window.vegaEmbed;
  })();
  return vegaPromise;
}

function renderMath(root) {
  if (!window.katex) return;
  for (const span of root.querySelectorAll("span.math")) {
    if (span.dataset.mbMath) continue;
    span.dataset.mbMath = "1";
    window.katex.render(span.textContent, span, {
      displayMode: span.classList.contains("display"),
      throwOnError: false,
    });
  }
}

// Plotly draws "$...$" text (legends, titles) with MathJax, as in marimo. MathJax loads only for
// figures that have such text, and it does not typeset the page (KaTeX does the page's math).
let mathJaxPromise;
function loadMathJax() {
  mathJaxPromise ??= (async () => {
    window.MathJax = { startup: { typeset: false } };
    window.PlotlyConfig = { MathJaxConfig: "local" };
    await loadScript("https://cdn.jsdelivr.net/npm/mathjax@3.2.2/es5/tex-svg.js");
    await window.MathJax.startup.promise;
  })();
  return mathJaxPromise;
}

function hasTex(value) {
  if (typeof value === "string") return value.length > 1 && value.startsWith("$") && value.endsWith("$");
  if (Array.isArray(value)) return value.some(hasTex);
  if (value && typeof value === "object") {
    return Object.entries(value).some(([key, v]) => key !== "template" && hasTex(v));
  }
  return false;
}

// ---- figures and charts ----

// Figures and charts draw when they come near the screen, one per animation frame: drawing all
// of a long post's figures at load keeps a phone busy for seconds. A change to a figure that is
// not drawn yet only changes its JSON; the figure shows the latest JSON when it is drawn.
const nearScreen = new IntersectionObserver((entries) => {
  for (const entry of entries) {
    if (!entry.isIntersecting) continue;
    nearScreen.unobserve(entry.target);
    entry.target.mbShow?.();
  }
}, { rootMargin: "600px 0px" });

function whenNear(div, show) {
  div.mbShow = show;
  nearScreen.observe(div);
}

let drawQueue = Promise.resolve();
function queueDraw(task) {
  drawQueue = drawQueue.then(() => new Promise(requestAnimationFrame)).then(task)
    .catch((error) => console.error("mb:", error));
  return drawQueue;
}

// A figure has at most one queued redraw; it draws the latest JSON (a slider drag changes a
// figure many times, and only the last state needs to be drawn).
function drawFigure(key) {
  const entry = figures.get(key);
  if (!entry) return Promise.resolve();
  entry.div.style.height = `${entry.fig.layout?.height ?? 540}px`;
  if (!entry.near) return Promise.resolve();
  if (entry.pending) return entry.pending;
  entry.pending = queueDraw(async () => {
    entry.pending = null;
    if (hasTex(entry.fig)) await loadMathJax();
    const Plotly = await loadPlotly((entry.fig.data || []).map((trace) => trace.type || "scatter"));
    await Plotly.react(entry.div, entry.fig.data || [], entry.fig.layout || {}, entry.config);
  });
  return entry.pending;
}

function drawChart(key, div, spec) {
  let resolveView;
  charts.set(key, new Promise((resolve) => (resolveView = resolve)));
  div.style.minHeight = `${(spec.height ?? 300) + 50}px`;
  whenNear(div, () => queueDraw(async () => {
    const vegaEmbed = await loadVega();
    const result = await vegaEmbed(div, core.resolve(spec, tables), { renderer: "canvas" });
    div.style.minHeight = "";
    resolveView(result.view);
  }));
}

function hydrate(cellEl, payload, firstTime) {
  const cell = cellEl.dataset.cell;
  payload.figures.forEach((item, n) => {
    const key = `${cell}:${n}`;
    const fig = core.resolve(item.figure, tables);
    if (firstTime) defaults.set(key, core.clone(fig));
    const entry = { div: cellEl.querySelector(`.mb-plot[data-fig="${n}"]`), fig, config: item.config, near: false };
    figures.set(key, entry);
    drawFigure(key);
    whenNear(entry.div, () => {
      entry.near = true;
      drawFigure(key);
    });
  });
  (payload.charts || []).forEach((spec, n) => {
    drawChart(`${cell}:${n}`, cellEl.querySelector(`.mb-chart[data-chart="${n}"]`), spec);
  });
  for (const el of cellEl.querySelectorAll("[data-control]")) mountControl(el);
}

function cellElement(cell) {
  return document.querySelector(`.mb-cell[data-cell="${cell}"]`);
}

// Replace a cell's output. Controls that are on the page already keep their element (and value).
function replaceCell(cell, payload) {
  const cellEl = cellElement(cell);
  const kept = new Map([...cellEl.querySelectorAll("[data-control]")].map((el) => [el.dataset.control, el]));
  cellEl.innerHTML = payload.html;
  for (const placeholder of cellEl.querySelectorAll("[data-control]")) {
    const old = kept.get(placeholder.dataset.control);
    if (old) placeholder.replaceWith(old);
  }
  renderMath(cellEl);
  hydrate(cellEl, payload, false);
}

// ---- effects ----

function follow(table, key) {
  let value = table[key];
  while (value && !Array.isArray(value) && value.same_as !== undefined) value = table[value.same_as];
  return value;
}

function applyEffect(effect, tablesForGroup) {
  for (const [cell, change] of Object.entries(effect || {})) {
    if (change.cell) {
      replaceCell(cell, core.resolve(change.cell, tablesForGroup));
      continue;
    }
    for (const [n, ops] of Object.entries(change.figures || {})) {
      const key = `${cell}:${n}`;
      const entry = figures.get(key);
      if (!entry) continue;
      entry.fig = core.applyOps(entry.fig, core.resolve(ops, tablesForGroup), defaults.get(key));
      drawFigure(key);
    }
  }
}

function loadGroup(gid) {
  if (!groupData.has(gid)) {
    const info = MODEL.groups[gid];
    groupData.set(gid, fetch(new URL(info.src, document.baseURI)).then((r) => {
      if (!r.ok) throw new Error(`cannot load ${info.src}`);
      return r.json();
    }).then((data) => ({ data, tables: { ...tables, arrays: data.arrays || {}, pools: data.pools || {} } })));
  }
  return groupData.get(gid);
}

function stateOf(gid) {
  if (!groupState.has(gid)) {
    const index = {}, values = {};
    for (const [name, spec] of Object.entries(MODEL.controls)) {
      if (spec.group !== gid) continue;
      if (spec.kind === "slider") index[name] = spec.index;
      if (spec.kind === "matrix" || spec.kind === "editor") values[name] = core.clone(spec.value);
    }
    groupState.set(gid, { index, values, clicks: {}, error: false, queue: Promise.resolve() });
  }
  return groupState.get(gid);
}

// Events of one group run one after the other.
function emit(name, value) {
  const gid = MODEL.controls[name]?.group;
  if (!gid) return;
  const state = stateOf(gid);
  state.queue = state.queue.then(async () => {
    const group = await loadGroup(gid);
    const handler = { table: tableEvent, sampler: samplerEvent, live: liveEvent }[group.data.kind];
    await handler(group, state, name, value);
  }).catch((error) => console.error("mb:", error));
}

function tableEvent(group, state, name, value) {
  const data = group.data;
  const spec = MODEL.controls[name];
  if (spec.kind === "slider") {
    state.index[name] = value;
    for (const key of data.reset_by[name] || []) {
      const entry = figures.get(key);
      if (entry) {
        entry.fig = core.clone(defaults.get(key));
        drawFigure(key);
      }
    }
    for (const [button, info] of Object.entries(data.buttons)) {
      if ((info.reset_on || []).includes(name)) state.clicks[button] = 0;
    }
    applyEffect(follow(data.states, core.stateKey(data.sliders.map((s) => state.index[s]))), group.tables);
    return;
  }
  const info = data.buttons[name];
  const entry = follow(info.table, core.stateKey(info.keys.map((s) => state.index[s])));
  if (info.kind === "fixed") {
    applyEffect(entry, group.tables);
    for (const button of info.resets || []) state.clicks[button] = 0;
    return;
  }
  const k = state.clicks[name] ?? 0;
  if (!entry || k >= entry.length) return; // the precomputed clicks are used up (until a reset)
  applyEffect(entry[k], group.tables);
  state.clicks[name] = k + 1;
}

async function samplerEvent(group, state, name, value) {
  const data = group.data;
  state.values[name] = value;
  const mean = data.mean.control ? state.values[data.mean.control].flat() : data.mean.value;
  const cov = state.values[data.cov.control];
  if (data.check === "raise" && !core.isPsd(cov)) {
    if (!state.error) replaceCell(data.cell, core.resolve(data.error, group.tables));
    state.error = true;
    return;
  }
  if (state.error) {
    replaceCell(data.cell, originals.get(String(data.cell)));
    state.error = false;
  }
  const samples = core.mvnSamples(mean, cov, data.z);
  const target = data.target;
  if (target.chart !== undefined) {
    const view = await charts.get(`${data.cell}:${target.chart}`);
    const rows = samples.map((s) => ({
      ...(target.extra || {}),
      ...Object.fromEntries(target.fields.map((field, j) => [field, s[j]])),
    }));
    await view.data(target.dataset, rows).runAsync();
  } else {
    const key = `${data.cell}:${target.figure}`;
    const entry = figures.get(key);
    target.paths.forEach((path, j) => {
      entry.fig = core.applyOps(entry.fig, [{ op: "set", path, value: samples.map((s) => s[j]) }]);
    });
    drawFigure(key);
  }
}

// ---- live code (Pyodide) ----

let pythonPromise;
function loadPython(data, status) {
  pythonPromise ??= (async () => {
    status("Loading Python (first run only)…");
    await loadScript(`https://cdn.jsdelivr.net/pyodide/v${data.pyodide}/full/pyodide.js`);
    const py = await window.loadPyodide();
    await py.loadPackage("micropip");
    const shim = await (await fetch(new URL("mb_live.py", RUNTIME))).text();
    py.FS.writeFile("/home/pyodide/mb_live.py", shim);
    py.runPython("import sys; sys.path.insert(0, '/home/pyodide'); import mb_live");
    return py;
  })();
  return pythonPromise;
}

async function liveEvent(group, state, name, value) {
  const data = group.data;
  const editorEl = document.querySelector(`[data-control="${name}"]`);
  const status = (text) => { editorEl.querySelector(".mb-editor-status").textContent = text; };
  const py = await loadPython(data, status);
  if (!state.ready) {
    status("Installing packages…");
    const micropip = py.pyimport("micropip");
    await micropip.install(py.toPy(data.packages));
    py.globals.set("mb_spec", JSON.stringify(data));
    py.runPython("mb_live.configure(mb_spec)");
    state.ready = true;
  }
  if (value === undefined) {
    // A warm-up (the reader clicked into the editor): Python is ready, nothing to run yet.
    status("");
    return;
  }
  status("Running…");
  py.globals.set("mb_code", value);
  const results = JSON.parse(py.runPython("mb_live.run(mb_code)"));
  for (const [cell, out] of Object.entries(results)) {
    const cellEl = cellElement(cell);
    if (!cellEl) continue; // a cell without output (it computes values for other cells)
    let errorBox = cellEl.querySelector(".mb-error");
    if (out.kind === "error") {
      if (!errorBox) {
        errorBox = document.createElement("pre");
        errorBox.className = "mb-error";
        cellEl.append(errorBox);
      }
      errorBox.textContent = out.text;
      continue;
    }
    errorBox?.remove();
    if (out.kind === "plotly" && out.figure && figures.has(`${cell}:0`)) {
      const entry = figures.get(`${cell}:0`);
      entry.fig = out.figure;
      entry.config = { ...entry.config, ...out.config };
      await drawFigure(`${cell}:0`);
    } else if (out.kind === "html" && out.html) {
      let box = cellEl.querySelector(".mb-live-html");
      if (!box) {
        box = document.createElement("div");
        box.className = "mb-live-html";
        cellEl.append(box);
      }
      box.innerHTML = out.html;
      renderMath(box);
    }
  }
  status("");
}

// ---- controls (marimo's look, see mb.css) ----

function escapeHtml(text) {
  return String(text).replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" })[c]);
}

function mountControl(el) {
  if (el.dataset.mounted) return;
  const spec = MODEL.controls[el.dataset.control];
  if (!spec) return;
  el.dataset.mounted = "1";
  ({ slider: mountSlider, button: mountButton, matrix: mountMatrix, editor: mountEditor })[spec.kind]?.(el, spec);
  if (!spec.group) disableControl(el);
}

// The converter could not make this control interactive: it stays at its default value, and a
// link points to the live notebook, where it works.
function disableControl(el) {
  el.classList.add("mb-static");
  for (const input of el.querySelectorAll("input, button, textarea")) input.disabled = true;
  for (const td of el.querySelectorAll("td")) td.classList.add("mb-disabled");
  if (MODEL.live) {
    const link = document.createElement("a");
    link.className = "mb-live-link";
    link.href = MODEL.live;
    link.textContent = "try it in the live notebook";
    el.append(link);
  }
}

function mountSlider(el, spec) {
  const id = `mb-${spec.name}`;
  el.classList.add("mb-control");
  // label_html: the notebook's label, with math as KaTeX spans (from the converter)
  el.innerHTML = `${spec.label_html ? `<label for="${id}">${spec.label_html}</label>` : ""}`
    + `<input type="range" id="${id}" min="0" max="${spec.values.length - 1}" step="1" value="${spec.index}">`
    + (spec.show_value ? `<span class="mb-value"></span>` : "");
  renderMath(el);
  const input = el.querySelector("input");
  const paint = () => {
    input.style.setProperty("--fill", `${(100 * input.value) / Math.max(1, input.max)}%`);
    if (spec.show_value) el.querySelector(".mb-value").textContent = spec.values[input.value];
  };
  paint();
  input.addEventListener("input", () => {
    paint();
    if (!spec.debounce) emit(spec.name, Number(input.value));
  });
  input.addEventListener("change", () => {
    if (spec.debounce) emit(spec.name, Number(input.value));
  });
}

function mountButton(el, spec) {
  const button = document.createElement("button");
  button.type = "button";
  button.className = `mb-btn mb-btn-${spec.kind_style}`;
  button.innerHTML = spec.label_html || escapeHtml(spec.label);
  renderMath(button);
  button.disabled = spec.disabled;
  button.addEventListener("click", () => emit(spec.name, 1));
  el.replaceChildren(button);
}

function cellParam(param, i, j) {
  return Array.isArray(param) ? (Array.isArray(param[i]) ? param[i][j] : param[i]) : param;
}

function mountMatrix(el, spec) {
  const value = spec.value.map((row) => row.map(Number));
  const format = (v) => v.toFixed(spec.precision ?? 1);
  el.classList.add("mb-matrix");
  if (spec.label_html && !el.previousElementSibling?.classList.contains("mb-matrix-label")) {
    // marimo shows the label before the matrix (outside its brackets)
    const label = document.createElement("span");
    label.className = "mb-control mb-matrix-label";
    label.innerHTML = spec.label_html;
    el.before(label);
    renderMath(label);
  }
  el.innerHTML = `<table><tbody>${value.map((row, i) => `<tr>${row.map((v, j) =>
    `<td tabindex="0" data-i="${i}" data-j="${j}" aria-label="Row ${i + 1}, Column ${j + 1}">${format(v)}</td>`).join("")}</tr>`).join("")}</tbody></table>`;
  const cellOf = (i, j) => el.querySelector(`td[data-i="${i}"][data-j="${j}"]`);
  const setValue = (i, j, v) => {
    value[i][j] = v;
    cellOf(i, j).textContent = format(v);
    if (spec.symmetric && i !== j && value[j]) {
      value[j][i] = v;
      cellOf(j, i).textContent = format(v);
    }
    emit(spec.name, value.map((row) => row.slice()));
  };
  for (const td of el.querySelectorAll("td")) {
    const i = Number(td.dataset.i), j = Number(td.dataset.j);
    const disabled = cellParam(spec.disabled, i, j);
    if (disabled) {
      td.classList.add("mb-disabled");
      continue;
    }
    const step = Number(cellParam(spec.step, i, j) ?? 1);
    const min = cellParam(spec.min, i, j), max = cellParam(spec.max, i, j);
    let start = null;
    td.addEventListener("pointerdown", (event) => {
      if (td.classList.contains("mb-disabled")) return;
      start = { x: event.clientX, value: value[i][j] };
      td.setPointerCapture(event.pointerId);
      td.classList.add("mb-dragging");
    });
    td.addEventListener("pointermove", (event) => {
      if (!start) return;
      const v = core.dragValue(start.value, event.clientX - start.x, step, min, max);
      if (v !== value[i][j]) setValue(i, j, v);
    });
    const stop = () => {
      start = null;
      td.classList.remove("mb-dragging");
    };
    td.addEventListener("pointerup", stop);
    td.addEventListener("pointercancel", stop);
    td.addEventListener("keydown", (event) => {
      if (td.classList.contains("mb-disabled")) return;
      const delta = { ArrowUp: 1, ArrowRight: 1, ArrowDown: -1, ArrowLeft: -1 }[event.key];
      if (!delta) return;
      event.preventDefault();
      const v = core.dragValue(value[i][j], delta * 10, step, min, max);
      if (v !== value[i][j]) setValue(i, j, v);
    });
  }
}

function mountEditor(el, spec) {
  el.classList.add("mb-editor");
  el.innerHTML = `<textarea name="${escapeHtml(spec.name)}" aria-label="Python code" spellcheck="false"`
    + ` autocapitalize="off" autocomplete="off"></textarea>`
    + `<div class="mb-editor-status">Edit the code to run it (Python loads the first time).</div>`;
  const area = el.querySelector("textarea");
  area.value = spec.value;
  const fit = () => {
    area.style.height = "auto";
    area.style.height = `${area.scrollHeight + 2}px`;
  };
  requestAnimationFrame(fit);
  // Python starts to load when the reader clicks into the editor (a warm-up: nothing runs)
  area.addEventListener("focus", () => emit(spec.name, undefined), { once: true });
  let timer;
  area.addEventListener("input", () => {
    fit();
    clearTimeout(timer);
    timer = setTimeout(() => emit(spec.name, area.value), 700);
  });
}

// ---- start ----

function start() {
  for (const cellEl of document.querySelectorAll(".mb-cell[data-cell]")) {
    const payload = MODEL.cells[cellEl.dataset.cell] || { figures: [], charts: [] };
    originals.set(cellEl.dataset.cell, { html: cellEl.innerHTML, ...payload });
    hydrate(cellEl, payload, true);
  }
  // Load a group's data when one of its cells comes near the viewport.
  const groupsOfCell = new Map();
  for (const [gid, info] of Object.entries(MODEL.groups)) {
    for (const cell of info.cells || []) groupsOfCell.set(String(cell), [...(groupsOfCell.get(String(cell)) || []), gid]);
  }
  const observer = new IntersectionObserver((entries) => {
    for (const entry of entries) {
      if (!entry.isIntersecting) continue;
      for (const gid of groupsOfCell.get(entry.target.dataset.cell) || []) loadGroup(gid);
      observer.unobserve(entry.target);
    }
  }, { rootMargin: "800px 0px" });
  for (const cellEl of document.querySelectorAll(".mb-cell[data-cell]")) observer.observe(cellEl);
}

start();
