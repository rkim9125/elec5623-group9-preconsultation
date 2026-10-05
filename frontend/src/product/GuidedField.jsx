import React, { useId, useState } from "react";
import Icon from "./Icons.jsx";
import BodyMap from "./BodyMap.jsx";
import {
  normalizeOptions,
  parseGuidedAnswer,
  serializeGuidedAnswer,
  toggleGuidedSelection,
} from "./answerValues.js";
import "./visual-inputs.css";

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
}) {
  const helperId = useId();
  const errorId = useId();
  const [showDetails, setShowDetails] = useState(false);
  const [error, setError] = useState("");
  const presentation = field.presentation;
  const options = normalizeOptions(presentation?.options);
  const guided =
    ["choices", "body_map", "scale"].includes(presentation?.kind) &&
    options.length > 0;
  const parsed = guided
    ? parseGuidedAnswer(answer.value, options)
    : { selected: [], details: answer.value };
  const update = (next) => {
    const value = serializeGuidedAnswer(next);
    if (value.length > 6000) {
      setError(
        "This answer is longer than 6,000 characters. Shorten your details before adding another selection.",
      );
      return;
    }
    setError("");
    onChange(value);
  };
  const select = (value) =>
    update({
      ...parsed,
      selected: toggleGuidedSelection(
        parsed.selected,
        value,
        presentation.multiple === true,
      ),
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
          ? "Optional: add what you remember or what you’re unsure about…"
          : guided
            ? "Anything else, a different answer, or details in your own words…"
            : "Your answer…"
      }
      onFocus={onFocus}
      onChange={(event) =>
        guided
          ? update({ ...parsed, details: event.target.value })
          : onChange(event.target.value)
      }
      aria-describedby={error ? errorId : guided ? helperId : undefined}
      aria-invalid={error ? true : undefined}
      disabled={disabled}
    />
  );
  if (!guided) return textarea;
  const expanded = showDetails || Boolean(parsed.details);
  return (
    <div
      className={`guided-field guided-${presentation.kind}`}
      onFocus={onFocus}
    >
      <p className="guided-field-helper" id={helperId}>
        {presentation.helper ||
          (presentation.multiple
            ? "Select all that fit. You can add details in your own words."
            : "Choose one, or add your answer in your own words.")}
      </p>
      <div
        className={`guided-options-layout ${presentation.kind === "body_map" ? "with-body-map" : ""}`}
      >
        {presentation.kind === "body_map" && (
          <BodyMap
            illustration={presentation.illustration}
            options={options}
            selected={parsed.selected}
            onSelect={select}
            disabled={disabled}
            label={field.label || field.question}
          />
        )}
        <div className="guided-choice-panel">
          {presentation.kind === "body_map" && (
            <span className="guided-choice-label">Choose locations</span>
          )}
          <div
            className={`answer-choices ${presentation.kind === "scale" ? "answer-scale" : ""}`}
            role="group"
            aria-labelledby={`${inputId}-question`}
            aria-describedby={helperId}
          >
            {options.map((option) => {
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
                  <span>{option.label}</span>
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
          <div className="guided-choice-footer" aria-live="polite">
            {parsed.selected.length ? (
              <span>
                {parsed.selected.length}{" "}
                {parsed.selected.length === 1 ? "option" : "options"} selected
              </span>
            ) : (
              <span>No selection yet</span>
            )}
            {parsed.selected.length > 0 && (
              <button
                type="button"
                className="guided-clear"
                onClick={() => update({ ...parsed, selected: [] })}
                disabled={disabled}
              >
                Clear selections
              </button>
            )}
          </div>
        </div>
      </div>
      <div className="guided-custom-answer">
        {expanded ? (
          <label className="guided-details-label" htmlFor={inputId}>
            Your own details <span>(optional)</span>
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
            <Icon name="plus" size={17} /> Add details or another answer
          </button>
        )}
        <div id={`${inputId}-details`} hidden={!expanded}>
          {textarea}
        </div>
      </div>
      {error && (
        <p id={errorId} className="guided-error" role="alert">
          {error}
        </p>
      )}
    </div>
  );
}
