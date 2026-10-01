// Pure functions of the blog widget runtime (no DOM). Tests: mb-core.test.mjs (node --test).
// The Python twins are in scripts/marimo_blog (ops.py: applyOps, rng.py: jacobiEigh/isPsd/
// sqrtFactor/mvnSamples); both sides must give the same results.

export function clone(value) {
  return value === undefined ? undefined : JSON.parse(JSON.stringify(value));
}

// Replace the shared references of the converter's JSON:
//   {"$a": id}         a number array in tables.arrays
//   {"$template": id}  a Plotly template in tables.templates
//   {"$normal": {loc, scale, z}}  loc + scale * z, z an array in tables.pools
export function resolve(value, tables) {
  if (Array.isArray(value)) return value.map((v) => resolve(v, tables));
  if (value === null || typeof value !== "object") return value;
  if ("$a" in value) return tables.arrays[value.$a].slice();
  if ("$template" in value) return clone(tables.templates[value.$template]);
  if ("$normal" in value) {
    const { loc, scale, z } = value.$normal;
    return normal(resolve(loc, tables), resolve(scale, tables), resolve(tables.pools[z], tables));
  }
  const out = {};
  for (const [key, v] of Object.entries(value)) out[key] = resolve(v, tables);
  return out;
}

// Operations on one figure (see scripts/marimo_blog/ops.py). Returns a new figure.
export function applyOps(figure, ops, defaultFigure) {
  let fig = clone(figure);
  for (const op of ops) {
    switch (op.op) {
      case "reset":
        fig = clone(defaultFigure);
        break;
      case "set":
      case "del": {
        // A set makes missing parent objects; a del of a missing value does nothing.
        let target = fig;
        for (const key of op.path.slice(0, -1)) {
          if (target[key] === undefined || target[key] === null) {
            if (op.op === "del") { target = null; break; }
            target[key] = {};
          }
          target = target[key];
        }
        if (target === null) break;
        const last = op.path[op.path.length - 1];
        if (op.op === "set") target[last] = clone(op.value);
        else if (Array.isArray(target)) target.splice(last, 1);
        else delete target[last];
        break;
      }
      case "add":
        fig.data = (fig.data || []).concat(clone(op.traces));
        break;
      case "truncate":
        fig.data = (fig.data || []).slice(0, op.n);
        break;
      case "restyle_all":
        for (const trace of fig.data || []) Object.assign(trace, clone(op.style));
        break;
      default:
        throw new Error(`unknown operation ${op.op}`);
    }
  }
  return fig;
}

// loc + scale * z (loc and scale: numbers, or arrays of the same length as z: the converter
// broadcasts them in Python)
export function normal(loc, scale, z) {
  const at = (v, i) => (Array.isArray(v) ? v[i] : v);
  return z.map((zi, i) => at(loc, i) + at(scale, i) * zi);
}

const copysign1 = (x) => (x < 0 || Object.is(x, -0) ? -1 : 1);

// Eigenvalues and eigenvectors (columns) of a small symmetric matrix: the cyclic Jacobi method,
// the same steps as rng.jacobi_eigh in Python.
export function jacobiEigh(matrix) {
  const n = matrix.length;
  const a = matrix.map((row) => row.map(Number));
  const vecs = Array.from({ length: n }, (_, i) => Array.from({ length: n }, (_, j) => (i === j ? 1 : 0)));
  for (let sweep = 0; sweep < 50; sweep++) {
    let off = 0;
    for (let i = 0; i < n; i++) for (let j = 0; j < n; j++) if (i !== j) off += a[i][j] ** 2;
    if (off < 1e-30) break;
    for (let p = 0; p < n - 1; p++) {
      for (let q = p + 1; q < n; q++) {
        if (Math.abs(a[p][q]) < 1e-300) continue;
        const theta = (a[q][q] - a[p][p]) / (2 * a[p][q]);
        const t = copysign1(theta) / (Math.abs(theta) + Math.sqrt(theta * theta + 1));
        const c = 1 / Math.sqrt(t * t + 1);
        const s = t * c;
        for (let k = 0; k < n; k++) {
          const akp = a[k][p], akq = a[k][q];
          a[k][p] = c * akp - s * akq;
          a[k][q] = s * akp + c * akq;
        }
        for (let k = 0; k < n; k++) {
          const apk = a[p][k], aqk = a[q][k];
          a[p][k] = c * apk - s * aqk;
          a[q][k] = s * apk + c * aqk;
        }
        for (let k = 0; k < n; k++) {
          const vkp = vecs[k][p], vkq = vecs[k][q];
          vecs[k][p] = c * vkp - s * vkq;
          vecs[k][q] = s * vkp + c * vkq;
        }
      }
    }
  }
  return { values: a.map((row, i) => row[i]), vectors: vecs };
}

// numpy's check_valid test: symmetric, and no eigenvalue below -tol (scaled).
export function isPsd(cov, tol = 1e-8) {
  const n = cov.length;
  for (let i = 0; i < n; i++) {
    for (let j = 0; j < n; j++) {
      if (Math.abs(cov[i][j] - cov[j][i]) > tol + tol * Math.abs(cov[j][i])) return false;
    }
  }
  const { values } = jacobiEigh(cov);
  const largest = Math.max(...values.map(Math.abs));
  return Math.min(...values) >= -tol * Math.max(1, largest);
}

// F with F^T F = cov for a valid matrix: F[i][j] = sqrt(abs(lambda_i)) * v[j][i] (numpy: an SVD)
export function sqrtFactor(cov) {
  const n = cov.length;
  const sym = cov.map((row, i) => row.map((v, j) => (v + cov[j][i]) / 2));
  const { values, vectors } = jacobiEigh(sym);
  return values.map((lambda, i) => {
    const root = Math.sqrt(Math.abs(lambda)); // |lambda|, as numpy (an SVD) does
    return Array.from({ length: n }, (_, j) => root * vectors[j][i]);
  });
}

// mean + z @ F for each row of z (n x d)
export function mvnSamples(mean, cov, z) {
  const f = sqrtFactor(cov);
  const d = mean.length;
  return z.map((row) => {
    const out = new Array(d);
    for (let j = 0; j < d; j++) {
      let sum = mean[j];
      for (let k = 0; k < d; k++) sum += row[k] * f[k][j];
      out[j] = sum;
    }
    return out;
  });
}

// One step of a matrix cell drag: about one step per 10 px (as marimo's matrix input).
export function dragValue(start, dx, step, min, max, pxPerStep = 10) {
  const steps = Math.round(dx / pxPerStep);
  const decimals = Math.max(0, -Math.floor(Math.log10(step)) + 2);
  let value = Number((start + steps * step).toFixed(decimals));
  if (min !== null && min !== undefined) value = Math.max(value, min);
  if (max !== null && max !== undefined) value = Math.min(value, max);
  return value;
}

export const stateKey = (indexes) => indexes.join(",");
