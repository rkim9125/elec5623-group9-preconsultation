import { getLocale, resources, translate } from "./core.js";

const names = {
  "patient-a": "demo.patient.garam",
  "patient-b": "demo.patient.narae",
  "patient-empty": "demo.patient.saebom",
};
export const demoName = (user, locale = getLocale()) =>
  names[user.id] ? translate(locale, names[user.id]) : user.name;

// Only appointment metadata uses this lookup; patient-entered text never does.
export function demoLabel(value, locale = getLocale()) {
  const key = Object.keys(resources.ko).find(
    (key) =>
      /^demo\.(hospital|department|clinician)\./.test(key) &&
      resources.ko[key] === value,
  );
  return key ? translate(locale, key) : value;
}

// Translate an untouched sample answer. Editing it makes it ordinary free text.
export function demoReason(data, value, locale = getLocale()) {
  return data.demoReason && data.demoReason.value === value
    ? translate(locale, data.demoReason.key)
    : value;
}

const seededReasons = {
  "intake-a-draft": "demo.reason.headache",
  "intake-a-ready": "demo.reason.sleep",
  "intake-a-sent": "demo.reason.throat",
  "intake-b-draft": "demo.reason.nose",
};
export function markSeededDemo(record) {
  const key = seededReasons[record.id];
  if (!key) return record;
  for (const data of [record.data, record.snapshot?.data]) {
    if (!data?.demoReasonEdited && data?.reasons[0] === resources.ko[key])
      data.demoReason = { key, value: data.reasons[0] };
    if (record.id === "intake-a-draft" && data?.onset.value === "며칠 전부터")
      data.onset.option = data.onset.value;
  }
  return record;
}
