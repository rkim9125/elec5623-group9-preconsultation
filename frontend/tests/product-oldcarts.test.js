import test from "node:test";
import assert from "node:assert/strict";
import {
  dimensionFor,
  symptomStories,
  symptomStatuses,
  painNumbers,
  withPainOptions,
  selectPainNumber,
} from "../src/product/oldcartsModel.js";
import { oldcartsTranslationRows } from "../src/product/oldcartsTranslations.js";
import {
  productResources,
  translateProduct,
} from "../src/product/translations.js";
import {
  parseGuidedAnswer,
  serializeGuidedAnswer,
  toggleGuidedSelection,
} from "../src/product/answerValues.js";

test("symptom stories retain server status distinctions without deriving a medical score", () => {
  const statuses = [
    "FILLED",
    "PARTIAL",
    "MISSING",
    "UNCERTAIN",
    "SKIPPED",
    "NOT_APPLICABLE",
  ];
  const rows = statuses.map((status, index) => ({
    id: ["O", "L", "D", "C", "A", "R"][index],
    status,
    keys: ["detail"],
    values: [],
  }));
  const [story] = symptomStories({
    concerns: [{ id: "one", title: "Leg pain" }],
    symptom_history: [
      { concern_id: "one", applicable: true, dimensions: rows },
    ],
  });
  assert.deepEqual(
    story.dimensions.map((item) => item.status),
    statuses.slice(0, 5),
  );
  assert.equal(story.unrecorded, 2);
  assert.equal(story.score, undefined);
  assert.equal(
    new Set(statuses.map((status) => symptomStatuses[status].label)).size,
    6,
  );
});

test("non-symptom visits and inapplicable dimensions stay out of the patient story", () => {
  assert.deepEqual(symptomStories({}), []);
  assert.deepEqual(
    symptomStories({
      symptom_history: [
        {
          concern_id: "refill",
          applicable: false,
          dimensions: [{ id: "O", status: "MISSING" }],
        },
      ],
    }),
    [],
  );
  assert.deepEqual(
    symptomStories({
      symptom_history: [
        {
          concern_id: "refill",
          applicable: true,
          dimensions: [{ id: "O", status: "NOT_APPLICABLE" }],
        },
      ],
    }),
    [],
  );
});

test("each concern keeps its own answer, including uncertainty text and historical combined factors", () => {
  const session = {
    concerns: [
      { id: "leg", title: "Leg pain" },
      { id: "head", title: "Headache" },
    ],
    symptom_history: ["leg", "head"].map((id) => ({
      concern_id: id,
      applicable: true,
      dimensions: [
        {
          id: "O",
          status: "UNCERTAIN",
          keys: ["symptom_onset"],
          values: [
            {
              key: "symptom_onset",
              value: id === "leg" ? "Maybe last week" : "I cannot remember",
              status: "UNCERTAIN",
            },
          ],
        },
        {
          id: "A",
          status: "PARTIAL",
          keys: ["aggravating_factors"],
          legacy_context: [
            { value: "Changes with movement", status: "FILLED" },
          ],
        },
      ],
    })),
  };
  const stories = symptomStories(session);
  assert.equal(stories[0].title, "Leg pain");
  assert.equal(stories[0].dimensions[0].values[0].value, "Maybe last week");
  assert.equal(stories[1].dimensions[0].values[0].value, "I cannot remember");
  assert.equal(stories[0].dimensions[1].status, "PARTIAL");
  assert.equal(
    stories[0].dimensions[1].legacy[0].value,
    "Changes with movement",
  );
});

test("radiation appears separately when active; dimension hints require explicit server metadata", () => {
  assert.equal(dimensionFor({ key: "some_pain" }), null);
  assert.equal(dimensionFor({ oldcarts_dimension: "R" }).label, "What helps");
  assert.equal(dimensionFor({ oldcarts_dimension: "__proto__" }), null);
  const [story] = symptomStories({
    symptom_history: [
      {
        concern_id: "one",
        applicable: true,
        dimensions: [{ id: "S", status: "FILLED" }],
        radiation: { id: "radiation", applicable: true, status: "UNCERTAIN" },
      },
    ],
  });
  assert.deepEqual(
    story.dimensions.map((item) => item.id),
    ["S", "radiation"],
  );
});

test("explicit none options are mutually exclusive but ordinary observations remain multi-select", () => {
  const options = [
    { value: "Walking" },
    { value: "Standing" },
    { value: "Nothing noticed", exclusive: true },
  ];
  assert.deepEqual(
    toggleGuidedSelection(
      ["Walking", "Standing"],
      "Nothing noticed",
      true,
      options,
    ),
    ["Nothing noticed"],
  );
  assert.deepEqual(
    toggleGuidedSelection(["Nothing noticed"], "Walking", true, options),
    ["Walking"],
  );
  assert.deepEqual(
    toggleGuidedSelection(["Walking"], "Standing", true, options),
    ["Walking", "Standing"],
  );
  assert.deepEqual(
    toggleGuidedSelection(
      ["Nothing noticed"],
      "Nothing noticed",
      true,
      options,
    ),
    [],
  );
});

test("optional pain numbers stay opt-in, replace each other, and preserve the patient's description", () => {
  const options = [{ value: "Mild", label: "Mild" }];
  assert.equal(withPainOptions(options, {}).length, 1);
  assert.equal(withPainOptions(options, { pain_scale: true }).length, 12);
  assert.equal(painNumbers[0].value, "0/10");
  assert.deepEqual(selectPainNumber(["Mild", "3/10"], "4/10"), [
    "Mild",
    "4/10",
  ]);
  assert.deepEqual(selectPainNumber(["Mild", "3/10"], "3/10"), ["Mild"]);
  const original = {
    selected: ["Mild", "3/10"],
    details: "Only after walking",
  };
  assert.deepEqual(
    parseGuidedAnswer(
      serializeGuidedAnswer(original),
      withPainOptions(options, { pain_scale: true }),
    ),
    { ...original, structured: true },
  );
});

test("new symptom UI and published backend copy is complete in all five locales", () => {
  const params = (value) =>
    [...value.matchAll(/\{(\w+)\}/g)].map((item) => item[1]).sort();
  for (const row of oldcartsTranslationRows) {
    assert.equal(row.length, 5, row[0]);
    for (const [index, locale] of [
      "en",
      "zh-CN",
      "zh-TW",
      "ko",
      "ja",
    ].entries()) {
      assert.ok(row[index]?.trim(), `${locale}: ${row[0]}`);
      assert.deepEqual(params(row[index]), params(row[0]), row[0]);
      assert.ok(productResources[locale][row[0]], `${locale}: ${row[0]}`);
    }
  }
  assert.equal(translateProduct("zh-CN", "Intensity"), "不适程度");
  assert.notEqual(
    translateProduct("ja", "Your symptom story"),
    "Your symptom story",
  );
});
