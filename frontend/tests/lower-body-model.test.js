import { test } from "node:test";
import assert from "node:assert/strict";
import {
  areaFromAnswer,
  areaSummary,
  bodyOptionsFor,
} from "../src/product/lowerBodyModel.js";
import {
  appendGuidedDetails,
  parseGuidedAnswer,
  serializeGuidedAnswer,
} from "../src/product/answerValues.js";
test("lower-body view survives readable form serialization and capture append", () => {
  const area = { side: "Left", key: "shin", view: "back" };
  const options = bodyOptionsFor({
    kind: "body_map",
    illustration: "legs",
    options: [],
  });
  const value = serializeGuidedAnswer({ selected: [areaSummary(area)] });
  const updated = appendGuidedDetails(value, "Patient's own detail", options);
  const parsed = parseGuidedAnswer(updated, options);
  assert.deepEqual(areaFromAnswer(parsed.selected), area);
  assert.equal(parsed.details, "Patient's own detail");
  assert.equal(areaFromAnswer(["Right knee"]), null);
});
