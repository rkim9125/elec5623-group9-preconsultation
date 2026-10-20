import React, { useId, useRef, useState } from "react";
import {
  bodyMapCopy as copy,
  lowerBodyShapes,
  areaName,
  areaSummary,
  normalizeAreas,
  toggleLowerBodyArea,
} from "./lowerBodyModel.js";
import { useLocale } from "./i18n.jsx";
import "./lower-body-map.css";

/** Controlled with value/onChange; otherwise initialValue seeds a local selection.
 * Selection: an array of { side: 'Right'|'Left', key, view: 'front'|'back' }.
 * A legacy single-area value is accepted and normalized without losing it.
 */
export default function LowerBodyMap({
  value,
  initialValue = null,
  onChange,
  disabled = false,
}) {
  const { locale, t } = useLocale();
  const localizedArea = (area) =>
    t("{side} {area} · {view}", {
      side: t(area.side),
      area: t(areaName(area.key, area.view)),
      view: t(copy[area.view]),
    });
  const [localValue, setLocalValue] = useState(initialValue);
  const [view, setView] = useState("front");
  const selected = normalizeAreas(value === undefined ? localValue : value);
  const titleId = useId();
  const viewButton = useRef(null);
  const change = (next) => {
    if (value === undefined) setLocalValue(next);
    onChange?.(next);
  };
  const active = (side, key) =>
    selected.some(
      (area) => area.side === side && area.key === key && area.view === view,
    );
  const choose = (side, key) => {
    change(toggleLowerBodyArea(selected, { side, key, view }));
  };
  const screenSides = view === "front" ? ["Right", "Left"] : ["Left", "Right"];
  const buttonProps = (side, key) => ({
    type: "button",
    disabled,
    "aria-label": localizedArea({ side, key, view }),
    "aria-pressed": active(side, key),
    onClick: () => choose(side, key),
  });
  return (
    <div className="lower-body-map" lang={locale}>
      <section className="bm-product" aria-labelledby={titleId}>
        <header>
          <h2 id={titleId}>{t(copy.title)}</h2>
          <p>{t(copy.description)}</p>
        </header>
        <div className="bm-top">
          <div className="bm-tabs" role="group" aria-label={t(copy.viewLabel)}>
            {["front", "back"].map((item) => (
              <button
                key={item}
                ref={view === item ? viewButton : null}
                type="button"
                aria-pressed={view === item}
                disabled={disabled}
                onClick={() => setView(item)}
              >
                {t(copy[item])}
              </button>
            ))}
          </div>
          <span className="bm-guide">
            <i aria-hidden="true" />
            {t(copy.guide)}
          </span>
        </div>
        <div className="bm-work">
          <div className="bm-map">
            <div className="bm-sides">
              {screenSides.map((side) => (
                <span key={side}>
                  <b>{t(side === "Right" ? "Your right" : "Your left")}</b>
                </span>
              ))}
            </div>
            <div className="bm-anatomy">
              <svg
                className="bm-outline"
                viewBox="0 0 220 360"
                role="img"
                aria-label={t("Lower body, {view}", { view: t(copy[view]) })}
              >
                <path d="M52 8 Q110 -2 168 8 L175 52 C182 86 163 135 158 164 Q155 183 161 213 C170 245 150 278 151 314 L169 335 Q177 351 159 353 L132 353 Q122 352 124 333 L125 311 Q122 278 120 252 L119 206 L111 100 Q110 88 109 100 L101 206 L100 252 Q98 278 95 311 L96 333 Q98 352 88 353 L61 353 Q43 351 51 335 L69 314 C70 278 50 245 59 213 Q65 183 62 164 C57 135 38 86 45 52 Z" />
                <path
                  className="detail"
                  d={
                    view === "front"
                      ? "M47 47 Q78 51 109 87 M173 47 Q142 51 111 87 M69 187 Q81 178 94 187 M126 187 Q139 178 151 187 M76 314 L92 316 M128 316 L145 314"
                      : "M47 48 Q71 86 109 65 Q147 86 173 48 M110 22 L110 66 M68 187 L95 187 M125 187 L152 187 M78 241 L83 281 M142 241 L137 281"
                  }
                />
              </svg>
              <div className="bm-zones">
                {lowerBodyShapes.flatMap((shape) =>
                  screenSides.map((side, column) => (
                    <button
                      {...buttonProps(side, shape.key)}
                      key={`${column}-${shape.key}`}
                      className="bm-zone"
                      style={{
                        left: column === 0 ? shape.x : 220 - shape.x - shape.w,
                        top: shape.y,
                        width: shape.w,
                        height: shape.h,
                      }}
                    >
                      {active(side, shape.key) && (
                        <span aria-hidden="true">✓</span>
                      )}
                    </button>
                  )),
                )}
              </div>
            </div>
            <div className="bm-note">
              <i className="bm-info" aria-hidden="true">
                i
              </i>
              {t(copy.note)}
            </div>
          </div>
          <div className="bm-list">
            <div className="bm-list-title">{t(copy.list)}</div>
            {lowerBodyShapes.map(({ key }) => (
              <div className="bm-row" key={key}>
                <span>{t(areaName(key, view))}</span>
                {["Right", "Left"].map((side) => (
                  <button {...buttonProps(side, key)} key={side}>
                    {t(side[0])}
                    {active(side, key) && (
                      <span className="bm-list-check" aria-hidden="true">
                        ✓
                      </span>
                    )}
                  </button>
                ))}
              </div>
            ))}
          </div>
        </div>
        <div className="bm-selection">
          <span className="bm-selected-icon" aria-hidden="true">
            {selected.length ? "✓" : "—"}
          </span>
          <div className="bm-result" aria-live="polite" aria-atomic="true">
            <small>{t(copy.selected)}</small>
            {selected.length ? (
              <ul className="bm-selected-areas">
                {selected.map((area) => (
                  <li key={areaSummary(area)}>
                    <span>{localizedArea(area)}</span>
                    <button
                      type="button"
                      disabled={disabled}
                      aria-label={t("Remove {area}", {
                        area: localizedArea(area),
                      })}
                      onClick={() =>
                        change(toggleLowerBodyArea(selected, area))
                      }
                    >
                      <span aria-hidden="true">×</span>
                    </button>
                  </li>
                ))}
              </ul>
            ) : (
              <strong>{t(copy.empty)}</strong>
            )}
          </div>
          <button
            type="button"
            className="bm-clear"
            disabled={disabled || !selected.length}
            onClick={() => {
              change([]);
              viewButton.current?.focus();
            }}
          >
            {t(copy.clear)}
          </button>
        </div>
      </section>
    </div>
  );
}
