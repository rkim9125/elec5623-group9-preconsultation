import { test } from "node:test";
import assert from "node:assert/strict";
import { initial, change, summary, describe } from "../src/model.js";
import {
  medicineOptions,
  medicineTags,
  editMedicines,
  medicineText,
} from "../src/medicines.js";
import { resources } from "../src/i18n/core.js";
import { freezeSubmission } from "../src/doctor/service.js";

test("medicine types have unique stable IDs and complete bilingual labels", () => {
  assert.equal(new Set(medicineOptions.map((o) => o.id)).size, 8);
  for (const o of medicineOptions)
    for (const locale of ["en", "ko"]) assert.ok(resources[locale][o.labelKey]);
});
test("type-only, details-only and combined answers stay separate without inferring drugs", () => {
  const legacy = {
    status: "answered",
    value: "",
    items: [{ name: "Original drug", detail: "Original instructions" }],
  };
  assert.deepEqual(medicineTags(legacy), []);
  const tagged = editMedicines(legacy, {
    tags: ["pain-relief", "pain-relief", "other"],
  });
  assert.deepEqual(tagged.items, legacy.items);
  assert.deepEqual(tagged.tags, ["pain-relief", "other"]);
  const text = medicineText(tagged, "en");
  assert.match(text, /Selected medicine types/);
  assert.match(text, /Entered medicine details/);
  assert.match(text, /Original drug/);
  assert.match(text, /No link/);
  assert.deepEqual(editMedicines(tagged, { tags: [] }).items, legacy.items);
  const only = editMedicines(initial().medicines, { tags: ["pain-relief"] });
  assert.deepEqual(only.items, []);
  assert.equal(only.status, "answered");
  assert.match(
    describe(only, "en"),
    /Exact medicine names and doses have not been confirmed/,
  );
  assert.equal(editMedicines(only, { tags: [] }).status, "unanswered");
  const updated = change({ ...initial(), approved: true }, "medicines", tagged);
  assert.equal(updated.approved, false);
  assert.match(summary(updated, "ko")[3].text, /진통제/);
  assert.match(summary(updated, "ko")[3].text, /Original instructions/);
});
test("exclusive responses retain inactive drafts without showing types or details", () => {
  const a = editMedicines(initial().medicines, {
    tags: ["sleep-medication"],
    items: [{ name: "Private draft", detail: "Kept" }],
  });
  for (const status of ["none", "unknown", "declined"]) {
    const inactive = { ...a, status };
    for (const locale of ["en", "ko"]) {
      const text = JSON.stringify(
        summary({ ...initial(), medicines: inactive }, locale),
      );
      assert.ok(!text.includes("Private draft"));
      assert.ok(!text.includes("Sleep medication"));
      assert.ok(!text.includes("수면제"));
    }
    assert.deepEqual(editMedicines(inactive, {}).items, a.items);
  }
});
test("frozen doctor answers preserve types and details and mark type-only information unconfirmed", () => {
  const d = initial();
  d.medicines = editMedicines(d.medicines, { tags: ["diabetes-medication"] });
  const snapshot = freezeSubmission(d, "test", 1, new Date().toISOString());
  d.medicines.tags.push("other");
  const answer = snapshot.answers.find((a) => a.field === "medicines");
  assert.deepEqual(answer.tags, ["diabetes-medication"]);
  assert.deepEqual(answer.items, []);
  assert.ok(
    snapshot.summary.sections
      .find((s) => s.key === "uncertain")
      .refs.includes(answer.id),
  );
});

test("inactive medicine details do not create an unconfirmed-information reference", () => {
  for (const status of ["none", "unknown", "declined"]) {
    const d = initial();
    d.medicines = {
      status,
      value: "",
      tags: ["pain-relief"],
      items: [{ name: "Draft only", detail: "" }],
    };
    const frozen = freezeSubmission(d, "inactive", 1, new Date().toISOString());
    const medicine = frozen.answers.find((a) => a.field === "medicines");
    const refs = frozen.summary.sections.find(
      (s) => s.key === "uncertain",
    ).refs;
    // Unknown/declined remain explicit uncertainty; a confirmed none is not
    // uncertain merely because an inactive detail draft has a blank dose.
    assert.equal(refs.includes(medicine.id), status !== "none");
  }
});
