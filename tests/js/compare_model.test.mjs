import test from "node:test";
import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";

const sourceText = await readFile(
  new URL("../../web/js/compare/models/compare_model.js", import.meta.url),
  "utf8"
);
const compareModelModule = await import(
  `data:text/javascript;base64,${Buffer.from(sourceText, "utf8").toString("base64")}`
);

const {
  buildAboveThresholdPlanRows,
  buildRingCommodityModel,
  interpolateMissingValuesBetweenRealBins,
} = compareModelModule;

test("buildAboveThresholdPlanRows projects mine and prospect counts by cutoff", () => {
  const rows = buildAboveThresholdPlanRows({
    allAsteroids: [
      { value: 10 },
      { value: 20 },
      { value: 30 },
      { value: 40 },
    ],
    interval: 10,
    xMax: 40,
    targetTons: 52,
    tonsPerPercentagePoint: 0.26,
  });

  assert.deepEqual(
    rows.map((row) => ({
      cutoff: row.cutoffYieldPercent,
      mine: row.asteroidsToMine,
      prospect: row.asteroidsToProspect,
    })),
    [
      { cutoff: 0, mine: 8, prospect: 8 },
      { cutoff: 10, mine: 7, prospect: 10 },
      { cutoff: 20, mine: 6, prospect: 12 },
      { cutoff: 30, mine: 5, prospect: 20 },
      { cutoff: 40, mine: 0, prospect: 0 },
    ]
  );
});

test("buildRingCommodityModel cutoff plan uses all prospected asteroids for prospect counts", () => {
  const ring = {
    asteroidList: [
      {
        sessionGuid: "session-1",
        commodityPercentages: new Map([["platinum", 0]]),
      },
      {
        sessionGuid: "session-1",
        commodityPercentages: new Map([["platinum", 20]]),
      },
      {
        sessionGuid: "session-1",
        commodityPercentages: new Map([["platinum", 40]]),
      },
    ],
  };

  const model = buildRingCommodityModel({
    ring,
    commodityKey: "platinum",
    interval: 20,
    forcedXMax: 40,
  });

  const cutoff20 = model.aboveThresholdPlanRows.find((row) => row.cutoffYieldPercent === 20);
  const cutoff0 = model.aboveThresholdPlanRows.find((row) => row.cutoffYieldPercent === 0);
  assert.ok(cutoff0);
  assert.equal(cutoff0.totalAsteroidsCount, 3);
  assert.equal(cutoff0.qualifyingAsteroidsCount, 2);
  assert.equal(cutoff0.asteroidsToMine, 67);
  assert.equal(cutoff0.asteroidsToProspect, 101);
  assert.ok(cutoff20);
  assert.equal(cutoff20.totalAsteroidsCount, 3);
  assert.equal(cutoff20.qualifyingAsteroidsCount, 1);
  assert.equal(cutoff20.asteroidsToMine, 50);
  assert.equal(cutoff20.asteroidsToProspect, 150);
});

test("buildAboveThresholdPlanRows treats every cutoff as strictly greater than the threshold", () => {
  const rows = buildAboveThresholdPlanRows({
    allAsteroids: [
      { value: 0 },
      { value: 0 },
      { value: 12 },
      { value: 28 },
    ],
    interval: 10,
    xMax: 30,
    targetTons: 52,
    tonsPerPercentagePoint: 0.26,
  });

  const cutoff0 = rows.find((row) => row.cutoffYieldPercent === 0);
  assert.deepEqual(
    {
      qualifying: cutoff0.qualifyingAsteroidsCount,
      total: cutoff0.totalAsteroidsCount,
      mine: cutoff0.asteroidsToMine,
      prospect: cutoff0.asteroidsToProspect,
      share: Number(cutoff0.aboveThresholdShare.toFixed(2)),
    },
    {
      qualifying: 2,
      total: 4,
      mine: 10,
      prospect: 20,
      share: 0.5,
    }
  );

  const cutoff10 = rows.find((row) => row.cutoffYieldPercent === 10);
  assert.deepEqual(
    {
      qualifying: cutoff10.qualifyingAsteroidsCount,
      mine: cutoff10.asteroidsToMine,
      prospect: cutoff10.asteroidsToProspect,
    },
    {
      qualifying: 2,
      mine: 10,
      prospect: 20,
    }
  );

  const cutoff20 = rows.find((row) => row.cutoffYieldPercent === 20);
  assert.deepEqual(
    {
      qualifying: cutoff20.qualifyingAsteroidsCount,
      mine: cutoff20.asteroidsToMine,
      prospect: cutoff20.asteroidsToProspect,
    },
    {
      qualifying: 1,
      mine: 8,
      prospect: 32,
    }
  );

  const cutoff30 = rows.find((row) => row.cutoffYieldPercent === 30);
  assert.deepEqual(
    {
      qualifying: cutoff30.qualifyingAsteroidsCount,
      mine: cutoff30.asteroidsToMine,
      prospect: cutoff30.asteroidsToProspect,
      real: cutoff30.hasRealData,
    },
    {
      qualifying: 0,
      mine: 0,
      prospect: 0,
      real: true,
    }
  );
});

test("buildRingCommodityModel respects a custom cargo target for above-threshold projections", () => {
  const ring = {
    asteroidList: [
      {
        sessionGuid: "session-1",
        commodityPercentages: new Map([["platinum", 20]]),
      },
      {
        sessionGuid: "session-1",
        commodityPercentages: new Map([["platinum", 40]]),
      },
    ],
  };

  const model = buildRingCommodityModel({
    ring,
    commodityKey: "platinum",
    interval: 20,
    forcedXMax: 40,
    targetTons: 104,
  });

  const cutoff20 = model.aboveThresholdPlanRows.find((row) => row.cutoffYieldPercent === 20);
  assert.ok(cutoff20);
  assert.equal(model.targetTons, 104);
  assert.equal(cutoff20.asteroidsToMine, 10);
  assert.equal(cutoff20.asteroidsToProspect, 20);
});

test("buildRingCommodityModel counts zero-hit asteroids from sessions with no commodity presence", () => {
  const ring = {
    asteroidList: [
      {
        sessionGuid: "session-1",
        commodityPercentages: new Map([["platinum", 20]]),
      },
      {
        sessionGuid: "session-1",
        commodityPercentages: new Map([["platinum", 40]]),
      },
      {
        sessionGuid: "session-2",
        commodityPercentages: new Map([["gold", 30]]),
      },
      {
        sessionGuid: "session-2",
        commodityPercentages: new Map([["silver", 15]]),
      },
    ],
  };

  const model = buildRingCommodityModel({
    ring,
    commodityKey: "platinum",
    interval: 20,
    forcedXMax: 40,
  });

  const cutoff20 = model.aboveThresholdPlanRows.find((row) => row.cutoffYieldPercent === 20);
  assert.ok(cutoff20);
  assert.equal(model.asteroidsCount, 4);
  assert.equal(model.presentAsteroidsCount, 2);
  assert.equal(cutoff20.totalAsteroidsCount, 4);
  assert.equal(cutoff20.qualifyingAsteroidsCount, 1);
  assert.equal(cutoff20.asteroidsToMine, 50);
  assert.equal(cutoff20.asteroidsToProspect, 200);
});

test("buildAboveThresholdPlanRows preserves a column for every cutoff even when no asteroids qualify", () => {
  const rows = buildAboveThresholdPlanRows({
    allAsteroids: [
      { value: 21 },
      { value: 23 },
    ],
    interval: 5,
    xMax: 30,
    targetTons: 52,
    tonsPerPercentagePoint: 0.26,
  });

  assert.deepEqual(
    rows.map((row) => ({
      cutoff: row.cutoffYieldPercent,
      mine: row.asteroidsToMine,
      prospect: row.asteroidsToProspect,
    })),
    [
      { cutoff: 0, mine: 10, prospect: 10 },
      { cutoff: 5, mine: 10, prospect: 10 },
      { cutoff: 10, mine: 10, prospect: 10 },
      { cutoff: 15, mine: 10, prospect: 10 },
      { cutoff: 20, mine: 10, prospect: 10 },
      { cutoff: 25, mine: null, prospect: null },
      { cutoff: 30, mine: 0, prospect: 0 },
    ]
  );
});

test("buildAboveThresholdPlanRows keeps the last non-zero cutoff and adds a terminal zero row", () => {
  const rows = buildAboveThresholdPlanRows({
    allAsteroids: [
      { value: 69 },
      { value: 61 },
      { value: 58 },
      { value: 42 },
      { value: 17 },
    ],
    interval: 5,
    xMax: 70,
    targetTons: 52,
    tonsPerPercentagePoint: 0.26,
  });

  const penultimateRow = rows[rows.length - 2];
  assert.deepEqual(
    {
      cutoff: penultimateRow.cutoffYieldPercent,
      mine: penultimateRow.asteroidsToMine,
      prospect: penultimateRow.asteroidsToProspect,
      qualifying: penultimateRow.qualifyingAsteroidsCount,
    },
    {
      cutoff: 65,
      mine: 3,
      prospect: 15,
      qualifying: 1,
    }
  );

  const lastRow = rows[rows.length - 1];
  assert.deepEqual(
    {
      cutoff: lastRow.cutoffYieldPercent,
      mine: lastRow.asteroidsToMine,
      prospect: lastRow.asteroidsToProspect,
      qualifying: lastRow.qualifyingAsteroidsCount,
      real: lastRow.hasRealData,
    },
    {
      cutoff: 70,
      mine: 0,
      prospect: 0,
      qualifying: 0,
      real: true,
    }
  );
});

test("interpolateMissingValuesBetweenRealBins fills non-real bins between adjacent real bins", () => {
  const entries = [
    { value: 1.0, hasRealData: true },
    { value: 0.7, hasRealData: false },
    { value: 0.4, hasRealData: true },
    { value: 0.4, hasRealData: false },
    { value: 0.4, hasRealData: false },
    { value: 0.1, hasRealData: true },
  ];

  const interpolated = interpolateMissingValuesBetweenRealBins({
    entries,
    readValue: (entry) => entry.value,
    isRealEntry: (entry) => entry.hasRealData,
  });

  assert.deepEqual(
    interpolated.map((entry) => ({
      value: Number(entry.value.toFixed(3)),
      inferred: entry.inferred,
    })),
    [
      { value: 1.0, inferred: false },
      { value: 0.7, inferred: true },
      { value: 0.4, inferred: false },
      { value: 0.3, inferred: true },
      { value: 0.2, inferred: true },
      { value: 0.1, inferred: false },
    ]
  );
});

test("interpolateMissingValuesBetweenRealBins can hold the previous real value for cumulative displays", () => {
  const entries = [
    { value: 6, hasRealData: true },
    { value: 6, hasRealData: false },
    { value: 10, hasRealData: true },
    { value: 10, hasRealData: false },
    { value: 10, hasRealData: false },
    { value: 20, hasRealData: true },
  ];

  const interpolated = interpolateMissingValuesBetweenRealBins({
    entries,
    readValue: (entry) => entry.value,
    isRealEntry: (entry) => entry.hasRealData,
    strategy: "previous",
  });

  assert.deepEqual(
    interpolated.map((entry) => ({
      value: entry.value,
      inferred: entry.inferred,
    })),
    [
      { value: 6, inferred: false },
      { value: 6, inferred: true },
      { value: 10, inferred: false },
      { value: 10, inferred: true },
      { value: 10, inferred: true },
      { value: 20, inferred: false },
    ]
  );
});

test("interpolateMissingValuesBetweenRealBins can hold the next real value for reversed cumulative displays", () => {
  const entries = [
    { value: 1, hasRealData: true },
    { value: 2, hasRealData: true },
    { value: 4, hasRealData: true },
    { value: 6, hasRealData: true },
    { value: 6, hasRealData: false },
    { value: 10, hasRealData: true },
  ];

  const interpolated = interpolateMissingValuesBetweenRealBins({
    entries,
    readValue: (entry) => entry.value,
    isRealEntry: (entry) => entry.hasRealData,
    strategy: "next",
  });

  assert.deepEqual(
    interpolated.map((entry) => ({
      value: entry.value,
      inferred: entry.inferred,
    })),
    [
      { value: 1, inferred: false },
      { value: 2, inferred: false },
      { value: 4, inferred: false },
      { value: 6, inferred: false },
      { value: 10, inferred: true },
      { value: 10, inferred: false },
    ]
  );
});
