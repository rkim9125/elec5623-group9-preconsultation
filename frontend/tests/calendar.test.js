import { test } from "node:test";
import assert from "node:assert/strict";
import {
  monthDays,
  shiftMonth,
  groupEvents,
  appointmentState,
} from "../src/doctor/calendar.js";
import { createDoctorService } from "../src/doctor/service.js";
test("Monday-first complete weeks across leap years and year boundaries", () => {
  assert.equal(shiftMonth("2026-12", 1), "2027-01");
  assert.equal(shiftMonth("2026-01", -1), "2025-12");
  assert.ok(monthDays("2024-02").includes("2024-02-29"));
  assert.ok(!monthDays("2025-02").includes("2025-02-29"));
  assert.equal(monthDays("2026-03").length, 42);
  assert.equal(monthDays("2026-03")[0], "2026-02-23");
  assert.equal(monthDays("2026-03").at(-1), "2026-04-05");
});
test("Seoul midnight/year/month boundaries and chronological order", () => {
  const rows = [
    { id: "b", startsAt: "2026-12-31T16:00:00Z" },
    { id: "a", startsAt: "2026-12-31T15:00:00Z" },
    { id: "c", startsAt: "2026-12-31T14:59:00Z" },
  ];
  assert.deepEqual(
    groupEvents(rows)["2027-01-01"].map((a) => a.id),
    ["a", "b"],
  );
  assert.equal(groupEvents(rows)["2026-12-31"][0].id, "c");
  assert.equal(
    groupEvents([{ startsAt: "2024-02-28T15:00:00Z" }])["2024-02-29"].length,
    1,
  );
});
test("elapsed appointments never imply visit completion or review", () => {
  const a = { status: "scheduled", startsAt: "2020-01-01T00:00:00Z" };
  assert.equal(appointmentState(a), "past");
  assert.equal(appointmentState({ ...a, status: "completed" }), "completed");
  assert.equal(appointmentState({ ...a, status: "cancelled" }), "cancelled");
});
test("range projection, auth, failures and expired in-flight requests", async () => {
  const api = createDoctorService({
    delay: 1,
    now: () => Date.parse("2026-09-22T00:00:00Z"),
  });
  await api.login("doctor@example.test", "Demo1234!");
  const scope = api.scope();
  const rows = await api.listRange(scope, "2026-08-31", "2026-10-04");
  assert.equal(rows.length, 5);
  assert.ok(!JSON.stringify(rows).includes("PRIVATE"));
  assert.ok(rows.every((r) => !("submissions" in r)));
  assert.equal(rows.find((r) => r.id === "doctor-apt-3").latest, null);
  assert.deepEqual(await api.listRange(scope, "2027-01-01", "2027-01-31"), []);
  api.failNext("calendar");
  await assert.rejects(api.listRange(scope, "2026-09-01", "2026-09-30"), {
    code: "FAILED",
  });
  assert.equal(
    (await api.listRange(scope, "2026-09-01", "2026-09-30")).length,
    5,
  );
  const request = api.listRange(scope, "2026-09-01", "2026-09-30");
  api.expire();
  await assert.rejects(request, { code: "SESSION_EXPIRED" });
});
test("shared patient source updates metadata and removes deleted appointments", async () => {
  const source = {
    appointments: [
      {
        id: "shared",
        userId: "patient-a",
        startsAt: "2026-09-22T15:00:00Z",
        status: "scheduled",
        hospital: "Original",
        department: "General",
      },
    ],
    intakes: [],
  };
  const api = createDoctorService({ delay: 1, patientSource: () => source });
  await api.login("doctor@example.test", "Demo1234!");
  const scope = api.scope();
  assert.equal((await api.detail(scope, "shared")).hospital, "Original");
  source.appointments[0].status = "completed";
  source.appointments[0].hospital = "Updated";
  api.sync();
  const row = (await api.listRange(scope, "2026-09-23", "2026-09-23")).find(
    (a) => a.id === "shared",
  );
  assert.equal(row.hospital, "Updated");
  assert.equal(row.status, "completed");
  source.appointments = [];
  api.sync();
  await assert.rejects(api.detail(scope, "shared"), { code: "NOT_FOUND" });
});
