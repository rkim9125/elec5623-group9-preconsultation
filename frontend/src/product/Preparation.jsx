import React, { useCallback, useEffect, useRef, useState } from "react";
import Icon from "./Icons.jsx";
import { request, dateLabel } from "./api.js";
import { Button, ErrorNotice, Loading, Modal } from "./UI.jsx";
import { registerNavigationGuard } from "./navigation.js";
import GuidedField from "./GuidedField.jsx";
import { bodyOptionsFor } from "./lowerBodyModel.js";
import {
  appendGuidedDetails,
  parseGuidedAnswer,
  serializeGuidedAnswer,
} from "./answerValues.js";
import VoiceComposer from "./VoiceComposer.jsx";
import { useLocale } from "./i18n.jsx";
import { topicVisual } from "./topics.js";
import {
  recordTitle,
  recordLabel,
  recordedValue,
  slotStatusLabel,
} from "./recordLocale.js";
import SymptomOverview, { SymptomContext } from "./SymptomOverview.jsx";
import { dimensionFor, withPainOptions } from "./oldcartsModel.js";

const stages = [
  "Your concerns",
  "Health information",
  "AI analysis & follow-up",
  "Review & share",
];
export function JourneyNavigation({ current = 0, onSelect, completed = 0 }) {
  const { t } = useLocale();
  return (
    <nav className="journey-navigation" aria-label={t("Consultation stages")}>
      <ol>
        {stages.map((label, index) => (
          <li
            key={label}
            className={
              index === current ? "current" : index < current ? "complete" : ""
            }
            aria-current={index === current ? "step" : undefined}
          >
            <button
              type="button"
              disabled={
                !onSelect ||
                index === 0 ||
                index > completed ||
                index === current
              }
              onClick={() => onSelect?.(index)}
            >
              <span>
                {index < current ? <Icon name="check" size={17} /> : index + 1}
              </span>
              <strong>{t(label)}</strong>
            </button>
          </li>
        ))}
      </ol>
    </nav>
  );
}

const fieldId = (field) => `${field.concern_id}::${field.key}`;
function initialAnswer(field) {
  return {
    concern_id: field.concern_id,
    key: field.key,
    value:
      typeof field.value === "string"
        ? field.value
        : field.value == null
          ? ""
          : JSON.stringify(field.value),
    status: ["FILLED", "UNCERTAIN", "SKIPPED"].includes(field.status)
      ? field.status
      : "MISSING",
  };
}
export function BaselineForm({
  session,
  onUpdate,
  refresh,
  Attachments,
  onContinue,
}) {
  const { t, locale } = useLocale();
  const [voiceBusy, setVoiceBusy] = useState(false);
  const [review, setReview] = useState(false);
  const [form, setForm] = useState(null);
  const [answers, setAnswers] = useState({});
  const [activeField, setActiveField] = useState("");
  const [error, setError] = useState("");
  const [loadError, setLoadError] = useState("");
  const [operation, setOperation] = useState("");
  const [saveState, setSaveState] = useState("Saved");
  const [revision, setRevision] = useState(0);
  const [leaving, setLeaving] = useState(false);
  const [organizing, setOrganizing] = useState(false);
  const [organizationNotice, setOrganizationNotice] = useState("");
  const organizingRef = useRef(false);
  const organizedDescriptions = useRef({});
  const latest = useRef({});
  const mounted = useRef(true);
  const dirty = useRef(false);
  const localRevision = useRef(0);
  const saving = useRef(null);
  const flushing = useRef(null);
  const timer = useRef(null);
  const continuing = useRef(false);
  const saveFailed = useRef(false);
  const serverRevision = useRef(session.revision);
  const onUpdateRef = useRef(onUpdate);
  onUpdateRef.current = onUpdate;

  const loadForm = useCallback(
    async ({ after } = {}) => {
      setLoadError("");
      try {
        const result = await request(`/intakes/${session.id}/form`);
        if (!mounted.current) return;
        const values = Object.fromEntries(
          result.groups.flatMap((group) =>
            group.fields.map((field) => [fieldId(field), initialAnswer(field)]),
          ),
        );
        latest.current = values;
        serverRevision.current = result.revision;
        dirty.current = false;
        saveFailed.current = false;
        setSaveState("Saved");
        setAnswers(values);
        setForm(result);
        const ordered = [
          ...result.groups.filter((g) => g.id !== "shared"),
          ...result.groups.filter((g) => g.id === "shared"),
        ].flatMap((g) => g.fields);
        const remaining = after
          ? ordered.slice(
              ordered.findIndex((field) => fieldId(field) === after) + 1,
            )
          : ordered;
        const first =
          remaining.find(
            (field) =>
              (!field.requires_permission ||
                (values[`${field.concern_id}::sensitive_permission`]?.status ===
                  "FILLED" &&
                  /^yes\b/i.test(
                    values[
                      `${field.concern_id}::sensitive_permission`
                    ]?.value?.trim() || "",
                  ))) &&
              !field.review_only &&
              !field.profile_reused &&
              field.status === "MISSING",
          ) || (after ? null : ordered[0]);
        if (first) setActiveField(fieldId(first));
        else if (after) setReview(true);
        return result;
      } catch (err) {
        if (mounted.current) {
          setLoadError(err.message);
          if (after) {
            // Organization may have changed the server. Never allow an older
            // full form snapshot to overwrite it after a failed reload.
            setForm(null);
            setError(err.message);
          }
        }
        return null;
      }
    },
    [session.id],
  );
  useEffect(() => {
    mounted.current = true;
    loadForm();
    const warn = (event) => {
      if (dirty.current || organizingRef.current) {
        event.preventDefault();
        event.returnValue = "";
      }
    };
    window.addEventListener("beforeunload", warn);
    return () => {
      mounted.current = false;
      clearTimeout(timer.current);
      window.removeEventListener("beforeunload", warn);
    };
  }, [loadForm]);

  useEffect(() => {
    if (!saving.current && session.revision)
      serverRevision.current = session.revision;
  }, [session.revision]);

  function permitted(field, values = latest.current) {
    if (!field.requires_permission) return true;
    const permission = values[`${field.concern_id}::sensitive_permission`];
    return (
      permission?.status === "FILLED" &&
      /^yes\b/i.test(permission.value?.trim() || "")
    );
  }
  function change(field, patch) {
    const key = fieldId(field);
    const previous = latest.current[key] || initialAnswer(field);
    const updated = { ...previous, ...patch };
    if (Object.hasOwn(patch, "value") && !Object.hasOwn(patch, "status"))
      updated.status =
        previous.status === "UNCERTAIN"
          ? "UNCERTAIN"
          : patch.value.trim()
            ? "FILLED"
            : "MISSING";
    if (updated.status === "SKIPPED" || updated.status === "MISSING")
      updated.value = "";
    let next = { ...latest.current, [key]: updated };
    if (
      field.key === "sensitive_permission" &&
      !/^yes\b/i.test(updated.value || "")
    ) {
      for (const candidate of form.groups.flatMap((group) => group.fields)) {
        if (
          candidate.concern_id === field.concern_id &&
          candidate.requires_permission
        )
          next = {
            ...next,
            [fieldId(candidate)]: {
              ...next[fieldId(candidate)],
              value: "",
              status: "MISSING",
            },
          };
      }
    }
    latest.current = next;
    localRevision.current += 1;
    dirty.current = true;
    saveFailed.current = false;
    setAnswers(next);
    setRevision(localRevision.current);
    setSaveState("Unsaved changes");
    setError("");
  }
  const save = useCallback(
    async (complete = false) => {
      clearTimeout(timer.current);
      if (complete) {
        continuing.current = true;
        setOperation("continuing");
        if (saving.current) await saving.current;
      } else if (saving.current || continuing.current) return saving.current;
      const snapshotRevision = localRevision.current;
      const snapshot = Object.values(latest.current).map((answer) => ({
        ...answer,
        value: answer.value.trim() || null,
      }));
      setOperation(complete ? "continuing" : "saving");
      setError("");
      setSaveState(complete ? "Preparing analysis and follow-up…" : "Saving…");
      const task = (async () => {
        try {
          const updated = await request(`/intakes/${session.id}/baseline`, {
            method: "PUT",
            body: {
              locale,
              answers: snapshot,
              complete,
              revision: serverRevision.current,
            },
          });
          if (!mounted.current) return;
          serverRevision.current = updated.revision;
          saveFailed.current = false;
          if (snapshotRevision === localRevision.current) {
            dirty.current = false;
            setSaveState("All changes saved");
          } else setSaveState("Unsaved changes");
          onUpdateRef.current(updated);
          if (complete) onContinue?.();
        } catch (err) {
          if (mounted.current) {
            saveFailed.current = true;
            setError(err.message);
            setSaveState("Could not save — try again");
          }
        } finally {
          saving.current = null;
          continuing.current = false;
          if (mounted.current) setOperation("");
        }
      })();
      saving.current = task;
      return task;
    },
    [session.id, onContinue, locale],
  );
  useEffect(() => {
    if (!dirty.current || operation || saveFailed.current) return;
    timer.current = setTimeout(() => save(false), 1400);
    return () => clearTimeout(timer.current);
  }, [revision, operation, save]);

  useEffect(
    () =>
      registerNavigationGuard(async () => {
        if (organizingRef.current) return false;
        if (voiceBusy) {
          setError(t("Finish or cancel voice input before leaving."));
          return false;
        }
        if (flushing.current) return flushing.current;
        if (!dirty.current && !saving.current) return true;
        setLeaving(true);
        clearTimeout(timer.current);
        const task = (async () => {
          try {
            if (saving.current) await saving.current;
            // A keystroke entered during the previous save belongs to a new revision.
            if (dirty.current) await save(false);
            return !dirty.current && !saveFailed.current;
          } finally {
            flushing.current = null;
            if (mounted.current) setLeaving(false);
          }
        })();
        flushing.current = task;
        return task;
      }),
    [save, voiceBusy, t],
  );

  useEffect(() => {
    if (!review) return;
    const frame = requestAnimationFrame(() =>
      document
        .getElementById("wizard-review-title")
        ?.focus({ preventScroll: true }),
    );
    return () => cancelAnimationFrame(frame);
  }, [review]);

  if (!form)
    return (
      <div className="baseline-loading">
        <ErrorNotice>{loadError}</ErrorNotice>
        {loadError ? (
          <Button className="secondary" onClick={loadForm}>
            {t("Retry loading questions")}
          </Button>
        ) : (
          <Loading label="Preparing your health information form…" />
        )}
      </div>
    );
  const fields = [
    ...form.groups.filter((g) => g.id !== "shared"),
    ...form.groups.filter((g) => g.id === "shared"),
  ].flatMap((group) => group.fields);
  const availableFields = fields.filter((field) => permitted(field));
  const stepFields = availableFields.filter((field) => !field.review_only);
  const current =
    availableFields.find((field) => fieldId(field) === activeField) ||
    stepFields.find(
      (field) =>
        answers[fieldId(field)]?.status === "MISSING" && !field.profile_reused,
    ) ||
    stepFields[0];
  if (!current)
    return (
      <Button className="primary" onClick={() => save(true)}>
        {t("Continue to AI analysis & follow-up")}
      </Button>
    );
  const key = fieldId(current);
  const dimension = dimensionFor(current);
  const index = stepFields.indexOf(current);
  const answer = answers[key] || initialAnswer(current);
  const group = form.groups.find((item) => item.fields.includes(current));
  const inputId = `answer-${current.concern_id}-${current.key}`;
  const options = withPainOptions(
    bodyOptionsFor(current.presentation),
    current.presentation,
  );
  const guided =
    ["choices", "body_map", "scale"].includes(current.presentation?.kind) &&
    options?.length > 0;
  const parsed = parseGuidedAnswer(answer.value, options);
  const resolved = stepFields.filter(
    (field) => answers[fieldId(field)]?.status !== "MISSING",
  ).length;
  const disabled = operation === "continuing" || leaving || organizing;
  const navigationDisabled = disabled || voiceBusy;
  const savedFields = fields.filter((field) => field.profile_reused);
  const previousAnswer = form.previous_answers?.[current.key];
  const priorDetails = availableFields.filter(
    (field) => field.review_only && answers[fieldId(field)]?.value,
  );
  const icon = current.key.includes("medication")
    ? "medicine"
    : current.key.includes("allerg")
      ? "shield"
      : current.key.includes("history")
        ? "file"
        : group?.workflow_id
          ? topicVisual({ id: group.workflow_id }).icon
          : "heart";
  function goTo(field) {
    if (!field || navigationDisabled) return;
    setActiveField(fieldId(field));
    setTimeout(() => document.getElementById("wizard-question")?.focus(), 0);
  }
  async function next() {
    if (navigationDisabled || organizingRef.current) return;
    if (
      current.key === "concern_description" &&
      answer.status === "FILLED" &&
      answer.value.trim() &&
      organizedDescriptions.current[key] !== answer.value
    ) {
      organizingRef.current = true;
      setOrganizing(true);
      setOrganizationNotice("");
      try {
        if (saving.current) await saving.current;
        if (dirty.current) await save(false);
        if (dirty.current || saveFailed.current || !mounted.current) return;
        const updated = await request(
          `/intakes/${session.id}/baseline/organize`,
          {
            method: "POST",
            body: { revision: serverRevision.current, locale },
          },
        );
        if (!mounted.current) return;
        serverRevision.current = updated.revision;
        onUpdateRef.current(updated);
        if (updated.status !== "active") return;
        organizedDescriptions.current[key] = answer.value;
        const reloaded = await loadForm({ after: key });
        if (!mounted.current || !reloaded) return;
        const filled = reloaded.groups.some((item) =>
          item.fields.some(
            (field) =>
              field.status === "FILLED" &&
              answers[fieldId(field)]?.status === "MISSING",
          ),
        );
        setOrganizationNotice(
          updated.ai_status?.mode !== "live" || !filled
            ? "Your description is saved. Continue at your own pace; you can review every answer."
            : "We’ve filled in details from your description. You can check or change them at any time.",
        );
        setTimeout(
          () => document.getElementById("wizard-question")?.focus(),
          0,
        );
      } catch (err) {
        // The description was already saved. Provider unavailability must not
        // trap the patient here or erase their manual answers.
        if (mounted.current) {
          if ([401, 403, 404, 409].includes(err.status)) {
            setError(err.message);
            return;
          }
          setOrganizationNotice(
            "Your description is saved. Continue at your own pace; you can review every answer.",
          );
          const nextField = stepFields
            .slice(index + 1)
            .find((field) => answers[fieldId(field)]?.status === "MISSING");
          if (nextField) setActiveField(fieldId(nextField));
          else setReview(true);
        }
      } finally {
        organizingRef.current = false;
        if (mounted.current) setOrganizing(false);
      }
      return;
    }
    if (current.review_only) {
      setReview(true);
      return;
    }
    const nextField = stepFields
      .slice(index + 1)
      .find((field) => answers[fieldId(field)]?.status === "MISSING");
    if (nextField) goTo(nextField);
    else setReview(true);
  }
  function appendText(text) {
    const combined = appendGuidedDetails(answer.value, text, options);
    if (combined.length > 6000) {
      setError(t("This answer is too long. Shorten it and try again."));
      return;
    }
    change(current, { value: combined });
  }
  return (
    <div className="intake-wizard">
      <div className="wizard-toolbar">
        <span>
          <Icon name="shield" size={16} />
          {t("YOUR PRIVATE PREPARATION")}
        </span>
        <span className="wizard-save" role="status">
          <Icon
            name={operation ? "clock" : dirty.current ? "file" : "check"}
            size={16}
          />
          {t(organizing ? "Organising what you shared…" : saveState)}
        </span>
      </div>
      <div
        className="wizard-progress"
        role="progressbar"
        aria-label={t("Preparation progress")}
        aria-valuenow={resolved}
        aria-valuemin={0}
        aria-valuemax={stepFields.length}
      >
        <span
          style={{
            width: `${(100 * resolved) / Math.max(1, stepFields.length)}%`,
          }}
        />
      </div>
      <ErrorNotice>{error}</ErrorNotice>
      {organizationNotice && (
        <p className="profile-prefilled" role="status">
          <Icon name="check" size={16} />
          <span>{t(organizationNotice)}</span>
        </p>
      )}
      {savedFields.length > 0 && (
        <div className="profile-prefilled">
          <Icon name="check" size={16} />
          <span>
            {t("Your saved background is filled in. No need to repeat it.")}
          </span>
          <button
            className="text-button"
            disabled={navigationDisabled}
            onClick={() => {
              setReview(false);
              goTo(savedFields[0]);
            }}
          >
            {t("Review saved details")}
          </button>
        </div>
      )}
      {review ? (
        <section className="wizard-review wizard-enter">
          <div className="wizard-emblem">
            <Icon name="check" size={38} />
          </div>
          <span className="overline">{t("LOOKING GOOD")}</span>
          <h2 id="wizard-review-title" tabIndex={-1}>
            {t("The essentials, in your own words.")}
          </h2>
          <p>
            {t(
              "Take a quick look. You can change any answer or continue with what you’ve shared.",
            )}
          </p>
          <SymptomOverview
            session={session}
            editableFields={availableFields}
            disabled={navigationDisabled}
            onEdit={(field) => {
              setReview(false);
              goTo(field);
            }}
          />
          <div className="wizard-review-list">
            {availableFields
              .filter(
                (field) =>
                  !field.review_only ||
                  answers[fieldId(field)]?.status !== "MISSING",
              )
              .map((field) => {
                const item = answers[fieldId(field)];
                return (
                  <button
                    key={fieldId(field)}
                    disabled={disabled}
                    onClick={() => {
                      setReview(false);
                      goTo(field);
                    }}
                  >
                    <Icon
                      name={item?.status === "FILLED" ? "check" : "file"}
                      size={18}
                    />
                    <span>
                      <strong>{t(field.label)}</strong>
                      <small>
                        {item?.status === "SKIPPED"
                          ? t("Prefer not to answer")
                          : item?.status === "UNCERTAIN"
                            ? `${t("I’m not sure")}${item?.value ? ` — ${recordedValue(item.value, t)}` : ""}`
                            : item?.value
                              ? recordedValue(item.value, t)
                              : t("Not answered yet")}
                      </small>
                    </span>
                    <Icon name="edit" size={17} />
                  </button>
                );
              })}
          </div>
          <div className="wizard-actions">
            <Button
              className="secondary"
              disabled={disabled}
              onClick={() => setReview(false)}
            >
              {t("Go back")}
            </Button>
            <Button
              className="primary"
              busy={disabled}
              onClick={() => save(true)}
            >
              {t("Continue to AI analysis & follow-up")}
              <Icon name="arrow" size={18} />
            </Button>
          </div>
        </section>
      ) : (
        <section className="wizard-question-card wizard-enter" key={key}>
          <div className="wizard-question-top">
            <span>{t(group?.title || "Your consultation")}</span>
            <span>
              {current.review_only
                ? t("Saved details")
                : `${index + 1} / ${stepFields.length}`}
            </span>
          </div>
          <div className="wizard-emblem">
            <Icon name={dimension?.icon || icon} size={36} />
            <span className="emblem-spark">
              <Icon name="sparkle" size={13} />
            </span>
          </div>
          <SymptomContext field={current} />
          <h2 id="wizard-question" tabIndex={-1}>
            {t(current.question || current.label)}
          </h2>
          <p className="wizard-question-hint">
            {t(
              current.hint ||
                dimension?.why ||
                (current.input_type === "permission"
                  ? "You decide what you’re comfortable sharing."
                  : guided
                    ? "Choose what fits, or tell us in your own words."
                    : "Tell us in your own words. You can type or use your voice."),
            )}
          </p>
          {current.input_type === "permission" ? (
            <div className="permission-choices">
              {[
                ["Yes", "Yes, I want to include these details"],
                ["No", "No, I prefer not to include these details"],
              ].map(([value, label]) => (
                <button
                  key={value}
                  type="button"
                  aria-pressed={answer.value === value}
                  disabled={disabled}
                  className={answer.value === value ? "selected" : ""}
                  onClick={() => change(current, { value, status: "FILLED" })}
                >
                  <Icon name={value === "Yes" ? "heart" : "lock"} size={23} />
                  <span>{t(label)}</span>
                </button>
              ))}
            </div>
          ) : (
            <>
              {answer.status !== "SKIPPED" && (
                <VoiceComposer
                  key={`voice-${key}`}
                  id={inputId}
                  value={guided ? parsed.details : answer.value}
                  onChange={(value) =>
                    change(current, {
                      value: guided
                        ? serializeGuidedAnswer({ ...parsed, details: value })
                        : value,
                    })
                  }
                  onError={setError}
                  onActivity={setVoiceBusy}
                  disabled={disabled}
                  placeholder={t(
                    guided
                      ? "Anything else you’d like to add?"
                      : "Type or tell us in your own words…",
                  )}
                />
              )}
              {guided && answer.status !== "SKIPPED" && (
                <GuidedField
                  key={key}
                  field={current}
                  inputId={inputId}
                  answer={answer}
                  hideDetails
                  hideHelper={
                    current.presentation?.helper ===
                    (current.hint || dimension?.why)
                  }
                  onFocus={() => {}}
                  onChange={(value) =>
                    change(current, {
                      value,
                      status: value.trim() ? "FILLED" : "MISSING",
                    })
                  }
                  disabled={disabled || voiceBusy}
                />
              )}
              {previousAnswer && (
                <aside className="previous-answer-card">
                  <div className="previous-answer-heading">
                    <Icon name="clock" size={18} />
                    <strong>{t("Your previous answer")}</strong>
                    <time dateTime={previousAnswer.recorded_at}>
                      {dateLabel(previousAnswer.recorded_at)}
                    </time>
                  </div>
                  <p className="previous-answer-value">
                    {previousAnswer.value}
                  </p>
                  <p className="field-hint">
                    {t(
                      "Check whether this is still accurate for this visit. Nothing is filled in until you choose it.",
                    )}
                  </p>
                  <Button
                    className="secondary"
                    disabled={
                      navigationDisabled ||
                      answer.value === previousAnswer.value
                    }
                    onClick={() =>
                      change(current, {
                        value: previousAnswer.value,
                        status: "FILLED",
                      })
                    }
                  >
                    <Icon name="check" size={16} />
                    {t("Use this answer for this visit")}
                  </Button>
                </aside>
              )}
              {current.key === "additional_information" &&
                priorDetails.length > 0 && (
                  <details className="remembered-details">
                    <summary>
                      <Icon name="file" size={18} />
                      {t("Already recorded — no need to repeat")}
                    </summary>
                    {priorDetails.map((field) => (
                      <div key={fieldId(field)}>
                        <strong>{t(field.label)}</strong>
                        <p>{answers[fieldId(field)].value}</p>
                        <button
                          type="button"
                          className="text-button"
                          disabled={navigationDisabled}
                          onClick={() => goTo(field)}
                        >
                          {t("Edit")}
                        </button>
                      </div>
                    ))}
                  </details>
                )}
              <div className="wizard-answer-status">
                <button
                  type="button"
                  aria-pressed={answer.status === "UNCERTAIN"}
                  disabled={navigationDisabled}
                  className={answer.status === "UNCERTAIN" ? "selected" : ""}
                  onClick={() =>
                    change(current, {
                      status:
                        answer.status === "UNCERTAIN"
                          ? answer.value
                            ? "FILLED"
                            : "MISSING"
                          : "UNCERTAIN",
                    })
                  }
                >
                  {t("I’m not sure")}
                </button>
                <button
                  type="button"
                  aria-pressed={answer.status === "SKIPPED"}
                  disabled={navigationDisabled}
                  className={answer.status === "SKIPPED" ? "selected" : ""}
                  onClick={() =>
                    change(current, {
                      status:
                        answer.status === "SKIPPED" ? "MISSING" : "SKIPPED",
                    })
                  }
                >
                  <Icon name="lock" size={13} />
                  {t("Prefer not to answer")}
                </button>
              </div>
            </>
          )}
          <div className="wizard-actions">
            <Button
              className="secondary"
              disabled={navigationDisabled || index <= 0}
              onClick={() => goTo(stepFields[index - 1])}
            >
              <Icon name="back" size={17} />
              {t("Go back")}
            </Button>
            <button
              type="button"
              className="text-button"
              disabled={navigationDisabled}
              onClick={() => setReview(true)}
            >
              {t("Review answers")}
            </button>
            <Button
              className="primary"
              disabled={navigationDisabled}
              busy={organizing}
              onClick={next}
            >
              {t(
                current.review_only || index === stepFields.length - 1
                  ? "Review answers"
                  : "Continue",
              )}
              <Icon name="arrow" size={17} />
            </Button>
          </div>
        </section>
      )}
      <details className="wizard-support">
        <summary>
          <Icon name="file" size={17} />
          {t("Add a document or revisit a question")}
          <Icon name="chevron" size={15} />
        </summary>
        <div className="wizard-support-grid">
          <div>
            <h3>{t("Your questions")}</h3>
            {availableFields.map((field) => (
              <button
                className="wizard-jump"
                key={fieldId(field)}
                disabled={navigationDisabled}
                onClick={() => {
                  setReview(false);
                  goTo(field);
                }}
              >
                <Icon
                  name={
                    answers[fieldId(field)]?.status === "MISSING"
                      ? "file"
                      : "check"
                  }
                  size={15}
                />
                <span>{t(field.label)}</span>
              </button>
            ))}
          </div>
          <Attachments
            session={session}
            onRefresh={refresh}
            onText={(text) => {
              appendText(text);
              setError(
                t(
                  "Document text was added to this answer. Review it before continuing.",
                ),
              );
            }}
            onError={setError}
          />
        </div>
      </details>
      <p className="wizard-privacy">
        <Icon name="lock" size={14} />
        {t("Private until you review and share.")}
      </p>
    </div>
  );
}

export function SynthesisSummary({
  synthesis,
  patientLocale,
  preserveApproved = false,
  doctor = false,
  onGenerate,
  busy,
  readOnly = false,
}) {
  const { t, locale } = useLocale();
  const [view, setView] = useState(doctor ? "clinician" : "patient");
  const [selectedSources, setSelectedSources] = useState(null);
  const outdated =
    synthesis?.status === "live" &&
    (synthesis.localization_outdated ||
      !synthesis.locale ||
      synthesis.locale !== (patientLocale || locale));
  const live = synthesis?.status === "live" && (!outdated || preserveApproved);
  const sources = synthesis?.sources || [];
  function citations(ids) {
    return ids?.length ? (
      <button
        className="source-link"
        type="button"
        onClick={() => setSelectedSources(ids)}
        aria-label={t("View {count} supporting sources", { count: ids.length })}
      >
        <Icon name="file" size={13} />
        {t("{count} sources", { count: ids.length })}
      </button>
    ) : null;
  }
  function prose(items) {
    return (
      <div className="synthesis-prose">
        {(items || []).map((item, i) => (
          <p key={i}>
            {item.text}
            {citations(item.source_ids)}
          </p>
        ))}
      </div>
    );
  }
  if (!live)
    return (
      <section className="synthesis-unavailable">
        <span className="assist-icon">
          <Icon name="sparkle" size={24} />
        </span>
        <div>
          <h3>
            {synthesis
              ? t("AI summary is currently unavailable")
              : t("This record contains structured notes")}
          </h3>
          <p>
            {t(
              outdated
                ? "Prepare the summary again to use your selected language. Your recorded answers remain saved."
                : synthesis?.message ||
                    "Generate a concise AI summary from the information you’ve provided. Every statement is linked to the underlying facts.",
            )}
          </p>
          {readOnly ? (
            <p className="field-hint">
              {t(
                "The approved version is shown exactly as shared. Its content cannot be changed here.",
              )}
            </p>
          ) : (
            <Button
              className="primary"
              icon="sparkle"
              busy={busy}
              onClick={onGenerate}
            >
              {t("Generate AI summary")}
            </Button>
          )}
        </div>
      </section>
    );
  const selected = selectedSources
    ? sources.filter((source) => selectedSources.includes(source.id))
    : [];
  return (
    <section className="synthesis-summary">
      {outdated && preserveApproved && (
        <p className="notice notice-info" role="status">
          {t(
            "This shared report keeps the language approved by the patient. Withdraw sharing before preparing a new version in another language.",
          )}
        </p>
      )}
      <div className="synthesis-heading">
        <div className="synthesis-label">
          <Icon name="sparkle" size={19} />
          <strong>{t("AI consultation summary")}</strong>
        </div>
        <span>{t("Based on your recorded information")}</span>
      </div>
      <div
        className="summary-view-switch"
        role="group"
        aria-label={t("Summary perspective")}
      >
        <button
          type="button"
          className={view === "patient" ? "active" : ""}
          aria-pressed={view === "patient"}
          onClick={() => setView("patient")}
        >
          <Icon name="person" size={17} />
          {t("Patient overview")}
        </button>
        <button
          type="button"
          className={view === "clinician" ? "active" : ""}
          aria-pressed={view === "clinician"}
          onClick={() => setView("clinician")}
        >
          <Icon name="file" size={17} />
          {t("Clinician brief")}
        </button>
      </div>
      <div className="synthesis-section">
        <h3>
          {view === "patient"
            ? t("Your situation, in plain language")
            : t("Pre-consultation brief")}
        </h3>
        {prose(
          view === "patient"
            ? synthesis.patient_overview
            : synthesis.clinician_brief,
        )}
      </div>
      {synthesis.concern_summaries?.length > 0 && (
        <div className="synthesis-section">
          <h3>{t("By concern")}</h3>
          <div className="synthesis-concerns">
            {synthesis.concern_summaries.map((concern, i) => (
              <article key={concern.concern_id || i}>
                <h4>{recordTitle(concern.title, t)}</h4>
                <p>
                  {concern.summary}
                  {citations(concern.source_ids)}
                </p>
              </article>
            ))}
          </div>
        </div>
      )}
      {synthesis.appointment_agenda?.length > 0 && (
        <div className="synthesis-section agenda-section">
          <h3>
            <Icon name="check" size={19} />
            {t("Your appointment agenda")}
          </h3>
          <ol>
            {synthesis.appointment_agenda.map((item, i) => (
              <li key={i}>
                {item.text}
                {citations(item.source_ids)}
              </li>
            ))}
          </ol>
        </div>
      )}
      {synthesis.uncertainties?.length > 0 && (
        <div className="synthesis-section uncertainty-section">
          <h3>
            <Icon name="info" size={19} />
            {t("Points to clarify")}
          </h3>
          {prose(synthesis.uncertainties)}
        </div>
      )}
      <details className="synthesis-sources">
        <summary>
          <Icon name="file" size={17} />
          <span>
            {t("Source information ({count})", { count: sources.length })}
          </span>
          <Icon name="chevron" size={17} />
        </summary>
        <p>
          {t(
            "These are the current patient-provided facts used in the summary. Original wording is preserved here, including any original-language details.",
          )}
        </p>
        <dl>
          {sources.map((source) => (
            <div key={source.id}>
              <dt>
                {recordLabel(source.label, t)}
                <span>{slotStatusLabel(source.status, t)}</span>
              </dt>
              <dd>{recordedValue(source.value, t)}</dd>
            </div>
          ))}
        </dl>
      </details>
      <div className="synthesis-meta">
        <span>{synthesis.model}</span>
        <span>{dateLabel(synthesis.generated_at, true)}</span>
      </div>
      {!doctor && (
        <p className="summary-translation-note">
          {t(
            "Please check that this summary accurately reflects your own words, including any translated details, before approving it.",
          )}
        </p>
      )}
      {selectedSources && (
        <Modal
          title={t("Supporting information")}
          onClose={() => setSelectedSources(null)}
        >
          <p className="modal-copy">
            {t(
              "This statement is based on the following information you provided.",
            )}
          </p>
          <dl className="source-modal-list">
            {selected.map((source) => (
              <div key={source.id}>
                <dt>{recordLabel(source.label, t)}</dt>
                <dd>
                  {recordedValue(source.value, t)}
                  <small>{slotStatusLabel(source.status, t)}</small>
                </dd>
              </div>
            ))}
          </dl>
          {!selected.length && (
            <p className="modal-copy">
              {t("No matching source is available in this version.")}
            </p>
          )}
          <div className="modal-actions">
            <Button
              className="primary"
              onClick={() => setSelectedSources(null)}
            >
              {t("Done")}
            </Button>
          </div>
        </Modal>
      )}
    </section>
  );
}
