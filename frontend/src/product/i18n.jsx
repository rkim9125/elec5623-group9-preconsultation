import React, {
  createContext,
  useContext,
  useEffect,
  useMemo,
  useState,
} from "react";
import {
  languages,
  readProductLocale,
  translateProduct,
  LOCALE_STORAGE_KEY,
} from "./translations.js";
import { navigateWithGuard } from "./navigation.js";

const LocaleContext = createContext({
  locale: "en",
  setLocale: () => {},
  t: (source, params) => translateProduct("en", source, params),
});

export function LocaleProvider({ children }) {
  const [locale, setLocale] = useState(readProductLocale);
  useEffect(() => {
    document.documentElement.lang = locale;
    try {
      localStorage.setItem(LOCALE_STORAGE_KEY, locale);
    } catch {
      // Preferences still work for this visit when browser storage is unavailable.
    }
  }, [locale]);
  const value = useMemo(
    () => ({
      locale,
      setLocale: (next) => {
        const selected = languages.some((item) => item.id === next) ? next : "en";
        // Non-component formatters also read this preference during rendering.
        // Update it first so dates do not lag one language switch behind.
        try {
          localStorage.setItem(LOCALE_STORAGE_KEY, selected);
        } catch {
          // The context still changes if preference storage is unavailable.
        }
        setLocale(selected);
      },
      t: (source, params) => translateProduct(locale, source, params),
    }),
    [locale],
  );
  return (
    <LocaleContext.Provider value={value}>{children}</LocaleContext.Provider>
  );
}

export function useLocale() {
  return useContext(LocaleContext);
}

export function LanguageSwitcher({ className = "" }) {
  const { locale, setLocale, t } = useLocale();
  return (
    <label className={`language-switcher ${className}`}>
      <svg
        aria-hidden="true"
        width="17"
        height="17"
        viewBox="0 0 24 24"
        fill="none"
        stroke="currentColor"
        strokeWidth="1.6"
      >
        <circle cx="12" cy="12" r="9" />
        <ellipse cx="12" cy="12" rx="4" ry="9" />
        <path d="M3 12h18" />
      </svg>
      <select
        value={locale}
        aria-label={t("Language")}
        onChange={(event) => {
          const next = event.target.value;
          navigateWithGuard(() => setLocale(next));
        }}
      >
        {languages.map((item) => (
          <option key={item.id} value={item.id} lang={item.id}>
            {item.name}
          </option>
        ))}
      </select>
    </label>
  );
}
