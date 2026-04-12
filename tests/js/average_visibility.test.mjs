import test from "node:test";
import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";

const sourceText = await readFile(
  new URL("../../web/js/compare_sessions/average_visibility.js", import.meta.url),
  "utf8"
);
const averageVisibilityModule = await import(
  `data:text/javascript;base64,${Buffer.from(sourceText, "utf8").toString("base64")}`
);

const {
  shouldShowOverallAverageMarker,
  shouldShowSessionMeanMarker,
} = averageVisibilityModule;

test("shouldShowOverallAverageMarker hides the overall Avg marker when 0% asteroids are excluded", () => {
  assert.equal(shouldShowOverallAverageMarker(true), false);
});

test("shouldShowOverallAverageMarker keeps the overall Avg marker when 0% asteroids are shown", () => {
  assert.equal(shouldShowOverallAverageMarker(false), true);
});

test("shouldShowSessionMeanMarker hides the per-session mean marker when 0% asteroids are excluded", () => {
  assert.equal(shouldShowSessionMeanMarker(true), false);
});

test("shouldShowSessionMeanMarker keeps the per-session mean marker when 0% asteroids are shown", () => {
  assert.equal(shouldShowSessionMeanMarker(false), true);
});
