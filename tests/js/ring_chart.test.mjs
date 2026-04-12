import test from "node:test";
import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";

const sourceText = await readFile(
  new URL("../../web/js/compare/charts/ring_chart.js", import.meta.url),
  "utf8"
);
const ringChartModule = await import(
  `data:text/javascript;base64,${Buffer.from(sourceText, "utf8").toString("base64")}`
);

const {
  buildAboveThresholdDisplayPoints,
  buildCdfAxisScale,
  isNoDataDot,
} = ringChartModule;

test("isNoDataDot keeps CDFb dots real when above-threshold data exists even without a bin hit", () => {
  assert.equal(
    isNoDataDot({
      displayBinCount: 0,
      hasRealData: true,
    }, true),
    false
  );
});

test("isNoDataDot marks only non-real CDFb dots as no-data", () => {
  assert.equal(
    isNoDataDot({
      displayBinCount: 4,
      hasRealData: false,
    }, true),
    true
  );
});

test("isNoDataDot keeps the terminal CDFb 0/total point real", () => {
  assert.equal(
    isNoDataDot({
      displayBinCount: 0,
      hasRealData: false,
      isTerminalThresholdPoint: true,
    }, true),
    false
  );
});

test("isNoDataDot preserves cumulative-frequency bin-count behavior", () => {
  assert.equal(
    isNoDataDot({
      displayBinCount: 0,
      hasRealData: true,
    }, false),
    true
  );
  assert.equal(
    isNoDataDot({
      displayBinCount: 2,
      hasRealData: false,
    }, false),
    false
  );
});

test("buildAboveThresholdDisplayPoints keeps the terminal CDFb point as real data when a cutoff row exists", () => {
  const points = buildAboveThresholdDisplayPoints({
    points: [
      {
        index: 0,
        intervalStart: 0,
        intervalEnd: 20,
        hasRealData: true,
        totalReverse: 2,
      },
      {
        index: 1,
        intervalStart: 20,
        intervalEnd: 40,
        hasRealData: true,
        totalReverse: 1,
      },
    ],
    aboveThresholdPlanRows: [
      { cutoffYieldPercent: 0, hasRealData: true },
      { cutoffYieldPercent: 20, hasRealData: true },
      { cutoffYieldPercent: 40, hasRealData: true },
    ],
  });

  const lastPoint = points[points.length - 1];
  assert.equal(lastPoint.intervalStart, 40);
  assert.equal(lastPoint.hasRealData, true);
  assert.equal(lastPoint.syntheticTrailingPoint, undefined);
});

test("buildAboveThresholdDisplayPoints stops once it reaches the first zero-probability cutoff", () => {
  const points = buildAboveThresholdDisplayPoints({
    points: [
      {
        index: 0,
        intervalStart: 0,
        intervalEnd: 20,
        hasRealData: true,
        totalReverse: 3,
      },
      {
        index: 1,
        intervalStart: 20,
        intervalEnd: 40,
        hasRealData: true,
        totalReverse: 0,
      },
    ],
    aboveThresholdPlanRows: [
      { cutoffYieldPercent: 0, hasRealData: true },
      { cutoffYieldPercent: 20, hasRealData: true },
      { cutoffYieldPercent: 40, hasRealData: true },
    ],
  });

  assert.equal(points.length, 2);
  assert.equal(points[points.length - 1].intervalStart, 20);
  assert.equal(points[points.length - 1].totalReverse, 0);
});

test("buildCdfAxisScale shrinks the CDFb y-axis to the observed probability range", () => {
  const axisScale = buildCdfAxisScale([
    { totalReverse: 7 },
    { totalReverse: 6 },
    { totalReverse: 5 },
    { totalReverse: 0 },
  ], 10);

  assert.deepEqual(
    axisScale,
    {
      countAxisScaleMax: 0.8,
      yTicks: [0.8, 0.6, 0.4, 0.2, 0],
    }
  );
});
