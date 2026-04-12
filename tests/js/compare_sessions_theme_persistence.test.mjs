import test from "node:test";
import assert from "node:assert/strict";

import {
  buildPersistedCompareThemeUpdate,
  normalizePersistedCompareThemeId,
  readPersistedCompareThemeId,
} from "../../web/js/compare_sessions/theme_persistence.js";

test("normalizePersistedCompareThemeId keeps valid compare theme ids", () => {
  assert.equal(normalizePersistedCompareThemeId("blue-dark"), "blue-dark");
  assert.equal(normalizePersistedCompareThemeId("green-light"), "green-light");
});

test("normalizePersistedCompareThemeId falls back to the default for invalid values", () => {
  assert.equal(normalizePersistedCompareThemeId(""), "orange-dark");
  assert.equal(normalizePersistedCompareThemeId("purple-neon"), "orange-dark");
});

test("buildPersistedCompareThemeUpdate writes the compareThemeId payload used by analysis settings", () => {
  assert.deepEqual(
    buildPersistedCompareThemeUpdate("blue-dark"),
    {
      compare: {
        compareThemeId: "blue-dark",
      },
    }
  );
});

test("readPersistedCompareThemeId reads the persisted compare theme from analysis settings payloads", () => {
  assert.equal(
    readPersistedCompareThemeId({
      report_settings: {
        compare: {
          compareThemeId: "green-dark",
        },
      },
    }),
    "green-dark"
  );
});

test("readPersistedCompareThemeId falls back when analysis settings payloads are missing or invalid", () => {
  assert.equal(readPersistedCompareThemeId(null, "blue-dark"), "blue-dark");
  assert.equal(
    readPersistedCompareThemeId({
      report_settings: {
        compare: {
          compareThemeId: "purple-neon",
        },
      },
    }, "blue-dark"),
    "blue-dark"
  );
});
