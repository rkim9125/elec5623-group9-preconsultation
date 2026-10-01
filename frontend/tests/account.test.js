import { test } from "node:test";
import assert from "node:assert/strict";
import { createAccountService } from "../src/account/service.js";
import {
  ACCOUNT_KEY,
  SESSION_KEY,
  DEMO_PASSWORD,
  safeReturn,
  appointmentGroup,
  sortAppointments,
} from "../src/account/domain.js";
import { initial, change } from "../src/model.js";
function setup() {
  const map = new Map();
  const storage = {
    getItem: (k) => map.get(k) || null,
    setItem: (k, v) => map.set(k, v),
    removeItem: (k) => map.delete(k),
  };
  let clock = Date.parse("2026-09-17T03:00:00Z");
  const api = createAccountService({ storage, delay: 3, now: () => clock });
  return { api, map, storage, advance: () => (clock += 3600001) };
}
async function login(api, email = "garam@example.test") {
  await api.restore();
  await api.login(email, DEMO_PASSWORD);
  return api.scope();
}
test("signup login empty home logout, no password persisted", async () => {
  const { api, map } = setup();
  await api.restore();
  await api.signup({
    name: "가상 새환자",
    email: "new@example.test",
    password: "Fiction1234",
  });
  await api.login("new@example.test", "Fiction1234");
  const scope = api.scope();
  assert.deepEqual(await api.load(scope), { appointments: [], intakes: [] });
  assert.ok(!JSON.stringify([...map]).includes("Fiction1234"));
  api.logout();
  assert.equal(api.getSnapshot().user, null);
  assert.ok(!map.has(SESSION_KEY));
});
test("late account A result rejected after logout and B login", async () => {
  const { api } = setup();
  const scope = await login(api);
  const pending = api.load(scope);
  const rejected = assert.rejects(pending, { code: "SESSION_EXPIRED" });
  api.logout();
  await api.login("narae@example.test", DEMO_PASSWORD);
  await rejected;
  const b = await api.load(api.scope());
  assert.ok(b.intakes.every((i) => i.userId === "patient-b"));
  assert.ok(b.appointments.every((a) => a.userId === "patient-b"));
});
test("ownership checks, missing ids and cancelled reservation", async () => {
  const { api } = setup();
  const scope = await login(api);
  assert.throws(() => api.startIntake(scope, "apt-b-next"), {
    code: "NOT_FOUND",
  });
  assert.throws(() => api.startIntake(scope, "missing"), { code: "NOT_FOUND" });
  assert.throws(() => api.startIntake(scope, "apt-a-cancelled"), {
    code: "CANCELLED",
  });
  assert.throws(
    () => api.saveIntake(scope, "intake-b-draft", initial(), "reason"),
    { code: "NOT_FOUND" },
  );
});
test("opening a reservation repeatedly reuses one intake", async () => {
  const { api } = setup();
  const scope = await login(api);
  const first = api.startIntake(scope, "apt-a-new");
  const second = api.startIntake(scope, "apt-a-new");
  assert.equal(first.id, second.id);
  assert.equal(
    (await api.load(scope)).intakes.filter(
      (i) => i.appointmentId === "apt-a-new",
    ).length,
    1,
  );
});
test("draft state and completion shared; edits revoke approval; snapshot is immutable", async () => {
  const { api } = setup();
  const scope = await login(api);
  const { intakes } = await api.load(scope);
  const ready = intakes.find((i) => i.id === "intake-a-ready");
  const updated = change(ready.data, "history", {
    status: "answered",
    value: "가상 수정",
  });
  api.saveIntake(scope, ready.id, updated, "review");
  let r = (await api.load(scope)).intakes.find((i) => i.id === ready.id);
  assert.equal(r.data.approved, false);
  assert.equal(r.status, "completed");
  api.saveIntake(
    scope,
    ready.id,
    { ...updated, approved: true, sent: true },
    "done",
  );
  r = (await api.load(scope)).intakes.find((i) => i.id === ready.id);
  const saved = structuredClone(r.snapshot);
  api.saveIntake(scope, ready.id, initial(), "reason");
  const after = (await api.load(scope)).intakes.find((i) => i.id === ready.id);
  assert.deepEqual(after.snapshot, saved);
  assert.equal(after.status, "sent");
});
test("expired session, failure once and retry", async () => {
  const { api, advance } = setup();
  const scope = await login(api);
  api.failOnce();
  await assert.rejects(api.load(scope), { code: "LOAD_FAILED" });
  assert.ok((await api.load(scope)).intakes.length);
  advance();
  await assert.rejects(api.load(scope), { code: "SESSION_EXPIRED" });
  assert.equal(api.getSnapshot().status, "anonymous");
});
test("safe return only accepts allowlisted internal paths", () => {
  for (const p of [
    "https://evil.test",
    "//evil.test",
    "/\\evil",
    "/my?next=https://evil.test",
    "/intakes/x/../account",
    "/login",
    "/%2f%2fevil",
  ])
    assert.equal(safeReturn(p), "/my");
  for (const p of [
    "/appointments/apt-a-next",
    "/intakes/intake-a-ready/edit/review",
    "/intakes",
    "/account",
  ])
    assert.equal(safeReturn(p), p);
});
test("classification never infers completed status and sorts by actual time", () => {
  const now = 100000;
  const a = {
    status: "scheduled",
    startsAt: new Date(now - 1000).toISOString(),
  };
  assert.equal(appointmentGroup(a, now), "past");
  assert.equal(a.status, "scheduled");
  assert.equal(
    appointmentGroup({ ...a, status: "cancelled" }, now),
    "cancelled",
  );
  const rows = [
    { ...a, id: "late", startsAt: new Date(now + 500).toISOString() },
    { ...a, id: "soon", startsAt: new Date(now + 100).toISOString() },
  ];
  assert.equal(sortAppointments(rows, "upcoming", now)[0].id, "soon");
});
test("guest import only explicit, isolated, and deduplicated", async () => {
  const { api } = setup();
  const scope = await login(api);
  const before = (await api.load(scope)).intakes.length;
  const guest = initial();
  guest.reasons = ["가상 방문"];
  assert.equal((await api.load(scope)).intakes.length, before);
  const a = api.importGuest(scope, guest, "onset");
  const b = api.importGuest(scope, guest, "onset");
  assert.equal(a.id, b.id);
  assert.equal(a.appointmentId, null);
  api.logout();
  await api.login("narae@example.test", DEMO_PASSWORD);
  assert.ok(!(await api.load(api.scope())).intakes.some((i) => i.id === a.id));
});
test("demo reload restores session and draft; signup credentials expire on reload", async () => {
  const { api, storage, map } = setup();
  const scope = await login(api);
  const r = api.startIntake(scope);
  const d = initial();
  d.reasons = ["저장한 데모"];
  api.saveIntake(scope, r.id, d, "onset");
  const fresh = createAccountService({
    storage,
    delay: 1,
    now: () => Date.parse("2026-09-17T03:01:00Z"),
  });
  await fresh.restore();
  assert.equal(fresh.getSnapshot().user.id, "patient-a");
  assert.equal(
    (await fresh.load(fresh.scope())).intakes.find((i) => i.id === r.id).step,
    "onset",
  );
  assert.ok(!JSON.stringify([...map]).includes(DEMO_PASSWORD));
  assert.ok(map.has(ACCOUNT_KEY));
});
test("aborted login does not authenticate", async () => {
  const { api } = setup();
  await api.restore();
  const controller = new AbortController();
  const pending = api.login(
    "garam@example.test",
    DEMO_PASSWORD,
    controller.signal,
  );
  controller.abort();
  await assert.rejects(pending, { code: "STALE" });
  assert.equal(api.getSnapshot().user, null);
});

test("unasked active questions remain draft and cannot bypass review", async () => {
  const { intakeStatus } = await import("../src/account/domain.js");
  const { api } = setup();
  const scope = await login(api);
  const record = api.startIntake(scope);
  const data = initial();
  data.reasons = ["미완성 가상 기록"];
  assert.equal(intakeStatus(data, "review"), "draft");
  assert.throws(
    () =>
      api.saveIntake(
        scope,
        record.id,
        { ...data, sent: true, approved: false },
        "done",
      ),
    { code: "REVIEW_REQUIRED" },
  );
  assert.equal(
    (await api.load(scope)).intakes.find((i) => i.id === record.id).snapshot,
    undefined,
  );
});
