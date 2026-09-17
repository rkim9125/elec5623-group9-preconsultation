import { translate } from "./i18n/core.js";
import { optionLabel } from "./copy.js";
const statusKeys = {
  unasked: "not.asked.yet",
  unanswered: "unanswered",
  none: "none",
  unknown: "not.sure",
  declined: "prefer.not.to.answer",
};
export const KEY = "maeum-intake-demo-v1";
export const statuses = Object.fromEntries(
  Object.entries(statusKeys).map(([status, key]) => [
    status,
    translate("ko", key),
  ]),
);
export const blank = () => ({ status: "unasked", value: "" });
export const initial = () => ({
  version: 1,
  revision: 0,
  approved: false,
  sent: false,
  reasons: [""],
  onset: blank(),
  course: blank(),
  frequency: blank(),
  impact: blank(),
  severity: blank(),
  history: blank(),
  medicines: { ...blank(), items: [] },
  allergies: { ...blank(), items: [] },
  questions: blank(),
  completed: [],
});
export const steps = [
  "start",
  "reason",
  "onset",
  "course",
  "frequency",
  "severity",
  "impact",
  "history",
  "medicines",
  "allergies",
  "questions",
  "review",
  "done",
];
export const activeSteps = (d) =>
  steps.filter((s) => s !== "frequency" || d.course.value === "반복돼요");
export function change(d, key, value) {
  const next = {
    ...d,
    [key]: value,
    revision: d.revision + 1,
    approved: false,
    sent: false,
  };
  if (key === "course" && value.value !== d.course.value)
    next.frequency = blank();
  if (key === "reasons" && value[0] !== d.reasons[0]) {
    for (const field of ["onset", "course", "frequency", "severity", "impact"])
      next[field] = blank();
    next.completed = next.completed.filter((x) => x !== 1);
  }
  return next;
}
export function describe(a, locale = "ko") {
  const tr = (key) => translate(locale, key);
  if (a.status !== "answered")
    return tr(statusKeys[a.status] || statusKeys.unanswered);
  if (a.items)
    return a.items.length
      ? a.items
          .map(
            (i) =>
              `${i.name.trim() || tr("name.unknown")} · ${i.detail.trim() || tr("details.unknown")}`,
          )
          .join("\n")
      : tr("unanswered");
  return (
    (a.option && a.option === a.value
      ? optionLabel(a.option, locale)
      : a.value.trim()) || tr("unanswered")
  );
}
export function summary(d, locale = "ko") {
  const tr = (key) => translate(locale, key);
  const symptom = [
    "onset",
    "course",
    ...(d.course.value === "반복돼요" ? ["frequency"] : []),
    "severity",
    "impact",
  ];
  const labels = {
    onset: tr("started"),
    course: tr("changes"),
    frequency: tr("frequency"),
    severity: tr("discomfort"),
    impact: tr("daily.impact"),
  };
  const uncertain = [
    ...symptom,
    "history",
    "medicines",
    "allergies",
    "questions",
  ]
    .filter((k) =>
      ["unasked", "unanswered", "unknown", "declined"].includes(d[k].status),
    )
    .map(
      (k) =>
        `${labels[k] || { history: tr("medical.history"), medicines: tr("medicines"), allergies: tr("allergies"), questions: tr("concerns.and.questions.2") }[k]}: ${describe(d[k], locale)}`,
    );
  for (const k of ["medicines", "allergies"])
    if (d[k].status === "answered")
      d[k].items.forEach((i) => {
        if (!i.name.trim() || !i.detail.trim())
          uncertain.push(
            `${k === "medicines" ? tr("medicines") : tr("allergies")}: ${i.name.trim() || tr("name.unknown")} · ${i.detail.trim() || tr("details.unknown")}`,
          );
      });
  return [
    {
      title: tr("reason.for.visit.2"),
      step: "reason",
      text:
        d.reasons
          .filter((x) => x.trim())
          .map((x, i) => `${i + 1}. ${x}`)
          .join("\n") || tr("unanswered"),
    },
    {
      title: tr("symptom.history"),
      step: "onset",
      text: symptom
        .map((k) => `${labels[k]}: ${describe(d[k], locale)}`)
        .join("\n"),
    },
    {
      title: tr("medical.history"),
      step: "history",
      text: describe(d.history, locale),
    },
    {
      title: tr("medicines"),
      step: "medicines",
      text: describe(d.medicines, locale),
    },
    {
      title: tr("allergies"),
      step: "allergies",
      text: describe(d.allergies, locale),
    },
    {
      title: tr("concerns.and.questions.2"),
      step: "questions",
      text: describe(d.questions, locale),
    },
    {
      title: tr("unconfirmed.information"),
      text: uncertain.join("\n") || tr("no.additional.unconfirmed.information"),
    },
  ];
}
export function example(locale = "ko") {
  const d = initial();
  d.reasons = [translate(locale, "example.reason")];
  return d;
}

export function completedStages(data) {
  const result = [];
  if (data.reasons.length && data.reasons.every((value) => value.trim()))
    result.push(0);
  const symptoms = [
    "onset",
    "course",
    ...(data.course.value === "반복돼요" ? ["frequency"] : []),
    "severity",
    "impact",
  ];
  if (symptoms.every((key) => data[key].status !== "unasked")) result.push(1);
  if (
    ["history", "medicines", "allergies", "questions"].every(
      (key) => data[key].status !== "unasked",
    )
  )
    result.push(2);
  if (data.sent) result.push(3);
  return result;
}
