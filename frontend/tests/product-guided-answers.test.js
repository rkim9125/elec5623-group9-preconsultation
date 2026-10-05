import test from "node:test";
import assert from "node:assert/strict";
import {
  normalizeOptions,
  parseGuidedAnswer,
  serializeGuidedAnswer,
  toggleGuidedSelection,
  appendGuidedDetails,
} from "../src/product/answerValues.js";
import { bodyMapViews, getBodyRegion } from "../src/product/bodyRegions.js";

const options = [
  { value: "Left knee", label: "Left knee" },
  { value: "Right calf", label: "Right calf" },
];

test("guided answers start without suggested or inferred facts", () => {
  assert.deepEqual(parseGuidedAnswer("", options), {
    selected: [],
    details: "",
    structured: false,
  });
  assert.deepEqual(parseGuidedAnswer("Left knee", options), {
    selected: [],
    details: "Left knee",
    structured: false,
  });
});

test("selection and custom prose survive an exact readable round trip", () => {
  const details =
    "Tender after walking.\nI am not sure when it began.\n\n右边也会痛。";
  const value = serializeGuidedAnswer({
    selected: ["Right calf", "Left knee"],
    details,
  });
  assert.equal(
    value,
    `Selected options:\n- Right calf\n- Left knee\n\nAdditional details:\n${details}`,
  );
  assert.deepEqual(parseGuidedAnswer(value, options), {
    selected: ["Right calf", "Left knee"],
    details,
    structured: true,
  });
});

test("arbitrary old prose stays intact when choosing and clearing options", () => {
  const original =
    "Sometimes both legs hurt — mainly the right.\nSelected options: not sure.\n  Keep spacing.";
  const parsed = parseGuidedAnswer(original, options);
  const updated = {
    ...parsed,
    selected: toggleGuidedSelection(parsed.selected, "Left knee"),
  };
  const stored = parseGuidedAnswer(serializeGuidedAnswer(updated), options);
  assert.equal(stored.details, original);
  assert.equal(serializeGuidedAnswer({ ...stored, selected: [] }), original);
});

test("unrecognised or malformed selection text remains patient text", () => {
  for (const value of [
    "Selected options:\n- Unknown place",
    "Selected options:\nLeft knee",
    "Selected options:\n- Left knee\n- Left knee",
    "Selected options:\n- Left knee\n\nMy voice transcript",
  ]) {
    assert.deepEqual(parseGuidedAnswer(value, options), {
      selected: [],
      details: value,
      structured: false,
    });
  }
});

test("deselecting one multiple choice preserves the remaining exact order", () => {
  assert.deepEqual(
    toggleGuidedSelection(["Left knee", "Right calf"], "Left knee", true),
    ["Right calf"],
  );
  assert.deepEqual(toggleGuidedSelection(["Left knee"], "Right calf", true), [
    "Left knee",
    "Right calf",
  ]);
});

test("single choices replace a selection and can be cleared without a default", () => {
  assert.deepEqual(toggleGuidedSelection(["Left knee"], "Right calf", false), [
    "Right calf",
  ]);
  assert.deepEqual(
    toggleGuidedSelection(["Right calf"], "Right calf", false),
    [],
  );
});

test("duplicate and malformed metadata cannot create duplicate selection targets", () => {
  assert.deepEqual(normalizeOptions(null), []);
  assert.deepEqual(normalizeOptions({ value: "Left knee" }), []);
  assert.deepEqual(
    normalizeOptions([
      null,
      {},
      { value: "" },
      { value: "\n" },
      { value: "Left knee", label: "Knee" },
      { value: "Left knee", label: "Duplicate" },
      { value: "Right calf" },
    ]),
    [
      { value: "Left knee", label: "Knee" },
      { value: "Right calf", label: "Right calf" },
    ],
  );
});

test("exact values are stored instead of friendlier option labels", () => {
  const choices = [{ value: "My sleep is affected.", label: "Sleep" }];
  const value = serializeGuidedAnswer({
    selected: [choices[0].value],
    details: "",
  });
  assert.deepEqual(parseGuidedAnswer(value, choices).selected, [
    "My sleep is affected.",
  ]);
});

test("reviewed voice or file text appends to custom details without losing selection", () => {
  const old = serializeGuidedAnswer({
    selected: ["Left knee"],
    details: "After walking.",
  });
  const appended = appendGuidedDetails(old, "Usually in the evening.", options);
  assert.deepEqual(parseGuidedAnswer(appended, options), {
    selected: ["Left knee"],
    details: "After walking.\n\nUsually in the evening.",
    structured: true,
  });
});

test("voice append retains unstructured text verbatim and handles empty values", () => {
  assert.equal(
    appendGuidedDetails("Legacy answer.", "More detail.", options),
    "Legacy answer.\n\nMore detail.",
  );
  assert.equal(appendGuidedDetails("", "New answer.", options), "New answer.");
});

test("detail contents that resemble headings are not discarded or reparsed", () => {
  const details =
    "I wrote:\n\nAdditional details:\nAnother line.\nSelected options:\n- Left knee";
  const value = serializeGuidedAnswer({ selected: ["Left knee"], details });
  assert.equal(parseGuidedAnswer(value, options).details, details);
});

test("old answers remain intact when their choices are no longer in metadata", () => {
  const original = serializeGuidedAnswer({
    selected: ["Left knee"],
    details: "Longstanding.",
  });
  assert.equal(
    parseGuidedAnswer(original, [{ value: "Right calf" }]).details,
    original,
  );
});

test("front and rear map left/right correspond to the patient's perspective", () => {
  const frontLeft = getBodyRegion("legs", "left_thigh", "front");
  const frontRight = getBodyRegion("legs", "right_thigh", "front");
  const rearLeft = getBodyRegion("legs", "left_thigh", "back");
  const rearRight = getBodyRegion("legs", "right_thigh", "back");
  assert.ok(frontLeft.x > frontRight.x);
  assert.ok(rearLeft.x < rearRight.x);
  assert.ok(
    getBodyRegion("back", "lower_back_left", "back").x <
      getBodyRegion("back", "lower_back_right", "back").x,
  );
});

test("posterior and anterior regions only appear on an appropriate view", () => {
  assert.equal(getBodyRegion("legs", "left_calf", "front"), null);
  assert.ok(getBodyRegion("legs", "left_calf", "back"));
  assert.equal(getBodyRegion("legs", "left_knee", "back"), null);
  assert.ok(getBodyRegion("legs", "left_shin", "front"));
  assert.equal(getBodyRegion("legs", "left_shin", "back"), null);
  assert.ok(
    getBodyRegion("legs", "left_shin", "front").x >
      getBodyRegion("legs", "right_shin", "front").x,
  );
  assert.equal(getBodyRegion("body", "back", "front"), null);
  assert.ok(getBodyRegion("body", "back", "back"));
  assert.equal(getBodyRegion("head", "back_head", "front"), null);
  assert.ok(getBodyRegion("head", "back_head", "back"));
  assert.equal(getBodyRegion("head", "forehead", "back"), null);
});

test("rear-only maps and unknown regions have explicit behavior", () => {
  assert.deepEqual(bodyMapViews("neck_shoulders"), ["back"]);
  assert.deepEqual(bodyMapViews("legs"), ["front", "back"]);
  assert.deepEqual(bodyMapViews("abdomen"), ["front"]);
  assert.equal(getBodyRegion("legs", "invented_area"), null);
});
