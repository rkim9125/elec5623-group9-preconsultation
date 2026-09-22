import { useEffect, useRef, useState, useSyncExternalStore } from "react";
import { LanguageSelect, useI18n } from "../i18n/react.jsx";
import { medicineText } from "../medicines.js";
import { historyText } from "../history.js";
import { getLocale } from "../i18n/core.js";
import { tr } from "../i18n/core.js";
import {
  go,
  RouteLink,
  setRouteBlocker,
  useRoute,
} from "../account/router.jsx";
import { formatDate } from "../account/domain.js";
import { doctorService as api, dayKey } from "./service.js";
import "./doctor.css";
const t = (key) => tr(`doctor.${key}`);
const errorKey = (e) =>
  [
    "FAILED",
    "LOGIN_FAILED",
    "SESSION_EXPIRED",
    "NOT_FOUND",
    "NEW_VERSION",
    "SUMMARY_UNAVAILABLE",
  ].includes(e?.code)
    ? e.code
    : "FAILED";
const stateOf = (row) =>
  !row.latest ? "unsubmitted" : row.latest.reviewed ? "reviewed" : "pending";
function Badge({ state }) {
  return <span className={`doctor-badge ${state}`}>{t(state)}</span>;
}
function ErrorMessage({ code, retry }) {
  return (
    code && (
      <div className="error" role="alert">
        <p>{t(code)}</p>
        {retry && (
          <button className="secondary" onClick={retry}>
            {t("retry")}
          </button>
        )}
      </div>
    )
  );
}

function Queue({
  date,
  setDate,
  search,
  setSearch,
  filter,
  setFilter,
  selected,
  revision,
}) {
  const [rows, setRows] = useState(null),
    [error, setError] = useState(""),
    [attempt, setAttempt] = useState(0);
  useEffect(() => {
    let live = true;
    setRows(null);
    setError("");
    api
      .list(api.scope(), date)
      .then((r) => {
        if (live) setRows(r);
      })
      .catch((e) => {
        if (live) setError(errorKey(e));
      });
    return () => {
      live = false;
    };
  }, [date, revision, attempt]);
  const visible = rows?.filter(
    (r) =>
      (filter === "all" || stateOf(r) === filter) &&
      `${r.patient.name} ${r.patient.identifier}`
        .toLowerCase()
        .includes(search.toLowerCase()),
  );
  return (
    <aside
      className={`doctor-queue ${selected ? "has-selection" : ""}`}
      aria-label={t("queue")}
    >
      <div className="queue-heading">
        <h1 tabIndex={-1}>{t("queue")}</h1>
        <button
          className="text-button"
          onClick={() => setAttempt((x) => x + 1)}
        >
          {t("reload")}
        </button>
      </div>
      <label htmlFor="doctor-date">{t("date")}</label>
      <input
        id="doctor-date"
        type="date"
        value={date}
        onChange={(e) => {
          if (e.target.value) {
            setDate(e.target.value);
            go("/doctor");
          }
        }}
      />
      <label htmlFor="doctor-search">{t("search")}</label>
      <input
        id="doctor-search"
        type="search"
        placeholder={t("searchPlaceholder")}
        value={search}
        onChange={(e) => setSearch(e.target.value)}
      />
      <label htmlFor="doctor-filter">{t("filter")}</label>
      <select
        id="doctor-filter"
        value={filter}
        onChange={(e) => setFilter(e.target.value)}
      >
        {["all", "unsubmitted", "pending", "reviewed"].map((k) => (
          <option key={k} value={k}>
            {t(k)}
          </option>
        ))}
      </select>
      <ErrorMessage code={error} retry={() => setAttempt((x) => x + 1)} />
      {!rows && !error && <p role="status">{t("loading")}</p>}
      {rows && !visible.length && (
        <p role="status">{t(rows.length ? "noMatches" : "empty")}</p>
      )}
      <details className="doctor-controls">
        <summary>{t("controls")}</summary>
        <button
          className="secondary"
          onClick={() => {
            api.failNext("load");
            setAttempt((x) => x + 1);
          }}
        >
          {t("failLoad")}
        </button>
      </details>
      <ul className="doctor-patients">
        {visible?.map((r) => (
          <li key={r.id}>
            <RouteLink
              to={`/doctor/appointments/${r.id}`}
              className={selected === r.id ? "selected" : ""}
              aria-current={selected === r.id ? "page" : undefined}
            >
              <div className="patient-row-top">
                <strong>{r.patient.name}</strong>
                <time dateTime={r.startsAt}>
                  {new Intl.DateTimeFormat(
                    document.documentElement.lang === "ko" ? "ko-KR" : "en-GB",
                    {
                      timeZone: "Asia/Seoul",
                      hour: "2-digit",
                      minute: "2-digit",
                    },
                  ).format(new Date(r.startsAt))}
                </time>
              </div>
              <small>
                {r.patient.identifier} · {t(r.status)}
              </small>
              <p>{r.latest?.reason || t("unsubmitted")}</p>
              <Badge state={stateOf(r)} />
              {r.latest && (
                <small className="submission-time">
                  {t("submitted")}: {formatDate(r.latest.submittedAt)}
                </small>
              )}
            </RouteLink>
          </li>
        ))}
      </ul>
    </aside>
  );
}
function Answer({ answer }) {
  if (answer.status !== "answered") return <span>{t(answer.status)}</span>;
  if (answer.field === "reasons")
    return (
      <ol>
        {answer.value.map((value, i) => (
          <li key={i}>{value}</li>
        ))}
      </ol>
    );
  if (answer.field === "history")
    return (
      <span className="patient-text">
        {historyText(answer, getLocale()) || t("unanswered")}
      </span>
    );
  if (answer.field === "medicines")
    return (
      <span className="patient-text">{medicineText(answer, getLocale())}</span>
    );
  if (answer.items)
    return (
      <ul>
        {answer.items.map((item, i) => (
          <li key={i}>
            {item.name || t("missingName")} ·{" "}
            {item.detail || t("missingDetail")}
          </li>
        ))}
      </ul>
    );
  return (
    <span className="patient-text">{answer.value || t("unanswered")}</span>
  );
}
function Detail({ id, revision }) {
  const [appointment, setAppointment] = useState(null),
    [error, setError] = useState(""),
    [attempt, setAttempt] = useState(0),
    [sid, setSid] = useState(null),
    [note, setNote] = useState(""),
    [savedNote, setSavedNote] = useState(""),
    [saving, setSaving] = useState(false),
    [noteStatus, setNoteStatus] = useState(""),
    [reviewBusy, setReviewBusy] = useState(false),
    [actionError, setActionError] = useState(""),
    [refs, setRefs] = useState(null),
    [pending, setPending] = useState(null),
    [announcement, setAnnouncement] = useState("");
  const lock = useRef(false),
    mounted = useRef(true),
    noteRef = useRef(null),
    sourceRef = useRef(null),
    headingRef = useRef(null),
    modalRef = useRef(null),
    cancelRef = useRef(null),
    opRef = useRef(null),
    activeSid = useRef(sid);
  activeSid.current = sid;
  const dirty = note !== savedNote;
  const selected = appointment?.submissions.find((s) => s.id === sid);
  const latest = appointment?.submissions.at(-1);
  useEffect(() => {
    mounted.current = true;
    headingRef.current?.focus();
    return () => {
      mounted.current = false;
    };
  }, []);
  useEffect(() => {
    let live = true;
    setError("");
    api
      .detail(api.scope(), id)
      .then((a) => {
        if (!live) return;
        setAppointment(a);
        setSid((current) => current || a.submissions.at(-1)?.id || null);
      })
      .catch((e) => {
        if (live) setError(errorKey(e));
      });
    return () => {
      live = false;
    };
  }, [id, revision, attempt]);
  useEffect(() => {
    if (!selected) return;
    setNote(selected.note);
    setSavedNote(selected.note);
    setNoteStatus("");
    setActionError("");
    setRefs(null);
  }, [sid]); // Only changing the submission resets its local note.
  // The first response supplies the selected submission before the effect above runs.
  useEffect(() => {
    const off = setRouteBlocker((resume) => {
      if (!dirty) return false;
      setPending(() => resume);
      return true;
    });
    const unload = (e) => {
      if (dirty) {
        e.preventDefault();
        e.returnValue = "";
      }
    };
    window.addEventListener("beforeunload", unload);
    return () => {
      off();
      window.removeEventListener("beforeunload", unload);
    };
  }, [dirty]);
  useEffect(() => {
    if (pending) cancelRef.current?.focus();
  }, [pending]);
  useEffect(() => {
    if (refs) {
      const target = document.getElementById(refs[0]);
      if (target) {
        target.focus();
        target.scrollIntoView({ block: "nearest" });
      } else sourceRef.current?.focus();
    }
  }, [refs]);
  function changeVersion(value) {
    const apply = () => {
      setSid(value);
      setRefs(null);
    };
    if (dirty) setPending(() => apply);
    else apply();
  }
  async function save() {
    if (lock.current || !selected) return false;
    lock.current = true;
    setSaving(true);
    setNoteStatus("saving");
    const scope = api.scope();
    try {
      await api.saveNote(scope, id, selected.id, note);
      if (!mounted.current || activeSid.current !== selected.id) return false;
      setSavedNote(note);
      setNoteStatus("saved");
      return true;
    } catch (e) {
      if (mounted.current && activeSid.current === selected.id)
        setNoteStatus(errorKey(e));
      return false;
    } finally {
      lock.current = false;
      if (mounted.current) setSaving(false);
    }
  }
  async function review() {
    if (lock.current || !selected) return;
    lock.current = true;
    setReviewBusy(true);
    setActionError("");
    try {
      await api.review(api.scope(), id, selected.id, selected.summary.id);
    } catch (e) {
      if (mounted.current && activeSid.current === selected.id)
        setActionError(errorKey(e));
    } finally {
      lock.current = false;
      if (mounted.current) setReviewBusy(false);
    }
  }
  function controls(operation) {
    api.failNext(operation);
    setAnnouncement("armed");
  }
  function trap(e) {
    if (e.key === "Escape") {
      setPending(null);
      noteRef.current?.focus();
    }
    if (e.key === "Tab") {
      const els = modalRef.current.querySelectorAll("button:not(:disabled)");
      const first = els[0],
        last = els[els.length - 1];
      if (e.shiftKey && document.activeElement === first) {
        e.preventDefault();
        last.focus();
      } else if (!e.shiftKey && document.activeElement === last) {
        e.preventDefault();
        first.focus();
      }
    }
  }
  return (
    <article className="doctor-detail">
      <RouteLink className="doctor-back" to="/doctor">
        ← {t("back")}
      </RouteLink>
      <h1 ref={headingRef} tabIndex={-1} className="sr-only">
        {t("title")}
      </h1>
      <ErrorMessage code={error} retry={() => setAttempt((n) => n + 1)} />
      {!appointment && !error && <p role="status">{t("loading")}</p>}
      {appointment && (
        <>
          <header className="doctor-patient-header">
            <div>
              <p className="eyebrow">{appointment.patient.identifier}</p>
              <h2>{appointment.patient.name}</h2>
              <p>
                {formatDate(appointment.startsAt)} · {appointment.department}
              </p>
              <span>
                {t("appointment")}: {t(appointment.status)}
              </span>
            </div>
            <Badge
              state={
                !latest
                  ? "unsubmitted"
                  : selected?.reviews.length
                    ? "reviewed"
                    : "pending"
              }
            />
          </header>
          {!latest ? (
            <p className="doctor-empty">{t("noSubmission")}</p>
          ) : (
            <>
              {selected && (
                <>
                  <div className="submission-meta">
                    <label htmlFor="submission-version">{t("version")}</label>
                    <select
                      id="submission-version"
                      value={sid}
                      onChange={(e) => changeVersion(e.target.value)}
                    >
                      {appointment.submissions.map((s) => (
                        <option key={s.id} value={s.id}>
                          v{s.version} · {formatDate(s.submittedAt)}
                        </option>
                      ))}
                    </select>
                    <p>
                      {t("submitted")}: {formatDate(selected.submittedAt)}
                      <br />
                      {t("generated")}:{" "}
                      {selected.summary.generatedAt
                        ? formatDate(selected.summary.generatedAt)
                        : t("notGenerated")}{" "}
                      · {t("summaryVersion")} {selected.summary.version}
                    </p>
                  </div>
                  {latest.id !== sid && (
                    <div className="info-note" role="status">
                      <p>{t("newVersion")}</p>
                      <button
                        className="secondary"
                        onClick={() => changeVersion(latest.id)}
                      >
                        {t("openLatest")}
                      </button>
                    </div>
                  )}
                  <div
                    className={`doctor-reading ${refs ? "with-original" : ""}`}
                  >
                    <section className="doctor-summary">
                      <h2>{t("summary")}</h2>
                      <p className="muted">{t("summaryHelp")}</p>
                      {selected.summary.state !== "ready" ? (
                        <div role="status">
                          <p>
                            {t(
                              selected.summary.state === "failed"
                                ? "failedSummary"
                                : "generating",
                            )}
                          </p>
                          <button
                            className="secondary"
                            onClick={async () => {
                              try {
                                await api.retrySummary(api.scope(), id, sid);
                              } catch (e) {
                                if (
                                  mounted.current &&
                                  activeSid.current === sid
                                )
                                  setActionError(errorKey(e));
                              }
                            }}
                          >
                            {t(
                              selected.summary.state === "failed"
                                ? "retry"
                                : "finishSummary",
                            )}
                          </button>
                        </div>
                      ) : (
                        selected.summary.sections.map((section) => (
                          <section
                            className="summary-section"
                            key={section.key}
                          >
                            <h3>{t(section.key)}</h3>
                            {section.refs.map((ref) => {
                              const a = selected.answers.find(
                                (a) => a.id === ref,
                              );
                              return a ? (
                                <div className="summary-answer" key={ref}>
                                  {(section.key === "uncertain" ||
                                    ![
                                      "reasons",
                                      "history",
                                      "medicines",
                                      "allergies",
                                      "impact",
                                      "questions",
                                    ].includes(a.field)) && (
                                    <strong>{t(a.field)}: </strong>
                                  )}
                                  <Answer answer={a} />
                                </div>
                              ) : (
                                <p key={ref}>{t("noSource")}</p>
                              );
                            })}
                            {!section.refs.length && (
                              <p>
                                {t(
                                  section.key === "uncertain"
                                    ? "noUncertain"
                                    : "noSource",
                                )}
                              </p>
                            )}
                            {section.refs.some((ref) =>
                              selected.answers.some((a) => a.id === ref),
                            ) && (
                              <button
                                className="text-button source-link"
                                onClick={() =>
                                  setRefs(
                                    section.refs.filter((ref) =>
                                      selected.answers.some(
                                        (a) => a.id === ref,
                                      ),
                                    ),
                                  )
                                }
                                aria-label={`${t("source")}: ${t(section.key)}`}
                              >
                                {t("source")} ↗
                              </button>
                            )}
                          </section>
                        ))
                      )}
                      <button
                        className="secondary"
                        onClick={() =>
                          setRefs(selected.answers.map((a) => a.id))
                        }
                      >
                        {t("allOriginal")}
                      </button>
                    </section>
                    {refs && (
                      <aside
                        className="doctor-original"
                        aria-label={t("original")}
                      >
                        <h2 ref={sourceRef} tabIndex={-1}>
                          {t("original")}
                        </h2>
                        <p>{t("originalHelp")}</p>
                        <button
                          className="text-button"
                          onClick={() => {
                            setRefs(null);
                            headingRef.current?.focus();
                          }}
                        >
                          {t("closeOriginal")}
                        </button>
                        {selected.answers.map((a) => (
                          <section
                            key={a.id}
                            id={a.id}
                            tabIndex={-1}
                            className={
                              refs.includes(a.id) ? "source-highlight" : ""
                            }
                          >
                            <h3>{t(a.field)}</h3>
                            <Answer answer={a} />
                          </section>
                        ))}
                      </aside>
                    )}
                  </div>
                  <section className="doctor-note">
                    <h2>{t("note")}</h2>
                    <p>{t("noteHelp")}</p>
                    <label htmlFor="doctor-note">{t("note")}</label>
                    <textarea
                      ref={noteRef}
                      id="doctor-note"
                      rows={5}
                      value={note}
                      disabled={saving}
                      onChange={(e) => {
                        setNote(e.target.value);
                        setNoteStatus("");
                      }}
                    />
                    <div className="note-actions">
                      <button
                        className="primary"
                        disabled={saving || !dirty}
                        onClick={save}
                      >
                        {t(saving ? "saving" : "save")}
                      </button>
                      <span role={noteStatus === "FAILED" ? "alert" : "status"}>
                        {noteStatus ? t(noteStatus) : dirty ? t("dirty") : ""}
                      </span>
                    </div>
                  </section>
                  <section className="doctor-review">
                    <h2>{t("reviewState")}</h2>
                    <p>{t("reviewHelp")}</p>
                    {selected.reviews.map((r) => (
                      <p
                        key={`${r.doctorId}:${r.submissionId}`}
                        className="review-record"
                        role="status"
                      >
                        ✓ {t("reviewBy")} {r.doctorId} ·{" "}
                        {formatDate(r.reviewedAt)} · v{r.submissionVersion} /{" "}
                        {t("summaryVersion")} {r.summaryVersion}
                      </p>
                    ))}
                    <button
                      ref={opRef}
                      className="primary"
                      disabled={
                        reviewBusy ||
                        saving ||
                        selected.reviews.length > 0 ||
                        sid !== latest.id ||
                        selected.summary.state !== "ready"
                      }
                      onClick={review}
                    >
                      {t(reviewBusy ? "saving" : "review")}
                    </button>
                    <ErrorMessage code={actionError} />
                  </section>
                  <details className="doctor-controls">
                    <summary>{t("controls")}</summary>
                    <div>
                      <button
                        className="secondary"
                        onClick={() => api.simulateSubmission(api.scope(), id)}
                      >
                        {t("newSubmission")}
                      </button>
                      <button
                        className="secondary"
                        onClick={() => controls("note")}
                      >
                        {t("failNote")}
                      </button>
                      <button
                        className="secondary"
                        onClick={() => controls("review")}
                      >
                        {t("failReview")}
                      </button>
                      <button
                        className="secondary"
                        onClick={() => {
                          api.failNext("load");
                          setAttempt((n) => n + 1);
                        }}
                      >
                        {t("failLoad")}
                      </button>
                      <button
                        className="secondary"
                        onClick={() => {
                          api.slowNext();
                          setAnnouncement("slowArmed");
                        }}
                      >
                        {t("slowNext")}
                      </button>
                      <button
                        className="secondary"
                        onClick={() => api.expire()}
                      >
                        {t("expire")}
                      </button>
                    </div>
                    <p role="status">{announcement ? t(announcement) : ""}</p>
                  </details>
                </>
              )}
            </>
          )}
        </>
      )}
      {pending && (
        <div className="modal-backdrop">
          <div
            className="modal"
            ref={modalRef}
            role="dialog"
            aria-modal="true"
            aria-labelledby="leave-title"
            aria-describedby="leave-description"
            onKeyDown={trap}
          >
            <h2 id="leave-title">{t("leaveTitle")}</h2>
            <p id="leave-description">{t("leaveBody")}</p>
            <p role="alert">{noteStatus === "FAILED" ? t("FAILED") : ""}</p>
            <button
              className="primary"
              disabled={saving}
              onClick={async () => {
                const resume = pending;
                if (await save()) {
                  setPending(null);
                  resume();
                }
              }}
            >
              {t(saving ? "saving" : "saveLeave")}
            </button>
            <button
              className="secondary"
              disabled={saving}
              onClick={() => {
                setNote(savedNote);
                const resume = pending;
                setPending(null);
                resume();
              }}
            >
              {t("discard")}
            </button>
            <button
              ref={cancelRef}
              className="text-button"
              onClick={() => {
                setPending(null);
                noteRef.current?.focus();
              }}
            >
              {t("stay")}
            </button>
          </div>
        </div>
      )}
    </article>
  );
}
export default function Doctor() {
  const locale = useI18n(),
    route = useRoute(),
    revision = useSyncExternalStore(api.subscribe, api.getSnapshot),
    auth = api.auth();
  const [date, setDate] = useState(dayKey()),
    [search, setSearch] = useState(""),
    [filter, setFilter] = useState("all");
  const match = route.match(/^\/doctor\/appointments\/([^/?]+)$/),
    selected = match?.[1];
  const authenticated = auth.status === "authenticated";
  useEffect(() => {
    document.title = `${t("title")} · Visit Notes`;
  }, [locale]);
  useEffect(() => {
    const timer = setInterval(() => {
      if (api.auth().expiresAt <= Date.now()) api.expire();
      else if (api.auth().status === "authenticated") api.sync();
    }, 3000);
    return () => clearInterval(timer);
  }, []);
  function logout() {
    go("/login", { onNavigate: () => api.logout() });
  } // Route blocker runs before any session is cleared.

  const valid = route === "/doctor" || route === "/doctor/login" || selected;
  return (
    <div className="doctor-app">
      <a
        href="#doctor-main"
        className="skip"
        onClick={(e) => {
          e.preventDefault();
          document.getElementById("doctor-main")?.focus();
        }}
      >
        {t("title")}
      </a>
      <header className="header doctor-header">
        <RouteLink className="brand" to="/doctor">
          {tr("visit.notes")} <small>{t("title")}</small>
        </RouteLink>
        <div className="doctor-header-actions">
          <span className="demo-badge">{t("demo")}</span>
          {authenticated && (
            <button className="text-button" onClick={logout}>
              {t("logout")}
            </button>
          )}
          <LanguageSelect />
        </div>
      </header>
      <aside className="doctor-disclaimer" aria-label={t("demo")}>
        {t("disclaimer")}
      </aside>
      <div id="doctor-main" tabIndex={-1}>
        {!authenticated ? (
          <p role="status">{t("loading")}</p>
        ) : !valid ? (
          <ErrorMessage code="NOT_FOUND" />
        ) : (
          <main
            className={`doctor-workspace ${selected ? "selected-detail" : ""}`}
          >
            <Queue
              date={date}
              setDate={setDate}
              search={search}
              setSearch={setSearch}
              filter={filter}
              setFilter={setFilter}
              selected={selected}
              revision={revision}
            />
            {selected ? (
              <Detail
                key={`${auth.epoch}:${selected}`}
                id={selected}
                revision={revision}
              />
            ) : (
              <section className="doctor-welcome">
                <h2>{t("title")}</h2>
                <p>{t("select")}</p>
                <p>{t("storage")}</p>
                <details className="doctor-controls">
                  <summary>{t("controls")}</summary>
                  <button className="secondary" onClick={() => api.expire()}>
                    {t("expire")}
                  </button>
                </details>
              </section>
            )}
          </main>
        )}
      </div>
    </div>
  );
}
