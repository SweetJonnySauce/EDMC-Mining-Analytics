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
      { cutoff: 10, mine: 8, prospect: 8 },
      { cutoff: 20, mine: 7, prospect: 10 },
      { cutoff: 30, mine: 6, prospect: 12 },
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
    populationMode: "present",
  });

  const cutoff20 = model.aboveThresholdPlanRows.find((row) => row.cutoffYieldPercent === 20);
  assert.ok(cutoff20);
  assert.equal(cutoff20.totalAsteroidsCount, 3);
  assert.equal(cutoff20.qualifyingAsteroidsCount, 2);
  assert.equal(cutoff20.asteroidsToMine, 67);
  assert.equal(cutoff20.asteroidsToProspect, 101);
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
    populationMode: "present",
    targetTons: 104,
  });

  const cutoff20 = model.aboveThresholdPlanRows.find((row) => row.cutoffYieldPercent === 20);
  assert.ok(cutoff20);
  assert.equal(model.targetTons, 104);
  assert.equal(cutoff20.asteroidsToMine, 14);
  assert.equal(cutoff20.asteroidsToProspect, 14);
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
      { cutoff: 5, mine: 10, prospect: 10 },
      { cutoff: 10, mine: 10, prospect: 10 },
      { cutoff: 15, mine: 10, prospect: 10 },
      { cutoff: 20, mine: 10, prospect: 10 },
      { cutoff: 25, mine: null, prospect: null },
    ]
  );
});

test("buildAboveThresholdPlanRows keeps a non-zero final cutoff when the highest plotted bin has real data", () => {
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

  const lastRow = rows[rows.length - 1];
  assert.deepEqual(
    {
      cutoff: lastRow.cutoffYieldPercent,
      mine: lastRow.asteroidsToMine,
      prospect: lastRow.asteroidsToProspect,
      qualifying: lastRow.qualifyingAsteroidsCount,
    },
    {
      cutoff: 65,
      mine: 3,
      prospect: 15,
      qualifying: 1,
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
