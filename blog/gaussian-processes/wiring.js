// Small helpers for the widgets in the Gaussian process post.
// They connect precomputed data to charts. All other math is in gp_data.py.

export const POOL_SIZE = 50;

/** The next count for a "New Sample" button. It stops at POOL_SIZE. */
export function addSample(n) {
  return Math.min(n + 1, POOL_SIZE);
}

/** Rows for Observable Plot, from two arrays of the same length. */
export function rows(xs, ys) {
  return ys.map((y, i) => ({x: xs[i], y}));
}

/** Heatmap cells for a matrix (an array of rows). */
export function matrixCells(matrix) {
  return matrix.flatMap((row, i) => row.map((value, j) => ({i, j, value})));
}

/** Read text such as "1.549, 2, 3" into numbers. */
export function parsePoints(text, maxPoints = 30) {
  const parts = String(text)
    .split(/[\s,;]+/)
    .filter((part) => part.length > 0);
  if (parts.length === 0) return {points: [], error: "Type at least one number."};
  if (parts.length > maxPoints) return {points: [], error: `Type ${maxPoints} numbers or fewer.`};
  const points = [];
  for (const part of parts) {
    const value = Number(part);
    if (!Number.isFinite(value)) return {points: [], error: `"${part}" is not a number.`};
    points.push(value);
  }
  return {points, error: null};
}

/** RBF kernel cells for the points xs: exp(-(xi - xj)^2 / (2 ell^2)). */
export function rbfCells(xs, ell) {
  if (!(ell > 0)) throw new RangeError("ell must be greater than 0");
  return xs.flatMap((xi, i) =>
    xs.map((xj, j) => ({i, j, value: Math.exp(-((xi - xj) ** 2) / (2 * ell * ell))})),
  );
}

/** Samples of a 2-D Gaussian: the 2x2 Cholesky formula applied to fixed standard-normal pairs z. */
export function mvn2(z, mean, cov) {
  const a = cov[0][0];
  const b = cov[0][1];
  const c = cov[1][1];
  if (![a, b, c, mean[0], mean[1]].every(Number.isFinite)) {
    return {ok: false, error: "Type a number in each box.", points: []};
  }
  if (a < 0 || c < 0 || a * c - b * b < -1e-12) {
    return {ok: false, error: "covariance is not symmetric positive-semidefinite.", points: []};
  }
  const l11 = Math.sqrt(a);
  const l21 = a > 0 ? b / l11 : 0;
  const l22 = Math.sqrt(Math.max(0, c - l21 * l21));
  const points = z.map(([z1, z2]) => [mean[0] + l11 * z1, mean[1] + l21 * z1 + l22 * z2]);
  return {ok: true, error: null, points};
}

/** mean + sqrt(variance) * z for each z. */
export function scaleNormals(z, mean, variance) {
  if (!(variance > 0)) throw new RangeError("variance must be greater than 0");
  const sd = Math.sqrt(variance);
  return z.map((value) => mean + sd * value);
}

/** The position of ell in [0.05, 0.10, ..., 2.00]. */
export function ellIndex(ell, step = 0.05) {
  return Math.round(ell / step) - 1;
}

/** Clicked ell positions, in order, to samples {idx, k}. At most POOL_SIZE samples for each idx. */
export function picksToSamples(picks) {
  const counts = new Map();
  const samples = [];
  for (const idx of picks) {
    const k = counts.get(idx) ?? 0;
    if (k >= POOL_SIZE) continue;
    counts.set(idx, k + 1);
    samples.push({idx, k});
  }
  return samples;
}
