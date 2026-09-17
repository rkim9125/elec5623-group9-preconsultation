import { useState, useSyncExternalStore } from "react";
import { getLocale, subscribeLocale, setLocale, tr } from "./core.js";
export function useI18n() {
  return useSyncExternalStore(subscribeLocale, getLocale, () => "en");
}
export function LanguageSelect() {
  const locale = useI18n();
  const [saved, setSaved] = useState(true);
  return (
    <div className="language-control">
      <label className="sr-only" htmlFor="ui-language">
        {tr("language.label")}
      </label>
      <select
        id="ui-language"
        value={locale}
        onChange={(event) => setSaved(setLocale(event.target.value))}
      >
        <option value="en" lang="en">
          English
        </option>
        <option value="ko" lang="ko">
          korean
        </option>
      </select>
      {!saved && (
        <span className="language-warning" role="status">
          {tr("language.memoryOnly")}
        </span>
      )}
    </div>
  );
}
