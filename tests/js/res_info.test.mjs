import test from "node:test";
import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";

const sourceText = await readFile(
  new URL("../../web/js/compare/ui/res_info.js", import.meta.url),
  "utf8"
);
const resInfoModule = await import(
  `data:text/javascript;base64,${Buffer.from(sourceText, "utf8").toString("base64")}`
);

const {
  RES_INFO_SOURCE_URL,
  getResInfoDialogModel,
} = resInfoModule;

test("RES info dialog model links the referenced EliteMiners thread", () => {
  assert.equal(
    RES_INFO_SOURCE_URL,
    "https://www.reddit.com/r/EliteMiners/comments/jordsf/basic_mining_facts_prospector_limpet_information/"
  );

  const model = getResInfoDialogModel();
  assert.equal(model.sourceUrl, RES_INFO_SOURCE_URL);
});

test("RES info dialog model includes the outside-RES 0.26 multiplier summary", () => {
  const model = getResInfoDialogModel();
  const tables = Array.isArray(model.tables) ? model.tables : [];
  const yieldTable = tables.find((entry) => entry && entry.title === "Yield Multiplier");
  const fragmentTable = tables.find((entry) => entry && entry.title === "Fragment Count");

  assert.ok(
    yieldTable
      && Array.isArray(yieldTable.rows)
      && yieldTable.rows.some((row) => Array.isArray(row) && row[0] === "Outside" && row[1] === "0.26 t")
  );
  assert.ok(
    Array.isArray(model.summaryPoints)
      && model.summaryPoints.some((entry) => String(entry).includes("0.26 tons of refined commodity"))
  );
  assert.ok(
    fragmentTable
      && String(fragmentTable.description).includes("Average fragment count per asteroid")
  );
});
