import test from "node:test";
import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";

const sourceText = await readFile(
  new URL("../../web/js/compare/models/session_violin_model.js", import.meta.url),
  "utf8"
);
const compareModelText = await readFile(
  new URL("../../web/js/compare/models/compare_model.js", import.meta.url),
  "utf8"
);

const compareModelDataUrl = `data:text/javascript;base64,${Buffer.from(compareModelText, "utf8").toString("base64")}`;
const rewrittenSourceText = sourceText.replace('./compare_model.js', compareModelDataUrl);
const violinModelModule = await import(
  `data:text/javascript;base64,${Buffer.from(rewrittenSourceText, "utf8").toString("base64")}`
);

const {
  buildSessionViolinModel,
  clusterSessionValueMarkers,
} = violinModelModule;

test("buildSessionViolinModel groups asteroid percentages by session and preserves zero values", () => {
  const ring = {
    asteroidList: [
      {
        sessionGuid: "session-a",
        asteroidId: 3,
        duplicate: false,
        commodityPercentages: new Map([["platinum", 20]]),
      },
      {
        sessionGuid: "session-a",
        asteroidId: 4,
        duplicate: true,
        commodityPercentages: new Map([["gold", 15]]),
      },
      {
        sessionGuid: "session-b",
        asteroidId: 8,
        duplicate: false,
        commodityPercentages: new Map([["platinum", 40]]),
      },
      {
        sessionGuid: "session-b",
        asteroidId: 9,
        duplicate: false,
        commodityPercentages: new Map([["silver", 10]]),
      },
    ],
  };

  const model = buildSessionViolinModel({
    ring,
    commodityKey: "platinum",
  });

  assert.equal(model.sessions.length, 2);
  assert.equal(model.totalAsteroids, 4);
  assert.equal(model.averageYield, 15);
  assert.deepEqual(
    model.sessions.map((session) => ({
      guid: session.sessionGuid,
      label: session.sessionLabel,
      values: session.values,
      asteroidSamples: session.asteroidSamples,
      count: session.asteroidCount,
      nonZeroCount: session.nonZeroCount,
    })),
    [
      {
        guid: "session-a",
        label: "S1",
        values: [0, 20],
        asteroidSamples: [
          {
            asteroidId: 4,
            duplicate: true,
            present: false,
            value: 0,
          },
          {
            asteroidId: 3,
            duplicate: false,
            present: true,
            value: 20,
          },
        ],
        count: 2,
        nonZeroCount: 1,
      },
      {
        guid: "session-b",
        label: "S2",
        values: [0, 40],
        asteroidSamples: [
          {
            asteroidId: 9,
            duplicate: false,
            present: false,
            value: 0,
          },
          {
            asteroidId: 8,
            duplicate: false,
            present: true,
            value: 40,
          },
        ],
        count: 2,
        nonZeroCount: 1,
      },
    ]
  );
});

test("buildSessionViolinModel produces density points and rounded y-axis limits", () => {
  const ring = {
    asteroidList: [
      {
        sessionGuid: "session-a",
        commodityPercentages: new Map([["platinum", 12]]),
      },
      {
        sessionGuid: "session-a",
        commodityPercentages: new Map([["platinum", 18]]),
      },
      {
        sessionGuid: "session-b",
        commodityPercentages: new Map([["platinum", 33]]),
      },
    ],
  };

  const model = buildSessionViolinModel({
    ring,
    commodityKey: "platinum",
    yStep: 2,
    yAxisStep: 5,
  });

  assert.equal(model.yMax, 35);
  assert.ok(model.maxDensity > 0);
  assert.equal(model.averageYield, 21);
  assert.ok(model.sessions.every((session) => Array.isArray(session.densityPoints) && session.densityPoints.length > 0));
  assert.ok(model.sessions.every((session) => session.bandwidth > 0));
});

test("clusterSessionValueMarkers merges repeated and near-overlapping values into weighted markers", () => {
  const markers = clusterSessionValueMarkers([
    { asteroidId: 11, value: 10 },
    { asteroidId: 12, value: 10.2 },
    { asteroidId: 13, value: 10.6 },
    { asteroidId: 21, value: 14 },
    { asteroidId: 22, value: 14.3 },
    { asteroidId: 31, value: 20 },
  ], 0.5);

  assert.deepEqual(
    markers.map((marker) => ({
      value: Number(marker.value.toFixed(3)),
      count: marker.count,
      minValue: marker.minValue,
      maxValue: marker.maxValue,
      asteroidIds: marker.members.map((member) => member.asteroidId),
    })),
    [
      {
        value: 10.267,
        count: 3,
        minValue: 10,
        maxValue: 10.6,
        asteroidIds: [11, 12, 13],
      },
      {
        value: 14.15,
        count: 2,
        minValue: 14,
        maxValue: 14.3,
        asteroidIds: [21, 22],
      },
      {
        value: 20,
        count: 1,
        minValue: 20,
        maxValue: 20,
        asteroidIds: [31],
      },
    ]
  );
});
