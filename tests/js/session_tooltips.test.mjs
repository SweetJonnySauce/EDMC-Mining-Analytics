import test from "node:test";
import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";

const sourceText = await readFile(
  new URL("../../web/js/compare_sessions/session_tooltips.js", import.meta.url),
  "utf8"
);
const sessionTooltipsModule = await import(
  `data:text/javascript;base64,${Buffer.from(sourceText, "utf8").toString("base64")}`
);

const {
  buildSessionTooltipText,
} = sessionTooltipsModule;

test("buildSessionTooltipText omits mean and median yield lines", () => {
  const tooltip = buildSessionTooltipText({
    commodityLabel: "Platinum",
    ringName: "Col 285 Sector KM-V d2-106 5 A Ring",
    session: {
      sessionLabel: "S1",
      asteroidCount: 23,
      averageYield: 30.34,
      median: 31.83,
      p25: 13.32,
      p75: 40.28,
      maxValue: 66.41,
    },
  });

  assert.equal(
    tooltip,
    [
      "Platinum | Col 285 Sector KM-V d2-106 5 A Ring",
      "S1",
      "Asteroids: 23",
      "P25-P75: 13.32% to 40.28%",
      "Max Yield: 66.41%",
    ].join("\n")
  );
  assert.equal(tooltip.includes("Avg Yield:"), false);
  assert.equal(tooltip.includes("Median:"), false);
});
