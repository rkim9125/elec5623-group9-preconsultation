import React, { useCallback, useEffect, useRef, useState } from "react";
import Icon from "./Icons.jsx";
import { request, dateLabel } from "./api.js";
import { Button, ErrorNotice, Loading, Modal } from "./UI.jsx";
import { registerNavigationGuard } from "./navigation.js";

const stages = [
  "Your concerns",
  "Health information",
  "AI follow-up",
  "Review & share",
];
export function JourneyNavigation({ current = 0, onSelect, completed = 0 }) {
  return (
    <nav className="journey-navigation" aria-label="Consultation stages">
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
              <strong>{label}</strong>
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
  VoiceInput,
  Attachments,
  onContinue,
}) {
  const [form, setForm] = useState(null);
  const [answers, setAnswers] = useState({});
  const [open, setOpen] = useState({});
  const [activeField, setActiveField] = useState("");
  const [error, setError] = useState("");
  const [loadError, setLoadError] = useState("");
  const [operation, setOperation] = useState("");
  const [saveState, setSaveState] = useState("Saved");
  const [capture, setCapture] = useState(null);
  const [capturedText, setCapturedText] = useState("");
  const [captureTarget, setCaptureTarget] = useState("");
  const [revision, setRevision] = useState(0);
  const [leaving, setLeaving] = useState(false);
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

  const loadForm = useCallback(async () => {
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
      setOpen({ [result.groups[0]?.id]: true });
      const first = result.groups
        .flatMap((group) => group.fields)
        .find((field) => !field.requires_permission);
      if (first) {
        setActiveField(fieldId(first));
        setCaptureTarget(fieldId(first));
      }
    } catch (err) {
      if (mounted.current) setLoadError(err.message);
    }
  }, [session.id]);
  useEffect(() => {
    mounted.current = true;
    loadForm();
    const warn = (event) => {
      if (dirty.current) {
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
      updated.status = patch.value.trim() ? "FILLED" : "MISSING";
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
      setSaveState(complete ? "Preparing relevant follow-up…" : "Saving…");
      const task = (async () => {
        try {
          const updated = await request(`/intakes/${session.id}/baseline`, {
            method: "PUT",
            body: {
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
    [session.id, onContinue],
  );
  useEffect(() => {
    if (!dirty.current || operation || saveFailed.current) return;
    timer.current = setTimeout(() => save(false), 1400);
    return () => clearTimeout(timer.current);
  }, [revision, operation, save]);

  useEffect(
    () =>
      registerNavigationGuard(async () => {
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
    [save],
  );

  if (!form)
    return (
      <div className="baseline-loading">
        <ErrorNotice>{loadError}</ErrorNotice>
        {loadError ? (
          <Button className="secondary" onClick={loadForm}>
            Retry loading questions
          </Button>
        ) : (
          <Loading label="Preparing your health information form…" />
        )}
      </div>
    );
  const fields = form.groups.flatMap((group) => group.fields);
  const availableFields = fields.filter(
    (field) => permitted(field) && field.input_type !== "permission",
  );
  const resolved = fields.filter(
    (field) => answers[fieldId(field)]?.status !== "MISSING",
  ).length;
  const disabled = operation === "continuing" || leaving;
  function reviewCapture(text, kind) {
    setCapture(kind);
    setCapturedText(text);
    setCaptureTarget(
      availableFields.some((field) => fieldId(field) === activeField)
        ? activeField
        : fieldId(availableFields[0] || {}),
    );
  }
  function insertCapture() {
    const field = fields.find((item) => fieldId(item) === captureTarget);
    if (!field || !permitted(field)) return;
    const previous = latest.current[captureTarget]?.value || "";
    const combined = previous
      ? `${previous}\n\n${capturedText.trim()}`
      : capturedText.trim();
    if (combined.length > 6000) {
      setError(
        "The combined answer is longer than 6,000 characters. Shorten the reviewed text before adding it.",
      );
      return;
    }
    change(field, { value: combined });
    setOpen((value) => ({
      ...value,
      [form.groups.find((group) =>
        group.fields.some((item) => fieldId(item) === captureTarget),
      )?.id]: true,
    }));
    setCapture(null);
  }
  return (
    <div className="baseline-layout">
      <section className="baseline-main">
        <div className="baseline-intro">
          <span className="section-kicker">
            STEP 2 · YOUR HEALTH INFORMATION
          </span>
          <h2>The essentials, all in one place.</h2>
          <p>
            Complete the questions that matter to you. You can leave a question
            unanswered, mark it unknown, or choose not to share. Your draft
            saves automatically.
          </p>
          <div className="baseline-save-status" role="status">
            <Icon
              name={operation ? "clock" : dirty.current ? "file" : "check"}
              size={17}
            />
            <span>{saveState}</span>
            <span>
              {resolved} of {fields.length} questions addressed
            </span>
          </div>
        </div>
        <ErrorNotice>{error}</ErrorNotice>
        <div className="baseline-groups">
          {form.groups.map((group, groupIndex) => {
            const count = group.fields.filter(
              (field) => answers[fieldId(field)]?.status !== "MISSING",
            ).length;
            return (
              <section
                className={`baseline-group ${open[group.id] ? "expanded" : ""}`}
                key={group.id}
              >
                <button
                  className="baseline-group-toggle"
                  type="button"
                  aria-expanded={!!open[group.id]}
                  aria-controls={`group-${group.id}`}
                  onClick={() =>
                    setOpen((value) => ({
                      ...value,
                      [group.id]: !value[group.id],
                    }))
                  }
                >
                  <span className="group-number">
                    {String(groupIndex + 1).padStart(2, "0")}
                  </span>
                  <span>
                    <strong>{group.title}</strong>
                    <small>
                      {group.description ||
                        `${group.fields.length} questions for your consultation`}
                    </small>
                  </span>
                  <span className="group-count">
                    {count}/{group.fields.length}
                  </span>
                  <Icon name="chevron" size={19} />
                </button>
                <div
                  id={`group-${group.id}`}
                  hidden={!open[group.id]}
                  className="baseline-fields"
                >
                  {group.fields.map((field) => {
                    const key = fieldId(field);
                    const answer = answers[key] || initialAnswer(field);
                    if (!permitted(field)) return null;
                    const inputId = `answer-${field.concern_id}-${field.key}`;
                    const permission = field.input_type === "permission";
                    return (
                      <div className="baseline-field" key={key}>
                        <label htmlFor={inputId}>
                          {field.question || field.label}
                        </label>
                        {field.label && field.label !== field.question && (
                          <span className="baseline-field-caption">
                            {field.label}
                          </span>
                        )}
                        {permission ? (
                          <select
                            id={inputId}
                            data-testid={`baseline-${field.concern_id}-${field.key}`}
                            className="select full"
                            value={answer.value}
                            onChange={(event) =>
                              change(field, {
                                value: event.target.value,
                                status: event.target.value
                                  ? "FILLED"
                                  : "MISSING",
                              })
                            }
                            disabled={disabled}
                          >
                            <option value="">
                              Choose whether to include this information
                            </option>
                            <option value="Yes">
                              Yes, I want to include these details
                            </option>
                            <option value="No">
                              No, I prefer not to include these details
                            </option>
                          </select>
                        ) : (
                          <>
                            {answer.status !== "SKIPPED" && (
                              <textarea
                                id={inputId}
                                data-testid={`baseline-${field.concern_id}-${field.key}`}
                                rows={2}
                                value={answer.value}
                                maxLength={6000}
                                placeholder={
                                  answer.status === "UNCERTAIN"
                                    ? "Optional: add what you remember or what you’re unsure about…"
                                    : "Your answer…"
                                }
                                onFocus={() => setActiveField(key)}
                                onChange={(event) =>
                                  change(field, {
                                    value: event.target.value,
                                    ...(answer.status === "UNCERTAIN"
                                      ? { status: "UNCERTAIN" }
                                      : {}),
                                  })
                                }
                                disabled={disabled}
                              />
                            )}
                            <div className="field-answer-controls">
                              <label htmlFor={`status-${inputId}`}>
                                Answer status
                              </label>
                              <select
                                id={`status-${inputId}`}
                                data-testid={`baseline-status-${field.concern_id}-${field.key}`}
                                className="select answer-status"
                                value={answer.status}
                                onChange={(event) =>
                                  change(field, { status: event.target.value })
                                }
                                disabled={disabled}
                              >
                                <option value="MISSING">
                                  Not answered yet
                                </option>
                                <option value="FILLED">
                                  Answered in my words
                                </option>
                                <option value="UNCERTAIN">I’m not sure</option>
                                <option value="SKIPPED">
                                  Prefer not to answer
                                </option>
                              </select>
                              {answer.status === "SKIPPED" && (
                                <span className="private-answer-note">
                                  <Icon name="lock" size={14} />
                                  No answer will be shared
                                </span>
                              )}
                            </div>
                          </>
                        )}
                      </div>
                    );
                  })}
                  <button
                    className="text-button group-next"
                    type="button"
                    onClick={() => {
                      const next = form.groups[groupIndex + 1];
                      if (next) {
                        setOpen((value) => ({ ...value, [next.id]: true }));
                        setTimeout(
                          () =>
                            document
                              .getElementById(`group-${next.id}`)
                              ?.parentElement?.scrollIntoView({
                                behavior: "smooth",
                                block: "start",
                              }),
                          30,
                        );
                      } else
                        document
                          .getElementById("baseline-continue")
                          ?.scrollIntoView({
                            behavior: "smooth",
                            block: "center",
                          });
                    }}
                  >
                    {groupIndex < form.groups.length - 1
                      ? "Next section"
                      : "Continue when ready"}
                    <Icon name="arrow" size={17} />
                  </button>
                </div>
              </section>
            );
          })}
        </div>
        <div className="baseline-continue" id="baseline-continue">
          <div>
            <h3>Ready for the next step?</h3>
            <p>
              The assistant will consider your answers and ask only relevant
              additional questions. Unanswered items remain clearly marked.
            </p>
          </div>
          <div className="baseline-continue-actions">
            <Button
              className="secondary"
              busy={operation === "saving"}
              disabled={disabled || !dirty.current}
              onClick={() => save(false)}
            >
              Save draft
            </Button>
            <Button
              className="primary"
              busy={disabled}
              onClick={() => save(true)}
            >
              Continue to AI follow-up
              <Icon name="arrow" size={17} />
            </Button>
          </div>
        </div>
      </section>
      <aside className="baseline-aside">
        <div className="baseline-help-card">
          <span className="assist-icon">
            <Icon name="sparkle" size={23} />
          </span>
          <h3>Write it, say it, or add a document.</h3>
          <p>
            Use your own words. You’ll review any transcript or extracted text
            before it is added to an answer.
          </p>
          <label className="field-label" htmlFor="voice-target">
            Voice answer for
          </label>
          <select
            id="voice-target"
            className="select full"
            value={activeField}
            onChange={(event) => setActiveField(event.target.value)}
            disabled={disabled}
          >
            {availableFields.map((field) => (
              <option key={fieldId(field)} value={fieldId(field)}>
                {
                  form.groups.find((group) => group.fields.includes(field))
                    ?.title
                }{" "}
                · {field.label || field.question}
              </option>
            ))}
          </select>
          <VoiceInput
            disabled={disabled || !availableFields.length}
            onTranscript={(text) => reviewCapture(text, "Voice transcript")}
            onError={setError}
          />
        </div>
        <Attachments
          session={session}
          onRefresh={refresh}
          onText={(text) => reviewCapture(text, "Extracted document details")}
          onError={setError}
        />
        <div className="baseline-privacy">
          <Icon name="shield" size={21} />
          <p>
            This is your private draft. Nothing is shared with your doctor until
            you review the summary and approve it.
          </p>
        </div>
      </aside>
      {capture && (
        <Modal
          title={`Review ${capture.toLowerCase()}`}
          onClose={() => setCapture(null)}
          wide
        >
          <p className="modal-copy">
            Check the wording and choose the answer this belongs to. Nothing is
            added until you confirm.
          </p>
          <label className="field-label" htmlFor="captured-answer">
            Reviewed text
          </label>
          <textarea
            id="captured-answer"
            rows={8}
            value={capturedText}
            onChange={(event) => setCapturedText(event.target.value)}
            maxLength={6000}
          />
          <label className="field-label" htmlFor="capture-target">
            Add this to
          </label>
          <select
            id="capture-target"
            className="select full"
            value={captureTarget}
            onChange={(event) => setCaptureTarget(event.target.value)}
          >
            {availableFields.map((field) => (
              <option value={fieldId(field)} key={fieldId(field)}>
                {
                  form.groups.find((group) => group.fields.includes(field))
                    ?.title
                }{" "}
                · {field.label || field.question}
              </option>
            ))}
          </select>
          <div className="modal-actions">
            <Button className="secondary" onClick={() => setCapture(null)}>
              Discard
            </Button>
            <Button
              className="primary"
              onClick={insertCapture}
              disabled={!capturedText.trim() || !captureTarget}
            >
              Add reviewed text
            </Button>
          </div>
        </Modal>
      )}
    </div>
  );
}

export function SynthesisSummary({
  synthesis,
  doctor = false,
  onGenerate,
  busy,
  readOnly = false,
}) {
  const [view, setView] = useState(doctor ? "clinician" : "patient");
  const [selectedSources, setSelectedSources] = useState(null);
  const live = synthesis?.status === "live";
  const sources = synthesis?.sources || [];
  function citations(ids) {
    return ids?.length ? (
      <button
        className="source-link"
        type="button"
        onClick={() => setSelectedSources(ids)}
        aria-label={`View ${ids.length} supporting source${ids.length === 1 ? "" : "s"}`}
      >
        <Icon name="file" size={13} />
        {ids.length} source{ids.length === 1 ? "" : "s"}
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
              ? "AI summary is currently unavailable"
              : "This record contains structured notes"}
          </h3>
          <p>
            {synthesis?.message ||
              "Generate a concise AI summary from the information you’ve provided. Every statement is linked to the underlying facts."}
          </p>
          {readOnly ? (
            <p className="field-hint">
              The approved version is shown exactly as shared. Its content
              cannot be changed here.
            </p>
          ) : (
            <Button
              className="primary"
              icon="sparkle"
              busy={busy}
              onClick={onGenerate}
            >
              Generate AI summary
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
      <div className="synthesis-heading">
        <div className="synthesis-label">
          <Icon name="sparkle" size={19} />
          <strong>AI consultation summary</strong>
        </div>
        <span>Based on your recorded information</span>
      </div>
      <div
        className="summary-view-switch"
        role="group"
        aria-label="Summary perspective"
      >
        <button
          type="button"
          className={view === "patient" ? "active" : ""}
          aria-pressed={view === "patient"}
          onClick={() => setView("patient")}
        >
          <Icon name="person" size={17} />
          Patient overview
        </button>
        <button
          type="button"
          className={view === "clinician" ? "active" : ""}
          aria-pressed={view === "clinician"}
          onClick={() => setView("clinician")}
        >
          <Icon name="file" size={17} />
          Clinician brief
        </button>
      </div>
      <div className="synthesis-section">
        <h3>
          {view === "patient"
            ? "Your situation, in plain language"
            : "Pre-consultation brief"}
        </h3>
        {prose(
          view === "patient"
            ? synthesis.patient_overview
            : synthesis.clinician_brief,
        )}
      </div>
      {synthesis.concern_summaries?.length > 0 && (
        <div className="synthesis-section">
          <h3>By concern</h3>
          <div className="synthesis-concerns">
            {synthesis.concern_summaries.map((concern, i) => (
              <article key={concern.concern_id || i}>
                <h4>{concern.title}</h4>
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
            <Icon name="check" size={19} /> Your appointment agenda
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
            <Icon name="info" size={19} /> Points to clarify
          </h3>
          {prose(synthesis.uncertainties)}
        </div>
      )}
      <details className="synthesis-sources">
        <summary>
          <Icon name="file" size={17} />
          <span>Source information ({sources.length})</span>
          <Icon name="chevron" size={17} />
        </summary>
        <p>
          These are the current patient-provided facts used in the summary.
          Original wording is preserved here, including any original-language
          details.
        </p>
        <dl>
          {sources.map((source) => (
            <div key={source.id}>
              <dt>
                {source.label}
                <span>{source.status?.toLowerCase().replace(/_/g, " ")}</span>
              </dt>
              <dd>
                {typeof source.value === "string"
                  ? source.value
                  : source.value == null
                    ? "Not provided"
                    : JSON.stringify(source.value)}
              </dd>
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
          Please check that this English summary accurately reflects your own
          words, including any translated details, before approving it.
        </p>
      )}
      {selectedSources && (
        <Modal
          title="Supporting information"
          onClose={() => setSelectedSources(null)}
        >
          <p className="modal-copy">
            This statement is based on the following information you provided.
          </p>
          <dl className="source-modal-list">
            {selected.map((source) => (
              <div key={source.id}>
                <dt>{source.label}</dt>
                <dd>
                  {typeof source.value === "string"
                    ? source.value
                    : source.value == null
                      ? "Not provided"
                      : JSON.stringify(source.value)}
                </dd>
                <small>{source.status?.toLowerCase().replace(/_/g, " ")}</small>
              </div>
            ))}
          </dl>
          {!selected.length && (
            <p className="modal-copy">
              No matching source is available in this version.
            </p>
          )}
          <div className="modal-actions">
            <Button
              className="primary"
              onClick={() => setSelectedSources(null)}
            >
              Done
            </Button>
          </div>
        </Modal>
      )}
    </section>
  );
}
