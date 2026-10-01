import { test } from "node:test";
import assert from "node:assert/strict";
import {
  createDoctorService,
  freezeSubmission,
  dayKey,
} from "../src/doctor/service.js";
import { createAccountService } from "../src/account/service.js";
import { initial } from "../src/model.js";
const NOW = Date.parse("2026-09-18T03:00:00Z");
async function setup(options = {}) {
  const map = new Map(),
    storage = {
      getItem: (k) => map.get(k),
      setItem: (k, v) => map.set(k, v),
      removeItem: (k) => map.delete(k),
    };
  const api = createDoctorService({
    storage,
    delay: 2,
    now: () => NOW,
    ...options,
  });
  await api.login("doctor@example.test", "Demo1234!");
  return { api, scope: api.scope(), map, storage };
}
test("shared auth denies patient scopes and unauthorized appointment IDs", async () => {
  const { api, scope, map } = await setup();
  const rows = await api.list(scope, dayKey(NOW));
  assert.equal(rows.length, 5);
  assert.ok(!JSON.stringify(rows).includes("PRIVATE"));
  for (const id of ["doctor-apt-private", "missing"])
    await assert.rejects(api.detail(scope, id), { code: "NOT_FOUND" });
  assert.ok(!JSON.stringify([...map]).includes("Demo1234!"));
  await api.login("garam@example.test", "Demo1234!");
  await assert.rejects(api.list(api.scope(), dayKey(NOW)), {
    code: "SESSION_EXPIRED",
  });
});
test("no draft is exposed; actual snapshot answers and references are frozen", async () => {
  const { api, scope } = await setup();
  const a = await api.detail(scope, "doctor-apt-3");
  assert.deepEqual(a.submissions, []);
  const d = initial();
  d.reasons = ["Original"];
  const s = freezeSubmission(d, "submission-1", 1, new Date(NOW).toISOString());
  d.reasons[0] = "Changed";
  assert.equal(s.answers[0].value[0], "Original");
  for (const section of s.summary.sections)
    for (const ref of section.refs)
      assert.ok(s.answers.some((a) => a.id === ref));
  assert.equal(s.answers.find((a) => a.field === "history").status, "unasked");
});
test("explicit version review is idempotent; new submissions preserve past review and reject stale review", async () => {
  const { api, scope } = await setup();
  const id = "doctor-apt-1";
  const first = (await api.detail(scope, id)).submissions[0];
  assert.equal(first.reviews.length, 0);
  await Promise.all([
    api.review(scope, id, first.id, first.summary.id),
    api.review(scope, id, first.id, first.summary.id),
  ]);
  assert.equal((await api.detail(scope, id)).submissions[0].reviews.length, 1);
  api.simulateSubmission(scope, id);
  const newer = await api.detail(scope, id);
  assert.equal(newer.submissions[0].reviews[0].doctorId, "doctor-demo");
  assert.equal(newer.submissions[1].reviews.length, 0);
  await assert.rejects(api.review(scope, id, first.id, first.summary.id), {
    code: "NEW_VERSION",
  });
  assert.equal(
    (await api.list(scope, dayKey(NOW))).find((a) => a.id === id).latest
      .reviewed,
    false,
  );
});
test("note/review failures preserve source, retries save once, notes scoped by submission", async () => {
  const { api, scope } = await setup();
  const id = "doctor-apt-1",
    s = (await api.detail(scope, id)).submissions[0];
  api.failNext("note");
  await assert.rejects(api.saveNote(scope, id, s.id, "Keep me"), {
    code: "FAILED",
  });
  assert.equal((await api.detail(scope, id)).submissions[0].note, "");
  await api.saveNote(scope, id, s.id, "Keep me");
  await api.saveNote(scope, id, s.id, "Keep me");
  api.failNext("review");
  await assert.rejects(api.review(scope, id, s.id, s.summary.id), {
    code: "FAILED",
  });
  assert.equal((await api.detail(scope, id)).submissions[0].reviews.length, 0);
  api.simulateSubmission(scope, id);
  const after = await api.detail(scope, id);
  assert.equal(after.submissions[0].note, "Keep me");
  assert.equal(after.submissions[1].note, "");
  assert.deepEqual(after.submissions[0].answers, s.answers);
});
test("late requests after logout and expiry cannot mutate or return prior data", async () => {
  const { api, scope } = await setup();
  const s = (await api.detail(scope, "doctor-apt-1")).submissions[0];
  const pending = api.saveNote(scope, "doctor-apt-1", s.id, "Stale");
  api.logout();
  await assert.rejects(pending, { code: "SESSION_EXPIRED" });
  await api.login("doctor@example.test", "Demo1234!");
  assert.equal(
    (await api.detail(api.scope(), "doctor-apt-1")).submissions[0].note,
    "",
  );
  let clock = NOW;
  const expired = await setup({ now: () => clock });
  clock += 3600001;
  await assert.rejects(expired.api.list(expired.scope, dayKey(NOW)), {
    code: "SESSION_EXPIRED",
  });
});
test("summary failures keep originals available and retry never changes submission", async () => {
  const { api, scope } = await setup();
  const a = await api.detail(scope, "doctor-apt-5"),
    s = a.submissions[0];
  assert.equal(s.summary.state, "failed");
  assert.ok(s.answers.length);
  await assert.rejects(api.review(scope, a.id, s.id, s.summary.id), {
    code: "SUMMARY_UNAVAILABLE",
  });
  await api.retrySummary(scope, a.id, s.id);
  const after = (await api.detail(scope, a.id)).submissions[0];
  assert.equal(after.summary.state, "ready");
  assert.deepEqual(after.answers, s.answers);
});
test("patient bridge excludes drafts and ingests only assigned submitted snapshots once", async () => {
  const patient = createAccountService({ delay: 1, now: () => NOW });
  await patient.restore();
  await patient.login("garam@example.test", "Demo1234!");
  const source = patient.doctorDemoSource();
  assert.ok(source.intakes.every((i) => i.snapshot && i.status === "sent"));
  const { api, scope } = await setup({
    patientSource: () => patient.doctorDemoSource(),
  });
  const draft = await api.detail(scope, "apt-a-next");
  assert.equal(draft.submissions.length, 0);
  const sent = await api.detail(scope, "apt-a-past");
  assert.equal(sent.submissions.length, 1);
  api.sync();
  assert.equal((await api.detail(scope, "apt-a-past")).submissions.length, 1);
});
test("reload restores doctor session and version notes without storing credentials", async () => {
  const { api, scope, storage } = await setup();
  const s = (await api.detail(scope, "doctor-apt-1")).submissions[0];
  await api.saveNote(scope, "doctor-apt-1", s.id, "Restored");
  const authService = createAccountService({
    storage,
    delay: 1,
    now: () => NOW,
  });
  await authService.restore();
  const restored = createDoctorService({
    storage,
    delay: 1,
    now: () => NOW,
    authService,
  });
  assert.equal(restored.auth().status, "authenticated");
  assert.equal(
    (await restored.detail(restored.scope(), "doctor-apt-1")).submissions[0]
      .note,
    "Restored",
  );
});

test("patient handoff becomes visible once without exposing the earlier draft", async () => {
  const patient = createAccountService({ delay: 1, now: () => NOW });
  await patient.restore();
  await patient.login("garam@example.test", "Demo1234!");
  const { api, scope } = await setup({
    patientSource: () => patient.doctorDemoSource(),
  });
  assert.equal((await api.detail(scope, "apt-a-next")).submissions.length, 0);
  const data = initial();
  data.reasons = ["Patient-entered handoff"];
  for (const field of [
    "onset",
    "course",
    "severity",
    "impact",
    "history",
    "medicines",
    "allergies",
    "questions",
  ])
    data[field] = { ...data[field], status: "unknown" };
  data.approved = true;
  data.sent = true;
  patient.saveIntake(patient.scope(), "intake-a-draft", data, "done");
  api.sync();
  api.sync();
  const record = await api.detail(scope, "apt-a-next");
  assert.equal(record.submissions.length, 1);
  assert.deepEqual(record.submissions[0].answers[0].value, [
    "Patient-entered handoff",
  ]);
  assert.equal(record.submissions[0].reviews.length, 0);
});
test("a new submission arriving during review prevents the stale review transaction", async () => {
  const { api, scope } = await setup();
  const id = "doctor-apt-1",
    s = (await api.detail(scope, id)).submissions[0];
  const pending = api.review(scope, id, s.id, s.summary.id);
  api.simulateSubmission(scope, id);
  await assert.rejects(pending, { code: "NEW_VERSION" });
  const a = await api.detail(scope, id);
  assert.ok(a.submissions.every((s) => s.reviews.length === 0));
});

test("aborted doctor login does not create a session after leaving login", async () => {
  const api = createDoctorService({ delay: 2, now: () => NOW });
  const controller = new AbortController();
  const pending = api.login(
    "doctor@example.test",
    "Demo1234!",
    controller.signal,
  );
  controller.abort();
  await assert.rejects(pending, { code: "STALE" });
  assert.notEqual(api.auth().status, "authenticated");
});
