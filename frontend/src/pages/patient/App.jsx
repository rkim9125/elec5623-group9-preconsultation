import { tr, message, messageText } from "../../i18n/core.js";
import { useI18n, LanguageSelect } from "../../i18n/react.jsx";
import { useEffect, useRef, useState } from "react";
import {
  KEY,
  initial,
  activeSteps,
  change,
  summary,
  example,
  describe,
  completedStages,
} from "../../model.js";
import { getCopy } from "../../copy.js";
import { go, RouteLink } from "../../account/router.jsx";
import { mock, extractExplicitOnset } from "../../api/mock.js";
const group = (s) =>
  s === "reason"
    ? 0
    : ["onset", "course", "frequency", "severity", "impact"].includes(s)
      ? 1
      : ["history", "medicines", "allergies", "questions"].includes(s)
        ? 2
        : 3;
function restore() {
  try {
    const d = JSON.parse(sessionStorage.getItem(KEY));
    return d?.version === 1 && Array.isArray(d.reasons) && d.allergies?.items
      ? d
      : initial();
  } catch {
    return initial();
  }
}
function Choice({ name, value, selected, onChange, children }) {
  return (
    <label className={"choice " + (selected ? "selected" : "")}>
      <input
        type="radio"
        name={name}
        value={value}
        checked={selected}
        onChange={onChange}
      />
      <span>{children}</span>
      <span className="radio-mark" aria-hidden="true" />
    </label>
  );
}
export default function App({ account = null, onAccountSave }) {
  const locale = useI18n();
  const t = getCopy(locale);
  const [data, setData] = useState(() =>
      account ? structuredClone(account.record.data) : restore(),
    ),
    latest = useRef(data);
  latest.current = data;
  const [step, setStep] = useState(() =>
    account
      ? location.hash.split("/").at(-1) || account.record.step
      : location.hash.slice(1) || "start",
  );
  const [editing, setEditing] = useState(() => Boolean(history.state?.editing)),
    [error, setError] = useState(""),
    [busy, setBusy] = useState(false),
    [notice, setNotice] = useState(""),
    [storageError, setStorageError] = useState(false),
    [resetOpen, setResetOpen] = useState(false);
  const heading = useRef(null),
    lock = useRef(false),
    generation = useRef(0),
    resetButton = useRef(null);
  const navigate = (s, keepEditing = false) => {
    generation.current++;
    lock.current = false;
    setBusy(false);
    setError("");
    setEditing(keepEditing);
    const hash = account ? `#/intakes/${account.record.id}/edit/${s}` : `#${s}`;
    if (location.hash !== hash)
      history.pushState({ editing: keepEditing }, "", hash);
    setStep(s);
  };
  useEffect(() => {
    const listener = () => {
      generation.current++;
      lock.current = false;
      setBusy(false);
      setError("");
      setEditing(Boolean(history.state?.editing));
      setStep(
        account
          ? location.hash.split("/").at(-1)
          : location.hash.slice(1) || "start",
      );
    };
    window.addEventListener("popstate", listener);
    return () => {
      generation.current++;
      window.removeEventListener("popstate", listener);
    };
  }, []);
  useEffect(() => {
    const valid = activeSteps(data);
    if (!valid.includes(step) || (step === "done" && !data.sent))
      navigate("review");
  }, [step, data.course.value, data.sent]);
  useEffect(() => {
    heading.current?.focus();
    window.scrollTo(0, 0);

    setNotice("");
  }, [step]);
  useEffect(() => {
    document.title = `${step === "start" ? tr("before.you.start") : t.stages[group(step)]} · ${t.brand}`;
  }, [step, locale]);
  useEffect(() => {
    try {
      if (account) {
        setStorageError(!onAccountSave(data, step));
      } else {
        sessionStorage.setItem(KEY, JSON.stringify(data));
        sessionStorage.setItem(`${KEY}-step`, step);
        setStorageError(false);
      }
    } catch {
      setStorageError(true);
    }
  }, [data, step]);
  const update = (key, value) => {
    generation.current++;
    lock.current = false;
    setBusy(false);
    setError("");
    setData((d) => change(d, key, value));
  };
  const edit = (s) => navigate(s, true);
  const answer = (status, value = "", option = null) =>
    update(step, { ...data[step], status, value, option });
  const fail = (message) => {
    setError(message);
    requestAnimationFrame(() =>
      document.querySelector('[aria-invalid="true"]')?.focus(),
    );
  };
  async function request(kind, target) {
    if (lock.current) return;
    if (
      kind === "send" &&
      (!latest.current.approved ||
        latest.current.reasons.some((value) => !value.trim()))
    )
      return;
    lock.current = true;
    setBusy(true);
    setError("");
    const token = ++generation.current,
      revision = latest.current.revision;
    try {
      await mock.request(kind, latest.current);
      if (token !== generation.current || revision !== latest.current.revision)
        return;
      if (kind === "send")
        setData((d) => ({ ...d, sent: true, completed: [0, 1, 2, 3] }));
      navigate(target);
    } catch (e) {
      if (token === generation.current) setError(e.message);
    } finally {
      if (token === generation.current) {
        lock.current = false;
        setBusy(false);
      }
    }
  }
  function next() {
    if (lock.current) return;
    if (
      step === "reason" &&
      (!data.reasons[0]?.trim() || data.reasons.some((x) => !x.trim()))
    )
      return fail(
        message(
          "enter.a.reason.for.your.visit.you.can.remove.any.empty.additional",
        ),
      );
    if (
      data[step]?.status === "answered" &&
      !data[step].items &&
      !data[step].value.trim()
    )
      return fail(
        message(
          "write.your.answer.or.choose.not.sure.or.prefer.not.to.answer.belo",
        ),
      );
    if (
      ["medicines", "allergies"].includes(step) &&
      data[step].status === "answered" &&
      !data[step].items.length
    )
      return fail(message("add.an.item.or.choose.none.or.not.sure"));
    let draft = data;
    if (draft[step]?.status === "unasked")
      draft = change(draft, step, { ...draft[step], status: "unanswered" });
    const flow = activeSteps(draft);
    let target = flow[flow.indexOf(step) + 1];
    const explicitOnset =
      step === "reason" && draft.onset.status === "unasked"
        ? extractExplicitOnset(draft.reasons[0])
        : null;
    if (explicitOnset) {
      draft = change(draft, "onset", {
        status: "answered",
        value: explicitOnset,
      });
      if (!editing) target = "course";
    }
    if (editing) {
      if (
        step === "course" &&
        draft.course.value === "반복돼요" &&
        draft.frequency.status === "unasked"
      )
        target = "frequency";
      else target = "review";
    }
    if (group(target) !== group(step))
      draft = {
        ...draft,
        completed: [...new Set([...draft.completed, group(step)])],
      };
    latest.current = draft;
    setData(draft);
    if (target === "review") request("summary", "review");
    else navigate(target, editing);
  }

  function download() {
    const text =
      tr("visit.notes.demo.summary.this.has.not.been.sent.to.a.hospital") +
      summary(data, locale)
        .map((s) => s.title + "\n" + s.text)
        .join("\n\n");
    const url = URL.createObjectURL(
      new Blob([text], { type: "text/plain;charset=utf-8" }),
    );
    const a = document.createElement("a");
    a.href = url;
    a.download = tr("visit.notes.demo.summary.txt");
    a.click();
    URL.revokeObjectURL(url);
    setNotice(message("summary.text.downloaded"));
  }
  const incomplete = activeSteps(data).filter(
    (k) => data[k]?.status === "unasked",
  );
  const completed = completedStages(data);
  const current = group(step),
    field = t.fields[step],
    a = data[step];
  const title =
    step === "start"
      ? tr("before.your.visit.put.your.story.into.words")
      : step === "reason"
        ? tr("what.brings.you.in")
        : field?.title ||
          (step === "medicines"
            ? tr("are.you.taking.any.medicines")
            : step === "allergies"
              ? tr("do.you.have.any.known.allergies")
              : step === "review"
                ? tr("review.your.notes.before.your.visit")
                : tr("handoff.simulation.complete"));
  const modes = (none = false) => (
    <div className="alternatives">
      {[
        ...(none ? [["none", tr("none")]] : []),
        ["unknown", tr("not.sure")],
        ["declined", tr("prefer.not.to.answer")],
      ].map(([v, l]) => (
        <button
          type="button"
          key={v}
          aria-pressed={a?.status === v}
          onClick={() => answer(v)}
        >
          {l}
        </button>
      ))}
    </div>
  );
  const listEditor = () => (
    <>
      <fieldset
        tabIndex={-1}
        aria-invalid={!!error && a.status === "answered" && !a.items.length}
        aria-describedby={error ? "form-error" : undefined}
      >
        <legend>
          {step === "medicines"
            ? tr("do.you.take.any.medicines")
            : tr("do.you.have.any.allergies")}
        </legend>
        <Choice
          name={step}
          value="answered"
          selected={a.status === "answered"}
          onChange={() =>
            update(step, {
              ...a,
              status: "answered",
              items: a.items.length ? a.items : [{ name: "", detail: "" }],
            })
          }
        >
          {tr("yes.enter.details")}
        </Choice>
        {modes(true)}
      </fieldset>
      {a.status === "answered" && (
        <div className="items">
          {a.items.map((item, i) => (
            <div className="item" key={i}>
              <div className="row">
                <h3>
                  {step === "medicines" ? tr("medicines") : tr("allergies")}{" "}
                  {i + 1}
                </h3>
                <button
                  type="button"
                  className="text-button"
                  aria-label={tr("remove.item.value", { p0: i + 1 })}
                  onClick={() => {
                    update(step, {
                      ...a,
                      items: a.items.filter((_, j) => i !== j),
                    });
                    setNotice(message("item.removed"));
                    requestAnimationFrame(() =>
                      document.querySelector(".items .add")?.focus(),
                    );
                  }}
                >
                  {tr("remove")}
                </button>
              </div>
              {["name", "detail"].map((k) => (
                <div className="input-group" key={k}>
                  <label htmlFor={`${step}-${i}-${k}`}>
                    {k === "name"
                      ? step === "medicines"
                        ? tr("medicine.name")
                        : tr("allergy.trigger")
                      : step === "medicines"
                        ? tr("dose.and.how.you.take.it")
                        : tr("reaction.experienced")}{" "}
                    <span className="muted">{tr("leave.blank.if.unsure")}</span>
                  </label>
                  <input
                    id={`${step}-${i}-${k}`}
                    maxLength={300}
                    value={item[k]}
                    onChange={(e) =>
                      update(step, {
                        ...a,
                        items: a.items.map((x, j) =>
                          i === j ? { ...x, [k]: e.target.value } : x,
                        ),
                      })
                    }
                  />
                </div>
              ))}
            </div>
          ))}
          <button
            className="add"
            type="button"
            onClick={() => {
              update(step, {
                ...a,
                items: [...a.items, { name: "", detail: "" }],
              });
              setNotice(message("new.item.added"));
              requestAnimationFrame(() =>
                document
                  .getElementById(`${step}-${a.items.length}-name`)
                  ?.focus(),
              );
            }}
          >
            {tr("add.item", {
              item: step === "medicines" ? tr("medicines") : tr("allergies"),
            })}
          </button>
        </div>
      )}
    </>
  );
  const errors = error && (
    <p role="alert" id="form-error" className="error">
      {messageText(error)}
    </p>
  );
  return (
    <>
      <a
        className="skip"
        href="#main"
        onClick={(e) => {
          e.preventDefault();
          heading.current?.focus();
        }}
      >
        {tr("skip.to.content")}
      </a>
      <header className="header">
        <a
          href="#start"
          className="brand"
          onClick={(e) => {
            e.preventDefault();
            account ? go("/my") : navigate("start");
          }}
        >
          <span className="brand-symbol" aria-hidden="true">
            ✳
          </span>
          {t.brand}
          <span className="brand-sub">{t.tagline}</span>
        </a>
        <div className="header-tools">
          <span className="demo-badge">
            <span />
            {tr("demo")}
          </span>
          <LanguageSelect />
        </div>
      </header>
      <div className="account-intake-bar">
        {account ? (
          <>
            <span>
              {account.user.name}
              {tr("writing.an.account.note")}
            </span>
            <button
              className="text-button"
              onClick={() => {
                onAccountSave(data, step);
                go("/intakes");
              }}
            >
              {tr("save.and.go.to.my.notes")}
            </button>
          </>
        ) : (
          <>
            <span>{tr("you.are.trying.the.questionnaire.as.a.guest")}</span>
            <RouteLink to="/login">{tr("log.in.my.visit.notes")}</RouteLink>
          </>
        )}
      </div>
      <div className="app-layout">
        <aside className="navigation">
          <div className="nav-caption">{tr("preparing.for.my.visit")}</div>
          <ol aria-label={tr("questionnaire.stages")}>
            {t.stages.map((label, i) => (
              <li
                key={label}
                aria-current={
                  step !== "start" && current === i ? "step" : undefined
                }
                className={step !== "start" && current === i ? "active" : ""}
              >
                <span className="step-number">
                  {completed.includes(i) ? "✓" : String(i + 1).padStart(2, "0")}
                </span>
                <span>
                  {label}
                  <small>
                    {step !== "start" && step !== "done" && current === i
                      ? tr("in.progress")
                      : completed.includes(i)
                        ? tr("completed")
                        : ""}
                  </small>
                </span>
              </li>
            ))}
          </ol>
          <div className="nav-note">
            <span aria-hidden="true">♧</span>
            <p>
              {tr("take.your.time")}
              <br />
              {tr("you.can.change.previous.answers")}
              <br className="desktop" />
              {tr("at.any.time")}
            </p>
          </div>
        </aside>
        <main id="main" className="workspace">
          <div className="topline">
            <span>
              {step === "start"
                ? tr("before.you.start")
                : step === "done"
                  ? tr("completed")
                  : `${String(current + 1).padStart(2, "0")} / ${t.stages[current]}`}
            </span>
            <span className="save-state">
              {storageError
                ? tr("unable.to.save.in.this.tab")
                : tr("saved.in.this.tab")}
            </span>
          </div>
          <div className="page-content" key={step}>
            <div className="eyebrow">
              {step === "start"
                ? tr("eyebrow.start")
                : step === "done"
                  ? tr("eyebrow.done")
                  : editing
                    ? tr("edit.answer")
                    : tr("eyebrow.writing")}
            </div>
            <h1 ref={heading} tabIndex={-1}>
              {title}
            </h1>
            {step === "start" ? (
              <>
                <p className="lead">
                  {tr("from.symptoms.to.questions")}
                  <br />
                  {tr("write.down.what.you.want.to.discuss.at.your.visit")}
                </p>
                <div className="intro-list">
                  <div>
                    <span>01</span>
                    <p>
                      <strong>{tr("tell.your.story")}</strong>
                      <small>
                        {tr("choose.an.option.or.write.a.short.answer")}
                      </small>
                    </p>
                  </div>
                  <div>
                    <span>02</span>
                    <p>
                      <strong>{tr("review.and.edit.your.summary")}</strong>
                      <small>
                        {tr("see.everything.you.have.shared.in.one.place")}
                      </small>
                    </p>
                  </div>
                  <div>
                    <span>03</span>
                    <p>
                      <strong>{tr("try.the.handoff.simulation")}</strong>
                      <small>
                        {tr("nothing.is.sent.to.a.real.clinician.or.hospital")}
                      </small>
                    </p>
                  </div>
                </div>
                <div className="info-note">
                  <strong>{tr("use.fictional.information.only")}</strong>
                  <p>
                    {tr(
                      "only.people.using.this.tab.can.view.these.notes.do.not.enter.real",
                    )}
                  </p>
                </div>
                <div className="actions">
                  <button
                    className="primary"
                    onClick={() => navigate("reason")}
                  >
                    {t.start}
                    <span>→</span>
                  </button>
                  <button
                    className="text-button"
                    onClick={() => {
                      setData(example(locale));
                      navigate("reason");
                      setNotice(message("fictional.reason.for.visit.loaded"));
                    }}
                  >
                    {tr("try.a.fictional.example")}
                  </button>
                </div>
              </>
            ) : step === "reason" ? (
              <>
                <p className="lead">
                  {tr("start.with.the.issue.you.most.want.to.discuss")}
                  <br />
                  {tr("you.do.not.need.to.know.the.medical.terms")}
                </p>
                <form
                  onSubmit={(e) => {
                    e.preventDefault();
                    next();
                  }}
                  noValidate
                >
                  {data.reasons.map((value, i) => (
                    <div className="input-group reason-input" key={i}>
                      <div className="row">
                        <label htmlFor={`reason-${i}`}>
                          {i === 0
                            ? tr("main.reason.for.your.visit")
                            : tr("another.issue.to.discuss")}{" "}
                          <span className="muted">
                            {i === 0 ? tr("required") : i + 1}
                          </span>
                        </label>
                        {i > 0 && (
                          <div>
                            <button
                              type="button"
                              className="text-button"
                              onClick={() => {
                                const r = [...data.reasons];
                                [r[i - 1], r[i]] = [r[i], r[i - 1]];
                                update("reasons", r);
                                setNotice(
                                  message("issue.moved.up.in.priority"),
                                );
                              }}
                            >
                              {tr("move.up")}
                            </button>
                            <button
                              type="button"
                              className="text-button"
                              onClick={() =>
                                update(
                                  "reasons",
                                  data.reasons.filter((_, j) => j !== i),
                                )
                              }
                            >
                              {tr("remove")}
                            </button>
                          </div>
                        )}
                      </div>
                      <textarea
                        id={`reason-${i}`}
                        rows={4}
                        maxLength={3000}
                        placeholder={tr(
                          "for.example.i.have.had.a.headache.for.a.few.days.it.feels.worse.i",
                        )}
                        value={value}
                        aria-invalid={!!error && !value.trim()}
                        aria-describedby={error ? "form-error" : undefined}
                        onChange={(e) =>
                          update(
                            "reasons",
                            data.reasons.map((x, j) =>
                              i === j ? e.target.value : x,
                            ),
                          )
                        }
                      />
                      <div className="field-meta">
                        <span>
                          {i === 0
                            ? tr(
                                "we.will.ask.follow.up.questions.about.this.issue",
                              )
                            : tr(
                                "additional.issues.will.also.appear.in.your.summary",
                              )}
                        </span>
                        <span>{value.length}/3,000</span>
                      </div>
                    </div>
                  ))}
                  <button
                    type="button"
                    className="add"
                    onClick={() => {
                      update("reasons", [...data.reasons, ""]);
                      requestAnimationFrame(() =>
                        document
                          .getElementById(`reason-${data.reasons.length}`)
                          ?.focus(),
                      );
                    }}
                  >
                    {tr("add.another.issue")}
                  </button>
                  {errors}
                  <div className="actions">
                    <button
                      type="button"
                      className="secondary"
                      onClick={() => navigate(editing ? "review" : "start")}
                    >
                      {editing ? tr("back.to.summary") : tr("back.2")}
                    </button>
                    <button disabled={busy} className="primary">
                      {busy
                        ? tr("preparing.summary")
                        : editing
                          ? t.editReturn
                          : t.next}
                      <span>→</span>
                    </button>
                  </div>
                </form>
              </>
            ) : field || ["medicines", "allergies"].includes(step) ? (
              <>
                <p className="lead">
                  {field?.subtitle ||
                    tr(
                      "add.each.item.separately.it.is.okay.if.you.do.not.know.the.exact",
                    )}
                </p>
                {field && (
                  <details className="help">
                    <summary>{tr("why.are.we.asking")}</summary>
                    <p>{field.help}</p>
                  </details>
                )}
                <form
                  noValidate
                  onSubmit={(e) => {
                    e.preventDefault();
                    next();
                  }}
                >
                  {field ? (
                    <fieldset>
                      <legend>{field.label}</legend>
                      {field.options?.map(({ value: v, label }) => (
                        <Choice
                          name={step}
                          value={v}
                          selected={
                            a.status === "answered" &&
                            (a.option === v ||
                              (a.option === undefined && a.value === v))
                          }
                          key={v}
                          onChange={() => answer("answered", v, v)}
                        >
                          {label}
                        </Choice>
                      ))}
                      <label className="input-label" htmlFor="free-answer">
                        {field.options
                          ? tr("describe.in.your.own.words")
                          : field.label}
                      </label>
                      <textarea
                        id="free-answer"
                        rows={field.options ? 2 : 4}
                        maxLength={3000}
                        placeholder={
                          field.placeholder ||
                          tr("if.no.option.fits.write.your.answer.here")
                        }
                        value={
                          a.status === "answered" &&
                          !a.option &&
                          !(
                            a.option === undefined &&
                            field.options?.some(
                              (option) => option.value === a.value,
                            )
                          )
                            ? a.value
                            : ""
                        }
                        aria-invalid={
                          !!error && a.status === "answered" && !a.value.trim()
                        }
                        aria-describedby={error ? "form-error" : undefined}
                        onChange={(e) => answer("answered", e.target.value)}
                      />
                      {modes(field.none)}
                    </fieldset>
                  ) : (
                    listEditor()
                  )}
                  {errors}
                  <div className="actions">
                    <button
                      type="button"
                      className="secondary"
                      disabled={busy}
                      onClick={() =>
                        editing
                          ? navigate("review")
                          : navigate(
                              activeSteps(data)[
                                activeSteps(data).indexOf(step) - 1
                              ],
                            )
                      }
                    >
                      {editing ? tr("back.to.summary") : tr("back.2")}
                    </button>
                    <button className="primary" disabled={busy}>
                      {busy
                        ? tr("preparing.summary")
                        : editing
                          ? t.editReturn
                          : t.next}
                      <span>→</span>
                    </button>
                  </div>
                  <p className="footnote">
                    {tr(
                      "continuing.without.an.answer.records.this.as.unanswered",
                    )}
                  </p>
                </form>
              </>
            ) : step === "review" ? (
              <>
                <p className="lead">
                  {tr("this.summary.only.includes.what.you.have.shared")}
                  <br />
                  {tr("please.edit.anything.that.is.missing.or.incorrect")}
                </p>
                <div className="review-notice">
                  {tr("demo.questionnaire.summary")}
                  <span>{tr("no.medical.assessment.is.included")}</span>
                </div>
                <div className="summary">
                  {summary(data, locale).map((s) => (
                    <section key={s.title}>
                      <div className="row">
                        <h2>{s.title}</h2>
                        {s.step && (
                          <button
                            className="text-button"
                            aria-label={tr("edit.value", { p0: s.title })}
                            onClick={() => edit(s.step)}
                          >
                            {tr("edit")}
                          </button>
                        )}
                      </div>
                      <p>{s.text}</p>
                      {s.step === "onset" && (
                        <div className="inline-edits">
                          {[
                            "course",
                            ...(data.course.value === "반복돼요"
                              ? ["frequency"]
                              : []),
                            "severity",
                            "impact",
                          ].map((k) => (
                            <button
                              key={k}
                              className="text-button"
                              onClick={() => edit(k)}
                            >
                              {tr("edit.field", { field: t.fields[k].label })}
                            </button>
                          ))}
                        </div>
                      )}
                    </section>
                  ))}
                </div>
                {data.reasons.some((value) => !value.trim()) && (
                  <div className="info-note">
                    <strong>
                      {tr("a.reason.for.your.visit.is.still.blank")}
                    </strong>
                    <p>
                      {tr(
                        "enter.an.answer.or.remove.the.empty.additional.item",
                      )}
                    </p>
                    <button
                      className="text-button"
                      onClick={() => edit("reason")}
                    >
                      {tr("check.reason.for.visit")}
                    </button>
                  </div>
                )}
                {incomplete.length > 0 && (
                  <div className="info-note">
                    <strong>
                      {tr("there.are.questions.you.have.not.seen.yet")}
                    </strong>
                    <p>
                      {tr(
                        "please.review.any.questions.added.after.your.edits.you.may.contin",
                      )}
                    </p>
                    <button
                      className="text-button"
                      onClick={() => edit(incomplete[0])}
                    >
                      {tr("go.to.remaining.questions")}
                    </button>
                  </div>
                )}
                <label className="approval">
                  <input
                    type="checkbox"
                    checked={data.approved}
                    disabled={busy}
                    onChange={(e) =>
                      setData((d) => ({ ...d, approved: e.target.checked }))
                    }
                  />
                  <span>
                    {tr(
                      "i.have.read.the.summary.and.it.matches.what.i.entered",
                    )}
                  </span>
                </label>
                <p className="footnote">
                  {tr("editing.an.answer.clears.this.confirmation")}
                </p>
                {errors}
                <div className="actions">
                  <button
                    className="primary"
                    disabled={
                      !data.approved ||
                      busy ||
                      incomplete.length > 0 ||
                      data.reasons.some((value) => !value.trim())
                    }
                    onClick={() =>
                      data.sent ? navigate("done") : request("send", "done")
                    }
                  >
                    {busy
                      ? tr("simulating.handoff")
                      : data.sent
                        ? tr("view.simulation.result")
                        : tr("confirm.and.simulate.handoff")}
                    <span>→</span>
                  </button>
                </div>
                <p className="footnote">
                  {tr("nothing.will.be.sent.to.a.real.clinician.or.hospital")}
                </p>
              </>
            ) : (
              <>
                <div className="completion-mark" aria-hidden="true">
                  ✓
                </div>
                <p className="lead">
                  {tr("your.notes.have.been.organised.into.a.summary")}
                  <br />
                  {tr("nothing.has.been.sent.to.a.real.doctor.or.hospital")}
                </p>
                <div className="info-note">
                  <strong>{tr("my.notes.for.the.next.visit")}</strong>
                  <p>
                    {tr(
                      "review.your.summary.or.download.it.as.text.no.appointment.or.chec",
                    )}
                  </p>
                </div>
                <div className="actions">
                  <button className="primary" onClick={download}>
                    {tr("download.summary.text")}
                  </button>
                  <button
                    className="secondary"
                    onClick={() => navigate("review")}
                  >
                    {tr("view.summary.again")}
                  </button>
                </div>
              </>
            )}
          </div>
          <footer className="workspace-footer">
            <span>{tr("helping.you.share.your.story")}</span>
            <span>{tr("visit.notes")}</span>
          </footer>
        </main>
        <aside className="context">
          <div className="context-label">
            {step === "start" ? tr("before.you.begin") : tr("my.visit.notes")}
          </div>
          <div className="paper-icon" aria-hidden="true">
            <span>✳</span>
            <i />
            <i />
            <i />
            <b>✓</b>
          </div>
          {step === "start" ? (
            <>
              <h2>{tr("no.need.to.remember.everything")}</h2>
              <p>
                {tr("bring.together.your.symptoms.medicines.allergies")}
                <br />
                {tr("and.questions")}
              </p>
              <div className="context-divider" />
              <p className="small">
                {tr("if.you.are.unsure")}
                <br />
                {tr("it.is.okay.to.choose.not.sure")}
              </p>
            </>
          ) : (
            <>
              <h2>{tr("what.i.want.to.discuss.first")}</h2>
              <p className="preview-text">
                {data.reasons[0] ||
                  tr("your.reason.for.visiting.will.appear.here")}
              </p>
              <div className="context-divider" />
              <dl>
                <dt>{tr("symptoms.started")}</dt>
                <dd>{describe(data.onset, locale)}</dd>
                <dt>{tr("medicines")}</dt>
                <dd>
                  {data.medicines.status === "answered"
                    ? tr("value.entered", { p0: data.medicines.items.length })
                    : describe(data.medicines, locale)}
                </dd>
              </dl>
              <p className="small">
                {tr("at.the.final.step.you.can")}
                <br />
                {tr("review.and.edit.all.your.answers")}
              </p>
            </>
          )}
        </aside>
      </div>
      <footer className="bottom">
        <span>{tr("demo.not.a.real.healthcare.service")}</span>
        <div>
          <details>
            <summary>{tr("demo.controls")}</summary>
            <button
              onClick={() => {
                mock.failOnce();
                setNotice(
                  message("the.next.summary.or.handoff.request.will.fail.once"),
                );
              }}
            >
              {tr("fail.next.response")}
            </button>
          </details>
          <button
            ref={resetButton}
            className="text-button"
            onClick={() => setResetOpen(true)}
          >
            {tr("reset.demo.data")}
          </button>
        </div>
      </footer>
      <div className="sr-only" aria-live="polite" role="status">
        {busy
          ? tr("processing.your.request")
          : messageText(notice) ||
            (storageError
              ? tr(
                  "temporary.saving.is.unavailable.refreshing.may.lose.your.answers",
                )
              : tr("value.screen", { p0: title }))}
      </div>
      {resetOpen && (
        <div className="modal-backdrop">
          <div
            role="alertdialog"
            aria-modal="true"
            aria-labelledby="reset-title"
            className="modal"
            onKeyDown={(e) => {
              if (e.key === "Escape") {
                setResetOpen(false);
                resetButton.current?.focus();
              }
              if (e.key === "Tab") {
                e.preventDefault();
                const buttons = e.currentTarget.querySelectorAll("button");
                (document.activeElement === buttons[0]
                  ? buttons[1]
                  : buttons[0]
                ).focus();
              }
            }}
          >
            <h2 id="reset-title">{tr("clear.your.demo.answers")}</h2>
            <p>{tr("this.resets.the.answers.and.review.status.in.this.tab")}</p>
            <div className="actions">
              <button
                autoFocus
                className="secondary"
                onClick={() => {
                  setResetOpen(false);
                  resetButton.current?.focus();
                }}
              >
                {tr("cancel")}
              </button>
              <button
                className="primary"
                onClick={() => {
                  setData(initial());
                  setEditing(false);
                  setResetOpen(false);
                  navigate("start");
                  setNotice(message("demo.data.reset"));
                }}
              >
                {tr("reset")}
              </button>
            </div>
          </div>
        </div>
      )}
    </>
  );
}
