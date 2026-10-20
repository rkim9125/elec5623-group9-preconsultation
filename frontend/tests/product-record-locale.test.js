import test from "node:test";
import assert from "node:assert/strict";
import { translateProduct, languages, productResources } from "../src/product/translations.js";
import { recordTitle, recordLabel, recordedValue, slotStatusLabel, followupAnswerText } from "../src/product/recordLocale.js";
import { followupPayload } from "../src/product/followupModel.js";

const t = (locale) => (value, params) => translateProduct(locale, value, params);

test("saved canonical titles and composed title lists localize without rewriting custom titles", () => {
  for (const { id } of languages.slice(1)) {
    assert.notEqual(recordTitle("Leg pain", t(id)), "Leg pain");
    assert.equal(recordTitle("Leg pain · Sleep difficulties", t(id)), `${t(id)("Leg pain")} · ${t(id)("Sleep difficulties")}`);
    assert.equal(recordTitle("Leg pain after work — my words", t(id)), "Leg pain after work — my words");
    assert.equal(recordTitle("Leg pain · my unusual concern", t(id)), "Leg pain · my unusual concern");
    assert.notEqual(recordTitle("Appointment preparation", t(id)), "Appointment preparation");
    assert.equal(recordLabel("Leg pain: Symptom onset", t(id)), `${t(id)("Leg pain")}: ${t(id)("Symptom onset")}`);
  }
});

test("recorded choice labels translate while free text, medication names, units and negation remain exact", () => {
  const details = "Not Burning; amlodipine 5 mg — I do not take 10 mg.";
  const original = `Selected options:\n- Aching\n- Sharp\n\nAdditional details:\n${details}`;
  const display = recordedValue(original, t("zh-CN"));
  assert.equal(display, `已选选项：\n- 酸痛\n- 刺痛\n\n补充说明：\n${details}`);
  assert.equal(recordedValue(details, t("zh-CN")), details);
  assert.equal(recordedValue("Selected options:\nI typed this narrative", t("zh-CN")), "Selected options:\nI typed this narrative");
  assert.equal(recordedValue("Aching", t("zh-CN")), "Aching");
});

test("localized suggested answers display their label and submit the unchanged choice value", () => {
  const question = { id: "q1", options: [{ id: "A", value: "Present all the time", label: "一直存在" }] };
  const answer = { question_id: "q1", value: "Present all the time", status: "FILLED" };
  assert.equal(followupAnswerText(question, answer, t("zh-CN")), "一直存在");
  assert.equal(followupPayload([question], { q1: answer })[0].value, "Present all the time");
  assert.equal(followupAnswerText(question, { ...answer, value: "Present all the time except at night" }, t("zh-CN")), "Present all the time except at night");
  assert.equal(followupAnswerText(question, { ...answer, value: "一直存在，但休息时会缓解" }, t("zh-CN")), "一直存在，但休息时会缓解");
});

test("all structured record statuses and source labels have full non-English copy", () => {
  for (const { id } of languages.slice(1)) {
    for (const status of ["FILLED", "MISSING", "UNCERTAIN", "SKIPPED", "NOT_APPLICABLE", "ATTACHED"]) {
      assert.notEqual(slotStatusLabel(status, t(id)), slotStatusLabel(status, t("en")));
    }
    for (const label of ["Date of birth (patient reported)", "Sex at birth (patient reported)", "Blood group (patient reported)", "Communication and accessibility needs", "Age at preparation (calculated from patient-reported date of birth)"]) {
      assert.ok(productResources[id][label]);
      assert.notEqual(recordLabel(label, t(id)), label);
    }
  }
});


test("dynamic field suffixes localize without rewriting medication identities or patient prose", () => {
  for (const { id } of languages.slice(1)) {
    for (const [suffix, canonical] of [["dose", "Dose"], ["frequency", "Frequency"], ["actual_use", "Actual use"], ["ordering clinician", "Ordering clinician"]]) {
      const name = "MetFORMIN XR 500 mg";
      assert.equal(recordLabel(`${name} · ${suffix}`, t(id)), `${name} · ${t(id)(canonical)}`);
      assert.notEqual(t(id)(canonical), canonical);
    }
    // A medicine name can coincide with a known interface word. It is still
    // an identity, whereas only the application-owned suffix is translated.
    assert.equal(recordLabel("Frequency · dose", t(id)), `Frequency · ${t(id)("Dose")}`);
    assert.equal(recordLabel("My own name: Aspirin (not currently taking)", t(id)), "My own name: Aspirin (not currently taking)");
    assert.equal(recordLabel("Aspirin · patient described an unusual response", t(id)), "Aspirin · patient described an unusual response");
    for (const label of ["Location", "Current medication", "Appointment goals"])
      assert.notEqual(recordLabel(label, t(id)), label);
  }
});
