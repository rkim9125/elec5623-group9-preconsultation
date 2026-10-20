import { uiTranslationRows } from "./uiTranslations.js";
import { clinicalTranslationRows } from "./clinicalTranslations.js";
import { workflowTranslationRows } from "./workflowTranslations.js";
import { topicTranslationRows } from "./topicTranslations.js";
import { reportTranslationRows } from "./reportTranslations.js";
import { fieldLabelTranslationRows } from "./fieldLabelTranslations.js";
import { portalTranslationRows } from "./portalTranslations.js";
import { preparationTranslationRows } from "./preparationTranslations.js";
import { bodyProfileTranslationRows } from "./bodyProfileTranslations.js";
import { followupTranslationRows } from "./followupTranslations.js";

export const LOCALE_STORAGE_KEY = "preconsultation.locale";
export const languages = [
  { id: "en", name: "English", speech: "en-AU" },
  { id: "zh-CN", name: "简体中文", speech: "zh-CN" },
  { id: "zh-TW", name: "繁體中文", speech: "zh-TW" },
  { id: "ko", name: "한국어", speech: "ko-KR" },
  { id: "ja", name: "日本語", speech: "ja-JP" },
];

export const productResources = Object.fromEntries(
  languages.map(({ id }) => [id, Object.create(null)]),
);
for (const row of [
  ...workflowTranslationRows,
  ...fieldLabelTranslationRows,
  ...clinicalTranslationRows,
  ...topicTranslationRows,
  ...portalTranslationRows,
  ...reportTranslationRows,
  ...uiTranslationRows,
  ...preparationTranslationRows,
  ...bodyProfileTranslationRows,
  ...followupTranslationRows,
]) {
  for (let index = 0; index < languages.length; index += 1) {
    productResources[languages[index].id][row[0]] = row[index] || row[0];
  }
}

export function readProductLocale(storage) {
  try {
    const selected = (storage || globalThis.localStorage)?.getItem(
      LOCALE_STORAGE_KEY,
    );
    return languages.some(({ id }) => id === selected) ? selected : "en";
  } catch {
    return "en";
  }
}

/** Translate interface strings only. Patient narrative and canonical answer values stay intact. */
export function translateProduct(locale, source, params = {}) {
  if (source == null) return "";
  const text = String(source);
  const catalogue = Object.prototype.hasOwnProperty.call(
    productResources,
    locale,
  )
    ? productResources[locale]
    : null;
  const translated = catalogue?.[text] || text;
  return translated.replace(/\{(\w+)\}/g, (match, key) =>
    Object.prototype.hasOwnProperty.call(params, key)
      ? String(params[key])
      : match,
  );
}
