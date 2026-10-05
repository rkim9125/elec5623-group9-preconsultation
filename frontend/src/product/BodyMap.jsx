import React, { useId, useState } from "react";
import { bodyMapViews, getBodyRegion } from "./bodyRegions.js";

function Figure({ illustration, view }) {
  if (illustration === "legs")
    return (
      <>
        <path d="M100 58Q150 47 200 58L201 110L194 189L186 285L189 310L204 324Q209 341 191 342H157L153 315L150 221L147 315L143 342H109Q91 341 96 324L111 310L114 285L106 189L99 110Z" />
        <path
          className="body-anatomy-line"
          d={
            view === "front"
              ? "M100 89q50 28 100 0M150 108v111M109 190q17 8 34 0M157 190q17 8 34 0"
              : "M100 85q24 28 50 11q26 17 50-11M150 96v125M111 218q14 53 29 0M160 218q14 53 29 0"
          }
        />
      </>
    );
  if (illustration === "back")
    return (
      <>
        <ellipse cx="150" cy="60" rx="29" ry="37" />
        <path d="M134 92v18l-49 18q-15 5-19 27l-21 92q-2 17 15 16l27-72 9 50-9 82q32 24 63 13q31 11 63-13l-9-82 9-50 27 72q17 1 15-16l-21-92q-4-22-19-27l-49-18V92" />
        <path
          className="body-anatomy-line"
          d="M150 119v124m-33-105 20 28m46-28-20 28M103 241q47 20 94 0M105 281q23-20 45 1q22-21 45-1"
        />
      </>
    );
  if (illustration === "neck_shoulders")
    return (
      <>
        <ellipse cx="150" cy="78" rx="42" ry="49" />
        <path d="M131 120v20l-63 17q-24 9-31 42L23 284h44l14-67 9 128h120l9-128 14 67h44l-14-85q-7-33-31-42l-63-17v-20" />
        <path
          className="body-anatomy-line"
          d="M150 139v106m-59-60 37 31m81-31-37 31M81 217l-2-35m140 35 2-35"
        />
      </>
    );
  if (illustration === "arms_hands")
    return (
      <>
        <ellipse cx="150" cy="44" rx="25" ry="31" />
        <path d="M138 72v17l-45 11q-10 3-14 20l-11 64-12 80-7 14-16 21q-5 11 5 13l8-7-3 29q1 13 12 8l12-14 9-37 4-25 16-70 14-39 9 96h62l9-96 14 39 16 70 4 25 9 37 12 14q11 5 12-8l-3-29 8 7q10-2 5-13l-16-21-7-14-12-80-11-64q-4-17-14-20l-45-11V72" />
        <path
          className="body-anatomy-line"
          d="M108 114q13 13 42 12q29 1 42-12M84 183l11 4m110 0 11-4M54 273l23 5m146 0 23-5"
        />
      </>
    );
  if (illustration === "head")
    return (
      <>
        <path d="M90 166Q78 78 150 65Q222 78 210 166Q221 151 223 180Q221 204 207 205Q199 247 171 264v31l42 14q18 7 27 35H60q9-28 27-35l42-14v-31q-28-17-36-59q-14-1-16-25q2-29 13-14Z" />
        {view === "front" ? (
          <path
            className="body-anatomy-line"
            d="M107 173h21m44 0h21M150 174l-8 35h16m-28 19q20 10 40 0M106 118q44 15 88 0"
          />
        ) : (
          <path
            className="body-anatomy-line"
            d="M103 215q47 20 94 0M133 269q17 8 34 0"
          />
        )}
      </>
    );
  if (illustration === "abdomen")
    return (
      <>
        <path d="M106 28Q150 50 194 28l48 36-18 65-7 118 11 90H72l11-90-7-118-18-65Z" />
        <path
          className="body-anatomy-line"
          d="M81 91q69 30 138 0M89 291q29 6 61 30q32-24 61-30M148 207q-5 9 2 12q7-3 2-12"
        />
      </>
    );
  return (
    <>
      <ellipse cx="150" cy="43" rx="24" ry="32" />
      <path d="M139 73v13l-37 11q-11 3-15 20l-22 82-5 19q-3 17 12 19l12-10 5-24 17-54 10 53-3 104-9 24q-6 15 8 17h30l8-120 8 120h30q14-2 8-17l-9-24-3-104 10-53 17 54 5 24 12 10q15-2 12-19l-5-19-22-82q-4-17-15-20l-37-11V73" />
      {view === "front" ? (
        <path
          className="body-anatomy-line"
          d="M119 109q31 14 62 0M119 198q31 11 62 0M148 174h4M139 45h2m18 0h2m-18 16h14"
        />
      ) : (
        <path
          className="body-anatomy-line"
          d="M150 99v101m-31-86 19 24m43-24-19 24M118 207q17-11 32 3q15-14 32-3"
        />
      )}
    </>
  );
}

export default function BodyMap({
  illustration = "body",
  options,
  selected,
  onSelect,
  disabled,
  label,
}) {
  const titleId = useId();
  const availableViews = bodyMapViews(illustration);
  const [chosenView, setView] = useState(availableViews[0]);
  const view = availableViews.includes(chosenView)
    ? chosenView
    : availableViews[0];
  const onRear = view === "back";
  return (
    <div className="body-map-panel">
      <div className="body-map-toolbar">
        <strong>{illustration === "head" ? "Head map" : "Body map"}</strong>
        {availableViews.length > 1 ? (
          <div className="body-map-views" aria-label="Diagram view">
            {availableViews.map((item) => (
              <button
                type="button"
                key={item}
                aria-pressed={view === item}
                onClick={() => setView(item)}
                disabled={disabled}
              >
                {item === "front" ? "Front" : "Back"}
              </button>
            ))}
          </div>
        ) : (
          <span className="body-map-view-label">
            {onRear ? "Back view" : "Front view"}
          </span>
        )}
      </div>
      <div className="body-map-orientation" aria-hidden="true">
        <span>Your {onRear ? "left" : "right"}</span>
        <span>Your {onRear ? "right" : "left"}</span>
      </div>
      <svg
        viewBox="0 0 300 360"
        className="body-map-drawing"
        role="group"
        aria-labelledby={titleId}
      >
        <title id={titleId}>
          {label} — {view} view, left and right refer to your body
        </title>
        <g className="body-silhouette" aria-hidden="true">
          <Figure illustration={illustration} view={view} />
        </g>
        {options.map((option) => {
          const shape = getBodyRegion(illustration, option.region, view);
          if (!shape) return null;
          const pressed = selected.includes(option.value);
          return (
            <g
              key={option.value}
              className={`body-map-region ${pressed ? "selected" : ""}`}
              role="button"
              aria-label={option.label}
              aria-pressed={pressed}
              aria-disabled={disabled || undefined}
              tabIndex={disabled ? -1 : 0}
              onClick={() => !disabled && onSelect(option.value)}
              onKeyDown={(event) => {
                if (["Enter", " "].includes(event.key)) {
                  event.preventDefault();
                  if (!disabled) onSelect(option.value);
                }
              }}
            >
              <title>{option.label}</title>
              <rect {...shape} />
              {pressed && (
                <path
                  className="body-region-check"
                  d={`m${shape.x + shape.width / 2 - 6} ${shape.y + shape.height / 2} 4 4 8-9`}
                />
              )}
            </g>
          );
        })}
      </svg>
      <p className="body-map-caption">
        Tap a highlighted area, or use the location buttons. Left and right
        refer to your body.
      </p>
    </div>
  );
}
