import { tr, message, messageText, getLocale } from "../i18n/core.js";
import { useI18n, LanguageSelect } from "../i18n/react.jsx";
import { useEffect, useRef, useState, useSyncExternalStore } from "react";
import IntakeApp from "../pages/patient/App.jsx";
import { KEY, steps } from "../model.js";
import { accountService as api } from "./service.js";
import { useRoute, go, RouteLink } from "./router.jsx";
import {
  demoUsers,
  DEMO_PASSWORD,
  safeReturn,
  formatDate,
  sortAppointments,
  intakeLabels,
  appointmentLabels,
  appointmentGroup,
  recordSummary,
} from "./domain.js";
import "./portal.css";
const nav = () => [
  ["/my", tr("my.home")],
  ["/appointments", tr("appointments")],
  ["/intakes", tr("my.notes")],
  ["/account", tr("account")],
];
const titleOf = (r) =>
  r.data.reasons.find((x) => x.trim()) || tr("reason.for.visit.not.entered");
const editPath = (r) =>
  r.snapshot
    ? `/intakes/${r.id}`
    : `/intakes/${r.id}/edit/${r.status === "completed" ? "review" : r.step}`;
function Status({ kind, children }) {
  return <span className={`account-status status-${kind}`}>{children}</span>;
}
function Loading() {
  const locale = useI18n();
  useEffect(() => {
    document.title = tr("loading.demo.information") + " · " + tr("visit.notes");
  }, [locale]);
  return (
    <div className="account-loading" role="status">
      <span className="loading-dot" />
      {tr("loading.demo.information")}
    </div>
  );
}
function Empty({ title, children }) {
  return (
    <div className="account-empty">
      <span aria-hidden="true">—</span>
      <h2>{title}</h2>
      <p>{children}</p>
    </div>
  );
}
function ErrorView({ error, retry }) {
  const locale = useI18n();
  useEffect(() => {
    document.title =
      tr("unable.to.load.information") + " · " + tr("visit.notes");
  }, [locale]);
  return (
    <div className="account-error" role="alert">
      <h2>{tr("unable.to.load.information")}</h2>
      <p>{messageText(error.message)}</p>
      <button className="secondary" onClick={retry}>
        {tr("try.again")}
      </button>
    </div>
  );
}
function Intro({ eyebrow, title, children, action }) {
  const locale = useI18n();
  const ref = useRef(null);
  useEffect(() => {
    document.title = tr("value.visit.notes", { p0: title });
  }, [title, locale]);
  useEffect(() => {
    ref.current?.focus();
  }, []);
  return (
    <div className="portal-intro">
      <div className="eyebrow">{eyebrow}</div>
      <div className="portal-title-row">
        <h1 ref={ref} tabIndex={-1}>
          {title}
        </h1>
        {action}
      </div>
      {children && <p className="lead">{children}</p>}
    </div>
  );
}
function Shell({ user, path, children }) {
  return (
    <div className="portal">
      <a
        className="skip"
        href="#portal-main"
        onClick={(e) => {
          e.preventDefault();
          document.querySelector("h1")?.focus();
        }}
      >
        {tr("skip.to.content")}
      </a>
      <header className="header">
        <RouteLink to={user ? "/my" : "start"} className="brand">
          <span className="brand-symbol" aria-hidden="true">
            ✳
          </span>
          {tr("visit.notes")}
          <span className="brand-sub">
            {tr("your.story.ready.for.your.visit")}
          </span>
        </RouteLink>
        <div className="portal-header-end">
          <span className="demo-badge">
            <span />
            {tr("demo")}
          </span>
          {user && (
            <button
              className="text-button"
              onClick={() => {
                api.logout();
                go("/login", { replace: true });
              }}
            >
              {tr("log.out")}
            </button>
          )}
          <LanguageSelect />
        </div>
      </header>
      {user ? (
        <div className="portal-layout">
          <aside className="portal-nav">
            <p className="nav-caption">{tr("preparing.for.my.visit")}</p>
            <nav aria-label={tr("patient.account.navigation")}>
              {nav().map(([to, text], i) => (
                <RouteLink
                  key={to}
                  to={to}
                  aria-current={
                    path.split("/")[1] === to.slice(1) ? "page" : undefined
                  }
                >
                  <span aria-hidden="true">{["⌂", "▦", "≡", "○"][i]}</span>
                  {text}
                </RouteLink>
              ))}
            </nav>
            <div className="portal-nav-bottom">
              <strong>{user.name}</strong>
              <small>{tr("demo.patient.account")}</small>
              <RouteLink to="start">
                {tr("try.the.guest.questionnaire")}
              </RouteLink>
            </div>
          </aside>
          <main id="portal-main" className="portal-main">
            {children}
          </main>
        </div>
      ) : (
        <main id="portal-main" className="auth-main">
          {children}
        </main>
      )}
      <footer className="portal-footer">
        <span>{tr("demo.no.connection.to.real.accounts.or.hospitals")}</span>
        <span>{tr("visit.notes")}</span>
      </footer>
    </div>
  );
}
function Auth({ signup, returnTo, onAuthenticated, authMessage }) {
  const [values, setValues] = useState({
      name: "",
      email: "",
      password: "",
      confirm: "",
    }),
    [errors, setErrors] = useState({}),
    [busy, setBusy] = useState(false),
    [visible, setVisible] = useState(false),
    [notice, setNotice] = useState("");
  const lock = useRef(false),
    alive = useRef(true),
    controller = useRef(null);
  useEffect(() => {
    alive.current = true;
    return () => {
      alive.current = false;
      controller.current?.abort();
    };
  }, []);
  const set = (key, value) => {
    setValues((v) => ({ ...v, [key]: value }));
    setErrors((e) => ({ ...e, [key]: null, form: null }));
  };
  async function submit(e) {
    e.preventDefault();
    if (lock.current) return;
    const err = {};
    if (signup && !values.name.trim()) err.name = message("enter.your.name");
    if (!values.email.trim()) err.email = message("enter.your.email.address");
    else if (!/^\S+@\S+\.\S+$/.test(values.email.trim()))
      err.email = message("use.an.email.address.such.as.name.example.test");
    if (!values.password) err.password = message("enter.your.password");
    else if (signup && !/(?=.*[A-Za-z])(?=.*\d).{8,}/.test(values.password))
      err.password = message(
        "use.at.least.8.characters.including.a.letter.and.a.number",
      );
    if (signup && values.password !== values.confirm)
      err.confirm = message("passwords.do.not.match.please.check.them.again");
    if (signup && !values.confirm)
      err.confirm = message("enter.your.password.again");
    setErrors(err);
    if (Object.keys(err).length) {
      requestAnimationFrame(() =>
        document.querySelector('[aria-invalid="true"]')?.focus(),
      );
      return;
    }
    lock.current = true;
    controller.current = new AbortController();
    setBusy(true);
    try {
      if (signup) {
        await api.signup(values, controller.current.signal);
        if (alive.current) {
          setValues((v) => ({ ...v, password: "", confirm: "" }));
          go(`/login?returnTo=${encodeURIComponent(returnTo)}&registered=1`);
        }
      } else {
        await api.login(
          values.email,
          values.password,
          controller.current.signal,
        );
        if (alive.current) {
          setValues((v) => ({ ...v, password: "" }));
          onAuthenticated(returnTo);
        }
      }
    } catch (error) {
      if (alive.current) {
        setErrors(
          error.code === "EMAIL_EXISTS"
            ? { email: error.message }
            : { form: error.message },
        );
        setValues((v) => ({ ...v, password: "", confirm: "" }));
        requestAnimationFrame(() =>
          (
            document.querySelector('[aria-invalid="true"]') ||
            document.querySelector('[role="alert"][tabindex]')
          )?.focus(),
        );
      }
    } finally {
      if (alive.current) {
        lock.current = false;
        setBusy(false);
      }
    }
  }
  function field(key, label, type = "text", auto = "") {
    return (
      <div className="input-group">
        <label htmlFor={key}>{label}</label>
        <div className={key === "password" ? "password-field" : ""}>
          <input
            id={key}
            name={key}
            type={key === "password" && visible ? "text" : type}
            autoComplete={auto}
            value={values[key]}
            maxLength={key === "name" ? 80 : 254}
            aria-invalid={!!errors[key]}
            aria-describedby={
              [
                errors[key] ? `${key}-error` : null,
                key === "password" && signup ? "password-hint" : null,
              ]
                .filter(Boolean)
                .join(" ") || undefined
            }
            onChange={(e) => set(key, e.target.value)}
          />
          {key === "password" && (
            <button
              type="button"
              className="text-button"
              aria-label={visible ? tr("hide.password") : tr("show.password")}
              aria-pressed={visible}
              onClick={() => setVisible((x) => !x)}
            >
              {visible ? tr("hide") : tr("show")}
            </button>
          )}
        </div>
        {errors[key] && (
          <p className="field-error" id={`${key}-error`} role="alert">
            {messageText(errors[key])}
          </p>
        )}
      </div>
    );
  }
  return (
    <>
      <div className="auth-panel">
        <Intro
          eyebrow={tr("eyebrow.auth")}
          title={
            signup ? tr("create.your.visit.notes.account") : tr("welcome.back")
          }
        >
          {signup
            ? tr(
                "use.fictional.details.to.try.an.account.and.manage.your.notes",
              )
            : tr("find.your.appointments.and.questionnaires.in.one.place")}
        </Intro>
        {authMessage && (
          <p className="info-note" role="status">
            {messageText(authMessage)}
          </p>
        )}
        {new URLSearchParams(location.hash.split("?")[1]).has("registered") && (
          <p className="info-note" role="status">
            {tr(
              "your.demo.account.is.ready.log.in.with.the.email.and.password.you",
            )}
          </p>
        )}
        <form onSubmit={submit} noValidate>
          {signup && field("name", tr("name"), "text", "name")}
          {field("email", tr("email"), "email", "username")}
          {signup && (
            <p id="password-hint" className="password-hint">
              {tr(
                "demo.password.at.least.8.characters.including.a.letter.and.a.numb",
              )}
            </p>
          )}
          {field(
            "password",
            tr("password"),
            "password",
            signup ? "new-password" : "current-password",
          )}
          {signup &&
            field(
              "confirm",
              tr("confirm.password"),
              "password",
              "new-password",
            )}
          {errors.form && (
            <p className="error" role="alert" tabIndex={-1}>
              {messageText(errors.form)}
            </p>
          )}
          <button disabled={busy} className="primary auth-submit">
            {busy ? tr("processing") : signup ? tr("sign.up") : tr("log.in")}
            <span aria-hidden="true">→</span>
          </button>
          <p className="auth-switch">
            {signup ? tr("already.have.an.account") : tr("new.here")}{" "}
            <RouteLink
              to={`/${signup ? "login" : "signup"}?returnTo=${encodeURIComponent(returnTo)}`}
            >
              {signup ? tr("log.in") : tr("sign.up")}
            </RouteLink>
          </p>
          <div className="sr-only" role="status">
            {busy ? tr("processing.your.request") : messageText(notice)}
          </div>
        </form>
        <RouteLink className="guest-link" to="start">
          {tr("try.the.questionnaire.without.an.account")}
        </RouteLink>
      </div>
      <aside className="auth-context">
        <span className="context-label">{tr("try.a.demo.account")}</span>
        <div className="paper-icon" aria-hidden="true">
          <span>✳</span>
          <i />
          <i />
          <i />
          <b>✓</b>
        </div>
        <h2>{tr("your.visit.preparation.in.one.place")}</h2>
        <p>
          {tr("explore.different.records.and.empty.states")}
          <br />
          {tr("using.fictional.accounts")}
        </p>
        <div className="demo-accounts">
          {demoUsers.map((u, i) => (
            <button
              key={u.id}
              disabled={signup || busy}
              onClick={() => {
                setValues({
                  name: "",
                  email: u.email,
                  password: DEMO_PASSWORD,
                  confirm: "",
                });
                setErrors({});
                setNotice(
                  message("demo.email.and.password.entered.for.value", {
                    p0: u.name,
                  }),
                );
              }}
            >
              <strong>
                {u.name}
                <small>
                  {
                    [
                      tr("appointments.and.notes"),
                      tr("another.patient.s.records"),
                      tr("empty.account"),
                    ][i]
                  }
                </small>
              </strong>
              <span>{u.email}</span>
            </button>
          ))}
        </div>
        <p className="demo-password">
          {tr("shared.password")}
          <code>{DEMO_PASSWORD}</code>
        </p>
        <p className="footnote">
          {tr(
            "new.accounts.last.until.you.refresh.this.is.not.a.real.authentica",
          )}
        </p>
        <details>
          <summary>{tr("demo.controls")}</summary>
          <button
            className="text-button"
            onClick={() => {
              api.failOnce();
              setNotice(
                message("the.next.signup.or.login.request.will.fail.once"),
              );
            }}
          >
            {tr("fail.next.authentication.request")}
          </button>
        </details>
      </aside>
    </>
  );
}
function AppointmentRows({ items, intakes }) {
  return (
    <div className="record-list">
      {items.map((a) => {
        const r = intakes.find((i) => i.appointmentId === a.id);
        return (
          <RouteLink
            className="appointment-row"
            to={`/appointments/${a.id}`}
            key={a.id}
          >
            <div className="date-stamp">
              <span>
                {new Intl.DateTimeFormat(
                  getLocale() === "ko" ? "ko-KR" : "en-GB",
                  {
                    timeZone: "Asia/Seoul",
                    month: "short",
                  },
                ).format(new Date(a.startsAt))}
              </span>
              <strong>
                {new Intl.DateTimeFormat(
                  getLocale() === "ko" ? "ko-KR" : "en-GB",
                  {
                    timeZone: "Asia/Seoul",
                    day: "numeric",
                  },
                )
                  .format(new Date(a.startsAt))
                  .replace("일", "")}
              </strong>
            </div>
            <div className="record-main">
              <h3>
                {a.hospital} <span>· {a.department}</span>
              </h3>
              <p>{formatDate(a.startsAt)}</p>
              <small>{a.clinician || tr("clinician.not.assigned")}</small>
            </div>
            <div className="record-state">
              <Status kind={a.status}>{tr(appointmentLabels[a.status])}</Status>
              <small>
                {r ? tr(intakeLabels[r.status]) : tr("not.started")}
              </small>
            </div>
            <span className="row-arrow" aria-hidden="true">
              ↗
            </span>
          </RouteLink>
        );
      })}
    </div>
  );
}
function IntakeRows({ items, appointments }) {
  return (
    <div className="record-list">
      {items.map((r) => {
        const a = appointments.find((a) => a.id === r.appointmentId);
        return (
          <div className="intake-row" key={r.id}>
            <div className="record-main">
              <RouteLink to={`/intakes/${r.id}`}>
                <h3>{titleOf(r)}</h3>
              </RouteLink>
              <p>
                {a
                  ? `${a.hospital} · ${a.department}`
                  : tr("no.linked.appointment")}
              </p>
              <small>
                {tr("last.updated")}
                {formatDate(r.updatedAt)}
              </small>
            </div>
            <div className="record-state">
              <Status kind={r.status}>{tr(intakeLabels[r.status])}</Status>
              <RouteLink className="row-action" to={editPath(r)}>
                {r.status === "draft"
                  ? tr("continue.writing")
                  : r.status === "completed"
                    ? tr("review.and.edit")
                    : tr("view.note")}{" "}
                →
              </RouteLink>
            </div>
          </div>
        );
      })}
    </div>
  );
}
function RecordsPage({ path, scope, bundle, refresh }) {
  const [filter, setFilter] = useState("all"),
    [appointmentFilter, setAppointmentFilter] = useState("upcoming"),
    [error, setError] = useState(""),
    [confirmReset, setConfirmReset] = useState(false);
  const { appointments, intakes } = bundle;
  const recent = [...intakes].sort(
    (a, b) => Date.parse(b.updatedAt) - Date.parse(a.updatedAt),
  );
  const next = sortAppointments(appointments, "upcoming")[0];
  const guest = () => {
    try {
      return JSON.parse(sessionStorage.getItem(KEY));
    } catch {
      return null;
    }
  };
  const [guestAvailable, setGuestAvailable] = useState(
    () => !!guest()?.reasons?.some((x) => x.trim()),
  );
  function start(appointmentId = null) {
    try {
      const r = api.startIntake(scope, appointmentId);
      go(editPath(r));
    } catch (e) {
      setError(e.message);
    }
  }
  function importGuest() {
    try {
      const r = api.importGuest(
        scope,
        guest(),
        sessionStorage.getItem(`${KEY}-step`) || "reason",
      );
      sessionStorage.removeItem(KEY);
      sessionStorage.removeItem(`${KEY}-step`);
      setGuestAvailable(false);
      go(`/intakes/${r.id}`);
    } catch (e) {
      setError(e.message);
    }
  }
  const testControls = (
    <details className="account-test">
      <summary>{tr("demo.controls")}</summary>
      <div>
        <button
          onClick={() => {
            api.failOnce();
            refresh();
          }}
        >
          {tr("simulate.load.failure")}
        </button>
        <button
          onClick={() => {
            api.slowOnce();
            refresh();
          }}
        >
          {tr("simulate.slow.loading")}
        </button>
        <button onClick={() => api.expire()}>
          {tr("simulate.session.expiry")}
        </button>
      </div>
    </details>
  );
  let content;
  if (path === "/my") {
    const draft = recent.find((r) => r.status === "draft");
    content = (
      <>
        <Intro
          eyebrow={tr("eyebrow.home")}
          title={tr("hello.value", { p0: api.getSnapshot().user.name })}
        >
          {tr("see.your.next.appointment.and.the.notes.you.have.prepared")}
        </Intro>
        <section className="home-next">
          <div className="section-heading">
            <h2>{tr("next.appointment")}</h2>
            <RouteLink to="/appointments">
              {tr("view.all.appointments")}
            </RouteLink>
          </div>
          {next ? (
            <>
              <div className="next-top">
                <div>
                  <Status kind="scheduled">{tr("confirmed")}</Status>
                  <h2>
                    {next.hospital}
                    <span>{next.department}</span>
                  </h2>
                  <p>
                    {formatDate(next.startsAt)}{" "}
                    <small>{tr("korea.time")}</small>
                  </p>
                  <p>{next.clinician || tr("clinician.not.assigned")}</p>
                </div>
                <div className="next-date" aria-hidden="true">
                  {new Intl.DateTimeFormat(
                    getLocale() === "ko" ? "ko-KR" : "en-GB",
                    {
                      timeZone: "Asia/Seoul",
                      day: "numeric",
                    },
                  ).format(new Date(next.startsAt))}
                  <small>{tr("next.visit")}</small>
                </div>
              </div>
              <RouteLink className="primary" to={`/appointments/${next.id}`}>
                {tr("view.appointment")}
                <span>→</span>
              </RouteLink>
            </>
          ) : (
            <Empty title={tr("no.upcoming.appointments")}>
              {tr(
                "this.demo.does.not.create.appointments.you.can.write.a.questionna",
              )}
            </Empty>
          )}
        </section>
        <section className="home-section">
          <div className="section-heading">
            <h2>{tr("continue.your.questionnaire")}</h2>
          </div>
          {draft ? (
            <IntakeRows items={[draft]} appointments={appointments} />
          ) : (
            <div className="inline-empty">
              <p>{tr("no.questionnaires.in.progress")}</p>
              <button className="secondary" onClick={() => start()}>
                {tr("start.without.an.appointment")}
              </button>
            </div>
          )}
        </section>
        <section className="home-section">
          <div className="section-heading">
            <h2>{tr("recent.notes")}</h2>
            <RouteLink to="/intakes">{tr("view.all.my.notes")}</RouteLink>
          </div>
          {recent.filter((r) => r.id !== draft?.id).length ? (
            <IntakeRows
              items={recent.filter((r) => r.id !== draft?.id).slice(0, 3)}
              appointments={appointments}
            />
          ) : (
            <p className="inline-empty">
              {recent.length
                ? tr("no.other.recent.notes.besides.your.draft")
                : tr("no.notes.yet.your.first.questionnaire.will.appear.here")}
            </p>
          )}
        </section>
        {guestAvailable && (
          <div className="guest-import">
            <h2>{tr("you.have.a.guest.questionnaire")}</h2>
            <p>
              {tr(
                "choose.below.only.if.you.want.to.move.it.into.this.account.it.wil",
              )}
            </p>
            <button className="secondary" onClick={importGuest}>
              {tr("import.into.my.account")}
            </button>
            <button
              className="text-button"
              onClick={() => setGuestAvailable(false)}
            >
              {tr("not.now")}
            </button>
          </div>
        )}
      </>
    );
  } else if (path === "/appointments") {
    const items = sortAppointments(appointments, appointmentFilter);
    content = (
      <>
        <Intro eyebrow={tr("eyebrow.appointments")} title={tr("appointments")}>
          {tr("all.appointment.times.are.shown.in.korea.time.asia.seoul")}
        </Intro>
        <div
          className="filter-tabs"
          role="group"
          aria-label={tr("appointment.category")}
        >
          {[
            ["upcoming", tr("upcoming")],
            ["past", tr("past")],
            ["cancelled", tr("cancel")],
          ].map(([v, l]) => (
            <button
              key={v}
              aria-pressed={appointmentFilter === v}
              onClick={() => setAppointmentFilter(v)}
            >
              {l}
            </button>
          ))}
        </div>
        <p className="list-count" role="status">
          {tr("appointments.count", { count: items.length })}
        </p>
        {items.length ? (
          <AppointmentRows items={items} intakes={intakes} />
        ) : (
          <Empty
            title={
              appointments.length
                ? tr("no.matching.appointments")
                : tr("no.appointments.recorded")
            }
          >
            {tr(
              "these.are.fictional.appointment.records.you.can.also.manage.unlin",
            )}
          </Empty>
        )}
        <p className="footnote">
          {tr(
            "past.appointments.remain.confirmed.unless.there.is.information.th",
          )}
        </p>
      </>
    );
  } else if (path === "/intakes") {
    const items = recent.filter((r) => filter === "all" || r.status === filter);
    content = (
      <>
        <Intro
          eyebrow={tr("eyebrow.notes")}
          title={tr("my.notes")}
          action={
            <button className="secondary" onClick={() => start()}>
              {tr("start.without.an.appointment.2")}
            </button>
          }
        >
          {tr("continue.writing.or.review.your.summary.before.your.visit")}
        </Intro>
        <div
          className="filter-tabs"
          role="group"
          aria-label={tr("questionnaire.status.filter")}
        >
          {[
            ["all", tr("all")],
            ["draft", tr("in.progress")],
            ["completed", tr("completed")],
            ["sent", tr("sent")],
          ].map(([v, l]) => (
            <button
              key={v}
              aria-pressed={filter === v}
              onClick={() => setFilter(v)}
            >
              {l}
            </button>
          ))}
        </div>
        <p className="list-count" role="status">
          {tr("notes.count", { count: items.length })}
        </p>
        {items.length ? (
          <IntakeRows items={items} appointments={appointments} />
        ) : (
          <Empty
            title={
              intakes.length
                ? tr("no.notes.with.this.status")
                : tr("no.questionnaires.yet")
            }
          >
            {intakes.length
              ? tr("choose.another.filter.to.see.your.notes")
              : tr(
                  "start.a.questionnaire.without.an.appointment.or.check.your.appoin",
                )}
          </Empty>
        )}
      </>
    );
  } else if (path === "/account") {
    const user = api.getSnapshot().user;
    content = (
      <>
        <Intro eyebrow={tr("eyebrow.account")} title={tr("account")}>
          {tr("view.your.name.and.email.address")}
        </Intro>
        <dl className="detail-facts">
          <div>
            <dt>{tr("name")}</dt>
            <dd>{user.name}</dd>
          </div>
          <div>
            <dt>{tr("email")}</dt>
            <dd>{user.email}</dd>
          </div>
          <div>
            <dt>{tr("account.type")}</dt>
            <dd>{tr("fictional.demo.account")}</dd>
          </div>
        </dl>
        <div className="info-note">
          {tr(
            "this.is.not.secure.authentication.signup.passwords.are.not.stored",
          )}
        </div>
        <div className="actions">
          <button
            className="primary"
            onClick={() => {
              api.logout();
              go("/login", { replace: true });
            }}
          >
            {tr("log.out")}
          </button>
        </div>
        <div className="reset-zone">
          <h2>{tr("reset.this.account.s.demo.records")}</h2>
          <p>
            {tr(
              "only.this.account.s.appointments.and.notes.will.be.cleared.other",
            )}
          </p>
          {confirmReset ? (
            <div role="alert">
              <p>{tr("clear.all.fictional.records.for.this.account")}</p>
              <button
                className="secondary"
                onClick={() => {
                  api.resetCurrent(scope);
                  refresh();
                }}
              >
                {tr("confirm.record.reset")}
              </button>
              <button
                className="text-button"
                onClick={() => setConfirmReset(false)}
              >
                {tr("cancel")}
              </button>
            </div>
          ) : (
            <button
              className="text-button"
              onClick={() => setConfirmReset(true)}
            >
              {tr("reset.demo.records")}
            </button>
          )}
        </div>
      </>
    );
  } else if (/^\/appointments\/[^/]+$/.test(path)) {
    const a = appointments.find((a) => a.id === path.split("/")[2]);
    const r = a && intakes.find((r) => r.appointmentId === a.id);
    content = a ? (
      <>
        <RouteLink className="back-link" to="/appointments">
          {tr("appointments.3")}
        </RouteLink>
        <Intro eyebrow={tr("eyebrow.appointmentDetails")} title={a.hospital}>
          {a.department}
          {tr("appointment.details")}
        </Intro>
        <Status kind={a.status}>{tr(appointmentLabels[a.status])}</Status>
        <dl className="detail-facts">
          <div>
            <dt>{tr("appointment.date.and.time")}</dt>
            <dd>
              {formatDate(a.startsAt)}
              <small>{tr("korea.time.asia.seoul")}</small>
            </dd>
          </div>
          <div>
            <dt>{tr("department")}</dt>
            <dd>{a.department}</dd>
          </div>
          <div>
            <dt>{tr("clinician")}</dt>
            <dd>{a.clinician || tr("not.yet.assigned")}</dd>
          </div>
        </dl>
        {appointmentGroup(a) === "past" && a.status === "scheduled" && (
          <p className="info-note">
            {tr(
              "the.appointment.time.has.passed.whether.the.visit.took.place.is.n",
            )}
          </p>
        )}
        <section className="home-section">
          <div className="section-heading">
            <h2>{tr("questionnaire.for.this.appointment")}</h2>
          </div>
          {r ? (
            <>
              <IntakeRows items={[r]} appointments={appointments} />
              <p className="footnote">
                {tr(
                  "appointment.and.questionnaire.handoff.statuses.are.tracked.separa",
                )}
              </p>
            </>
          ) : (
            <div className="inline-empty">
              <p>
                {a.status === "cancelled"
                  ? tr(
                      "you.cannot.start.a.questionnaire.for.a.cancelled.appointment",
                    )
                  : tr(
                      "no.questionnaire.is.linked.yet.start.with.your.reason.for.visitin",
                    )}
              </p>
              {a.status !== "cancelled" && (
                <button className="primary" onClick={() => start(a.id)}>
                  {tr("start.questionnaire.2")}
                  <span>→</span>
                </button>
              )}
            </div>
          )}
        </section>
      </>
    ) : (
      <NotFound />
    );
  } else if (/^\/intakes\/[^/]+$/.test(path)) {
    const r = intakes.find((r) => r.id === path.split("/")[2]);
    const a = r && appointments.find((a) => a.id === r.appointmentId);
    content = r ? (
      <>
        <RouteLink className="back-link" to="/intakes">
          {tr("my.notes.2")}
        </RouteLink>
        <Intro
          eyebrow={r.snapshot ? tr("eyebrow.sent") : tr("eyebrow.noteDetails")}
          title={titleOf(r)}
        >
          {tr("last.updated")}
          {formatDate(r.updatedAt)}
        </Intro>
        <Status kind={r.status}>{tr(intakeLabels[r.status])}</Status>
        <p className="record-appointment">
          {a ? (
            <RouteLink to={`/appointments/${a.id}`}>
              {a.hospital} · {a.department}
              {tr("view.linked.appointment")}
            </RouteLink>
          ) : (
            tr("no.linked.appointment")
          )}
        </p>
        {r.snapshot ? (
          <div className="info-note">
            <strong>{tr("record.at.handoff.read.only")}</strong>
            <p>
              {formatDate(r.snapshot.sentAt)}
              {tr(
                "this.is.the.summary.from.the.handoff.simulation.nothing.was.sent",
              )}
            </p>
          </div>
        ) : (
          <div className="actions">
            <RouteLink className="primary" to={editPath(r)}>
              {r.status === "draft"
                ? tr("continue.writing")
                : tr("review.and.edit")}
              <span>→</span>
            </RouteLink>
          </div>
        )}
        <div className="summary">
          {recordSummary(r, getLocale()).map((s) => (
            <section key={s.title}>
              <h2>{s.title}</h2>
              <p>{s.text}</p>
            </section>
          ))}
        </div>
      </>
    ) : (
      <NotFound />
    );
  } else content = <NotFound />;
  return (
    <>
      {content}
      {error && (
        <p className="error" role="alert">
          {messageText(error)}
        </p>
      )}
      <div className="portal-page-bottom">
        <span>{tr("helping.you.share.your.story.2")}</span>
        {testControls}
      </div>
    </>
  );
}
function NotFound() {
  return (
    <>
      <Intro eyebrow={tr("eyebrow.notFound")} title={tr("record.not.found")}>
        {tr("the.address.is.invalid.or.this.account.cannot.access.the.record")}
      </Intro>
      <RouteLink className="secondary" to="/my">
        {tr("go.to.my.home")}
      </RouteLink>
    </>
  );
}
function ProtectedContent({ path, user, scope }) {
  const [result, setResult] = useState({ status: "loading" }),
    [attempt, setAttempt] = useState(0);
  const refresh = () => setAttempt((x) => x + 1);
  useEffect(() => {
    let active = true;
    setResult({ status: "loading" });
    api
      .load(scope)
      .then((bundle) => {
        if (active) setResult({ status: "ready", bundle });
      })
      .catch((error) => {
        if (active && error.code !== "SESSION_EXPIRED")
          setResult({ status: "error", error });
      });
    return () => {
      active = false;
    };
  }, [path, attempt, scope.epoch]);
  if (result.status === "loading")
    return (
      <Shell user={user} path={path}>
        <Loading />
      </Shell>
    );
  if (result.status === "error")
    return (
      <Shell user={user} path={path}>
        <ErrorView error={result.error} retry={refresh} />
      </Shell>
    );
  const match = path.match(/^\/intakes\/([^/]+)\/edit\/([a-z]+)$/);
  if (match) {
    const record = result.bundle.intakes.find((i) => i.id === match[1]);
    if (!record || !steps.includes(match[2]))
      return (
        <Shell user={user} path={path}>
          <NotFound />
        </Shell>
      );
    if (record.snapshot) return <ReadOnlyRedirect id={record.id} />;
    return (
      <IntakeApp
        key={`${user.id}:${record.id}`}
        account={{ record, scope, user }}
        onAccountSave={(data, step) => {
          const saved = api.saveIntake(scope, record.id, data, step);
          if (saved.record.snapshot)
            go(`/intakes/${record.id}`, { replace: true });
          return saved.saved;
        }}
      />
    );
  }
  return (
    <Shell user={user} path={path}>
      <RecordsPage
        key={path + attempt}
        path={path}
        scope={scope}
        bundle={result.bundle}
        refresh={refresh}
      />
    </Shell>
  );
}
function ReadOnlyRedirect({ id }) {
  useEffect(() => go(`/intakes/${id}`, { replace: true }), [id]);
  return <Loading />;
}
function LoginRedirect({ path }) {
  useEffect(
    () =>
      go(`/login?returnTo=${encodeURIComponent(safeReturn(path))}`, {
        replace: true,
      }),
    [path],
  );
  return <Loading />;
}
export default function Portal() {
  useI18n();
  const route = useRoute(),
    auth = useSyncExternalStore(api.subscribe, api.getSnapshot);
  const [path, query = ""] = route.split("?");
  const returnTo = safeReturn(new URLSearchParams(query).get("returnTo"));
  useEffect(() => {
    api.restore();
  }, []);
  useEffect(() => {
    if (auth.status !== "authenticated") return;
    const timer = setTimeout(
      () => api.expire(),
      Math.max(0, auth.expiresAt - Date.now()),
    );
    return () => clearTimeout(timer);
  }, [auth.epoch, auth.status, auth.expiresAt]);
  if (!path.startsWith("/")) return <IntakeApp key="guest" />;
  if (auth.status === "checking")
    return (
      <Shell>
        <Loading />
      </Shell>
    );
  if (path === "/login" || path === "/signup")
    return (
      <Shell>
        <Auth
          key={path}
          signup={path === "/signup"}
          returnTo={returnTo}
          authMessage={auth.message}
          onAuthenticated={(to) => go(to, { replace: true })}
        />
      </Shell>
    );
  if (auth.status !== "authenticated")
    return (
      <Shell>
        <LoginRedirect path={path} />
      </Shell>
    );
  return (
    <ProtectedContent
      key={`${auth.epoch}:${path}`}
      path={path}
      user={auth.user}
      scope={{ userId: auth.user.id, epoch: auth.epoch }}
    />
  );
}
