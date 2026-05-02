import test from "node:test";
import assert from "node:assert/strict";

import {
  parseRequestedSessionGuid,
  chooseInitialSessionFilename,
  buildSessionAnalysisUrl,
} from "../../web/js/shared/session_navigation.js";

test("parseRequestedSessionGuid reads the session_guid query param", () => {
  assert.equal(
    parseRequestedSessionGuid("?theme=blue-dark&session_guid=session-123"),
    "session-123"
  );
  assert.equal(parseRequestedSessionGuid("?theme=blue-dark"), "");
});

test("chooseInitialSessionFilename prefers the requested guid and falls back to the newest file", () => {
  const filenames = [
    "session_data_300.json",
    "session_data_200.json",
    "session_data_100.json",
  ];
  const detailsByFilename = new Map([
    ["session_data_300.json", { sessionGuid: "guid-300" }],
    ["session_data_200.json", { sessionGuid: "guid-200" }],
    ["session_data_100.json", { sessionGuid: "guid-100" }],
  ]);

  assert.equal(
    chooseInitialSessionFilename(filenames, detailsByFilename, "guid-200"),
    "session_data_200.json"
  );
  assert.equal(
    chooseInitialSessionFilename(filenames, detailsByFilename, "missing-guid"),
    "session_data_300.json"
  );
});

test("buildSessionAnalysisUrl preserves session guid and theme", () => {
  assert.equal(
    buildSessionAnalysisUrl({ sessionGuid: "guid-7", themeId: "green-dark" }),
    "/web/index.html?session_guid=guid-7&theme=green-dark"
  );
  assert.equal(
    buildSessionAnalysisUrl({}),
    "/web/index.html"
  );
});
