import { medicineDetailsMissing } from "../medicines.js";
import { initial, activeSteps } from "../model.js";
import { accountService, createAccountService } from "../account/service.js";
import { demoUsers, TIME_ZONE } from "../account/domain.js";
import { DOCTOR } from "../account/domain.js";
export { DOCTOR };
const DB_KEY = "visit-notes-doctor-v1";
export const dayKey = (time = Date.now()) =>
  new Intl.DateTimeFormat("en-CA", {
    timeZone: TIME_ZONE,
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
  }).format(new Date(time));
const clone = (value) => structuredClone(value);
const fault = (code) => Object.assign(new Error(code), { code });
const fields = [
  "onset",
  "course",
  "frequency",
  "severity",
  "impact",
  "history",
  "medicines",
  "allergies",
  "questions",
];
export function freezeSubmission(
  data,
  id,
  version,
  time,
  summaryState = "ready",
) {
  const answers = [
    {
      id: `${id}:reasons`,
      field: "reasons",
      status: data.reasons.some((s) => s.trim()) ? "answered" : "unanswered",
      value: clone(data.reasons),
    },
    ...fields
      .filter((f) => activeSteps(data).includes(f))
      .map((field) => ({ id: `${id}:${field}`, field, ...clone(data[field]) })),
  ];
  const groups = [
    ["reasons"],
    ["onset", "course", "frequency", "severity"],
    ["history"],
    ["medicines"],
    ["allergies"],
    ["impact"],
    ["questions"],
    answers
      .filter(
        (a) =>
          ["unknown", "unasked", "unanswered", "declined"].includes(a.status) ||
          ((a.field !== "medicines" || a.status === "answered") &&
            a.items?.some((i) => !i.name.trim() || !i.detail.trim())) ||
          (a.field === "medicines" &&
            a.status === "answered" &&
            medicineDetailsMissing(a)),
      )
      .map((a) => a.field),
  ];
  return {
    id,
    version,
    submittedAt: time,
    data: clone(data),
    answers,
    summary: {
      id: `${id}:summary:1`,
      version: 1,
      state: summaryState,
      generatedAt: summaryState === "ready" ? time : null,
      sections: groups.map((group, index) => ({
        key: [
          "reason",
          "symptoms",
          "history",
          "medicines",
          "allergies",
          "impact",
          "questions",
          "uncertain",
        ][index],
        refs: answers.filter((a) => group.includes(a.field)).map((a) => a.id),
      })),
    },
    note: "",
    noteUpdatedAt: null,
    reviews: [],
  };
}
function seed(now) {
  const date = dayKey(now);
  const makeData = (reason) => {
    const d = initial();
    d.reasons = [reason];
    d.onset = { status: "answered", value: "Three days ago" };
    d.course = { status: "answered", value: "Comes and goes" };
    d.impact = {
      status: "answered",
      value: "Difficult to concentrate at work.",
    };
    d.history = { status: "unknown", value: "" };
    d.medicines = {
      status: "answered",
      value: "",
      items: [{ name: "", detail: "One tablet yesterday; dose unknown" }],
    };
    d.allergies = { status: "none", value: "", items: [] };
    d.questions = { status: "declined", value: "" };
    return d;
  };
  const appointments = [
    "Ari Demo",
    "Bo Demo",
    "Casey Demo",
    "Drew Demo",
    "Ellis Demo",
  ].map((name, index) => {
    const id = `doctor-apt-${index + 1}`;
    const time = new Date(
      `${date}T${String(9 + index).padStart(2, "0")}:00:00+09:00`,
    ).toISOString();
    const submissions =
      index === 2
        ? []
        : [
            freezeSubmission(
              makeData(
                index === 1
                  ? "Knee discomfort after walking"
                  : "Headache affecting my work",
              ),
              `${id}:v1`,
              1,
              new Date(now - 3600000).toISOString(),
              index === 3 ? "generating" : index === 4 ? "failed" : "ready",
            ),
          ];
    if (index === 1)
      submissions[0].reviews.push({
        doctorId: DOCTOR.id,
        submissionId: submissions[0].id,
        submissionVersion: 1,
        summaryId: submissions[0].summary.id,
        summaryVersion: 1,
        reviewedAt: new Date(now - 1800000).toISOString(),
      });
    return {
      id,
      doctorId: DOCTOR.id,
      patient: {
        id: `demo-patient-${index + 1}`,
        name,
        identifier: `DEMO-00${index + 1}`,
      },
      startsAt: time,
      department: "General medicine",
      status: index === 4 ? "cancelled" : "scheduled",
      submissions,
    };
  });
  appointments.push({
    id: "doctor-apt-private",
    doctorId: "another-doctor",
    patient: {
      id: "private",
      name: "Restricted demo patient",
      identifier: "PRIVATE",
    },
    startsAt: new Date(now).toISOString(),
    status: "scheduled",
    department: "General medicine",
    submissions: [],
  });
  return { version: 1, appointments };
}
export function createDoctorService({
  storage,
  delay = 350,
  now = () => Date.now(),
  patientSource,
  authService = createAccountService({ storage, delay, now }),
} = {}) {
  let db,
    revision = 0;
  const listeners = new Set();
  let failure = "",
    slow = false;
  try {
    const saved = JSON.parse(storage?.getItem(DB_KEY));
    if (saved?.version === 1) db = saved;
  } catch {
    /* memory fallback */
  }
  db ||= seed(now());
  const emit = () => {
    revision++;
    listeners.forEach((fn) => fn());
  };
  const persist = () => {
    try {
      storage?.setItem(DB_KEY, JSON.stringify(db));
    } catch {
      /* session memory only */
    }
    emit();
  };
  authService.subscribe(() => {
    failure = "";
    slow = false;
    emit();
  });
  function assert(scope) {
    authService.assertScope(scope, "doctor");
  }
  async function wait(scope, operation) {
    const fail = failure === operation;
    if (fail) failure = "";
    const duration = slow ? 1400 : delay;
    slow = false;
    await new Promise((r) => setTimeout(r, duration));
    if (scope) assert(scope);
    if (fail) throw fault("FAILED");
  }
  function ingest() {
    const source = patientSource?.();
    if (!source) return;
    let changed = false;
    // Explicit demo assignment: only the two established demo patients are assigned.
    for (const apt of source.appointments.filter((a) =>
      ["patient-a", "patient-b"].includes(a.userId),
    )) {
      let target = db.appointments.find((a) => a.id === apt.id);
      if (!target) {
        const patient = demoUsers.find((u) => u.id === apt.userId);
        target = {
          id: apt.id,
          doctorId: DOCTOR.id,
          patient: {
            id: patient.id,
            name: patient.name,
            identifier: patient.id.toUpperCase(),
          },
          startsAt: apt.startsAt,
          department: apt.department,
          status: apt.status,
          submissions: [],
        };
        db.appointments.push(target);
        changed = true;
      }
      const record = source.intakes.find(
        (i) =>
          i.appointmentId === apt.id &&
          i.userId === apt.userId &&
          i.snapshot?.data &&
          i.status === "sent",
      );
      if (
        record &&
        !target.submissions.some(
          (s) => s.id === `${record.id}:${record.snapshot.sentAt}`,
        )
      ) {
        target.submissions.push(
          freezeSubmission(
            record.snapshot.data,
            `${record.id}:${record.snapshot.sentAt}`,
            target.submissions.length + 1,
            record.snapshot.sentAt,
          ),
        );
        changed = true;
      }
    }
    if (changed) persist();
  }
  function appointment(scope, id) {
    assert(scope);
    ingest();
    const a = db.appointments.find(
      (a) => a.id === id && a.doctorId === scope.userId,
    );
    if (!a) throw fault("NOT_FOUND");
    return a;
  }
  function submission(scope, id, sid) {
    const a = appointment(scope, id);
    const s = a.submissions.find((s) => s.id === sid);
    if (!s) throw fault("NOT_FOUND");
    return { a, s };
  }
  const api = {
    subscribe(fn) {
      listeners.add(fn);
      return () => listeners.delete(fn);
    },
    getSnapshot: () => revision,
    auth: () => clone(authService.getSnapshot()),
    scope: () => authService.scope(),
    login: (...args) => authService.login(...args),
    logout: () => authService.logout(),
    expire: () => authService.expire(),
    async list(scope, date) {
      await wait(scope, "load");
      ingest();
      return clone(
        db.appointments
          .filter(
            (a) => a.doctorId === scope.userId && dayKey(a.startsAt) === date,
          )
          .sort((a, b) => a.startsAt.localeCompare(b.startsAt))
          .map(({ submissions, ...a }) => ({
            ...a,
            latest: submissions.length
              ? {
                  id: submissions.at(-1).id,
                  version: submissions.at(-1).version,
                  submittedAt: submissions.at(-1).submittedAt,
                  reason: submissions.at(-1).data.reasons.join("; "),
                  reviewed: submissions.at(-1).reviews.length > 0,
                }
              : null,
          })),
      );
    },
    async detail(scope, id) {
      await wait(scope, "load");
      return clone(appointment(scope, id));
    },
    async saveNote(scope, id, sid, text) {
      await wait(scope, "note");
      const { s } = submission(scope, id, sid);
      s.note = text;
      s.noteUpdatedAt = new Date(now()).toISOString();
      persist();
      return clone(s);
    },
    async review(scope, id, sid, summaryId) {
      await wait(scope, "review");
      const { a, s } = submission(scope, id, sid);
      if (a.submissions.at(-1).id !== sid) throw fault("NEW_VERSION");
      if (s.summary.id !== summaryId || s.summary.state !== "ready")
        throw fault("SUMMARY_UNAVAILABLE");
      if (!s.reviews.some((r) => r.doctorId === scope.userId))
        s.reviews.push({
          doctorId: scope.userId,
          submissionId: s.id,
          submissionVersion: s.version,
          summaryId,
          summaryVersion: s.summary.version,
          reviewedAt: new Date(now()).toISOString(),
        });
      persist();
      return clone(s);
    },
    async retrySummary(scope, id, sid) {
      await wait(scope, "summary");
      const { s } = submission(scope, id, sid);
      if (s.summary.state === "ready") return;
      s.summary.state = "ready";
      s.summary.generatedAt = new Date(now()).toISOString();
      persist();
    },
    simulateSubmission(scope, id) {
      const a = appointment(scope, id);
      if (!a.submissions.length) throw fault("NOT_FOUND");
      const prior = a.submissions.at(-1),
        data = clone(prior.data);
      data.questions = {
        status: "answered",
        value: "What should I prepare for the visit? (new demo submission)",
      };
      const v = prior.version + 1;
      a.submissions.push(
        freezeSubmission(data, `${id}:v${v}`, v, new Date(now()).toISOString()),
      );
      persist();
    },
    failNext(operation) {
      failure = operation;
    },
    slowNext() {
      slow = true;
    },
    sync() {
      ingest();
    },
  };
  return api;
}
let storage;
try {
  storage = globalThis.sessionStorage;
} catch {
  /* no storage */
}
export const doctorService = createDoctorService({
  storage,
  patientSource: () => accountService.doctorDemoSource(),
  authService: accountService,
});
