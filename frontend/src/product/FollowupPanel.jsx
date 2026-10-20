import React, { useCallback, useEffect, useRef, useState } from "react";
import Icon from "./Icons.jsx";
import VoiceComposer from "./VoiceComposer.jsx";
import { Button, ErrorNotice } from "./UI.jsx";
import { request } from "./api.js";
import { useLocale } from "./i18n.jsx";
import { registerNavigationGuard } from "./navigation.js";
import {
  answerIsComplete,
  followupDraft,
  followupPayload,
} from "./followupModel.js";
import "./followup.css";
import { followupAnswerText } from "./recordLocale.js";

/** One question per step; the complete set is reviewed and submitted together. */
export default function FollowupPanel({ session, onUpdate, renderContext }) {
  const { t, locale } = useLocale();
  const batch = session.followup_batch;
  const questions = batch.questions || [];
  const pending = batch.status === "pending" && session.status === "active";
  const dismissed = batch.status === "dismissed";
  const baselineChanged =
    dismissed && batch.invalidated_reason === "baseline_changed";
  const [answers, setAnswers] = useState(() => followupDraft(batch));
  const [step, setStep] = useState(() => {
    const saved = followupDraft(batch);
    const firstUnanswered = questions.findIndex(
      (question) => !answerIsComplete(saved[question.id]),
    );
    return firstUnanswered < 0 ? questions.length : firstUnanswered;
  });
  const [editingReview, setEditingReview] = useState(false);
  const [moving, setMoving] = useState(false);
  const [version, setVersion] = useState(0);
  const [saveState, setSaveState] = useState("Saved");
  const [error, setError] = useState("");
  const [action, setAction] = useState("");
  const [saving, setSaving] = useState(false);
  const [activeVoice, setActiveVoice] = useState(null);
  const [leaving, setLeaving] = useState(false);
  const latest = useRef(answers);
  const dirty = useRef(false);
  const mounted = useRef(true);
  const revision = useRef(session.revision);
  const editVersion = useRef(0);
  const savePromise = useRef(null);
  const timer = useRef(null);
  const updateRef = useRef(onUpdate);
  const actionRef = useRef(action);
  const voiceRef = useRef(activeVoice);
  const questionsRef = useRef(questions);
  const movingRef = useRef(false);
  const stepHeading = useRef(null);
  const didNavigate = useRef(false);
  updateRef.current = onUpdate;
  actionRef.current = action;
  voiceRef.current = activeVoice;
  questionsRef.current = questions;

  useEffect(() => {
    if (!didNavigate.current) return;
    stepHeading.current?.focus({ preventScroll: true });
    stepHeading.current?.scrollIntoView({ block: "start", behavior: "auto" });
  }, [step]);

  useEffect(() => {
    if (!savePromise.current) revision.current = session.revision;
  }, [session.revision]);

  useEffect(() => {
    mounted.current = true;
    const warn = (event) => {
      if (dirty.current || actionRef.current || voiceRef.current) {
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
  }, []);

  const saveDraft = useCallback(async () => {
    clearTimeout(timer.current);
    if (savePromise.current) await savePromise.current;
    if (!dirty.current || !mounted.current) return !dirty.current;
    const snapshotVersion = editVersion.current;
    const snapshot = followupPayload(questionsRef.current, latest.current);
    setSaving(true);
    setSaveState("Saving…");
    const task = (async () => {
      try {
        const updated = await request(`/intakes/${session.id}/followup/draft`, {
          method: "PUT",
          body: {
            batch_id: batch.id,
            answers: snapshot,
            revision: revision.current,
          },
        });
        if (!mounted.current) return false;
        revision.current = updated.revision;
        if (snapshotVersion === editVersion.current) dirty.current = false;
        setSaveState(dirty.current ? "Unsaved changes" : "All changes saved");
        updateRef.current(updated);
        return true;
      } catch (err) {
        if (mounted.current) {
          setError(err.message);
          setSaveState("Could not save — try again");
        }
        return false;
      } finally {
        savePromise.current = null;
        if (mounted.current) setSaving(false);
      }
    })();
    savePromise.current = task;
    return task;
  }, [session.id, batch.id]);

  useEffect(() => {
    if (
      !pending ||
      !dirty.current ||
      saving ||
      action ||
      saveState === "Could not save — try again"
    )
      return;
    timer.current = setTimeout(saveDraft, 700);
    return () => clearTimeout(timer.current);
  }, [version, pending, saving, action, saveState, saveDraft]);

  useEffect(
    () =>
      registerNavigationGuard(async () => {
        if (actionRef.current || movingRef.current) return false;
        if (voiceRef.current) {
          setError(t("Finish or cancel voice input before leaving."));
          return false;
        }
        setLeaving(true);
        try {
          const saved = await saveDraft();
          return saved && !dirty.current;
        } finally {
          if (mounted.current) setLeaving(false);
        }
      }),
    [saveDraft, t],
  );

  function change(questionId, value, status) {
    const next = {
      ...latest.current,
      [questionId]: {
        question_id: questionId,
        value,
        status: status || (value.trim() ? "FILLED" : "MISSING"),
      },
    };
    latest.current = next;
    editVersion.current += 1;
    dirty.current = true;
    setAnswers(next);
    setVersion(editVersion.current);
    setSaveState("Unsaved changes");
    setError("");
  }

  async function goToStep(nextStep, fromReview = false) {
    if (actionRef.current || voiceRef.current || movingRef.current) return;
    movingRef.current = true;
    setMoving(true);
    try {
      const saved = await saveDraft();
      if (!saved || dirty.current || !mounted.current) return;
      setError("");
      setEditingReview(fromReview);
      didNavigate.current = true;
      setStep(nextStep);
    } finally {
      movingRef.current = false;
      if (mounted.current) setMoving(false);
    }
  }

  async function review() {
    const next = await request(`/intakes/${session.id}/review`, {
      method: "POST",
      body: { locale },
    });
    if (mounted.current) updateRef.current(next);
  }

  async function submit() {
    if (actionRef.current || voiceRef.current || movingRef.current) return;
    if (!pending && session.status === "review") {
      updateRef.current(session);
      return;
    }
    const payload = followupPayload(questions, latest.current);
    if (pending && payload.some((answer) => answer.status === "MISSING"))
      return;
    actionRef.current = "submit";
    setAction("submit");
    setError("");
    clearTimeout(timer.current);
    try {
      if (savePromise.current) await savePromise.current;
      if (pending) {
        const next = await request(`/intakes/${session.id}/followup/answers`, {
          method: "POST",
          body: {
            batch_id: batch.id,
            answers: payload,
            revision: revision.current,
            locale,
          },
        });
        dirty.current = false;
        revision.current = next.revision;
        if (!mounted.current) return;
        setSaveState("All changes saved");
        updateRef.current(next);
        if (
          next.status !== "active" ||
          next.followup_batch?.status === "pending"
        )
          return;
      }
      await review();
    } catch (err) {
      if (mounted.current) setError(err.message);
    } finally {
      actionRef.current = "";
      if (mounted.current) setAction("");
    }
  }

  const answered = questions.filter((question) =>
    answerIsComplete(answers[question.id]),
  ).length;
  const reviewing = step >= questions.length;
  const currentAnswer = answers[questions[step]?.id];
  const blocked = !!action || leaving || !!activeVoice || moving;
  return (
    <div
      className={`conversation-workspace followup-workspace ${pending ? "followup-wizard" : ""}`}
    >
      <section className="followup-main" aria-labelledby="followup-title">
        <header className="followup-intro">
          <div className="wizard-emblem">
            <Icon name="sparkle" size={30} />
          </div>
          <span className="overline">{t("AI analysis & follow-up")}</span>
          <h2 id="followup-title">
            {t(
              baselineChanged
                ? "Your health information has changed."
                : dismissed
                  ? "This question set is closed."
                  : pending
                    ? "One question at a time."
                    : "Your answers are ready.",
            )}
          </h2>
          <p>
            {t(
              baselineChanged
                ? "The earlier questions no longer apply. Review your summary using your updated information."
                : dismissed
                  ? "You can review your summary. Unsubmitted drafts are kept below for reference."
                  : pending
                    ? "Take it one step at a time. Your answers are saved as you go; review them together at the end."
                    : "Your follow-up answers have been saved. Continue to review your consultation summary.",
            )}
          </p>
        </header>
        {!dismissed && batch.second_round_reason && (
          <div className="followup-exception" role="status">
            <Icon name="info" size={20} />
            <div>
              <strong>{t("A necessary clarification")}</strong>
              <p>{t(batch.second_round_reason)}</p>
            </div>
          </div>
        )}
        {!dismissed && batch.overview && (
          <details className="followup-overview followup-analysis">
            <summary>
              <Icon name="sparkle" size={19} />
              <strong>{t("What we’re clarifying")}</strong>
              <Icon name="chevron" size={16} />
            </summary>
            <p>{t(batch.overview)}</p>
          </details>
        )}
        <ErrorNotice>{error}</ErrorNotice>
        {pending ? (
          <>
            <div className="followup-progress" role="status">
              <span>
                {reviewing
                  ? t("{answered} of {count} answered", {
                      answered,
                      count: questions.length,
                    })
                  : t("Question {number} of {count}", {
                      number: step + 1,
                      count: questions.length,
                    })}
              </span>
              <span className="followup-save">
                <Icon name={saving ? "clock" : "check"} size={15} />
                {t(saveState)}
                {saveState === "Could not save — try again" && (
                  <button
                    className="text-button"
                    onClick={saveDraft}
                    disabled={blocked}
                  >
                    {t("Try again")}
                  </button>
                )}
              </span>
            </div>
            <div
              className="followup-step-progress"
              role="progressbar"
              aria-label={t("Follow-up progress")}
              aria-valuenow={answered}
              aria-valuemin={0}
              aria-valuemax={questions.length}
            >
              <span
                style={{
                  width: `${(100 * answered) / Math.max(1, questions.length)}%`,
                }}
              />
            </div>
            {reviewing ? (
              <section
                className="followup-review wizard-enter"
                aria-labelledby="followup-review-title"
              >
                <div className="wizard-emblem">
                  <Icon name="check" size={30} />
                </div>
                <h3 id="followup-review-title" tabIndex={-1} ref={stepHeading}>
                  {t("Review your follow-up answers")}
                </h3>
                <p>
                  {t(
                    "Check your answers before submitting. You can return to any question to make a change.",
                  )}
                </p>
                <div className="followup-review-list">
                  {questions.map((question, index) => {
                    const answer = answers[question.id];
                    return (
                      <div className="followup-review-answer" key={question.id}>
                        <span className="followup-number" aria-hidden="true">
                          {String(index + 1).padStart(2, "0")}
                        </span>
                        <div>
                          <h4>{t(question.question)}</h4>
                          <p>
                            {answer?.status === "FILLED"
                              ? followupAnswerText(question, answer, t)
                              : t(
                                  answer?.status === "UNCERTAIN"
                                    ? "I don’t know"
                                    : answer?.status === "SKIPPED"
                                      ? "Skip this question"
                                      : "Not answered",
                                )}
                          </p>
                        </div>
                        <button
                          type="button"
                          className="text-button"
                          aria-label={t("Edit answer {number}", {
                            number: index + 1,
                          })}
                          disabled={blocked}
                          onClick={() => goToStep(index, true)}
                        >
                          {t("Edit")}
                        </button>
                      </div>
                    );
                  })}
                </div>
              </section>
            ) : (
              <div className="followup-questions">
                {questions.map((question, index) => {
                  if (index !== step) return null;
                  const answer = answers[question.id];
                  const options = question.options || [];
                  const inputId = `followup-answer-${index}`;
                  const disabled =
                    !!action ||
                    leaving ||
                    moving ||
                    (!!activeVoice && activeVoice !== question.id);
                  const voiceHere = activeVoice === question.id;
                  return (
                    <section
                      className={`followup-question wizard-enter ${answerIsComplete(answer) ? "is-answered" : ""}`}
                      key={question.id}
                      aria-labelledby={`followup-question-${index}`}
                    >
                      <div className="followup-question-heading">
                        <span className="followup-number" aria-hidden="true">
                          {String(index + 1).padStart(2, "0")}
                        </span>
                        <div>
                          <h3
                            id={`followup-question-${index}`}
                            tabIndex={-1}
                            ref={stepHeading}
                          >
                            {t(question.question)}
                          </h3>
                          {question.why && (
                            <p className="followup-why">{t(question.why)}</p>
                          )}
                        </div>
                        {answerIsComplete(answer) && (
                          <span
                            className="followup-done"
                            role="img"
                            aria-label={t("Answered")}
                          >
                            <Icon name="check" size={17} />
                          </span>
                        )}
                      </div>
                      {options.length > 0 && (
                        <div
                          className="followup-options"
                          role="group"
                          aria-label={t("Suggested answers")}
                        >
                          {options.map((option, optionIndex) => {
                            const selected =
                              answer?.status === "FILLED" &&
                              answer.value === option.value;
                            return (
                              <button
                                type="button"
                                key={option.id}
                                className={`followup-option ${selected ? "selected" : ""}`}
                                aria-pressed={selected}
                                disabled={disabled || voiceHere}
                                onClick={() =>
                                  change(
                                    question.id,
                                    selected ? "" : option.value,
                                  )
                                }
                              >
                                <span className="followup-letter">
                                  {String.fromCharCode(65 + optionIndex)}
                                </span>
                                <span>{t(option.label)}</span>
                                {selected && <Icon name="check" size={16} />}
                              </button>
                            );
                          })}
                        </div>
                      )}
                      <label
                        className="followup-answer-label"
                        htmlFor={inputId}
                      >
                        {t(
                          options.length
                            ? "Your answer — edit or add your own details"
                            : "Your answer",
                        )}
                      </label>
                      <VoiceComposer
                        id={inputId}
                        value={followupAnswerText(question, answer, t)}
                        onChange={(value) => change(question.id, value)}
                        disabled={disabled}
                        maxLength={6000}
                        onError={setError}
                        onActivity={(active) =>
                          setActiveVoice((current) =>
                            active
                              ? question.id
                              : current === question.id
                                ? null
                                : current,
                          )
                        }
                        placeholder={t(
                          options.length
                            ? "Choose above, or type or speak your own answer…"
                            : "Type or speak in your own words…",
                        )}
                      />
                      <div className="followup-answer-actions">
                        {[
                          ["UNCERTAIN", "I don’t know"],
                          ["SKIPPED", "Skip this question"],
                        ].map(([status, label]) => (
                          <button
                            key={status}
                            type="button"
                            className={`followup-status ${answer?.status === status ? "selected" : ""}`}
                            aria-pressed={answer?.status === status}
                            disabled={disabled || voiceHere}
                            onClick={() =>
                              change(
                                question.id,
                                "",
                                answer?.status === status ? "MISSING" : status,
                              )
                            }
                          >
                            {t(label)}
                          </button>
                        ))}
                      </div>
                    </section>
                  );
                })}
              </div>
            )}
          </>
        ) : dismissed ? (
          <>
            {(batch.draft_answers || []).some(
              (answer) => answer.status !== "MISSING",
            ) && (
              <details className="followup-history">
                <summary>{t("Earlier draft answers (not submitted)")}</summary>
                <p>
                  {t(
                    "These earlier drafts are for your reference and are not included as confirmed answers.",
                  )}
                </p>
                {batch.draft_answers
                  .filter((answer) => answer.status !== "MISSING")
                  .map((answer) => (
                    <div key={answer.question_id}>
                      <strong>
                        {t(
                          questions.find(
                            (question) => question.id === answer.question_id,
                          )?.question || "Your answer",
                        )}
                      </strong>
                      <p>
                        {answer.status === "FILLED"
                          ? followupAnswerText(questions.find((question) => question.id === answer.question_id), answer, t)
                          : t(
                              answer.status === "UNCERTAIN"
                                ? "I don’t know"
                                : "Skip this question",
                            )}
                      </p>
                    </div>
                  ))}
              </details>
            )}
          </>
        ) : (
          <div className="followup-complete">
            <Icon name="check" size={24} />
            <span>{t("All follow-up answers saved")}</span>
          </div>
        )}
        {pending ? (
          <>
            <footer className="followup-footer followup-step-navigation">
              <Button
                className="secondary"
                disabled={blocked || step === 0}
                onClick={() => goToStep(Math.max(0, step - 1))}
              >
                <Icon name="arrow" size={17} className="followup-back-arrow" />
                {t("Previous question")}
              </Button>
              {reviewing ? (
                <Button
                  className="primary"
                  icon="arrow"
                  busy={!!action}
                  disabled={blocked || answered !== questions.length}
                  onClick={submit}
                >
                  {t(
                    action
                      ? "Preparing your summary…"
                      : "Submit answers & continue",
                  )}
                </Button>
              ) : (
                <Button
                  className="primary"
                  icon="arrow"
                  busy={moving}
                  disabled={blocked || !answerIsComplete(currentAnswer)}
                  onClick={() =>
                    goToStep(editingReview ? questions.length : step + 1)
                  }
                >
                  {t(
                    editingReview || step === questions.length - 1
                      ? "Review answers"
                      : "Next question",
                  )}
                </Button>
              )}
            </footer>
            <p className="followup-step-hint">
              {t(
                reviewing
                  ? "You can review and edit your summary before sharing."
                  : "Choose an answer, write your own, or select “I don’t know” or “Skip”.",
              )}
            </p>
          </>
        ) : (
          <footer className="followup-footer">
            <p>
              {t(
                pending
                  ? "Answer each question, or choose “I don’t know” or “Skip”."
                  : "You can review and edit your summary before sharing.",
              )}
            </p>
            <Button
              className="primary"
              icon="arrow"
              busy={!!action}
              disabled={blocked || (pending && answered !== questions.length)}
              onClick={submit}
            >
              {t(
                action
                  ? "Preparing your summary…"
                  : pending
                    ? "Submit answers & continue"
                    : "Review my summary",
              )}
            </Button>
          </footer>
        )}
        <p className="wizard-privacy">
          <Icon name="lock" size={14} />
          {t("Private until you review and share.")}
        </p>
      </section>
      {renderContext?.({ blocked: blocked || saving, onError: setError })}
    </div>
  );
}
