import test from "node:test";
import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";

const sourceText = await readFile(
  new URL("../../web/js/shared/system_name.js", import.meta.url),
  "utf8"
);

const systemNameModule = await import(
  `data:text/javascript;base64,${Buffer.from(sourceText, "utf8").toString("base64")}`
);

const { extractSystemNameFromRingName } = systemNameModule;

test("extractSystemNameFromRingName keeps non-ring names unchanged", () => {
  assert.equal(extractSystemNameFromRingName("Synuefe UZ-O c22-10"), "Synuefe UZ-O c22-10");
});

test("extractSystemNameFromRingName strips common body and ring suffixes", () => {
  assert.equal(
    extractSystemNameFromRingName("Col 285 Sector VZ-W b15-0 1 A Ring"),
    "Col 285 Sector VZ-W b15-0"
  );
  assert.equal(
    extractSystemNameFromRingName("Col 285 Sector LB-O c6-3 A 8 A Ring"),
    "Col 285 Sector LB-O c6-3"
  );
  assert.equal(
    extractSystemNameFromRingName("Col 285 Sector QB-E b12-3 AB 1 B Ring"),
    "Col 285 Sector QB-E b12-3"
  );
});

test("extractSystemNameFromRingName leaves star ring names at the system level", () => {
  assert.equal(
    extractSystemNameFromRingName("Col 285 Sector HM-M c7-17 9 A Ring"),
    "Col 285 Sector HM-M c7-17"
  );
});
