export const KEY = "maeum-intake-demo-v1";
export const statuses = {
  unasked: "아직 질문하지 않음",
  unanswered: "미응답",
  none: "없음",
  unknown: "모름",
  declined: "답변 원하지 않음",
};
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
export function describe(a) {
  if (a.status !== "answered") return statuses[a.status] || statuses.unanswered;
  if (a.items)
    return a.items.length
      ? a.items
          .map(
            (i) =>
              `${i.name.trim() || "이름 모름"} · ${i.detail.trim() || "세부 정보 모름"}`,
          )
          .join("\n")
      : "미응답";
  return a.value.trim() || "미응답";
}
export function summary(d) {
  const symptom = [
    "onset",
    "course",
    ...(d.course.value === "반복돼요" ? ["frequency"] : []),
    "severity",
    "impact",
  ];
  const labels = {
    onset: "시작 시점",
    course: "경과",
    frequency: "빈도",
    severity: "불편 정도",
    impact: "일상 영향",
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
        `${labels[k] || { history: "관련 병력", medicines: "복용약", allergies: "알레르기", questions: "걱정·질문" }[k]}: ${describe(d[k])}`,
    );
  for (const k of ["medicines", "allergies"])
    if (d[k].status === "answered")
      d[k].items.forEach((i) => {
        if (!i.name.trim() || !i.detail.trim())
          uncertain.push(
            `${k === "medicines" ? "복용약" : "알레르기"}: ${i.name.trim() || "이름 모름"} · ${i.detail.trim() || "세부 정보 모름"}`,
          );
      });
  return [
    {
      title: "방문 목적",
      step: "reason",
      text:
        d.reasons
          .filter((x) => x.trim())
          .map((x, i) => `${i + 1}. ${x}`)
          .join("\n") || "미응답",
    },
    {
      title: "증상 경과",
      step: "onset",
      text: symptom.map((k) => `${labels[k]}: ${describe(d[k])}`).join("\n"),
    },
    { title: "관련 병력", step: "history", text: describe(d.history) },
    { title: "복용약", step: "medicines", text: describe(d.medicines) },
    { title: "알레르기", step: "allergies", text: describe(d.allergies) },
    { title: "걱정·질문", step: "questions", text: describe(d.questions) },
    {
      title: "미확인 내용",
      text: uncertain.join("\n") || "추가로 표시할 미확인 내용이 없습니다.",
    },
  ];
}
export function example() {
  const d = initial();
  d.reasons = [
    "며칠 전부터 머리가 아파요. 오후에 특히 불편해서 상담받고 싶어요.",
  ];
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
