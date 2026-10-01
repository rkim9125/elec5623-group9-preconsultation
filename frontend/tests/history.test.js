import { test } from "node:test";
import assert from "node:assert/strict";
import { initial, change, summary, describe } from "../src/model.js";
import { historyOptions, editHistory, historyTags } from "../src/history.js";
import { resources } from "../src/i18n/core.js";
import { createAccountService } from "../src/account/service.js";
import { createDoctorService } from "../src/doctor/service.js";

test("history choices have stable unique IDs and translations", () => {
  assert.equal(new Set(historyOptions.map((o) => o.id)).size, 7);
  for (const option of historyOptions)
    for (const locale of ["en", "ko"])
      assert.ok(resources[locale][option.labelKey]);
});
test("legacy text is preserved; tag edits invalidate review and empty means unanswered", () => {
  const legacy = {
    status: "answered",
    value: "Original text\nNot a diagnosis",
  };
  assert.deepEqual(historyTags(legacy), []);
  const d = change(
    { ...initial(), approved: true },
    "history",
    editHistory(legacy, { tags: ["asthma", "diabetes", "asthma"] }),
  );
  assert.equal(d.approved, false);
  assert.equal(d.history.value, legacy.value);
  assert.equal(describe(d.history, "en"), "Asthma\nDiabetes\n" + legacy.value);
  assert.equal(describe(d.history, "ko"), "천식\n당뇨병\n" + legacy.value);
  assert.equal(
    editHistory(d.history, { tags: [], value: "" }).status,
    "unanswered",
  );
  assert.equal(editHistory(legacy, {}).value, legacy.value);
});
test("exclusive responses retain inactive drafts but never show them in either summary", () => {
  const history = editHistory(initial().history, {
    tags: ["diabetes"],
    value: "Keep this explanation",
  });
  for (const status of ["none", "unknown", "declined"]) {
    const inactive = { ...history, status };
    for (const locale of ["en", "ko"]) {
      const text = JSON.stringify(
        summary({ ...initial(), history: inactive }, locale),
      );
      assert.ok(!text.includes("Keep this explanation"));
      assert.ok(!text.includes("Diabetes"));
      assert.ok(!text.includes("당뇨병"));
    }
    assert.equal(editHistory(inactive, {}).status, "answered");
    assert.equal(editHistory(inactive, {}).value, history.value);
  }
});
test("saved tag submission survives restore, is immutable, and reaches doctor source answers", async () => {
  const map = new Map();
  const storage = {
    getItem: (k) => map.get(k),
    setItem: (k, v) => map.set(k, v),
    removeItem: (k) => map.delete(k),
  };
  const auth = createAccountService({ storage, delay: 1 });
  await auth.login("garam@example.test", "Demo1234!");
  const scope = auth.scope();
  const old = (await auth.load(scope)).intakes.find(
    (i) => i.id === "intake-a-sent",
  );
  const data = initial();
  data.reasons = ["Demo visit"];
  for (const key of [
    "onset",
    "course",
    "severity",
    "impact",
    "medicines",
    "allergies",
    "questions",
  ])
    data[key].status = "unknown";
  data.history = editHistory(data.history, {
    tags: ["diabetes", "surgery"],
    value: "Additional original text",
  });
  data.approved = true;
  data.sent = true;
  const saved = auth.saveIntake(scope, "intake-a-draft", data, "done").record;
  data.history.tags.push("asthma");
  auth.saveIntake(scope, "intake-a-draft", data, "history");
  auth.saveIntake(scope, old.id, data, "history");
  const records = (await auth.load(scope)).intakes;
  assert.deepEqual(
    records.find((i) => i.id === old.id),
    old,
  );
  assert.deepEqual(
    records.find((i) => i.id === saved.id),
    saved,
  );
  const restored = createAccountService({ storage, delay: 1 });
  await restored.restore();
  assert.deepEqual(
    (await restored.load(restored.scope())).intakes.find(
      (i) => i.id === saved.id,
    ).snapshot.data.history.tags,
    ["diabetes", "surgery"],
  );
  await auth.login("doctor@example.test", "Demo1234!");
  const doctor = createDoctorService({
    storage,
    delay: 1,
    authService: auth,
    patientSource: () => auth.doctorDemoSource(),
  });
  const submission = (await doctor.detail(doctor.scope(), "apt-a-next"))
    .submissions[0];
  const answer = submission.answers.find((a) => a.field === "history");
  assert.deepEqual(answer.tags, ["diabetes", "surgery"]);
  assert.equal(answer.value, "Additional original text");
  assert.ok(
    submission.summary.sections
      .find((s) => s.key === "history")
      .refs.includes(answer.id),
  );
});
