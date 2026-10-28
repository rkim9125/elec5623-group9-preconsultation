import React, { useId, useState } from "react";
import Icon from "./Icons.jsx";
import BodyMap from "./BodyMap.jsx";
import LowerBodyMap from "./LowerBodyMap.jsx";
import { useLocale } from "./i18n.jsx";
import {
  bodyOptionsFor,
  areasFromAnswer,
  areaSummary,
  normalizeLowerBodyAnswer,
} from "./lowerBodyModel.js";
import {
  normalizeOptions,
  parseGuidedAnswer,
  serializeGuidedAnswer,
  toggleGuidedSelection,
} from "./answerValues.js";
import "./visual-inputs.css";
import {
  painNumbers,
  selectPainNumber,
  withPainOptions,
} from "./oldcartsModel.js";

const activityIcons = {
  "Daily tasks": "grid",
  "Work or study": "file",
  Sleep: "sleep",
  "Exercise or movement": "leg",
  "Social activities": "person",
  "Personal care": "heart",
};
function choiceIcon(field, option) {
  if (option.icon) return option.icon;
  if (field.key === "functional_impact") return activityIcons[option.label];
  if (field.key === "sleep.main_difficulty")
    return option.label.includes("routine")
      ? "clock"
      : option.label.includes("refreshed")
        ? "fatigue"
        : "sleep";
  if (["fatigue.daily_pattern", "cough.daily_pattern"].includes(field.key))
    return option.label.includes("night") ? "sleep" : "clock";
  return null;
}

export default function GuidedField({
  field,
  answer,
  inputId,
  disabled,
  onChange,
  onFocus,
  hideDetails = false,
  hideHelper = false,
}) {
  const { t } = useLocale();
  const helperId = useId();
  const errorId = useId();
  const [showDetails, setShowDetails] = useState(false);
  const [showPainNumbers, setShowPainNumbers] = useState(false);
  const [error, setError] = useState("");
  const presentation = field.presentation;
  const isLowerBody =
    presentation?.kind === "body_map" && presentation.illustration === "legs";
  const baseOptions = normalizeOptions(bodyOptionsFor(presentation));
  const options = normalizeOptions(withPainOptions(baseOptions, presentation));
  const painScale = presentation?.pain_scale === true;
  const guided =
    ["choices", "body_map", "scale"].includes(presentation?.kind) &&
    options.length > 0;
  const rawParsed = guided
    ? parseGuidedAnswer(answer.value, options)
    : { selected: [], details: answer.value };
  const parsed = isLowerBody ? normalizeLowerBodyAnswer(rawParsed) : rawParsed;
  const update = (next) => {
    const value = serializeGuidedAnswer(next);
    if (value.length > 6000) {
      setError(
        t(
          "This answer is longer than 6,000 characters. Shorten your details before adding another selection.",
        ),
      );
      return;
    }
    setError("");
    onChange(value);
  };
  const select = (value) =>
    update({
      ...parsed,
      selected: [
        ...toggleGuidedSelection(
          painScale
            ? parsed.selected.filter(
                (item) => !painNumbers.some((option) => option.value === item),
              )
            : parsed.selected,
          value,
          isLowerBody || presentation.multiple === true,
          baseOptions,
        ),
        ...(painScale
          ? parsed.selected.filter((item) =>
              painNumbers.some((option) => option.value === item),
            )
          : []),
      ],
    });
  const textarea = (
    <textarea
      id={inputId}
      data-testid={`baseline-${field.concern_id}-${field.key}`}
      rows={guided ? 3 : 2}
      value={parsed.details}
      maxLength={6000}
      placeholder={
        answer.status === "UNCERTAIN"
          ? t("Optional: add what you remember or what you’re unsure about…")
          : guided
            ? t(
                "Anything else, a different answer, or details in your own words…",
              )
            : t("Your answer…")
      }
      onFocus={onFocus}
      onChange={(event) =>
        guided
          ? update({ ...parsed, details: event.target.value })
          : onChange(event.target.value)
      }
      aria-describedby={
        error ? errorId : guided && !hideHelper ? helperId : undefined
      }
      aria-invalid={error ? true : undefined}
      disabled={disabled}
    />
  );
  if (!guided) return hideDetails ? null : textarea;
  const expanded = showDetails || Boolean(parsed.details);
  return (
    <div
      className={`guided-field guided-${presentation.kind}`}
      onFocus={onFocus}
    >
      {!hideHelper && (
        <p className="guided-field-helper" id={helperId}>
          {t(
            (isLowerBody
              ? "Choose all affected areas, including both sides or views. You can add details in your own words."
              : presentation.helper) ||
              (presentation.multiple
                ? "Select all that fit. You can add details in your own words."
                : "Choose one, or add your answer in your own words."),
          )}
        </p>
      )}
      <div
        className={`guided-options-layout ${presentation.kind === "body_map" && !isLowerBody ? "with-body-map" : ""}`}
      >
        {isLowerBody && (
          <LowerBodyMap
            value={areasFromAnswer(parsed.selected)}
            disabled={disabled}
            onChange={(areas) =>
              update({ ...parsed, selected: areas.map(areaSummary) })
            }
          />
        )}
        {presentation.kind === "body_map" && !isLowerBody && (
          <BodyMap
            illustration={presentation.illustration}
            options={options}
            selected={parsed.selected}
            onSelect={select}
            disabled={disabled}
            label={field.label || field.question}
          />
        )}
        {!isLowerBody && (
          <div className="guided-choice-panel">
            {presentation.kind === "body_map" && (
              <span className="guided-choice-label">
                {t("Choose locations")}
              </span>
            )}
            <div
              className={`answer-choices ${presentation.kind === "scale" ? "answer-scale" : ""}`}
              role="group"
              aria-label={t(field.question || field.label)}
              aria-describedby={hideHelper ? undefined : helperId}
            >
              {baseOptions.map((option) => {
                const selected = parsed.selected.includes(option.value);
                const icon = choiceIcon(field, option);
                return (
                  <button
                    type="button"
                    key={option.value}
                    className={`answer-choice ${selected ? "selected" : ""}`}
                    aria-pressed={selected}
                    onClick={() => select(option.value)}
                    disabled={disabled}
                  >
                    {icon && (
                      <span className="answer-choice-icon">
                        <Icon name={icon} size={19} />
                      </span>
                    )}
                    <span>
                      {t(
                        field.key === "eye_sensation" &&
                          option.label === "Watery"
                          ? "Watery eyes"
                          : option.label,
                      )}
                    </span>
                    <span
                      className={`answer-choice-mark ${presentation.multiple ? "multiple" : "single"}`}
                      aria-hidden="true"
                    >
                      {selected && <Icon name="check" size={13} />}
                    </span>
                  </button>
                );
              })}
            </div>
            {painScale && (
              <div className="optional-pain-scale">
                <button
                  className="pain-number-toggle"
                  type="button"
                  disabled={disabled}
                  aria-expanded={showPainNumbers}
                  aria-controls={`${inputId}-pain-numbers`}
                  onClick={() => setShowPainNumbers(!showPainNumbers)}
                >
                  <Icon name={showPainNumbers ? "chevron" : "plus"} size={15} />
                  {t(
                    showPainNumbers
                      ? "Hide pain numbers"
                      : "Add a pain number (optional)",
                  )}
                </button>
                {showPainNumbers && (
                  <div
                    id={`${inputId}-pain-numbers`}
                    className="pain-number-panel"
                  >
                    <p>
                      {t(
                        "0 means no pain; 10 means the worst pain you can imagine.",
                      )}
                    </p>
                    <div
                      className="pain-number-options"
                      role="group"
                      aria-label={t("Pain number")}
                    >
                      {painNumbers.map((option) => (
                        <button
                          key={option.value}
                          type="button"
                          disabled={disabled}
                          className={
                            parsed.selected.includes(option.value)
                              ? "selected"
                              : ""
                          }
                          aria-pressed={parsed.selected.includes(option.value)}
                          aria-label={t("Pain level {number} out of 10", {
                            number: option.label,
                          })}
                          onClick={() =>
                            update({
                              ...parsed,
                              selected: selectPainNumber(
                                parsed.selected,
                                option.value,
                              ),
                            })
                          }
                        >
                          {option.label}
                        </button>
                      ))}
                    </div>
                  </div>
                )}
              </div>
            )}
            <div className="guided-choice-footer" aria-live="polite">
              {parsed.selected.length ? (
                <span>
                  {painScale
                    ? parsed.selected
                        .map((value) =>
                          painNumbers.some((option) => option.value === value)
                            ? value
                            : t(
                                baseOptions.find(
                                  (option) => option.value === value,
                                )?.label || value,
                              ),
                        )
                        .join(" · ")
                    : t("{count} selected", { count: parsed.selected.length })}
                </span>
              ) : (
                <span>{t("No selection yet")}</span>
              )}
              {parsed.selected.length > 0 && (
                <button
                  type="button"
                  className="guided-clear"
                  onClick={() => update({ ...parsed, selected: [] })}
                  disabled={disabled}
                >
                  {t("Clear selections")}
                </button>
              )}
            </div>
          </div>
        )}
      </div>
      {!hideDetails && (
        <div className="guided-custom-answer">
          {expanded ? (
            <label className="guided-details-label" htmlFor={inputId}>
              {t("Your own details")} <span>{t("(optional)")}</span>
            </label>
          ) : (
            <button
              className="guided-add-details"
              type="button"
              aria-expanded="false"
              aria-controls={`${inputId}-details`}
              onClick={() => setShowDetails(true)}
              disabled={disabled}
            >
              <Icon name="plus" size={17} />{" "}
              {t("Add details or another answer")}
            </button>
          )}
          <div id={`${inputId}-details`} hidden={!expanded}>
            {textarea}
          </div>
        </div>
      )}
      {error && (
        <p id={errorId} className="guided-error" role="alert">
          {error}
        </p>
      )}
    </div>
  );
}
