import { getLocale } from "../i18n/core.js";
import { initial, summary, activeSteps } from "../model.js";
export const ACCOUNT_KEY = "jinryo-account-demo-v1";
export const SESSION_KEY = "jinryo-session-demo-v1";
export const TIME_ZONE = "Asia/Seoul";
export const DEMO_PASSWORD = "Demo1234!";
export const demoUsers = [
  { id: "patient-a", name: "데모 가람", email: "garam@example.test" },
  { id: "patient-b", name: "데모 나래", email: "narae@example.test" },
  { id: "patient-empty", name: "데모 새봄", email: "empty@example.test" },
];
export const intakeLabels = {
  draft: "in.progress",
  completed: "completed",
  sent: "status.sentDemo",
};
export const appointmentLabels = {
  scheduled: "confirmed",
  completed: "status.visitCompleted",
  cancelled: "status.cancelled",
};
export function safeReturn(value) {
  return typeof value === "string" &&
    /^\/(?:my|account|appointments(?:\/[a-zA-Z0-9_-]+)?|intakes(?:\/[a-zA-Z0-9_-]+(?:\/edit\/[a-z]+)?)?)$/.test(
      value,
    )
    ? value
    : "/my";
}
export function appointmentGroup(a, now = Date.now()) {
  if (a.status === "cancelled") return "cancelled";
  return a.status === "scheduled" && Date.parse(a.startsAt) >= now
    ? "upcoming"
    : "past";
}
export function sortAppointments(items, category, now = Date.now()) {
  return items
    .filter((a) => appointmentGroup(a, now) === category)
    .sort((a, b) =>
      category === "upcoming"
        ? Date.parse(a.startsAt) - Date.parse(b.startsAt)
        : Date.parse(b.startsAt) - Date.parse(a.startsAt),
    );
}
export function formatDate(value) {
  return new Intl.DateTimeFormat(getLocale() === "ko" ? "ko-KR" : "en-GB", {
    timeZone: TIME_ZONE,
    year: "numeric",
    month: "long",
    day: "numeric",
    weekday: "short",
    hour: "2-digit",
    minute: "2-digit",
    hour12: false,
  }).format(new Date(value));
}
export function intakeStatus(data, step) {
  if (data.sent) return "sent";
  const complete =
    data.reasons.every((value) => value.trim()) &&
    activeSteps(data).every(
      (key) => !data[key]?.status || data[key].status !== "unasked",
    );
  return complete && ["review", "done"].includes(step) ? "completed" : "draft";
}
export function seedDatabase(now = Date.now()) {
  const at = (days, hours = 1) =>
    new Date(now + days * 86400000 + hours * 3600000).toISOString();
  const appointments = [
    {
      id: "apt-a-next",
      userId: "patient-a",
      hospital: "가상 온유의원",
      department: "가정의학과",
      clinician: "데모 의료진 가",
      startsAt: at(2),
      status: "scheduled",
    },
    {
      id: "apt-a-new",
      userId: "patient-a",
      hospital: "가상 온유의원",
      department: "내과",
      clinician: null,
      startsAt: at(8),
      status: "scheduled",
    },
    {
      id: "apt-a-past",
      userId: "patient-a",
      hospital: "가상 온유의원",
      department: "가정의학과",
      clinician: "데모 의료진 가",
      startsAt: at(-14),
      status: "scheduled",
    },
    {
      id: "apt-a-cancelled",
      userId: "patient-a",
      hospital: "가상 온유의원",
      department: "내과",
      clinician: null,
      startsAt: at(4),
      status: "cancelled",
    },
    {
      id: "apt-b-next",
      userId: "patient-b",
      hospital: "가상 다온의원",
      department: "이비인후과",
      clinician: "데모 의료진 나",
      startsAt: at(3),
      status: "scheduled",
    },
    {
      id: "apt-b-past",
      userId: "patient-b",
      hospital: "가상 다온의원",
      department: "이비인후과",
      clinician: null,
      startsAt: at(-7),
      status: "completed",
    },
  ];
  const filled = (reason) => {
    const d = initial();
    d.reasons = [reason];
    for (const key of [
      "onset",
      "course",
      "severity",
      "impact",
      "history",
      "medicines",
      "allergies",
      "questions",
    ])
      d[key] = { ...d[key], status: "unknown", value: "" };
    return d;
  };
  const a = initial();
  a.reasons = ["오후에 머리가 불편해요."];
  a.onset = { status: "answered", value: "며칠 전부터" };
  const completed = filled("잠을 잘 못 자서 상담하고 싶어요.");
  completed.approved = true;
  const sent = filled("지난번 목의 불편함에 대해 정리했어요.");
  sent.approved = true;
  sent.sent = true;
  const b = initial();
  b.reasons = ["코가 답답해서 상담하고 싶어요."];
  const intakes = [
    {
      id: "intake-a-draft",
      userId: "patient-a",
      appointmentId: "apt-a-next",
      data: a,
      step: "course",
      status: "draft",
      updatedAt: at(-1),
    },
    {
      id: "intake-a-ready",
      userId: "patient-a",
      appointmentId: null,
      data: completed,
      step: "review",
      status: "completed",
      updatedAt: at(-3),
    },
    {
      id: "intake-a-sent",
      userId: "patient-a",
      appointmentId: "apt-a-past",
      data: sent,
      step: "done",
      status: "sent",
      updatedAt: at(-15),
      snapshot: {
        sections: summary(sent),
        data: structuredClone(sent),
        sentAt: at(-15),
      },
    },
    {
      id: "intake-b-draft",
      userId: "patient-b",
      appointmentId: "apt-b-next",
      data: b,
      step: "onset",
      status: "draft",
      updatedAt: at(-2),
    },
  ];
  return { version: 1, appointments, intakes };
}

// Language is a presentation choice; never rewrite a handed-off record.
export function recordSummary(record, locale) {
  if (!record.snapshot) return summary(record.data, locale);
  if (record.snapshot.data) return summary(record.snapshot.data, locale);
  // Older snapshots stored text only. Re-render only when the retained answers
  // demonstrably reproduce that exact snapshot; otherwise preserve its text.
  if (
    JSON.stringify(summary(record.data, "ko")) ===
    JSON.stringify(record.snapshot.sections)
  )
    return summary(record.data, locale);
  const original = summary(initial(), "ko");
  const localized = summary(initial(), locale);
  return record.snapshot.sections.map((section) => ({
    ...section,
    title:
      localized[original.findIndex((s) => s.title === section.title)]?.title ||
      section.title,
  }));
}
