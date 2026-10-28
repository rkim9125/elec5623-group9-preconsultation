import React, { useCallback, useEffect, useRef, useState } from "react";
import Icon from "./Icons.jsx";
import {
  request,
  attachmentUrl,
  dateLabel,
  fileSize,
  progressFor,
} from "./api.js";
import { Button, ErrorNotice, Loading, Status, Empty, Modal } from "./UI.jsx";
import {
  BaselineForm,
  JourneyNavigation,
  SynthesisSummary,
} from "./Preparation.jsx";
import "./product.css";
import { navigateWithGuard } from "./navigation.js";
import { topicDescription, topicVisual } from "./topics.js";
import AssessmentReport, { ReportDownloadCard } from "./AssessmentReport.jsx";
import { shouldGenerateAssessment } from "./reportState.js";
import "./portal-theme.css";
import "./wizard.css";
import VoiceComposer from "./VoiceComposer.jsx";
import ProfileWizard, { hasProfile } from "./ProfileWizard.jsx";
import { LocaleProvider, useLocale, LanguageSwitcher } from "./i18n.jsx";
import FollowupPanel from "./FollowupPanel.jsx";
import { bloodGroupLabel } from "./bloodGroup.js";
import { recordTitle, recordLabel, recordedValue, slotStatusLabel } from "./recordLocale.js";
import SymptomOverview from "./SymptomOverview.jsx";

const setRoute = (path) => {
  return navigateWithGuard(() => {
    window.location.hash = path;
  });
};
function useHash() {
  const [route, update] = useState(
    location.hash.slice(1) ||
      (location.pathname.startsWith("/doctor") ? "/doctor" : "/patient"),
  );
  const currentRoute = useRef(route);
  useEffect(() => {
    const listener = async () => {
      const target =
        location.hash.slice(1) ||
        (location.pathname.startsWith("/doctor") ? "/doctor" : "/patient");
      const previous = currentRoute.current;
      const changed = await navigateWithGuard(() => {
        currentRoute.current = target;
        update(target);
      });
      if (
        !changed &&
        currentRoute.current === previous &&
        location.hash.slice(1) === target
      )
        history.replaceState(null, "", `#${previous}`);
    };
    const links = (event) => {
      const link = event.target.closest?.("a[href^='#/']");
      if (
        !link ||
        event.button !== 0 ||
        event.metaKey ||
        event.ctrlKey ||
        event.shiftKey ||
        event.altKey ||
        link.target === "_blank"
      )
        return;
      event.preventDefault();
      setRoute(link.getAttribute("href").slice(1));
    };
    window.addEventListener("hashchange", listener);
    document.addEventListener("click", links, true);
    return () => {
      window.removeEventListener("hashchange", listener);
      document.removeEventListener("click", links, true);
    };
  }, []);
  return route;
}
const roleFromRoute = (route) =>
  route.startsWith("/doctor") ? "doctor" : "patient";
function Brand({ light = false, role = "patient" }) {
  const { t } = useLocale();
  return (
    <a
      className={`brand ${light ? "brand-light" : ""}`}
      href={`#/${role}`}
      aria-label={t("PreConsult home")}
    >
      <span className="brand-symbol">
        <span />
        <span />
        <span />
        <span />
      </span>
      <span>
        PreConsult<span className="brand-sub">ELEC5623 · GROUP 9</span>
      </span>
    </a>
  );
}

function Login({ role, config, onLogin, currentUser, onSwitch, switchError }) {
  const { t } = useLocale();
  const [email, setEmail] = useState("");
  const [code, setCode] = useState("");
  const [sent, setSent] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [resendAt, setResendAt] = useState(0);
  const [seconds, setSeconds] = useState(0);
  const attemptGeneration = useRef(0);
  useEffect(() => {
    const timer = setInterval(
      () => setSeconds(Math.max(0, Math.ceil((resendAt - Date.now()) / 1000))),
      1000,
    );
    return () => clearInterval(timer);
  }, [resendAt]);
  useEffect(() => {
    attemptGeneration.current += 1;
    setSent(false);
    setError("");
    setCode("");
    setNotice("");
    setBusy(false);
    return () => {
      attemptGeneration.current += 1;
    };
  }, [role]);
  async function send(event) {
    event?.preventDefault();
    const attempt = attemptGeneration.current;
    setBusy(true);
    setError("");
    try {
      const result = await request("/auth/request-code", {
        method: "POST",
        body: { email: email.trim(), role },
      });
      if (attempt !== attemptGeneration.current) return;
      setSent(true);
      setNotice(
        result.message || "A sign-in code has been sent to your email.",
      );
      setResendAt(Date.now() + 60000);
      setSeconds(60);
    } catch (err) {
      if (attempt === attemptGeneration.current) setError(err.message);
    } finally {
      if (attempt === attemptGeneration.current) setBusy(false);
    }
  }
  async function verify(event) {
    event.preventDefault();
    const attempt = attemptGeneration.current;
    setBusy(true);
    setError("");
    try {
      const result = await request("/auth/verify", {
        method: "POST",
        body: { email: email.trim(), code: code.trim(), role },
      });
      if (attempt === attemptGeneration.current) onLogin(result.user);
    } catch (err) {
      if (attempt === attemptGeneration.current) setError(err.message);
    } finally {
      if (attempt === attemptGeneration.current) setBusy(false);
    }
  }
  return (
    <div className="auth-page" data-portal={role}>
      <div className="auth-story">
        <Brand light role={role} />
        <div className="story-copy">
          <span className="eyebrow">
            <span className="tiny-dot" />
            {t("A BETTER START TO YOUR CONSULTATION")}
          </span>
          <h1>
            {t("More understanding.")}
            <br />
            <em>{t("Better conversations.")}</em>
          </h1>
          <p>
            {t(
              "A little preparation makes room for what matters. Bring your health story together before you meet your doctor.",
            )}
          </p>
          <div className="story-illustration" aria-hidden="true">
            <div className="illustration-orbit orbit-one" />
            <div className="illustration-orbit orbit-two" />
            <div className="illustration-card">
              <span className="illustration-icon">
                <Icon name="heart" size={30} />
              </span>
              <div>
                <span className="illustration-line long" />
                <span className="illustration-line" />
              </div>
              <span className="illustration-check">
                <Icon name="check" size={16} />
              </span>
            </div>
            <div className="illustration-note">
              <Icon name="sparkle" size={18} />
              <span>{t("Your story, thoughtfully organised")}</span>
            </div>
          </div>
          <div className="story-points">
            <span>
              <Icon name="shield" size={18} />
              {t("You control what you share")}
            </span>
            <span>
              <Icon name="clock" size={18} />
              {t("Prepare at your own pace")}
            </span>
          </div>
        </div>
        <div className="auth-story-footer">
          {t("Pre-consultation preparation · For non-emergency care")}
        </div>
      </div>
      <div className="auth-form-side">
        <nav className="portal-switch" aria-label={t("Choose your portal")}>
          <a href="#/patient" className={role === "patient" ? "active" : ""}>
            {t("Patient portal")}
          </a>
          <a href="#/doctor" className={role === "doctor" ? "active" : ""}>
            {t("Doctor portal")}
          </a>
        </nav>
        <div className="auth-form-wrap">
          <span className="overline">
            {role === "doctor"
              ? t("CLINICIAN WORKSPACE")
              : t("YOUR HEALTH, IN YOUR WORDS")}
          </span>
          <h2>
            {currentUser
              ? t("Switch to the {role} portal?", {
                  role: t(role === "doctor" ? "Doctor" : "Patient"),
                })
              : sent
                ? t("Check your inbox.")
                : role === "doctor"
                  ? t("Welcome, doctor.")
                  : t("Let’s start with you.")}
          </h2>
          <p className="auth-intro">
            {currentUser ? (
              <>
                {t("You’re signed in to the {role} portal as {email}.", {
                  role: t(currentUser.role === "doctor" ? "Doctor" : "Patient"),
                  email: currentUser.email,
                })}{" "}
                {t("This browser uses one account and portal at a time.")}
              </>
            ) : sent ? (
              <>
                {t("Enter the verification code sent to {email}.", { email })}
              </>
            ) : role === "doctor" ? (
              t("Sign in to review patient-approved consultation summaries.")
            ) : (
              t(
                "Sign in or create your account with an email verification code. No password to remember.",
              )
            )}
          </p>
          <ErrorNotice>{error || switchError}</ErrorNotice>
          {config && (!config.auth_configured || !config.mail_configured) && (
            <div className="notice warning">
              <Icon name="info" />
              <span>
                {t(
                  "Email sign-in is not configured yet. The service administrator needs to finish email delivery setup.",
                )}
              </span>
            </div>
          )}
          {currentUser ? (
            <div className="portal-session-switch">
              <p>
                {t(
                  "Sign out and verify another email to switch portals. Your saved consultations will remain available.",
                )}
              </p>
              <Button
                className="primary full"
                busy={busy}
                onClick={async () => {
                  setBusy(true);
                  try {
                    await onSwitch();
                  } finally {
                    setBusy(false);
                  }
                }}
              >
                {t("Sign out and continue to {role} sign-in", {
                  role: t(role === "doctor" ? "Doctor" : "Patient"),
                })}
              </Button>
              <a
                className="button secondary full"
                href={`#/${currentUser.role}`}
              >
                {t("Return to {role} portal", {
                  role: t(currentUser.role === "doctor" ? "Doctor" : "Patient"),
                })}
              </a>
              <p className="field-hint">
                {t(
                  "To use both portals at the same time, open one in a private window or another browser profile.",
                )}
              </p>
            </div>
          ) : sent ? (
            <form onSubmit={verify}>
              <label className="field-label" htmlFor="auth-code">
                {t("Verification code")}
              </label>
              <input
                id="auth-code"
                className="input code-input"
                value={code}
                onChange={(e) =>
                  setCode(e.target.value.replace(/\D/g, "").slice(0, 8))
                }
                inputMode="numeric"
                autoComplete="one-time-code"
                placeholder={t("Enter your code")}
                required
                autoFocus
              />
              <p className="field-hint" role="status">
                {notice}
              </p>
              <Button
                type="submit"
                className="primary full"
                busy={busy}
                disabled={code.length < 6}
              >
                {t("Verify & continue")}
                <Icon name="arrow" size={18} />
              </Button>
              <div className="auth-resend">
                <button
                  type="button"
                  className="text-button"
                  disabled={busy || seconds > 0}
                  onClick={send}
                >
                  {seconds > 0
                    ? t("Resend code in {seconds}s", { seconds })
                    : t("Resend code")}
                </button>
                <button
                  type="button"
                  className="text-button"
                  disabled={busy}
                  onClick={() => {
                    setSent(false);
                    setCode("");
                    setError("");
                  }}
                >
                  {t("Use another email")}
                </button>
              </div>
            </form>
          ) : (
            <form onSubmit={send}>
              <label className="field-label" htmlFor="auth-email">
                {t("Email address")}
              </label>
              <div className="input-icon">
                <Icon name="mail" />
                <input
                  id="auth-email"
                  type="email"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  autoComplete="email"
                  placeholder={
                    role === "doctor"
                      ? t("you@yourclinic.com")
                      : t("you@example.com")
                  }
                  required
                />
              </div>
              <Button type="submit" className="primary full" busy={busy}>
                {t("Continue with email")}
                <Icon name="arrow" size={18} />
              </Button>
            </form>
          )}
          <div className="auth-assurance">
            <Icon name="lock" size={17} />
            <p>
              {t(
                "Your intake is shared with a doctor only after you review and approve it.",
              )}
            </p>
          </div>
          {role === "doctor" && (
            <p className="field-hint">
              {t(
                "Register with any email. Use a different email for your patient account.",
              )}
            </p>
          )}
        </div>
        <footer className="auth-footer">
          <LanguageSwitcher />
          <span>{t("Built for a more informed visit")}</span>
        </footer>
      </div>
    </div>
  );
}

function Shell({ user, route, onLogout, children }) {
  const { t } = useLocale();
  const [menu, setMenu] = useState(false);
  const doctor = user.role === "doctor";
  const base = doctor ? "/doctor" : "/patient";
  useEffect(() => setMenu(false), [route]);
  return (
    <div
      className={`app-shell ${menu ? "menu-open" : ""}`}
      data-portal={user.role}
    >
      <a
        className="skip-link"
        href="#main-content"
        onClick={(event) => {
          event.preventDefault();
          document.getElementById("main-content")?.focus();
        }}
      >
        {t("Skip to content")}
      </a>
      <aside className="sidebar">
        <Brand role={user.role} />
        <div className="workspace-label">
          {doctor ? t("CLINICIAN WORKSPACE") : t("PATIENT WORKSPACE")}
        </div>
        <nav className="side-nav" aria-label={t("Main navigation")}>
          <a href={`#${base}`} className={route === base ? "active" : ""}>
            <Icon name="grid" />
            <span>{doctor ? t("Patient overview") : t("Overview")}</span>
          </a>
          {!doctor && (
            <a
              href="#/patient/new"
              className={route === "/patient/new" ? "active" : ""}
            >
              <Icon name="plus" />
              <span>{t("New consultation")}</span>
            </a>
          )}
          <a
            href={`#${base}/history`}
            className={route.endsWith("/history") ? "active" : ""}
          >
            <Icon name="clock" />
            <span>
              {doctor ? t("All submissions") : t("Consultation history")}
            </span>
          </a>
          <a
            href={`#${base}/account`}
            className={route.endsWith("/account") ? "active" : ""}
          >
            <Icon name="person" />
            <span>{t("My account")}</span>
          </a>
        </nav>
        <div className="side-note">
          <span className="side-note-icon">
            <Icon name={doctor ? "shield" : "heart"} size={21} />
          </span>
          <h4>
            {doctor
              ? t("Patient-led sharing")
              : t("Make space for your story.")}
          </h4>
          <p>
            {doctor
              ? t("You see only approved summaries shared with your account.")
              : t("Pause anytime. Your progress is saved as you go.")}
          </p>
        </div>
        <div className="sidebar-bottom">
          <div className="user-avatar">
            {(user.name || user.email).slice(0, 1).toUpperCase()}
          </div>
          <div className="user-details">
            <strong>
              {user.name || (doctor ? "Clinician" : "My account")}
            </strong>
            <span title={user.email}>{user.email}</span>
          </div>
          <button
            className="icon-button"
            aria-label={t("Sign out")}
            onClick={onLogout}
          >
            <Icon name="logout" size={19} />
          </button>
        </div>
      </aside>
      {menu && (
        <button
          className="sidebar-scrim"
          aria-label={t("Close navigation")}
          onClick={() => setMenu(false)}
        />
      )}
      <div className="workspace">
        <header className="topbar">
          <button
            className="icon-button mobile-menu"
            aria-label={t("Open navigation")}
            onClick={() => setMenu(!menu)}
          >
            <Icon name="menu" />
          </button>
          <div className="breadcrumb">
            {doctor ? t("Doctor portal") : t("Patient portal")}
            <span>/</span>
            <strong>
              {route.endsWith("/account")
                ? t("My account")
                : route.endsWith("/new")
                  ? t("New consultation")
                  : route.includes("/intake/")
                    ? t("Consultation")
                    : route.endsWith("/history")
                      ? t("History")
                      : t("Overview")}
            </strong>
          </div>
          <LanguageSwitcher />
          <span className="connection-tag">
            <i />
            {t("Private workspace")}
          </span>
        </header>
        <main id="main-content" tabIndex="-1">
          {children}
        </main>
        <footer className="workspace-footer">
          <span>PreConsult · ELEC5623 Group 9</span>
          <span>
            {t("Preparation for care. Not a diagnosis or emergency service.")}
          </span>
        </footer>
      </div>
    </div>
  );
}

function Consultations({
  sessions,
  doctor = false,
  history = false,
  refresh,
  busy,
}) {
  const { t } = useLocale();
  const [query, setQuery] = useState("");
  const [filter, setFilter] = useState("all");
  const filtered = sessions.filter(
    (s) =>
      `${s.title || ""} ${recordTitle(s.title, t)} ${s.patient_name || ""} ${s.patient_email || ""} ${(s.concerns || []).map((c) => `${c.title} ${recordTitle(c.title, t)}`).join(" ")}`
        .toLowerCase()
        .includes(query.toLowerCase()) &&
      (filter === "all" ||
        (doctor
          ? filter === "reviewed"
            ? !!s.reviewed_at
            : !s.reviewed_at
          : s.status === filter)),
  );
  return (
    <section className="consultation-section">
      <div className="section-heading">
        <div>
          <h2>
            {doctor
              ? t("Patient submissions")
              : history
                ? t("Your consultations")
                : t("Recent consultations")}
          </h2>
          <p>
            {doctor
              ? t("Patient-approved information, ready for your review.")
              : t("Everything you’ve prepared, in one place.")}
          </p>
        </div>
        <Button className="subtle" icon="clock" busy={busy} onClick={refresh}>
          {t("Refresh")}
        </Button>
      </div>
      <div className="list-controls">
        <div className="search-field">
          <Icon name="search" size={18} />
          <input
            aria-label={t("Search consultations")}
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder={
              doctor
                ? t("Search patient or concern…")
                : t("Search your consultations…")
            }
          />
        </div>
        <select
          className="select"
          aria-label={t("Filter consultations")}
          value={filter}
          onChange={(e) => setFilter(e.target.value)}
        >
          <option value="all">{t("All statuses")}</option>
          {doctor ? (
            <>
              <option value="pending">{t("Needs review")}</option>
              <option value="reviewed">{t("Reviewed")}</option>
            </>
          ) : (
            <>
              <option value="active">{t("In progress")}</option>
              <option value="review">{t("Ready for review")}</option>
              <option value="approved">{t("Shared with doctor")}</option>
              <option value="withdrawn">{t("Sharing withdrawn")}</option>
              <option value="interrupted">{t("Safety pause")}</option>
            </>
          )}
        </select>
      </div>
      {!sessions.length ? (
        <Empty
          title={
            doctor
              ? t("Your workspace is ready")
              : t("Your first consultation starts here")
          }
          icon={doctor ? "shield" : "file"}
          action={
            !doctor && (
              <Button
                className="primary"
                icon="plus"
                onClick={() => setRoute("/patient/new")}
              >
                {t("Prepare a consultation")}
              </Button>
            )
          }
        >
          {doctor
            ? t(
                "When a patient approves a summary and shares it with your email, it will appear here.",
              )
            : t(
                "Tell us what’s on your mind. We’ll help organise the details for your doctor.",
              )}
        </Empty>
      ) : !filtered.length ? (
        <Empty title={t("No consultations found")} icon="search">
          {t("Try a different search or status filter.")}
        </Empty>
      ) : (
        <div className="consultation-list">
          <div className="list-header">
            <span>{doctor ? t("PATIENT & CONCERN") : t("CONSULTATION")}</span>
            <span>{t("LAST UPDATED")}</span>
            <span>{t("STATUS")}</span>
            <span />
          </div>
          {(history || doctor ? filtered : filtered.slice(0, 5)).map((s) => (
            <a
              className="consultation-row"
              href={`#/${doctor ? "doctor" : "patient"}/intake/${s.id}`}
              key={s.id}
            >
              <span className="row-main">
                <span className="row-icon">
                  <Icon name={doctor ? "person" : "file"} />
                </span>
                <span>
                  <strong>
                    {doctor
                      ? s.patient_name || s.patient_email || t("Patient")
                      : recordTitle(s.title, t, "Consultation preparation")}
                  </strong>
                  <small>
                    {doctor
                      ? recordTitle(s.title, t, "") ||
                        (s.concerns || []).map((c) => recordTitle(c.title, t)).join(" · ") ||
                        t("Consultation preparation")
                      : (s.concerns || []).map((c) => recordTitle(c.title, t)).join(" · ") ||
                        t("Getting to know your concerns")}
                  </small>
                </span>
              </span>
              <span className="row-date">{dateLabel(s.updated_at)}</span>
              <span>
                {doctor && s.reviewed_at ? (
                  <span className="status status-reviewed">
                    <i />
                    {t("Reviewed")}
                  </span>
                ) : (
                  <Status status={s.status} />
                )}
              </span>
              <Icon name="chevron" size={17} />
            </a>
          ))}
        </div>
      )}
      {!history && !doctor && sessions.length > 5 && (
        <a className="view-all" href="#/patient/history">
          {t("View all consultations")}
          <Icon name="arrow" size={16} />
        </a>
      )}
    </section>
  );
}

function Dashboard({ user, sessions, busy, error, refresh, history }) {
  const { t } = useLocale();
  const doctor = user.role === "doctor";
  const awaiting = sessions.filter((s) =>
    doctor ? !s.reviewed_at : ["active", "review"].includes(s.status),
  ).length;
  const shared = sessions.filter((s) =>
    doctor ? !!s.reviewed_at : s.status === "approved",
  ).length;
  return (
    <div className="page dashboard-page">
      <div className="page-heading">
        <div>
          <span className="overline">
            {history
              ? t("YOUR WORKSPACE")
              : doctor
                ? t("CARE STARTS WITH UNDERSTANDING")
                : t("A LITTLE PREPARATION. A BETTER VISIT.")}
          </span>
          <h1>
            {history
              ? t("Consultation history")
              : doctor
                ? user.name
                  ? t("Welcome, {name}.", { name: user.name })
                  : t("Welcome back.")
                : user.name
                  ? t("Welcome, {name}.", { name: user.name.split(" ")[0] })
                  : t("Welcome back.")}
          </h1>
          <p>
            {history
              ? t("Find, revisit and manage your consultation records.")
              : doctor
                ? t(
                    "A clearer picture of your patients, before the conversation begins.",
                  )
                : t("Let’s help your doctor see the whole picture.")}
          </p>
        </div>
        <div className="date-chip">
          <Icon name="clock" size={16} />
          {dateLabel(new Date())}
        </div>
      </div>
      <ErrorNotice>{error}</ErrorNotice>
      {!history && (
        <>
          {!doctor && (
            <section className="welcome-card">
              <div>
                <span className="eyebrow">{t("YOUR NEXT STEP")}</span>
                <h2>
                  {t("Good care starts")}
                  <br />
                  {t("with your story.")}
                </h2>
                <p>
                  {t(
                    "Share your concerns, add relevant documents, and create a summary you can review before sharing.",
                  )}
                </p>
                <Button
                  className="cream"
                  onClick={() => setRoute("/patient/new")}
                >
                  {t("Prepare a consultation")}
                  <Icon name="arrow" size={18} />
                </Button>
                <span className="welcome-footnote">
                  {t("At your pace · Saved as you go")}
                </span>
              </div>
              <div className="welcome-visual" aria-hidden="true">
                <div className="visual-circle" />
                <div className="visual-document">
                  <span className="document-cross">+</span>
                  <span className="document-title">
                    {t("Your visit, prepared.")}
                  </span>
                  <span className="document-rule" />
                  <span className="document-rule short" />
                  <span className="document-item">
                    <i />
                    {t("Your concerns")}
                  </span>
                  <span className="document-item">
                    <i />
                    {t("Your health context")}
                  </span>
                  <span className="document-item">
                    <i />
                    {t("Your questions")}
                  </span>
                  <span className="document-complete">
                    <Icon name="check" size={14} />
                    {t("Reviewed by you")}
                  </span>
                </div>
                <div className="visual-heart">
                  <Icon name="heart" size={30} />
                </div>
              </div>
            </section>
          )}
          <div className="metric-grid">
            <div className="metric-card">
              <span className="metric-icon mint">
                <Icon name="file" />
              </span>
              <div>
                <span>
                  {doctor ? t("Shared submissions") : t("Total consultations")}
                </span>
                <strong>{sessions.length.toString().padStart(2, "0")}</strong>
              </div>
            </div>
            <div className="metric-card">
              <span className="metric-icon peach">
                <Icon name="clock" />
              </span>
              <div>
                <span>
                  {doctor ? t("Awaiting your review") : t("In preparation")}
                </span>
                <strong>{awaiting.toString().padStart(2, "0")}</strong>
              </div>
            </div>
            <div className="metric-card">
              <span className="metric-icon blue">
                <Icon name="check" />
              </span>
              <div>
                <span>{doctor ? t("Reviewed") : t("Shared with doctor")}</span>
                <strong>{shared.toString().padStart(2, "0")}</strong>
              </div>
            </div>
          </div>
        </>
      )}
      <Consultations
        sessions={sessions}
        doctor={doctor}
        history={history}
        refresh={refresh}
        busy={busy}
      />
      {!history && !doctor && (
        <div className="how-it-works">
          <h3>{t("Your preparation, step by step")}</h3>
          <div>
            <p>
              <span>01</span>
              <strong>{t("Choose your concerns")}</strong>
              <small>{t("Select topics or describe your own.")}</small>
            </p>
            <p>
              <span>02</span>
              <strong>{t("Complete the essentials")}</strong>
              <small>
                {t("A grouped form, followed by relevant AI questions.")}
              </small>
            </p>
            <p>
              <span>03</span>
              <strong>{t("Review and share")}</strong>
              <small>
                {t("Check the AI summary, then approve it for your doctor.")}
              </small>
            </p>
          </div>
        </div>
      )}
    </div>
  );
}

function NewIntake({ workflows, config, onCreated }) {
  const { t, locale } = useLocale();
  const [selected, setSelected] = useState(null);
  const [query, setQuery] = useState("");
  const [category, setCategory] = useState("All concerns");
  const [model, setModel] = useState(config?.default_model || "gpt-6-sol");
  const [consent, setConsent] = useState(false);
  const [text, setText] = useState("");
  const [profile, setProfile] = useState(null);
  const [profileError, setProfileError] = useState("");
  const [editingProfile, setEditingProfile] = useState(false);
  const [useProfile, setUseProfile] = useState(true);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [voiceBusy, setVoiceBusy] = useState(false);
  const pendingSession = useRef(null);
  const heading = useRef(null);
  useEffect(() => {
    let alive = true;
    request("/auth/profile")
      .then((data) => {
        if (alive) setProfile(data.profile);
      })
      .catch((err) => {
        if (alive) setProfileError(err.message);
      });
    return () => {
      alive = false;
    };
  }, []);
  useEffect(() => {
    if (selected) heading.current?.focus();
  }, [selected]);
  const categories = [
    "All concerns",
    ...new Set(workflows.map((w) => topicVisual(w).area)),
  ];
  const shown = workflows.filter(
    (w) =>
      (category === "All concerns" || topicVisual(w).area === category) &&
      `${t(w.title)} ${t(topicDescription(w))} ${t(topicVisual(w).area)} ${w.title}`
        .toLowerCase()
        .includes(query.toLowerCase()),
  );
  const custom = selected === "custom";
  const current = workflows.find((w) => w.id === selected);
  const remembered = hasProfile(profile);
  async function create() {
    if (!consent || (custom && !text.trim()) || busy || voiceBusy) return;
    setBusy(true);
    setError("");
    try {
      let session = pendingSession.current;
      if (!session) {
        session = await request("/intakes", {
          method: "POST",
          body: {
            consent,
            model,
            workflow_ids: custom ? [] : [selected],
            mode: custom ? "chat" : "wizard",
            locale,
            use_profile: useProfile,
            title: current?.title,
          },
        });
        pendingSession.current = session;
      }
      if (custom)
        session = await request(`/intakes/${session.id}/messages`, {
          method: "POST",
          body: { text: text.trim(), action: "answer", locale },
        });
      pendingSession.current = null;
      onCreated(session);
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  }
  const profileCard = (
    <div className="remembered-card">
      <span className="remembered-icon">
        <Icon name={remembered ? "check" : "person"} size={22} />
      </span>
      <div>
        <strong>
          {t(
            remembered
              ? "Your background is already here"
              : "A little about you, remembered",
          )}
        </strong>
        <p>
          {t(
            remembered
              ? "Saved details fill themselves in. You can edit them anytime."
              : "Add lasting details once to make future visits easier.",
          )}
        </p>
      </div>
      <button
        className="text-button"
        type="button"
        disabled={busy || !!pendingSession.current}
        onClick={() => setEditingProfile(true)}
      >
        {t(remembered ? "Edit profile" : "Add profile")}
      </button>
      {remembered && (
        <label className="remember-toggle">
          <input
            type="checkbox"
            checked={useProfile}
            disabled={busy || !!pendingSession.current}
            onChange={(e) => setUseProfile(e.target.checked)}
          />
          {t("Use saved details for this visit")}
        </label>
      )}
      {profileError && (
        <p role="alert">
          {t("Saved profile is unavailable. You can still start without it.")}
        </p>
      )}
    </div>
  );
  const consentControl = (
    <label className="checkbox-label wizard-consent">
      <input
        type="checkbox"
        checked={consent}
        disabled={busy || voiceBusy || !!pendingSession.current}
        onChange={(e) => setConsent(e.target.checked)}
      />
      <span>
        {t(
          "I agree to AI processing of my answers and uploads to prepare my summary and preliminary assessment. I review it and choose what to share with my doctor.",
        )}
      </span>
    </label>
  );
  return (
    <div className="page new-page wizard-new">
      <a className="back-link" href="#/patient">
        <Icon name="back" size={16} />
        {t("Back to overview")}
      </a>
      <JourneyNavigation current={0} />
      {!selected ? (
        <>
          <header className="wizard-hero">
            <div className="wizard-emblem hero-emblem">
              <Icon name="heart" size={34} />
              <span className="emblem-spark">
                <Icon name="sparkle" size={15} />
              </span>
            </div>
            <span className="overline">
              {t("A LITTLE PREPARATION. A BETTER VISIT.")}
            </span>
            <h1>{t("How are you feeling today?")}</h1>
            <p>
              {t(
                "Start with one thing on your mind. We’ll take it one step at a time.",
              )}
            </p>
          </header>
          <button
            className="custom-chat-card"
            onClick={() => setSelected("custom")}
          >
            <span className="custom-chat-icon">
              <Icon name="message" size={29} />
            </span>
            <span>
              <span className="mini-label">{t("IN YOUR OWN WORDS")}</span>
              <strong>{t("Something else? Let’s talk.")}</strong>
              <small>
                {t(
                  "No category needed. Just type or speak, and we’ll take it from there.",
                )}
              </small>
            </span>
            <span className="custom-voice-decoration" aria-hidden="true">
              {[10, 20, 30, 17, 24].map((h, i) => (
                <i key={i} style={{ height: h }} />
              ))}
            </span>
            <Icon name="arrow" size={22} />
          </button>
          <div className="topic-browser">
            <div className="workflow-heading">
              <div>
                <h2>{t("Or choose a symptom or topic")}</h2>
                <p>{t("30 guided paths, shaped around you.")}</p>
              </div>
              <div className="search-field">
                <Icon name="search" size={18} />
                <input
                  value={query}
                  onChange={(e) => setQuery(e.target.value)}
                  aria-label={t("Search care pathways")}
                  placeholder={t("Search symptoms or concerns…")}
                />
              </div>
            </div>
            <div className="topic-filters" aria-label={t("Concern category")}>
              {categories.map((item) => (
                <button
                  type="button"
                  aria-pressed={category === item}
                  className={category === item ? "active" : ""}
                  key={item}
                  onClick={() => setCategory(item)}
                >
                  {t(item)}
                </button>
              ))}
            </div>
            <div className="workflow-grid">
              {shown.map((w) => (
                <button
                  key={w.id}
                  className={`workflow-card topic-${topicVisual(w).tone}`}
                  data-topic-id={w.id}
                  onClick={() => setSelected(w.id)}
                >
                  <div className="workflow-card-top">
                    <span className="pathway-icon">
                      <Icon name={topicVisual(w).icon} size={29} />
                    </span>
                    <Icon name="arrow" size={16} />
                  </div>
                  <strong>{t(w.title)}</strong>
                  <p>{t(topicDescription(w))}</p>
                  <small>{t(topicVisual(w).area)}</small>
                </button>
              ))}
            </div>
            {!shown.length && (
              <Empty title={t("No matching pathways")} icon="search">
                {t("Try another search or tell us in your own words.")}
              </Empty>
            )}
          </div>
          {profileCard}
        </>
      ) : (
        <div className="start-visit wizard-enter">
          <button
            className="text-button"
            disabled={busy || voiceBusy || !!pendingSession.current}
            onClick={() => {
              setSelected(null);
              setError("");
            }}
          >
            <Icon name="back" size={16} />
            {t("Change topic")}
          </button>
          <div className="wizard-emblem">
            <Icon
              name={custom ? "message" : topicVisual(current || {}).icon}
              size={38}
            />
          </div>
          <span className="overline">
            {t(custom ? "YOUR SPACE TO TALK" : "LET’S TAKE IT STEP BY STEP")}
          </span>
          <h1 ref={heading} tabIndex={-1}>
            {custom
              ? t("Tell us what’s on your mind.")
              : t(current?.title || "Your consultation")}
          </h1>
          <p>
            {t(
              custom
                ? "You don’t need the right words. Start wherever feels comfortable."
                : "A few simple questions, with room for your own words. You’re in control.",
            )}
          </p>
          {custom && (
            <>
              {consentControl}
              <VoiceComposer
                value={text}
                onChange={setText}
                onSend={consent ? create : undefined}
                onError={setError}
                disabled={busy}
                voiceEnabled={consent}
                onActivity={setVoiceBusy}
                maxLength={12000}
                placeholder={t("What would you like your doctor to know?")}
              />
            </>
          )}
          {profileCard}
          <details className="advanced-options">
            <summary>
              <Icon name="sparkle" size={16} />
              {t("Advanced options")}
            </summary>
            <label className="field-label" htmlFor="model">
              {t("Assistant model")}
            </label>
            <select
              id="model"
              className="select full"
              value={model}
              disabled={busy || !!pendingSession.current}
              onChange={(e) => setModel(e.target.value)}
            >
              {(
                config?.models || [{ id: "gpt-6-sol", label: "gpt-6-sol" }]
              ).map((m) => (
                <option key={m.id} value={m.id}>
                  {m.label}
                </option>
              ))}
            </select>
          </details>
          {!custom && consentControl}
          <ErrorNotice>{error}</ErrorNotice>
          {!custom && (
            <Button
              className="primary wizard-start"
              busy={busy}
              disabled={!consent}
              onClick={create}
            >
              {t("Let’s begin")}
              <Icon name="arrow" size={18} />
            </Button>
          )}
          {custom && (
            <Button
              className="primary full"
              busy={busy}
              disabled={!consent || !text.trim() || voiceBusy}
              onClick={create}
            >
              {t("Start conversation")}
              <Icon name="arrow" size={17} />
            </Button>
          )}
          <p className="wizard-privacy">
            <Icon name="lock" size={14} />
            {t("Private until you review and share.")}
          </p>
        </div>
      )}
      {editingProfile && (
        <ProfileWizard
          onClose={() => setEditingProfile(false)}
          onSaved={setProfile}
        />
      )}
    </div>
  );
}

function readable(value) {
  return typeof value === "string"
    ? value
    : value?.label ||
        value?.question ||
        value?.text ||
        value?.title ||
        JSON.stringify(value);
}
function SummaryText({ text }) {
  const { t } = useLocale();
  if (!text)
    return (
      <p className="muted">{t("A summary will appear after preparation.")}</p>
    );
  const lines = String(text).split("\n");
  const gapStart = lines.findIndex(
    (line) => line.trim() === "Unknown, skipped and uncollected information",
  );
  const gapEnd =
    gapStart < 0
      ? -1
      : lines.findIndex(
          (line, index) =>
            index > gapStart &&
            line.trim() === "Patient corrections awaiting reconciliation",
        );
  function render(line, i, list) {
    const clean = line.replace(/\*\*/g, "").trim();
    const bullet = /^[-*•]\s/.test(clean);
    const heading =
      /^#{1,4}\s/.test(clean) ||
      i === 0 ||
      (!bullet && /^[-*•]\s/.test((list[i + 1] || "").trim()));
    return !clean ? (
      <div className="summary-space" key={i} />
    ) : heading ? (
      <h3 key={i}>{clean.replace(/^#{1,4}\s*/, "")}</h3>
    ) : bullet ? (
      <p className="summary-bullet" key={i}>
        {clean.replace(/^[-*•]\s*/, "")}
      </p>
    ) : (
      <p key={i}>{clean}</p>
    );
  }
  const primary = gapStart < 0 ? lines : lines.slice(0, gapStart);
  const gaps =
    gapStart < 0
      ? []
      : lines.slice(gapStart + 1, gapEnd < 0 ? undefined : gapEnd);
  return (
    <div className="summary-text">
      {primary.map((line, i) => render(line, i, primary))}
      {gaps.length > 0 && (
        <details>
          <summary>{t("Unknown, skipped and uncollected information")}</summary>
          {gaps.map((line, i) => render(line, i + 1, gaps))}
        </details>
      )}
      {gapEnd > 0 &&
        lines.slice(gapEnd).map((line, i, list) => render(line, i, list))}
    </div>
  );
}

function Attachments({
  session,
  readonly = false,
  onRefresh,
  onText,
  onError,
}) {
  const { t } = useLocale();
  const [busy, setBusy] = useState(false);
  const [analyzing, setAnalyzing] = useState("");
  const [drag, setDrag] = useState(false);
  const input = useRef(null);
  const canEdit =
    !readonly &&
    !["approved", "withdrawn", "interrupted"].includes(session.status);
  async function upload(files) {
    setDrag(false);
    if (!files?.length || !canEdit) return;
    setBusy(true);
    onError("");
    try {
      for (const file of files) {
        if (
          ![
            "application/pdf",
            "image/jpeg",
            "image/png",
            "image/webp",
          ].includes(file.type)
        )
          throw new Error(
            `${file.name}: please upload a PDF, JPEG, PNG or WebP file.`,
          );
        if (file.size > 10 * 1024 * 1024)
          throw new Error(
            `${file.name} is too large. Each file must be 10 MB or smaller.`,
          );
        const body = new FormData();
        body.append("file", file);
        await request(`/intakes/${session.id}/attachments`, {
          method: "POST",
          body,
        });
      }
    } catch (err) {
      onError(err.message);
    } finally {
      await onRefresh();
      setBusy(false);
      if (input.current) input.current.value = "";
    }
  }
  async function remove(id) {
    setBusy(true);
    onError("");
    try {
      await request(`/intakes/${session.id}/attachments/${id}`, {
        method: "DELETE",
      });
      await onRefresh();
    } catch (err) {
      onError(err.message);
    } finally {
      setBusy(false);
    }
  }
  async function analyze(id) {
    setAnalyzing(id);
    onError("");
    try {
      const result = await request(
        `/intakes/${session.id}/attachments/${id}/analyze`,
        { method: "POST" },
      );
      onText(result.text);
    } catch (err) {
      onError(err.message);
    } finally {
      setAnalyzing("");
    }
  }
  return (
    <section className="attachments-panel">
      <div className="small-heading">
        <h3>{t("Supporting documents")}</h3>
        <span>{(session.attachments || []).length}</span>
      </div>
      {canEdit && (
        <>
          <input
            ref={input}
            type="file"
            accept="application/pdf,image/jpeg,image/png,image/webp"
            multiple
            hidden
            aria-label={t("Upload supporting documents")}
            onChange={(e) => upload(Array.from(e.target.files))}
          />
          <button
            disabled={busy}
            className={`upload-area ${drag ? "dragging" : ""}`}
            onClick={() => input.current?.click()}
            onDragOver={(e) => {
              e.preventDefault();
              setDrag(true);
            }}
            onDragLeave={() => setDrag(false)}
            onDrop={(e) => {
              e.preventDefault();
              upload(Array.from(e.dataTransfer.files));
            }}
          >
            {busy ? (
              <span className="spinner" />
            ) : (
              <Icon name="upload" size={22} />
            )}
            <strong>
              {busy ? t("Uploading…") : t("Drop a file or browse")}
            </strong>
            <span>{t("PDF, JPG, PNG or WebP · Up to 10 MB")}</span>
          </button>
          <p className="file-help">
            {t(
              "Files are shared with your approved summary. Use “Extract details” to review AI-read content before adding it to your story. The final AI assessment considers all uploaded files, and the complete PDF includes every image and uploaded PDF page.",
            )}
          </p>
        </>
      )}
      {!session.attachments?.length && !canEdit && (
        <p className="muted small">{t("No supporting documents attached.")}</p>
      )}
      <div className="attachment-list">
        {(session.attachments || []).map((file) => (
          <div className="attachment" key={file.id}>
            <a
              className="attachment-main"
              href={attachmentUrl(session.id, file.id)}
              target="_blank"
              rel="noreferrer"
            >
              {file.media_type?.startsWith("image/") ? (
                <img
                  src={attachmentUrl(session.id, file.id)}
                  alt="Uploaded document preview"
                />
              ) : (
                <span className="attachment-icon">
                  <Icon name="file" size={21} />
                </span>
              )}
              <span>
                <strong>{file.filename || file.name || "Document"}</strong>
                <small>
                  {fileSize(file.size_bytes || file.size)} ·{" "}
                  <span>{t("Open file")}</span>
                </small>
              </span>
            </a>
            {canEdit && (
              <div className="attachment-actions">
                {onText && (
                  <button
                    className="text-button"
                    disabled={!!analyzing || busy}
                    onClick={() => analyze(file.id)}
                  >
                    {analyzing === file.id ? (
                      t("Reading…")
                    ) : (
                      <>
                        <Icon name="sparkle" size={13} />
                        {t("Extract details")}
                      </>
                    )}
                  </button>
                )}
                <button
                  className="icon-button"
                  disabled={busy || !!analyzing}
                  aria-label={`Remove ${file.filename}`}
                  onClick={() => remove(file.id)}
                >
                  <Icon name="trash" size={15} />
                </button>
              </div>
            )}
          </div>
        ))}
      </div>
    </section>
  );
}

function CarePlan({ session }) {
  const { t } = useLocale();
  const progress = progressFor(session);
  return (
    <section className="care-plan">
      <div className="small-heading">
        <h3>{t("Your preparation plan")}</h3>
        <Icon name="sparkle" size={17} />
      </div>
      <div className="progress-heading">
        <span>{t("Questions addressed")}</span>
        <strong>{progress.percent}%</strong>
      </div>
      <div
        className="progress-track"
        role="progressbar"
        aria-label={t("Preparation progress")}
        aria-valuenow={progress.percent}
        aria-valuemin={0}
        aria-valuemax={100}
      >
        <span style={{ width: `${progress.percent}%` }} />
      </div>
      <p className="progress-hint">
        {progress.total
          ? t("{completed} of {total} questions addressed. Includes unknown and skipped answers.", { completed: progress.completed, total: progress.total })
          : t("Your plan develops as you share.")}
      </p>
      {session.concerns?.length ? (
        <div className="concern-plan-list">
          {session.concerns.map((concern, i) => {
            const slots = Object.values(concern.slots || {}).filter(
              (slot) => slot.status !== "NOT_APPLICABLE",
            );
            const done = slots.filter((s) => s.status !== "MISSING").length;
            return (
              <div
                key={concern.id}
                className={`concern-plan ${session.current_question?.concern_id === concern.id ? "current" : ""}`}
              >
                <span className="concern-number">
                  {slots.length && done === slots.length ? (
                    <Icon name="check" size={13} />
                  ) : (
                    String(i + 1).padStart(2, "0")
                  )}
                </span>
                <div>
                  <strong>{recordTitle(concern.title, t)}</strong>
                  <small>
                    {slots.length
                      ? t("{completed} of {total} topics addressed", { completed: done, total: slots.length })
                      : t("Details being gathered")}
                  </small>
                </div>
              </div>
            );
          })}
        </div>
      ) : (
        <p className="muted small">
          {t(
            "Start with what’s on your mind. The assistant will build a plan around your concerns.",
          )}
        </p>
      )}
      {session.plan?.rationale && (
        <details className="plan-details">
          <summary>{t("How this plan was chosen")}</summary>
          <p>{readable(session.plan.rationale)}</p>
        </details>
      )}
      <div className="plan-footer">
        <Icon name="info" size={15} />
        <p>
          {t(
            "You can say “I don’t know”, skip a question, or review at any time.",
          )}
        </p>
      </div>
    </section>
  );
}

function IntakeChat(props) {
  const { t } = useLocale();
  const { session, onUpdate, refresh, config, onEditBaseline } = props;
  if (!session.followup_batch) {
    const hasStory = (session.messages || []).some(
      (message) => message.role === "patient",
    );
    return session.baseline?.completed || hasStory ? (
      <FollowupEntry {...props} />
    ) : (
      <IntakeConversation {...props} />
    );
  }
  return (
    <FollowupPanel
      key={`${session.followup_batch.id}:${session.followup_batch.locale || session.locale || "en"}`}
      session={session}
      onUpdate={onUpdate}
      renderContext={({ blocked, onError }) => (
        <aside className="chat-context">
          <details className="chat-context-panel">
            <summary>
              <Icon name="file" size={18} />
              {t("Your consultation details")}
              <Icon name="chevron" size={16} />
            </summary>
            <CarePlan session={session} />
            {session.mode !== "chat" && (
              <Button
                className="secondary full"
                disabled={blocked}
                onClick={() => navigateWithGuard(onEditBaseline)}
              >
                {t("Edit health information")}
              </Button>
            )}
            <p className="model-caption">
              {config?.models?.find((model) => model.id === session.model)
                ?.label || session.model}
            </p>
          </details>
          <Attachments
            session={session}
            readonly={blocked}
            onRefresh={refresh}
            onError={onError}
          />
        </aside>
      )}
    />
  );
}

function FollowupEntry({ session, onUpdate, refresh, onEditBaseline }) {
  const { t, locale } = useLocale();
  const [action, setAction] = useState("");
  const [error, setError] = useState("");
  const ready =
    session.assistant?.mode === "ready" || session.status === "review";
  const unavailable = session.assistant?.mode === "unavailable";
  async function perform(kind) {
    if (kind === "review" && session.status === "review") {
      onUpdate(session);
      return;
    }
    setAction(kind);
    setError("");
    try {
      const next = await request(`/intakes/${session.id}/${kind}`, {
        method: "POST",
        body: { locale },
      });
      onUpdate(next);
    } catch (err) {
      setError(err.message);
    } finally {
      setAction("");
    }
  }
  return (
    <div className="conversation-workspace followup-workspace">
      <section className="followup-main">
        <header className="followup-intro">
          <div className="wizard-emblem">
            <Icon name="sparkle" size={30} />
          </div>
          <span className="overline">{t("AI analysis & follow-up")}</span>
          <h2>
            {t(
              ready
                ? "Your answers are ready."
                : "Let’s bring the remaining questions together.",
            )}
          </h2>
          <p>
            {t(
              ready
                ? "There are no more questions in this set. You can review your summary now."
                : "Your previous answers are saved. We’ll gather up to five useful questions into one set.",
            )}
          </p>
        </header>
        <ErrorNotice>{error}</ErrorNotice>
        {unavailable && (
          <p className="notice warning">
            {t(
              "AI analysis is temporarily unavailable. Your answers are saved; you can retry or review your summary.",
            )}
          </p>
        )}
        <div className="followup-footer">
          {!ready && (
            <Button
              className="primary"
              icon="sparkle"
              busy={action === "followup"}
              disabled={!!action}
              onClick={() => perform("followup")}
            >
              {t(unavailable ? "Try again" : "Prepare follow-up questions")}
            </Button>
          )}
          <Button
            icon="arrow"
            className={!ready ? "secondary" : "primary"}
            busy={action === "review"}
            disabled={!!action}
            onClick={() => perform("review")}
          >
            {t("Review my summary")}
          </Button>
        </div>
        {session.messages?.length > 0 && (
          <details className="followup-history">
            <summary>{t("Your saved conversation")}</summary>
            {session.messages.map((message, index) => (
              <div key={message.id || index}>
                <strong>
                  {t(
                    message.role === "patient" ? "You" : "PreConsult assistant",
                  )}
                </strong>
                <p>{message.text}</p>
              </div>
            ))}
          </details>
        )}
        <p className="wizard-privacy">
          <Icon name="lock" size={14} />
          {t("Private until you review and share.")}
        </p>
      </section>
      <aside className="chat-context">
        {session.mode !== "chat" && (
          <Button
            className="secondary full"
            disabled={!!action}
            onClick={onEditBaseline}
          >
            {t("Edit health information")}
          </Button>
        )}
        <Attachments
          session={session}
          readonly={!!action}
          onRefresh={refresh}
          onError={setError}
        />
      </aside>
    </div>
  );
}

function IntakeConversation({
  session,
  onUpdate,
  refresh,
  config,
  onEditBaseline,
}) {
  const { t, locale } = useLocale();
  const [voiceBusy, setVoiceBusy] = useState(false);
  const [text, setText] = useState("");
  const [notice, setNotice] = useState("");
  const [error, setError] = useState("");
  const [busyAction, setBusyAction] = useState("");
  const composer = useRef(null);
  const threadEnd = useRef(null);
  useEffect(() => {
    threadEnd.current?.scrollIntoView({ behavior: "smooth", block: "nearest" });
  }, [session.messages?.length]);
  const busy = !!busyAction;
  const assistant = session.assistant || {};
  const question = session.current_question;
  const messages = (session.messages || []).filter(
    (message) =>
      !session.followup_started_at ||
      message.created_at >= session.followup_started_at,
  );
  async function perform(action) {
    if (action === "answer" && !text.trim()) return;
    setBusyAction(action);
    setError("");
    setNotice("");
    try {
      const path =
        action === "review"
          ? "review"
          : action === "retry"
            ? "followup"
            : "messages";
      const next = await request(`/intakes/${session.id}/${path}`, {
        method: "POST",
        ...(["review", "retry"].includes(action)
          ? { body: { locale } }
          : {
              body: {
                text: action === "answer" ? text.trim() : "",
                action,
                locale,
              },
            }),
      });
      onUpdate(next);
      if (action === "answer") setText("");
    } catch (err) {
      setError(err.message);
    } finally {
      setBusyAction("");
    }
  }
  function addText(value, kind) {
    if (!value?.trim()) return;
    setText((previous) => (previous ? `${previous}\n\n${value}` : value));
    setNotice(
      `${kind} is ready to review below. Correct the wording, then send when you’re ready.`,
    );
    composer.current?.focus();
  }
  return (
    <div className="conversation-workspace">
      <section className="chat-main">
        <div className="chat-intro">
          <div className="wizard-emblem">
            <Icon name="message" size={31} />
          </div>
          <span className="overline">
            {t(
              session.mode === "chat"
                ? "YOUR SPACE TO TALK"
                : "A LITTLE MORE CONTEXT",
            )}
          </span>
          <h2>
            {t(
              session.mode === "chat"
                ? "Let’s put your story into words."
                : "Anything else you’d like to share?",
            )}
          </h2>
          <p>
            {t(
              "Take your time. Type or speak, and review your answers before sharing.",
            )}
          </p>
        </div>
        <ErrorNotice>{error}</ErrorNotice>
        <div
          className="chat-thread"
          role="log"
          aria-label={t("Preparation conversation")}
          aria-live="polite"
        >
          {messages.map((message, i) => (
            <div
              className={`chat-message chat-${message.role}`}
              key={message.id || i}
            >
              {message.role !== "patient" && (
                <span className="chat-assistant-icon">
                  <Icon name="sparkle" size={17} />
                </span>
              )}
              <div>
                <span className="chat-author">
                  {t(
                    message.role === "patient" ? "You" : "PreConsult assistant",
                  )}
                </span>
                <p>{message.text}</p>
              </div>
            </div>
          ))}
          {!messages.length && (
            <div className="chat-message chat-assistant">
              <span className="chat-assistant-icon">
                <Icon name="sparkle" size={17} />
              </span>
              <div>
                <span className="chat-author">{t("PreConsult assistant")}</span>
                <p>
                  {question?.question ||
                    t(
                      "Tell me what you’d like your doctor to know. You can start anywhere.",
                    )}
                </p>
              </div>
            </div>
          )}
          {question &&
            !messages.some(
              (message) =>
                message.role === "assistant" &&
                message.text === question.question,
            ) && (
              <div className="chat-message chat-assistant">
                <span className="chat-assistant-icon">
                  <Icon name="sparkle" size={17} />
                </span>
                <div>
                  <span className="chat-author">
                    {t("PreConsult assistant")}
                  </span>
                  <p>{t(question.question)}</p>
                </div>
              </div>
            )}
          {busy && (
            <div className="chat-thinking" role="status">
              <span className="spinner" />
              {t("Thinking about your answer…")}
            </div>
          )}
          <div ref={threadEnd} />
        </div>
        {question?.why && (
          <details className="question-why">
            <summary>
              <Icon name="info" size={14} />
              {t("Why this question?")}
            </summary>
            <p>{t(question.why)}</p>
          </details>
        )}
        {assistant.mode === "unavailable" && (
          <div className="chat-unavailable">
            <Icon name="info" size={17} />
            <span>
              {t("AI analysis & follow-up is unavailable. Your answers are saved.")}
            </span>
            <button
              type="button"
              className="text-button"
              disabled={busy || voiceBusy}
              onClick={() => perform("retry")}
            >
              {t("Try again")}
            </button>
          </div>
        )}
        {notice && (
          <p className="notice success" role="status">
            {notice}
          </p>
        )}
        <VoiceComposer
          value={text}
          onChange={setText}
          onSend={() => perform("answer")}
          onError={setError}
          disabled={busy}
          inputRef={composer}
          id="response"
          maxLength={12000}
          onActivity={setVoiceBusy}
          placeholder={t("Answer in your own words…")}
        />
        <div className="chat-bottom-actions">
          <div>
            {question && (
              <>
                <button
                  className="text-button"
                  disabled={busy || voiceBusy}
                  onClick={() => perform("unknown")}
                >
                  {t("I don’t know")}
                </button>
                <button
                  className="text-button"
                  disabled={busy || voiceBusy}
                  onClick={() => perform("skip")}
                >
                  {t("Skip this question")}
                </button>
              </>
            )}
          </div>
          <Button
            className="secondary"
            icon="sparkle"
            busy={busyAction === "review"}
            disabled={busy || voiceBusy || !!text.trim()}
            onClick={() => perform("review")}
          >
            {t("Review my summary")}
          </Button>
        </div>
        {!!text.trim() && (
          <p className="field-hint">
            {t(
              "Send or clear your unsent response before generating the summary.",
            )}
          </p>
        )}
        <p className="wizard-privacy">
          <Icon name="lock" size={14} />
          {t("Private until you review and share.")}
        </p>
      </section>
      <aside className="chat-context">
        <details className="chat-context-panel">
          <summary>
            <Icon name="file" size={18} />
            {t("Your consultation details")}
            <Icon name="chevron" size={16} />
          </summary>
          <CarePlan session={session} />
          {session.mode !== "chat" && (
            <Button
              className="secondary full"
              disabled={busy || voiceBusy}
              onClick={onEditBaseline}
            >
              {t("Edit health information")}
            </Button>
          )}
          <p className="model-caption">
            {config?.models?.find((model) => model.id === session.model)
              ?.label || session.model}
          </p>
        </details>
        <Attachments
          session={session}
          onRefresh={refresh}
          onText={(value) => addText(value, t("Extracted document details"))}
          onError={setError}
        />
      </aside>
    </div>
  );
}

function SlotDetails({ session }) {
  const { t } = useLocale();
  return (
    <div className="structured-details">
      {[
        ...(session.concerns || []),
        ...(Object.keys(session.shared_slots || {}).length
          ? [
              {
                id: "shared",
                title: "Shared health context",
                slots: session.shared_slots,
              },
            ]
          : []),
      ].map((concern) => (
        <details key={concern.id} className="concern-details">
          <summary>
            <span>{recordTitle(concern.title, t)}</span>
            <span>
              {Object.keys(concern.slots || {}).length} {t("topics")}
            </span>
            <Icon name="chevron" size={16} />
          </summary>
          <dl>
            {Object.entries(concern.slots || {}).map(([key, slot]) => (
              <div key={key}>
                <dt>{recordLabel(slot.label || key.replace(/_/g, " "), t)}</dt>
                <dd>
                  {slot.value != null && slot.value !== "" ? (
                    recordedValue(slot.value, t)
                  ) : (
                    <span className="muted">{t("Not provided")}</span>
                  )}
                  <span
                    className={`slot-status slot-${slot.status?.toLowerCase()}`}
                  >
                    {slotStatusLabel(slot.status, t)}
                  </span>
                </dd>
              </div>
            ))}
          </dl>
        </details>
      ))}
    </div>
  );
}

function ProfileSnapshot({ profile }) {
  const { t } = useLocale();
  if (!profile) return null;
  const sex = {
    female: "Female",
    male: "Male",
    intersex: "Intersex",
    prefer_not_to_say: "Prefer not to say",
  };
  const rows = [
    ["Date of birth", profile.date_of_birth],
    [
      "Age at this visit",
      profile.age_years == null ? "" : String(profile.age_years),
    ],
    ["Sex recorded at birth", t(sex[profile.sex_at_birth] || "")],
    ["Blood group", bloodGroupLabel(profile.blood_group, t)],
    ["Accessibility needs", profile.accessibility_needs],
  ].filter(([, value]) => value);
  if (!rows.length) return null;
  return (
    <section className="profile-snapshot">
      <h3>
        <Icon name="person" size={18} />
        {t("Background for this visit")}
      </h3>
      <p>{t("Your saved details at the start of this consultation.")}</p>
      <dl>
        {rows.map(([label, value]) => (
          <div key={label}>
            <dt>{t(label)}</dt>
            <dd>{value}</dd>
          </div>
        ))}
      </dl>
    </section>
  );
}

function Review({
  session,
  config,
  doctor,
  onUpdate,
  refresh,
  assessmentBusy,
  assessmentError,
  onGenerateAssessment,
}) {
  const { t, locale } = useLocale();
  const [correction, setCorrection] = useState("");
  const [doctorEmail, setDoctorEmail] = useState(session.doctor_email || "");
  const [confirmed, setConfirmed] = useState(false);
  const [actionBusy, setBusy] = useState(false);
  const busy = actionBusy || assessmentBusy;
  const [error, setError] = useState("");
  const [approvalError, setApprovalError] = useState("");
  const approvalErrorRef = useRef(null);
  const [notice, setNotice] = useState("");
  const [withdraw, setWithdraw] = useState(false);
  useEffect(
    () => setConfirmed(false),
    [
      session.summary?.version,
      locale,
      session.attachments?.map((file) => file.id).join(","),
    ],
  );
  const canApprove = !doctor && session.status === "review";
  const staleSummaryLanguage = session.summary?.synthesis?.status === "live" &&
    (session.summary.synthesis.localization_outdated ||
      session.summary.synthesis.locale !== locale);
  const staleAssessmentLanguage = session.ai_report?.status === "ready" &&
    (session.ai_report.localization_outdated || session.ai_report.locale !== locale);
  const staleReportLanguage = staleSummaryLanguage || staleAssessmentLanguage;
  useEffect(() => {
    if (!approvalError) return;
    approvalErrorRef.current?.focus({ preventScroll: true });
    approvalErrorRef.current?.scrollIntoView({ block: "nearest", behavior: "auto" });
  }, [approvalError]);
  async function correct(event) {
    event.preventDefault();
    setBusy(true);
    setError("");
    try {
      const updated = await request(`/intakes/${session.id}/review`, {
        method: "PATCH",
        body: { text: correction, locale },
      });
      onUpdate(updated);
      if (!updated.summary?.needs_reconciliation) setCorrection("");
      setConfirmed(false);
      setNotice(
        updated.summary?.needs_reconciliation
          ? ""
          : "Your summary has been updated. Please review the revised version before approving.",
      );
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  }
  async function approve(event) {
    event.preventDefault();
    if (staleReportLanguage) {
      setApprovalError("Refresh the summary and assessment in your selected language before sharing.");
      return;
    }
    setBusy(true);
    setError("");
    setApprovalError("");
    try {
      onUpdate(
        await request(`/intakes/${session.id}/approve`, {
          method: "POST",
          body: {
            version: session.summary?.version,
            doctor_email: doctorEmail.trim(),
          },
        }),
      );
      setNotice("Your approved summary has been shared with your doctor.");
    } catch (err) {
      setApprovalError(err.message);
    } finally {
      setBusy(false);
    }
  }
  async function action(kind) {
    setBusy(true);
    setError("");
    setWithdraw(false);
    try {
      onUpdate(
        await request(
          doctor
            ? `/clinician/intakes/${session.id}/reviewed`
            : `/intakes/${session.id}/${kind}`,
          {
            method: "POST",
            ...(!doctor && kind === "review" ? { body: { locale } } : {}),
          },
        ),
      );
      setNotice(
        doctor
          ? "This submission has been marked as reviewed."
          : kind === "review"
            ? "Your summary has been refreshed. Review the current version before sharing."
            : "Sharing has been withdrawn. This summary is no longer visible in the doctor portal.",
      );
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  }
  return (
    <>
      <ErrorNotice>{error}</ErrorNotice>
      {notice && (
        <div className="notice success" role="status">
          <Icon name="check" />
          <span>{notice}</span>
        </div>
      )}
      {session.summary?.needs_reconciliation && (
        <div className="notice warning">
          <Icon name="info" />
          <span>
            {t(
              "A saved correction has not been reconciled with the summary. Sharing is paused. Retry the correction in the form below when the AI service is available, then review the revised summary.",
            )}
          </span>
        </div>
      )}
      {session.status === "approved" && !doctor && (
        <div className="shared-banner">
          <span>
            <Icon name="check" size={25} />
          </span>
          <div>
            <h2>{t("Your story is ready for your doctor.")}</h2>
            <p>
              {t("You approved version {version}. Shared with {email}.", {
                version: session.summary?.version,
                email: session.doctor_email,
              })}
            </p>
          </div>
        </div>
      )}
      {session.status === "withdrawn" && (
        <div className="notice warning">
          <Icon name="shield" />
          <span>
            {t(
              "You withdrew sharing. Your doctor can no longer access this record in PreConsult.",
            )}
          </span>
          {session.consent && (
            <Button
              className="secondary"
              busy={busy}
              onClick={() => action("review")}
            >
              {t("Revise preparation")}
            </Button>
          )}
        </div>
      )}
      {session.status === "interrupted" && (
        <div className="notice error">
          <Icon name="info" />
          <span>
            {t(
              "This preparation was paused for safety. Follow the safety guidance below. For an emergency in Australia, call 000.",
            )}
          </span>
        </div>
      )}
      <div className="review-layout">
        <section className="review-document">
          <div className="review-document-heading">
            <div>
              <span className="overline">
                {doctor
                  ? t("SHARED CONSULTATION RECORD")
                  : canApprove
                    ? t("YOUR DRAFT · FOR YOUR REVIEW")
                    : t("YOUR CONSULTATION SUMMARY")}
              </span>
              <h2>
                {doctor
                  ? session.patient_name || session.patient_email
                  : t("Your consultation report")}
              </h2>
              <p>
                {dateLabel(session.created_at)} <span>·</span> {t("Version")}{" "}
                {session.summary?.version || 1}
                {doctor && (
                  <>
                    {" "}
                    <span>·</span> {session.patient_email}
                  </>
                )}
              </p>
            </div>
          </div>
          <ProfileSnapshot profile={session.profile_snapshot} />
          <AssessmentReport
            session={session}
            busy={busy}
            generating={assessmentBusy}
            error={assessmentError}
            onGenerate={onGenerateAssessment}
            configured={config?.ai_configured !== false}
          />
          <div className="factual-summary-heading">
            <span className="section-kicker">
              {t("THE RECORDED INFORMATION")}
            </span>
            <h2>{t("Patient preparation summary")}</h2>
          </div>
          <div className="summary-disclaimer">
            <Icon name="info" size={17} />
            <p>
              {session.summary?.synthesis?.status === "live"
                ? t("AI-assisted, patient-reported information.")
                : t("Structured, patient-reported information.")}{" "}
              {doctor
                ? t(
                    "Verify details with the patient. This is not a diagnosis or treatment recommendation.",
                  )
                : t(
                    "Check for missing or incorrect details. This is not a diagnosis or treatment recommendation.",
                  )}
            </p>
          </div>
          <SymptomOverview session={session} />
          {session.summary && (
            <SynthesisSummary
              synthesis={session.summary.synthesis}
              patientLocale={session.locale || "en"}
              preserveApproved={session.status === "approved"}
              doctor={doctor}
              busy={busy}
              readOnly={
                doctor || !canApprove || !!session.summary.needs_reconciliation
              }
              onGenerate={() => action("review")}
            />
          )}
          <details
            className="raw-record"
            open={session.summary?.synthesis?.status !== "live"}
          >
            <summary>
              <Icon name="file" size={18} />
              <span>{t("Structured preparation record")}</span>
              <Icon name="chevron" size={17} />
            </summary>
            <SummaryText
              text={
                session.summary?.text ||
                (session.status === "interrupted"
                  ? session.messages
                      ?.filter((m) => m.role === "assistant")
                      .at(-1)?.text
                  : "")
              }
            />
            {session.summary?.gaps?.length > 0 &&
              !session.summary?.text?.includes(
                "Unknown, skipped and uncollected information",
              ) && (
                <details className="summary-gaps">
                  <summary>
                    <Icon name="info" size={18} />
                    <span>
                      {t("Details still to clarify ({count})", {
                        count: session.summary.gaps.length,
                      })}
                    </span>
                    <Icon name="chevron" size={16} />
                  </summary>
                  <ul>
                    {session.summary.gaps.map((gap, i) => (
                      <li key={i}>{readable(gap)}</li>
                    ))}
                  </ul>
                </details>
              )}
            <div className="structured-heading">
              <h3>{t("Detailed health information")}</h3>
              <p>{t("Review the information gathered for each concern.")}</p>
            </div>
            <SlotDetails session={session} />
          </details>
          {canApprove && (
            <form className="correction-form" onSubmit={correct}>
              <label htmlFor="correction">
                <Icon name="file" size={19} />
                {t("Anything to correct or add?")}
              </label>
              <p>
                {t(
                  "Describe the change, and we’ll revise the summary for another review.",
                )}
              </p>
              <textarea
                id="correction"
                value={correction}
                onChange={(e) => setCorrection(e.target.value)}
                rows={3}
                placeholder={t(
                  "e.g. The pain started on Monday, not last week…",
                )}
                required
                maxLength={10000}
                disabled={busy}
              />
              <Button
                className="secondary"
                type="submit"
                disabled={!correction.trim() || busy}
                busy={busy}
              >
                {t("Update my summary")}
              </Button>
            </form>
          )}
        </section>
        <aside className="review-aside">
          <ReportDownloadCard
            session={session}
            busy={busy}
            onBusyChange={setBusy}
          />
          {canApprove && (
            <form className="approval-card" onSubmit={approve}>
              <span className="approval-icon">
                <Icon name="shield" size={25} />
              </span>
              <h2>{t("You’re in control.")}</h2>
              <p>
                {t(
                  "When you’re happy with the details, choose your doctor and approve sharing.",
                )}
              </p>
              <label className="field-label" htmlFor="doctor-email">
                {t("Doctor’s email address")}
              </label>
              <input
                id="doctor-email"
                className="input"
                type="email"
                list="registered-doctors"
                placeholder={t("doctor@clinic.com")}
                value={doctorEmail}
                onChange={(e) => {
                  setDoctorEmail(e.target.value);
                  setApprovalError("");
                }}
                aria-describedby={approvalError ? "approval-error" : undefined}
                required
              />
              <datalist id="registered-doctors">
                {config?.care_team?.map((person) => (
                  <option key={person.email} value={person.email}>
                    {person.name || person.email}
                  </option>
                ))}
              </datalist>
              <p className="field-hint">
                {t(
                  "Only this authorised clinician can access the shared record.",
                )}
              </p>
              {config?.doctor_configured === false && (
                <div className="notice warning" role="status">
                  <Icon name="info" />
                  <span>
                    {t(
                      "Ask your doctor to create a doctor account, then enter their email. Your draft is saved.",
                    )}
                  </span>
                </div>
              )}
              <label className="checkbox-label">
                <input
                  type="checkbox"
                  checked={confirmed}
                  disabled={staleReportLanguage}
                  onChange={(e) => setConfirmed(e.target.checked)}
                />
                <span>
                  {t(
                    "I have reviewed this consultation record and approve sharing the summary, AI assessment and my attached files with this doctor.",
                  )}
                </span>
              </label>
              {approvalError && (
                <div id="approval-error" ref={approvalErrorRef} tabIndex={-1}>
                  <ErrorNotice>{approvalError}</ErrorNotice>
                </div>
              )}
              <Button
                className="primary full"
                type="submit"
                disabled={
                  !confirmed ||
                  !doctorEmail.trim() ||
                  busy ||
                  !!correction.trim() ||
                  session.summary?.needs_reconciliation ||
                  staleReportLanguage
                }
                busy={busy}
              >
                {t("Approve & share")}
                <Icon name="arrow" size={16} />
              </Button>
              {staleReportLanguage && <p className="field-hint">{t("Refresh the summary and assessment in your selected language before sharing.")}</p>}
              {correction.trim() && (
                <p className="field-hint">
                  {t("Apply or clear your correction before approving.")}
                </p>
              )}
              <small>{t("You can withdraw sharing later.")}</small>
            </form>
          )}
          {doctor && (
            <div className="approval-card">
              <span className="approval-icon">
                <Icon name="check" size={25} />
              </span>
              <h2>
                {session.reviewed_at
                  ? t("Review complete")
                  : t("Ready for your review")}
              </h2>
              <p>
                {session.reviewed_at
                  ? `Marked as reviewed ${dateLabel(session.reviewed_at, true)}.`
                  : t(
                      "Review the patient’s summary, preliminary AI assessment and supporting documents before your consultation.",
                    )}
              </p>
              {!session.reviewed_at && (
                <Button
                  className="primary full"
                  busy={busy}
                  icon="check"
                  onClick={() => action("reviewed")}
                >
                  {t("Mark as reviewed")}
                </Button>
              )}
              <p className="field-hint">
                {t(
                  "Marking this record as reviewed does not confirm the AI’s proposed diagnoses.",
                )}
              </p>
            </div>
          )}
          <Attachments
            session={session}
            readonly={busy || doctor || session.status !== "review"}
            onRefresh={refresh}
            onError={setError}
          />
          {session.status === "approved" && !doctor && (
            <div className="sharing-control">
              <h3>{t("Sharing settings")}</h3>
              <p>
                {t("Your summary, AI assessment and files are visible to")}{" "}
                <strong>{session.doctor_email}</strong>.
              </p>
              <Button
                className="secondary full"
                busy={busy}
                onClick={() => setWithdraw(true)}
              >
                {t("Withdraw sharing")}
              </Button>
              <p className="field-hint">
                {t(
                  "Withdrawal removes portal access. It cannot recall copies your doctor has already saved.",
                )}
              </p>
            </div>
          )}
          <div className="review-meta">
            <Icon name="lock" size={16} />
            <span>
              {doctor
                ? t("Patient approval is required for access.")
                : t(
                    "Your information is private to your account until you approve sharing.",
                  )}
            </span>
          </div>
        </aside>
      </div>
      {withdraw && (
        <Modal
          title={t("Withdraw this shared summary?")}
          onClose={() => setWithdraw(false)}
        >
          <p className="modal-copy">
            {t(
              "Your doctor will no longer be able to access this summary or its files in PreConsult. Copies already downloaded or added to clinical records cannot be recalled.",
            )}
          </p>
          <div className="modal-actions">
            <Button className="secondary" onClick={() => setWithdraw(false)}>
              {t("Keep sharing")}
            </Button>
            <Button className="danger" onClick={() => action("withdraw")}>
              {t("Withdraw sharing")}
            </Button>
          </div>
        </Modal>
      )}
    </>
  );
}

function IntakePage({ id, user, config, onChanged }) {
  const { t, locale } = useLocale();
  const [session, setSession] = useState(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);
  const [deleting, setDeleting] = useState(false);
  const [deleteOpen, setDeleteOpen] = useState(false);
  const [view, setView] = useState(null);
  const [assessmentBusy, setAssessmentBusy] = useState(false);
  const [assessmentError, setAssessmentError] = useState("");
  const assessmentPending = useRef(false);
  const mounted = useRef(true);
  const readGeneration = useRef(0);
  const [localizing, setLocalizing] = useState(false);
  const [localeError, setLocaleError] = useState("");
  const localePending = useRef(false);
  const localeDesired = useRef(locale);
  localeDesired.current = locale;
  const doctor = user.role === "doctor";
  const languageNeedsUpdate = !!session && !doctor &&
    ["active", "review"].includes(session.status) &&
    ((session.locale || "en") !== locale ||
      (session.followup_batch?.status === "pending" &&
        session.followup_batch.locale !== locale));
  async function updateLanguage() {
    if (!languageNeedsUpdate || localePending.current) return;
    localePending.current = true;
    setLocalizing(true);
    setLocaleError("");
    const desired = locale;
    try {
      const data = await request(`/intakes/${id}/locale`, {
        method: "POST",
        body: { locale: desired, revision: session.revision },
      });
      if (!mounted.current) return;
      readGeneration.current += 1;
      setSession(data);
    } catch {
      if (mounted.current && localeDesired.current === desired)
        setLocaleError("We could not update the consultation language. Your answers are saved. Please try again.");
    } finally {
      localePending.current = false;
      if (mounted.current) setLocalizing(false);
    }
  }
  useEffect(() => {
    if (languageNeedsUpdate && !localeError && !localizing) updateLanguage();
    // Reconcile the loaded record when the patient changes language. Drafts
    // have already been saved by LanguageSwitcher's navigation boundary.
  }, [id, locale, session?.locale, session?.status, session?.followup_batch?.locale, localizing, localeError]);
  useEffect(() => setLocaleError(""), [id, locale]);
  const refresh = useCallback(async () => {
    const generation = ++readGeneration.current;
    try {
      const data = await request(`${doctor ? "/clinician" : ""}/intakes/${id}`);
      if (!mounted.current || generation !== readGeneration.current) return;
      setSession(data);
      setError("");
      return data;
    } catch (err) {
      if (!mounted.current || generation !== readGeneration.current) return;
      setError(err.message);
      if (err.status === 401 || err.status === 404) setSession(null);
    } finally {
      if (mounted.current && generation === readGeneration.current)
        setLoading(false);
    }
  }, [id, doctor]);
  useEffect(() => {
    mounted.current = true;
    setLoading(true);
    setSession(null);
    refresh();
    return () => {
      mounted.current = false;
      readGeneration.current += 1;
    };
  }, [refresh]);
  async function generateAssessment() {
    if (!mounted.current || assessmentPending.current) return;
    assessmentPending.current = true;
    setAssessmentBusy(true);
    setAssessmentError("");
    try {
      await request(`/intakes/${id}/ai-report`, {
        method: "POST",
        body: { locale: doctor ? session.locale || "en" : locale },
      });
      if (mounted.current) await refresh();
    } catch (err) {
      if (mounted.current) setAssessmentError(err.message);
    } finally {
      assessmentPending.current = false;
      if (mounted.current) setAssessmentBusy(false);
    }
  }
  function update(data) {
    if (!mounted.current) return;
    const generate = shouldGenerateAssessment(session, data, doctor);
    readGeneration.current += 1;
    setSession(data);
    onChanged();
    if (generate && config?.ai_configured !== false) generateAssessment();
  }
  async function remove() {
    setDeleting(true);
    setError("");
    try {
      await request(`/intakes/${id}`, { method: "DELETE" });
      if (!mounted.current) return;
      onChanged();
      setRoute("/patient");
    } catch (err) {
      setError(err.message);
      setDeleteOpen(false);
    } finally {
      setDeleting(false);
    }
  }
  if (loading) return <Loading label="Opening your consultation…" />;
  if (!session)
    return (
      <div className="page">
        <a className="back-link" href={`#/${doctor ? "doctor" : "patient"}`}>
          <Icon name="back" size={16} />
          {t("Back to overview")}
        </a>
        <ErrorNotice>
          {error || "This consultation could not be found."}
        </ErrorNotice>
        <Button className="secondary" onClick={refresh}>
          {t("Try again")}
        </Button>
      </div>
    );
  if (languageNeedsUpdate || localizing)
    return (
      <div className="page intake-page" aria-live="polite">
        {localizing ? <Loading label="Updating your consultation language…" /> : null}
        <p>{t("Your answers are saved. We are translating the questions and suggested answers into your selected language.")}</p>
        <ErrorNotice>{localeError}</ErrorNotice>
        {localeError && <Button className="primary" onClick={updateLanguage}>{t("Try again")}</Button>}
      </div>
    );
  return (
    <div className="page intake-page">
      <a className="back-link" href={`#/${doctor ? "doctor" : "patient"}`}>
        <Icon name="back" size={16} />
        {t("Back to overview")}
      </a>
      <div className="page-heading intake-heading">
        <div>
          <span className="overline">
            {doctor
              ? t("CONSULTATION PREPARATION")
              : session.status === "active"
                ? t("TELL YOUR STORY")
                : t("REVIEW & SHARE")}
          </span>
          <h1>{recordTitle(session.title, t)}</h1>
          <div className="intake-metadata">
            <Status status={session.status} />
            <span>
              {t("Started")} {dateLabel(session.created_at)}
            </span>
          </div>
        </div>
        {!doctor && (
          <button
            className="icon-button delete-consultation"
            aria-label={t("Delete consultation")}
            disabled={assessmentBusy}
            onClick={() => setDeleteOpen(true)}
          >
            <Icon name="trash" size={18} />
          </button>
        )}
      </div>
      {!doctor && ["approved", "withdrawn"].includes(session.status) && (session.locale || "en") !== locale && (
        <div className="notice notice-info" role="status">{t("This shared report keeps the language approved by the patient. Withdraw sharing before preparing a new version in another language.")}</div>
      )}
      {!doctor && (
        <JourneyNavigation
          current={
            view === "baseline"
              ? 1
              : view === "followup"
                ? 2
                : session.status === "active"
                  ? session.stage === "baseline" || !session.stage
                    ? 1
                    : 2
                  : 3
          }
          completed={
            session.baseline?.completed
              ? session.status === "review"
                ? 3
                : 2
              : 1
          }
          onSelect={
            !assessmentBusy &&
            !["approved", "withdrawn", "interrupted"].includes(session.status)
              ? (step) =>
                  navigateWithGuard(() => {
                    if (step === 1) setView("baseline");
                    else if (step === 2) setView("followup");
                    else setView(null);
                  })
              : undefined
          }
        />
      )}
      <ErrorNotice>{error}</ErrorNotice>
      {!doctor &&
      !["approved", "withdrawn", "interrupted"].includes(session.status) &&
      (view === "baseline" ||
        (session.status === "active" &&
          view !== "followup" &&
          (session.stage === "baseline" || !session.stage))) ? (
        <BaselineForm
          key={`form-${session.id}`}
          session={session}
          onUpdate={update}
          refresh={refresh}
          Attachments={Attachments}
          onContinue={() => setView(null)}
        />
      ) : !doctor && (session.status === "active" || view === "followup") ? (
        <IntakeChat
          key={session.id}
          session={session}
          config={config}
          onUpdate={(data) => {
            update(data);
            if (data.status === "review") setView(null);
          }}
          refresh={refresh}
          onEditBaseline={() => setView("baseline")}
        />
      ) : (
        <Review
          key={session.id}
          session={session}
          config={config}
          doctor={doctor}
          onUpdate={update}
          refresh={refresh}
          assessmentBusy={assessmentBusy}
          assessmentError={assessmentError}
          onGenerateAssessment={generateAssessment}
        />
      )}{" "}
      {deleteOpen && (
        <Modal
          title={t("Delete this consultation?")}
          onClose={() => !deleting && setDeleteOpen(false)}
        >
          <p className="modal-copy">
            {t(
              "This permanently deletes the consultation, its messages and uploaded files from PreConsult. This action cannot be undone.",
            )}
          </p>
          {session.status === "approved" && (
            <p className="modal-copy">
              {t(
                "It also removes your doctor’s access. Copies already saved by your doctor cannot be recalled.",
              )}
            </p>
          )}
          <div className="modal-actions">
            <Button
              className="secondary"
              disabled={deleting}
              onClick={() => setDeleteOpen(false)}
            >
              {t("Keep consultation")}
            </Button>
            <Button className="danger" busy={deleting} onClick={remove}>
              {t("Delete consultation")}
            </Button>
          </div>
        </Modal>
      )}
    </div>
  );
}

function Account({ user, onUpdated, onLogout }) {
  const { t } = useLocale();
  const [editingProfile, setEditingProfile] = useState(false);
  const [name, setName] = useState(user.name || "");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  async function save(event) {
    event.preventDefault();
    setBusy(true);
    setError("");
    setNotice("");
    try {
      const result = await request("/auth/me", {
        method: "PATCH",
        body: { name: name.trim() },
      });
      onUpdated(result.user);
      setNotice("Your profile has been updated.");
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  }
  return (
    <div className="page account-page">
      <div className="page-heading">
        <div>
          <span className="overline">{t("YOUR WORKSPACE")}</span>
          <h1>{t("My account")}</h1>
          <p>{t("A few details to make this space yours.")}</p>
        </div>
      </div>
      <section className="account-card">
        <h2>{t("Personal details")}</h2>
        <ErrorNotice>{error}</ErrorNotice>
        {notice && (
          <div className="notice success" role="status">
            <Icon name="check" size={17} />
            {notice}
          </div>
        )}
        <form onSubmit={save}>
          <label className="field-label" htmlFor="profile-name">
            {t("Your name")}
          </label>
          <input
            id="profile-name"
            className="input"
            value={name}
            onChange={(e) => setName(e.target.value)}
            placeholder={t("How would you like to be addressed?")}
            maxLength={100}
            autoComplete="name"
          />
          <label className="field-label" htmlFor="profile-email">
            {t("Email address")}
          </label>
          <input
            id="profile-email"
            className="input"
            value={user.email}
            readOnly
          />
          <p className="field-hint">
            {t(
              "Your verified email is used to sign in and identify your account.",
            )}
          </p>
          <Button type="submit" className="primary" busy={busy}>
            {t("Save changes")}
          </Button>
        </form>
      </section>
      {user.role === "patient" && (
        <section className="account-card profile-account-card">
          <span className="wizard-emblem">
            <Icon name="heart" size={28} />
          </span>
          <h2>{t("Your remembered health profile")}</h2>
          <p>{t("Add lasting details once to make future visits easier.")}</p>
          <p>
            {t(
              "Current medicines, allergies, measurements and symptoms are asked again each visit.",
            )}
          </p>
          <Button className="primary" onClick={() => setEditingProfile(true)}>
            {t("Edit profile")}
          </Button>
          {editingProfile && (
            <ProfileWizard onClose={() => setEditingProfile(false)} />
          )}
        </section>
      )}
      <section className="account-card">
        <h2>{t("Privacy & access")}</h2>
        <p>
          {t(
            "You sign in with a code delivered to your email. Keep access to your email account secure.",
          )}
        </p>
        <p>
          {user.role === "doctor"
            ? t(
                "You can access only approved consultation records explicitly shared with your authorised email.",
              )
            : t(
                "You control sharing for each consultation. You can withdraw sharing or permanently delete a consultation from its detail page.",
              )}
        </p>
        <Button className="secondary" icon="logout" onClick={onLogout}>
          {t("Sign out of this device")}
        </Button>
      </section>
    </div>
  );
}

function ProductAppContent() {
  const { t } = useLocale();
  const route = useHash();
  const [user, setUser] = useState(null);
  const [config, setConfig] = useState(null);
  const [workflows, setWorkflows] = useState([]);
  const [sessions, setSessions] = useState([]);
  const [loading, setLoading] = useState(true);
  const [listBusy, setListBusy] = useState(false);
  const [error, setError] = useState("");
  const [bootError, setBootError] = useState("");
  const [epoch, setEpoch] = useState(0);
  const authGeneration = useRef(0);
  const listGeneration = useRef(0);
  const currentGeneration = authGeneration.current;
  const requestedRole = roleFromRoute(route);
  const portalMatches = !!user && requestedRole === user.role;
  function adoptIdentity(value) {
    authGeneration.current += 1;
    listGeneration.current += 1;
    setSessions([]);
    setWorkflows([]);
    setConfig((previous) =>
      previous ? { ...previous, care_team: [] } : previous,
    );
    setListBusy(false);
    setError("");
    setUser(value);
  }
  useEffect(() => {
    let expanded = [];
    const beforePrint = () => {
      expanded = Array.from(
        document.querySelectorAll(".review-document details:not([open])"),
      );
      expanded.forEach((detail) => {
        detail.open = true;
      });
    };
    const afterPrint = () => {
      expanded.forEach((detail) => {
        detail.open = false;
      });
      expanded = [];
    };
    window.addEventListener("beforeprint", beforePrint);
    window.addEventListener("afterprint", afterPrint);
    return () => {
      window.removeEventListener("beforeprint", beforePrint);
      window.removeEventListener("afterprint", afterPrint);
    };
  }, []);
  useEffect(() => {
    let alive = true;
    async function boot() {
      const results = await Promise.allSettled([
        request("/config"),
        request("/auth/me"),
        request("/workflows"),
      ]);
      if (!alive) return;
      if (results[0].status === "fulfilled") setConfig(results[0].value);
      else setBootError(results[0].reason.message);
      if (results[1].status === "fulfilled")
        adoptIdentity(results[1].value.user);
      if (results[2].status === "fulfilled")
        setWorkflows(
          Array.isArray(results[2].value)
            ? results[2].value
            : results[2].value.workflows || [],
        );
      setLoading(false);
    }
    boot();
    return () => {
      alive = false;
    };
  }, [epoch]);
  const refresh = useCallback(async () => {
    if (!user || !portalMatches || currentGeneration !== authGeneration.current)
      return;
    const read = ++listGeneration.current;
    const isCurrent = () =>
      currentGeneration === authGeneration.current &&
      read === listGeneration.current;
    setListBusy(true);
    setError("");
    try {
      const result = await request(
        user.role === "doctor" ? "/clinician/intakes" : "/intakes",
      );
      if (!isCurrent()) return;
      setSessions(Array.isArray(result) ? result : result.intakes || []);
    } catch (err) {
      if (!isCurrent()) return;
      if (err.status === 401) {
        adoptIdentity(null);
        return;
      }
      if (err.status === 403) {
        try {
          const identity = await request("/auth/me");
          if (!isCurrent()) return;
          if (
            identity.user.id !== user.id ||
            identity.user.role !== user.role
          ) {
            adoptIdentity(identity.user);
            return;
          }
        } catch (identityError) {
          if (!isCurrent()) return;
          if ([401, 403].includes(identityError.status)) {
            adoptIdentity(null);
            return;
          }
        }
      }
      setError(err.message);
    } finally {
      if (isCurrent()) setListBusy(false);
    }
  }, [user, currentGeneration, portalMatches]);
  useEffect(() => {
    refresh();
  }, [refresh]);
  useEffect(() => {
    if (!user) return;
    let alive = true;
    Promise.allSettled([request("/config"), request("/workflows")]).then(
      (results) => {
        if (!alive || currentGeneration !== authGeneration.current) return;
        if (results[0].status === "fulfilled") setConfig(results[0].value);
        else setError(results[0].reason.message);
        if (results[1].status === "fulfilled")
          setWorkflows(
            Array.isArray(results[1].value)
              ? results[1].value
              : results[1].value.workflows || [],
          );
        else setError(results[1].reason.message);
      },
    );
    return () => {
      alive = false;
    };
  }, [user?.id, user?.role, currentGeneration]);
  useEffect(() => {
    if (loading) return;
    let alive = true;
    let checking = false;
    const revalidate = async () => {
      if (checking || document.visibilityState === "hidden") return;
      checking = true;
      const generation = authGeneration.current;
      try {
        const result = await request("/auth/me");
        if (!alive || generation !== authGeneration.current) return;
        if (result.user.id !== user?.id || result.user.role !== user?.role)
          adoptIdentity(result.user);
      } catch (err) {
        if (
          alive &&
          generation === authGeneration.current &&
          user &&
          [401, 403].includes(err.status)
        )
          adoptIdentity(null);
      } finally {
        checking = false;
      }
    };
    window.addEventListener("focus", revalidate);
    document.addEventListener("visibilitychange", revalidate);
    return () => {
      alive = false;
      window.removeEventListener("focus", revalidate);
      document.removeEventListener("visibilitychange", revalidate);
    };
  }, [user?.id, user?.role, currentGeneration, loading]);
  async function logout() {
    await navigateWithGuard(async () => {
      try {
        await request("/auth/logout", { method: "POST" });
        adoptIdentity(null);
      } catch (err) {
        if (currentGeneration === authGeneration.current) setError(err.message);
      }
    });
  }
  if (loading)
    return (
      <div className="boot-screen">
        <Brand role={requestedRole} />
        <Loading />
      </div>
    );
  if (bootError && !config)
    return (
      <div className="boot-screen">
        <Brand role={requestedRole} />
        <div className="connection-error">
          <h1>{t("Let’s reconnect.")}</h1>
          <p>{t("The PreConsult server could not be reached.")}</p>
          <ErrorNotice>{bootError}</ErrorNotice>
          <Button
            className="primary"
            onClick={() => {
              setBootError("");
              setLoading(true);
              setEpoch((x) => x + 1);
            }}
          >
            {t("Try again")}
          </Button>
        </div>
      </div>
    );
  if (!user || !portalMatches)
    return (
      <Login
        key={`${requestedRole}:${user ? `switch:${user.id}:${user.role}` : "signin"}`}
        role={requestedRole}
        config={config}
        currentUser={user}
        onSwitch={logout}
        switchError={error}
        onLogin={(value) => {
          adoptIdentity(value);
          setRoute(`/${value.role}`);
        }}
      />
    );
  const intakeId = route.match(/^\/(patient|doctor)\/intake\/([^/]+)/)?.[2];
  return (
    <Shell user={user} route={route} onLogout={logout}>
      {intakeId ? (
        <IntakePage
          key={`${user.role}:${user.id}:${intakeId}`}
          id={intakeId}
          user={user}
          config={config}
          onChanged={refresh}
        />
      ) : route.endsWith("/account") ? (
        <Account
          user={user}
          onUpdated={(value) => {
            if (currentGeneration === authGeneration.current) setUser(value);
          }}
          onLogout={logout}
        />
      ) : route === "/patient/new" ? (
        <NewIntake
          workflows={workflows}
          config={config}
          onCreated={(session) => {
            if (currentGeneration !== authGeneration.current) return;
            refresh();
            setRoute(`/patient/intake/${session.id}`);
          }}
        />
      ) : (
        <Dashboard
          user={user}
          sessions={sessions}
          busy={listBusy}
          error={error}
          refresh={refresh}
          history={route.endsWith("/history")}
        />
      )}
    </Shell>
  );
}

export default function ProductApp() {
  return (
    <LocaleProvider>
      <ProductAppContent />
    </LocaleProvider>
  );
}
