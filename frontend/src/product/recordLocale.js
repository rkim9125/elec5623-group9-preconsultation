import { productResources } from "./translations.js";

const slotLabels = {
  FILLED: "Reported",
  MISSING: "Not collected",
  UNCERTAIN: "Uncertain",
  SKIPPED: "Skipped",
  NOT_APPLICABLE: "Not applicable",
  ATTACHED: "Attached",
};

export function slotStatusLabel(status, t) {
  return t(slotLabels[String(status || "MISSING").toUpperCase()] || status || "Not collected");
}

// Only exact catalogue strings and application-composed title lists are localized.
// Never replace words inside a patient's custom consultation title or narrative.
export function recordTitle(value, t, fallback = "Your consultation") {
  if (!value) return t(fallback);
  if (Object.hasOwn(productResources.en, value)) return t(value);
  const parts = String(value).split(/( · |; )/);
  if (parts.length > 1 && parts.every((part, index) => index % 2 || Object.hasOwn(productResources.en, part)))
    return parts.map((part, index) => index % 2 ? part : t(part)).join("");
  return value;
}

const dynamicFieldLabels = {
  name: "Name",
  dose: "Dose",
  frequency: "Frequency",
  "actual use": "Actual use",
  experience: "Experience",
  supply: "Supply",
  date: "Date",
  source: "Source",
  unit: "Unit",
  value: "Value",
  reason: "Reason",
  "ordering clinician": "Ordering clinician",
};

export function recordLabel(value, t) {
  if (!value) return t("Not provided");
  if (Object.hasOwn(productResources.en, value)) return t(value);
  // Dynamic item labels contain a patient-supplied medicine/test name followed
  // by one application-owned field suffix. Never translate that item name,
  // even if it happens to match an interface string such as "Frequency".
  const item = String(value).match(/^(.*)( · | — |: )([^·]+)$/);
  if (item) {
    const key = item[3].replace(/_/g, " ").toLowerCase();
    const field = Object.hasOwn(dynamicFieldLabels, key) ? dynamicFieldLabels[key] : null;
    if (field) return `${item[1]}${item[2]}${t(field)}`;
  }
  // Source labels are assembled from trusted field and concern labels.
  return String(value).split(/( — |: )/).map((part) => recordTitle(part, t, "")).join("");
}

export function recordedValue(value, t) {
  if (value == null || value === "") return t("Not provided");
  if (typeof value !== "string") return JSON.stringify(value);
  const prefix = "Selected options:\n";
  const separator = "\n\nAdditional details:\n";
  if (!value.startsWith(prefix)) return value;
  const detailAt = value.indexOf(separator, prefix.length);
  const choices = value.slice(prefix.length, detailAt < 0 ? undefined : detailAt).split("\n");
  // Recognize only the application's serialized choice envelope. The free-text
  // suffix is left byte-for-byte intact, including medication names and units.
  if (!choices.length || choices.some((line) => !line.startsWith("- "))) return value;
  const localized = choices.map((line) => `- ${t(line.slice(2))}`).join("\n");
  const details = detailAt < 0 ? "" : value.slice(detailAt + separator.length);
  return `${t("Selected options:")}\n${localized}${details ? `\n\n${t("Additional details:")}\n${details}` : ""}`;
}

export function followupAnswerText(question, answer, t) {
  const value = answer?.value || "";
  const option = question?.options?.find((item) => item.value === value);
  return option ? t(option.label || option.value) : value;
}
