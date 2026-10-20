import { test } from "node:test";
import assert from "node:assert/strict";
import {
  areaFromAnswer,
  areasFromAnswer,
  areaSummary,
  bodyOptionsFor,
  normalizeLowerBodyAnswer,
  toggleLowerBodyArea,
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

test("multiple areas retain their sides and views through edits and serialization", () => {
  const rightKnee = { side: "Right", key: "knee", view: "front" };
  const leftCalf = { side: "Left", key: "shin", view: "back" };
  const selected = toggleLowerBodyArea(rightKnee, leftCalf);
  assert.deepEqual(selected, [rightKnee, leftCalf]);
  const options = bodyOptionsFor({ kind: "body_map", illustration: "legs" });
  const serialized = serializeGuidedAnswer({
    selected: selected.map(areaSummary),
    details: "Patient’s exact wording 我的描述",
  });
  const parsed = normalizeLowerBodyAnswer(
    parseGuidedAnswer(serialized, options),
  );
  assert.deepEqual(areasFromAnswer(parsed.selected), selected);
  assert.equal(parsed.details, "Patient’s exact wording 我的描述");
  assert.deepEqual(toggleLowerBodyArea(selected, rightKnee), [leftCalf]);
});

test("legacy broad locations remain as details alongside precise multi-area answers", () => {
  const area = { side: "Left", key: "foot", view: "front" };
  const raw = {
    selected: ["Right knee", areaSummary(area)],
    details: "Only after walking.\n  Patient spacing retained.",
  };
  assert.deepEqual(normalizeLowerBodyAnswer(raw), {
    selected: [areaSummary(area)],
    details: "Right knee\nOnly after walking.\n  Patient spacing retained.",
  });
});
