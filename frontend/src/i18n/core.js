import en from "./en.json" with { type: "json" };
import ko from "./ko.json" with { type: "json" };

export const LANGUAGE_KEY = "visit-notes-language";
export const resources = { en, ko };
export const normalizeLocale = (value) => (value === "ko" ? "ko" : "en");
export function readLocale(storage) {
  try {
    return normalizeLocale(storage?.getItem(LANGUAGE_KEY));
  } catch {
    return "en";
  }
}
let storage;
try {
  storage = globalThis.localStorage;
} catch {
  /* Memory-only preference. */
}
let locale = readLocale(storage);
const listeners = new Set();
export const missingKeys = new Set();
export const getLocale = () => locale;
export function subscribeLocale(listener) {
  listeners.add(listener);
  return () => listeners.delete(listener);
}
function applyLocale(value) {
  locale = normalizeLocale(value);
  if (typeof document !== "undefined") document.documentElement.lang = locale;
  listeners.forEach((listener) => listener());
}
export function setLocale(value) {
  applyLocale(value);
  try {
    if (!storage) return false;
    storage.setItem(LANGUAGE_KEY, locale);
    return true;
  } catch {
    return false;
  }
}
if (typeof document !== "undefined") document.documentElement.lang = locale;
if (typeof window !== "undefined")
  window.addEventListener("storage", (event) => {
    if (event.key === LANGUAGE_KEY || event.key === null)
      applyLocale(readLocale(storage));
  });
export function translate(language, key, params = {}) {
  const selected = normalizeLocale(language);
  let value = resources[selected][key];
  if (typeof value !== "string") {
    missingKeys.add(`${selected}:${key}`);
    if (import.meta.env?.DEV)
      console.warn("Missing translation:", selected, key);
    value = en[key] || resources[selected]["fallback.message"];
  }
  return value.replace(/\{(\w+)\}/g, (_, name) => String(params[name] ?? ""));
}
export const tr = (key, params) => translate(locale, key, params);
// Keep messages as keys until rendering so existing errors change language too.
export const message = (key, params = {}) => ({ key, params });
export function messageText(value) {
  if (!value) return "";
  if (typeof value === "object") return tr(value.key, value.params);
  if (en[value]) return tr(value);
  // Only for old service messages; never use this on patient-entered content.
  const key = Object.keys(ko).find((key) => ko[key] === value);
  return tr(key || value);
}
