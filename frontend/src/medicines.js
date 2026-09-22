import { translate } from "./i18n/core.js";
import { historyTags } from "./history.js";

// Demo categories, never a mapping to exact drugs, ingredients or doses.
export const medicineOptions = [
  { id: "diabetes-medication", labelKey: "medicine.tag.diabetes" },
  { id: "blood-pressure-medication", labelKey: "medicine.tag.pressure" },
  { id: "cold-medication", labelKey: "medicine.tag.cold" },
  { id: "pain-relief", labelKey: "medicine.tag.pain" },
  { id: "stomach-medication", labelKey: "medicine.tag.stomach" },
  { id: "allergy-medication", labelKey: "medicine.tag.allergy" },
  { id: "sleep-medication", labelKey: "medicine.tag.sleep" },
  { id: "other", labelKey: "medicine.tag.other" },
];
export const medicineTags = historyTags;
export const hasMedicines = (a) =>
  medicineTags(a).length > 0 || (a.items || []).length > 0;
export const medicineDetailsMissing = (a) =>
  medicineTags(a).length > 0 &&
  !(a.items || []).some((i) => i.name.trim() || i.detail.trim());
export function editMedicines(answer, patch) {
  const next = { ...answer, items: answer.items || [], ...patch };
  return {
    ...next,
    tags: medicineTags(next),
    status: hasMedicines(next) ? "answered" : "unanswered",
  };
}
export function medicineText(answer, locale) {
  const tr = (key) => translate(locale, key);
  const tags = medicineTags(answer);
  const sections = [];
  if (tags.length)
    sections.push(
      `${tr("medicine.selectedTypes")}:\n${tags
        .map((id) => {
          const option = medicineOptions.find((o) => o.id === id);
          return option ? tr(option.labelKey) : id;
        })
        .join("\n")}`,
    );
  if (answer.items?.length)
    sections.push(
      `${tr("medicine.enteredDetails")}:\n${answer.items.map((i) => `${i.name.trim() || tr("name.unknown")} · ${i.detail.trim() || tr("details.unknown")}`).join("\n")}`,
    );
  if (medicineDetailsMissing(answer)) sections.push(tr("medicine.unconfirmed"));
  if (tags.length && answer.items?.length)
    sections.push(tr("medicine.noMapping"));
  return sections.join("\n\n") || tr("unanswered");
}
