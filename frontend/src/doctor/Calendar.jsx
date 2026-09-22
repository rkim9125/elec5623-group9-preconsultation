import { useCallback, useEffect, useRef, useState } from "react";
import { useI18n } from "../i18n/react.jsx";
import { tr } from "../i18n/core.js";
import { TIME_ZONE, formatDate } from "../account/domain.js";
import { RouteLink } from "../account/router.jsx";
import { doctorService as api, dayKey } from "./service.js";
import {
  appointmentState,
  civilDate,
  groupEvents,
  monthDays,
  shiftMonth,
} from "./calendar.js";
import "./calendar.css";
const t = (key, vars) => tr(`calendar.${key}`, vars);
const dt = (key) => tr(`doctor.${key}`);
const errorCode = (e) =>
  ["NOT_FOUND", "SESSION_EXPIRED"].includes(e.code) ? e.code : "FAILED";

function Inspector({ id, revision, onUnavailable }) {
  const [result, setResult] = useState(null),
    [attempt, setAttempt] = useState(0);
  useEffect(() => {
    let live = true;
    setResult(null);
    api
      .detail(api.scope(), id)
      .then((data) => {
        if (live) setResult({ id, revision, data });
      })
      .catch((e) => {
        if (!live) return;
        if (e.code === "NOT_FOUND") onUnavailable();
        else setResult({ id, revision, error: errorCode(e) });
      });
    return () => {
      live = false;
    };
  }, [id, revision, attempt, onUnavailable]);
  const current =
    result?.id === id && result?.revision === revision ? result : null;
  if (!current) return <p role="status">{t("detailLoading")}</p>;
  if (current.error)
    return (
      <div role="alert">
        <p>{dt(current.error)}</p>
        {current.error === "FAILED" && (
          <button
            className="secondary"
            onClick={() => setAttempt((x) => x + 1)}
          >
            {dt("retry")}
          </button>
        )}
      </div>
    );
  const a = current.data,
    latest = a.submissions.at(-1);
  return (
    <>
      <span className="sr-only" role="status">
        {t("detailUpdated")}: {a.patient.name}
      </span>
      <h3>{a.patient.name}</h3>
      <p className="calendar-identifier">{a.patient.identifier}</p>
      <dl>
        <dt>{t("when")}</dt>
        <dd>{formatDate(a.startsAt)}</dd>
        {["hospital", "department", "clinician"].map((field) =>
          a[field] ? (
            <div key={field}>
              <dt>{t(field)}</dt>
              <dd>{a[field]}</dd>
            </div>
          ) : null,
        )}
        <dt>{t("appointmentStatus")}</dt>
        <dd>
          <span className="doctor-badge">{t(appointmentState(a))}</span>
        </dd>
        <dt>{t("completion")}</dt>
        <dd>{t(a.status === "completed" ? "completed" : "unconfirmed")}</dd>
        <dt>{t("intake")}</dt>
        <dd>{latest ? t("submitted") : dt("unsubmitted")}</dd>
        {latest && (
          <>
            <dt>{t("purpose")}</dt>
            <dd className="patient-text">
              {latest.data.reasons.filter(Boolean).join("; ") ||
                t("unconfirmed")}
            </dd>
            <dt>{t("submittedAt")}</dt>
            <dd>{formatDate(latest.submittedAt)}</dd>
            <dt>{t("version")}</dt>
            <dd>{latest.version}</dd>
            <dt>{t("review")}</dt>
            <dd>{dt(latest.reviews.length ? "reviewed" : "pending")}</dd>
          </>
        )}
      </dl>
      <details className="doctor-controls">
        <summary>{dt("controls")}</summary>
        <button
          className="secondary"
          onClick={() => {
            api.failNext("load");
            setAttempt((x) => x + 1);
          }}
        >
          {dt("failLoad")}
        </button>
      </details>
      {latest ? (
        <RouteLink
          className="primary calendar-detail-link"
          to={`/doctor/appointments/${encodeURIComponent(a.id)}`}
        >
          {t("openIntake")}
        </RouteLink>
      ) : (
        <p>{t("noIntake")}</p>
      )}
    </>
  );
}
export default function Calendar({ view, setView, revision }) {
  const locale = useI18n(),
    lang = locale === "ko" ? "ko-KR" : "en-GB";
  const { month, date, selected } = view;
  const days = monthDays(month),
    start = days[0],
    end = days.at(-1);
  const [result, setResult] = useState(null),
    [attempt, setAttempt] = useState(0),
    [notice, setNotice] = useState("");
  const panel = useRef(null),
    dayList = useRef(null);
  const today = dayKey();
  const onUnavailable = useCallback(() => {
    setNotice("unavailable");
    setView((v) => ({ ...v, selected: null }));
  }, [setView]);
  useEffect(() => {
    let live = true;
    setResult(null);
    api
      .listRange(api.scope(), start, end)
      .then((rows) => {
        if (!live) return;
        setResult({ start, end, revision, rows });
      })
      .catch((e) => {
        if (live) setResult({ start, end, revision, error: errorCode(e) });
      });
    return () => {
      live = false;
    };
  }, [start, end, revision, attempt, setView]);
  const current =
    result?.start === start &&
    result?.end === end &&
    result?.revision === revision
      ? result
      : null;
  useEffect(() => {
    if (!current?.rows || !selected) return;
    const row = current.rows.find((a) => a.id === selected);
    if (!row) onUnavailable();
    else if (view.selectedDate !== dayKey(row.startsAt)) {
      setView((v) => ({ ...v, selectedDate: dayKey(row.startsAt) }));
    }
  }, [current, selected, view.selectedDate, setView, onUnavailable]);
  const groups = groupEvents(current?.rows || []);
  const monthLabel = new Intl.DateTimeFormat(lang, {
    year: "numeric",
    month: "long",
    timeZone: "UTC",
  }).format(civilDate(`${month}-01`));
  const dateLabel = (value) =>
    new Intl.DateTimeFormat(lang, {
      dateStyle: "full",
      timeZone: "UTC",
    }).format(civilDate(value));
  const time = (value) =>
    new Intl.DateTimeFormat(lang, {
      hour: "2-digit",
      minute: "2-digit",
      hour12: false,
      timeZone: TIME_ZONE,
    }).format(new Date(value));
  function move(next) {
    const range = monthDays(next);
    setNotice("");
    setView((v) => ({
      ...v,
      month: next,
      date:
        v.date >= range[0] && v.date <= range.at(-1) ? v.date : `${next}-01`,
      selected:
        v.selectedDate >= range[0] && v.selectedDate <= range.at(-1)
          ? v.selected
          : null,
    }));
  }
  function select(row) {
    setNotice("");
    setView((v) => ({
      ...v,
      selected: row.id,
      selectedDate: dayKey(row.startsAt),
      date: dayKey(row.startsAt),
    }));
    if (window.matchMedia("(max-width: 700px)").matches) panel.current?.focus();
  }
  function chooseDate(value, focusList = false) {
    setView((v) => ({ ...v, date: value }));
    if (focusList) dayList.current?.focus();
  }
  const eventButton = (row) => (
    <button
      key={row.id}
      type="button"
      className={`calendar-event ${selected === row.id ? "is-selected" : ""}`}
      aria-pressed={selected === row.id}
      aria-label={`${formatDate(row.startsAt)}, ${row.patient.name}, ${t(appointmentState(row))}`}
      onClick={() => select(row)}
    >
      <span>
        <time dateTime={row.startsAt}>{time(row.startsAt)}</time>{" "}
        <strong>{row.patient.name}</strong>
      </span>
      <small>{t(appointmentState(row))}</small>
    </button>
  );
  return (
    <section
      className="doctor-welcome calendar-workspace"
      aria-label={t("title")}
    >
      <div className="calendar-main">
        <div className="calendar-heading">
          <div>
            <p className="calendar-kicker">{t("title")}</p>
            <h2>{monthLabel}</h2>
          </div>
          <div className="calendar-navigation">
            <button
              className="secondary"
              aria-label={t("previous")}
              onClick={() => move(shiftMonth(month, -1))}
            >
              ‹
            </button>
            <button
              className="secondary"
              onClick={() => {
                move(today.slice(0, 7));
                setView((v) => ({ ...v, date: today, selected: null }));
              }}
            >
              {t("today")}
            </button>
            <button
              className="secondary"
              aria-label={t("next")}
              onClick={() => move(shiftMonth(month, 1))}
            >
              ›
            </button>
          </div>
        </div>
        <p className="calendar-legend">
          {["upcoming", "past", "completed", "cancelled"].map((k) => (
            <span key={k}>{t(k)}</span>
          ))}
        </p>
        <p className="sr-only" role="status">
          {monthLabel} ·{" "}
          {t(!current ? "loading" : current.error ? "loadFailed" : "loaded")}
        </p>
        {!current && <p>{t("loading")}</p>}
        {current?.error && (
          <div role="alert">
            <p>{dt(current.error)}</p>
            {current.error === "FAILED" && (
              <button
                className="secondary"
                onClick={() => setAttempt((x) => x + 1)}
              >
                {dt("retry")}
              </button>
            )}
          </div>
        )}
        {current?.rows &&
          !current.rows.some((a) => dayKey(a.startsAt).startsWith(month)) && (
            <p role="status">{t("emptyMonth")}</p>
          )}
        <table className="calendar-table">
          <caption className="sr-only">{monthLabel}</caption>
          <thead>
            <tr>
              {days.slice(0, 7).map((d) => (
                <th key={d} scope="col">
                  {new Intl.DateTimeFormat(lang, {
                    weekday: "short",
                    timeZone: "UTC",
                  }).format(civilDate(d))}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {Array.from({ length: days.length / 7 }, (_, week) => (
              <tr key={week}>
                {days.slice(week * 7, week * 7 + 7).map((d) => (
                  <td
                    key={d}
                    className={`${d.startsWith(month) ? "" : "outside-month"} ${d === today ? "is-today" : ""} ${d === date ? "selected-day" : ""}`}
                  >
                    <button
                      className="calendar-day"
                      aria-label={`${dateLabel(d)}, ${t("count", { count: groups[d]?.length || 0 })}`}
                      aria-current={d === today ? "date" : undefined}
                      aria-pressed={d === date}
                      onClick={() => chooseDate(d)}
                    >
                      {Number(d.slice(-2))}
                      <span className="calendar-count">
                        {groups[d]?.length || ""}
                      </span>
                    </button>
                    <div className="calendar-cell-events">
                      {groups[d]?.slice(0, 2).map(eventButton)}
                      {groups[d]?.length > 2 && (
                        <button
                          className="calendar-more"
                          onClick={() => chooseDate(d, true)}
                        >
                          {t("more", { count: groups[d].length - 2 })}
                        </button>
                      )}
                    </div>
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
        <section
          className="calendar-day-list"
          ref={dayList}
          tabIndex={-1}
          aria-label={t("dayList")}
        >
          <h3>{dateLabel(date)}</h3>
          {current?.rows &&
            (groups[date]?.length ? (
              groups[date].map(eventButton)
            ) : (
              <p>{t("emptyDay")}</p>
            ))}
        </section>
        <details className="doctor-controls">
          <summary>{dt("controls")}</summary>
          <div>
            <button
              className="secondary"
              onClick={() => {
                api.failNext("calendar");
                setAttempt((x) => x + 1);
              }}
            >
              {t("failMonth")}
            </button>
            <button className="secondary" onClick={() => api.slowNext()}>
              {dt("slowNext")}
            </button>
            <button className="secondary" onClick={() => api.expire()}>
              {dt("expire")}
            </button>
          </div>
        </details>
      </div>
      <aside
        className="calendar-inspector"
        ref={panel}
        id="calendar-inspector"
        tabIndex={-1}
        aria-label={t("details")}
      >
        <h2>{t("details")}</h2>
        {notice && <p role="status">{t(notice)}</p>}
        {selected && current?.rows?.some((a) => a.id === selected) ? (
          <Inspector
            key={selected}
            id={selected}
            revision={revision}
            onUnavailable={onUnavailable}
          />
        ) : (
          <p>{t("select")}</p>
        )}
      </aside>
      {selected && (
        <button
          className="calendar-focus secondary"
          onClick={() => panel.current?.focus()}
        >
          {t("focusDetails")}
        </button>
      )}
    </section>
  );
}
