import { test } from "node:test";
import assert from "node:assert/strict";
import { createAccountService } from "../src/account/service.js";
import { createDoctorService } from "../src/doctor/service.js";
import {
  ACCOUNT_KEY,
  SESSION_KEY,
  LEGACY_SESSION_KEYS,
  safeReturn,
} from "../src/account/domain.js";
function setup() {
  const map = new Map();
  const storage = {
    getItem: (k) => map.get(k),
    setItem: (k, v) => map.set(k, v),
    removeItem: (k) => map.delete(k),
  };
  const auth = createAccountService({ storage, delay: 1 });
  const doctor = createDoctorService({ storage, delay: 15, authService: auth });
  return { map, storage, auth, doctor };
}
test("one identity, role restrictions, late reads and writes cannot cross account switches", async () => {
  const { auth, doctor } = setup();
  await auth.login("garam@example.test", "Demo1234!");
  const patientScope = auth.scope();
  const pendingPatient = auth.load(patientScope);
  await auth.login("doctor@example.test", "Demo1234!");
  await pendingPatient; // request finished before the identity changed
  await assert.rejects(auth.load(patientScope), { code: "SESSION_EXPIRED" });
  await assert.rejects(auth.load(auth.scope()), { code: "SESSION_EXPIRED" });
  const scope = doctor.scope();
  const detail = await doctor.detail(scope, "doctor-apt-1");
  const sid = detail.submissions[0].id;
  const pending = doctor.saveNote(scope, "doctor-apt-1", sid, "Must not save");
  const rejected = assert.rejects(pending, { code: "SESSION_EXPIRED" });
  await auth.login("narae@example.test", "Demo1234!");
  await rejected;
  await assert.rejects(doctor.detail(auth.scope(), "doctor-apt-1"), {
    code: "SESSION_EXPIRED",
  });
  await auth.login("doctor@example.test", "Demo1234!");
  assert.equal(
    (await doctor.detail(doctor.scope(), "doctor-apt-1")).submissions[0].note,
    "",
  );
});
test("legacy sessions invalidated together, patient records and saved doctor notes preserved", async () => {
  const { map, storage, auth, doctor } = setup();
  await auth.login("doctor@example.test", "Demo1234!");
  const d = await doctor.detail(doctor.scope(), "doctor-apt-1");
  await doctor.saveNote(
    doctor.scope(),
    d.id,
    d.submissions[0].id,
    "Preserve me",
  );
  const records = map.get(ACCOUNT_KEY),
    notes = map.get("visit-notes-doctor-v1");
  map.delete(SESSION_KEY);
  for (const k of LEGACY_SESSION_KEYS)
    map.set(
      k,
      JSON.stringify({ userId: "doctor-demo", expiresAt: Date.now() + 60000 }),
    );
  const restored = createAccountService({ storage, delay: 1 });
  await restored.restore();
  assert.equal(restored.getSnapshot().status, "anonymous");
  for (const k of LEGACY_SESSION_KEYS) assert.equal(map.has(k), false);
  assert.equal(map.get(ACCOUNT_KEY), records);
  assert.equal(map.get("visit-notes-doctor-v1"), notes);
  assert.ok(!JSON.stringify([...map]).includes("Demo1234!"));
});
test("signup ignores injected role and return paths are role allowlisted", async () => {
  const { auth } = setup();
  await auth.signup({
    name: "Patient",
    email: "new@example.test",
    password: "Demo1234!",
    role: "doctor",
  });
  assert.equal(
    (await auth.login("new@example.test", "Demo1234!")).role,
    "patient",
  );
  for (const path of [
    "//evil.test",
    "https://evil.test",
    "/doctor/../my",
    "/doctor/login",
    "/my",
    "/doctor/appointments/a?x=1",
  ])
    assert.equal(safeReturn(path, "doctor"), "/doctor");
  assert.equal(
    safeReturn("/doctor/appointments/doctor-apt-1", "doctor"),
    "/doctor/appointments/doctor-apt-1",
  );
  assert.equal(safeReturn("/doctor", "patient"), "/my");
});
