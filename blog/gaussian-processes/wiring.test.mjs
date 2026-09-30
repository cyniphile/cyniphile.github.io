import assert from "node:assert/strict";
import {test} from "node:test";

import {
  POOL_SIZE,
  addSample,
  ellIndex,
  matrixCells,
  mvn2,
  parsePoints,
  picksToSamples,
  rbfCells,
  rows,
  scaleNormals,
} from "./wiring.js";

test("addSample counts up and stops at the pool size", () => {
  assert.equal(addSample(0), 1);
  assert.equal(addSample(POOL_SIZE - 1), POOL_SIZE);
  assert.equal(addSample(POOL_SIZE), POOL_SIZE);
});

test("rows pairs x and y values", () => {
  assert.deepEqual(rows([1, 2], [3, 4]), [{x: 1, y: 3}, {x: 2, y: 4}]);
});

test("matrixCells lists each cell with its row and column", () => {
  assert.deepEqual(matrixCells([[1, 2], [3, 4]]), [
    {i: 0, j: 0, value: 1},
    {i: 0, j: 1, value: 2},
    {i: 1, j: 0, value: 3},
    {i: 1, j: 1, value: 4},
  ]);
});

test("parsePoints reads the default text", () => {
  assert.deepEqual(parsePoints("1.549, 2, 3, 4, 5, 6, 10"), {points: [1.549, 2, 3, 4, 5, 6, 10], error: null});
});

test("parsePoints accepts spaces, semicolons, negative numbers and exponents", () => {
  assert.deepEqual(parsePoints("  -1;2  3e-1,,4 ").points, [-1, 2, 0.3, 4]);
});

test("parsePoints rejects text that is not a number", () => {
  assert.deepEqual(parsePoints("1, two, 3"), {points: [], error: '"two" is not a number.'});
});

test("parsePoints rejects empty text and too many points", () => {
  assert.equal(parsePoints("   ").error, "Type at least one number.");
  const many = Array.from({length: 31}, (_, i) => i).join(",");
  assert.equal(parsePoints(many).error, "Type 30 numbers or fewer.");
});

test("rbfCells has ones on the diagonal and the RBF value elsewhere", () => {
  const cells = rbfCells([0, 1], 1);
  assert.equal(cells.length, 4);
  assert.equal(cells[0].value, 1);
  assert.ok(Math.abs(cells[1].value - Math.exp(-0.5)) < 1e-12);
  assert.equal(cells[1].value, cells[2].value);
});

test("rbfCells rejects a length scale that is not positive", () => {
  assert.throws(() => rbfCells([0, 1], 0), RangeError);
  assert.throws(() => rbfCells([0, 1], Number.NaN), RangeError);
});

test("mvn2 with the identity matrix only moves the points by the mean", () => {
  assert.deepEqual(mvn2([[1, 2]], [0.5, -1], [[1, 0], [0, 1]]), {ok: true, error: null, points: [[1.5, 1]]});
});

test("mvn2 applies the 2x2 Cholesky factor", () => {
  const {points} = mvn2([[1, 0], [0, 1]], [0, 0], [[1, 0.5], [0.5, 1]]);
  assert.deepEqual(points[0], [1, 0.5]);
  assert.ok(Math.abs(points[1][1] - Math.sqrt(0.75)) < 1e-12);
});

test("mvn2 rejects a matrix that is not positive semi-definite", () => {
  assert.deepEqual(mvn2([[1, 1]], [0, 0], [[1, 2], [2, 1]]), {
    ok: false,
    error: "covariance is not symmetric positive-semidefinite.",
    points: [],
  });
});

test("mvn2 accepts a zero variance", () => {
  assert.deepEqual(mvn2([[1, 2]], [0, 0], [[0, 0], [0, 4]]).points, [[0, 4]]);
});

test("mvn2 rejects an empty input box", () => {
  assert.deepEqual(mvn2([[1, 2]], [0, 0], [[Number.NaN, 0], [0, 1]]), {
    ok: false,
    error: "Type a number in each box.",
    points: [],
  });
});

test("scaleNormals uses the square root of the variance", () => {
  assert.deepEqual(scaleNormals([1, -1], 2, 4), [4, 0]);
  assert.throws(() => scaleNormals([1], 0, 0), RangeError);
});

test("ellIndex maps slider values to list positions", () => {
  assert.equal(ellIndex(0.05), 0);
  assert.equal(ellIndex(0.15000000000000002), 2);
  assert.equal(ellIndex(2.0), 39);
});

test("picksToSamples counts samples for each length scale and stops at the pool size", () => {
  assert.deepEqual(picksToSamples([3, 3, 5, 3]), [
    {idx: 3, k: 0},
    {idx: 3, k: 1},
    {idx: 5, k: 0},
    {idx: 3, k: 2},
  ]);
  assert.equal(picksToSamples(Array(POOL_SIZE + 5).fill(1)).length, POOL_SIZE);
});

test("rbfCells uses the squared distance and the squared length scale", () => {
  const cells = rbfCells([0, 3], 2);
  assert.ok(Math.abs(cells[1].value - Math.exp(-9 / 8)) < 1e-12);
});

test("mvn2 Cholesky factor when the variance is not 1", () => {
  const {points} = mvn2([[1, 0], [0, 1]], [0, 0], [[4, 2], [2, 3]]);
  assert.deepEqual(points[0], [2, 1]);
  assert.ok(Math.abs(points[1][1] - Math.sqrt(2)) < 1e-12);
});

test("mvn2 never returns NaN at the edge of a valid matrix", () => {
  const edge = mvn2([[1, 2]], [0, 0], [[0.1, 0.9], [0.9, 8.1]]);
  assert.equal(edge.ok, true);
  assert.ok(edge.points.flat().every(Number.isFinite));
  assert.equal(mvn2([[1, 2]], [0, 0], [[0.7, 2.1], [2.1, 6.3]]).ok, true);
});

test("mvn2 rejects negative variances and an empty mean box", () => {
  assert.equal(mvn2([[1, 1]], [0, 0], [[-1, 0], [0, -1]]).ok, false);
  assert.equal(mvn2([[1, 1]], [Number.NaN, 0], [[1, 0], [0, 1]]).ok, false);
});

test("parsePoints accepts exactly 30 numbers and rejects Infinity", () => {
  assert.equal(parsePoints(Array.from({length: 30}, (_, i) => i).join(",")).error, null);
  assert.equal(parsePoints("1e999").error, '"1e999" is not a number.');
});

test("ellIndex rounds decimal slider values", () => {
  assert.equal(ellIndex(0.15), 2);
  assert.equal(ellIndex(0.35), 6);
});

test("scaleNormals rejects a NaN variance", () => {
  assert.throws(() => scaleNormals([1], 0, Number.NaN), RangeError);
});
