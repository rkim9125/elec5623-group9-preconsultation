import { translate } from "./i18n/core.js";

// Demo examples only, not a complete or clinically validated classification.
export const historyOptions = [
  { id: "diabetes", labelKey: "history.tag.diabetes" },
  { id: "hypertension", labelKey: "history.tag.hypertension" },
  { id: "asthma", labelKey: "history.tag.asthma" },
  { id: "heart-disease", labelKey: "history.tag.heart" },
  { id: "kidney-disease", labelKey: "history.tag.kidney" },
  { id: "liver-disease", labelKey: "history.tag.liver" },
  { id: "surgery", labelKey: "history.tag.surgery" },
];
export const historyTags = (answer) => [
  ...new Set(Array.isArray(answer.tags) ? answer.tags : []),
];
export const hasHistory = (answer) =>
  historyTags(answer).length > 0 || !!answer.value?.trim();
export function editHistory(answer, patch) {
  const next = { ...answer, tags: historyTags(answer), ...patch };
  return {
    ...next,
    tags: historyTags(next),
    status: hasHistory(next) ? "answered" : "unanswered",
  };
}
export function historyText(answer, locale) {
  return [
    ...historyTags(answer).map((id) => {
      const option = historyOptions.find((option) => option.id === id);
      return option ? translate(locale, option.labelKey) : id;
    }),
    answer.value || "",
  ]
    .filter(Boolean)
    .join("\n");
}
