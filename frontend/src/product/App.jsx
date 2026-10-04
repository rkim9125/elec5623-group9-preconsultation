import React, { useCallback, useEffect, useRef, useState } from "react";
import Icon from "./Icons.jsx";
import {
  request,
  attachmentUrl,
  dateLabel,
  fileSize,
  progressFor,
  statusLabel,
} from "./api.js";
import "./product.css";

const setRoute = (path) => {
  window.location.hash = path;
};
function useHash() {
  const [route, update] = useState(
    location.hash.slice(1) ||
      (location.pathname.startsWith("/doctor") ? "/doctor" : "/patient"),
  );
  useEffect(() => {
    const listener = () =>
      update(
        location.hash.slice(1) ||
          (location.pathname.startsWith("/doctor") ? "/doctor" : "/patient"),
      );
    window.addEventListener("hashchange", listener);
    return () => window.removeEventListener("hashchange", listener);
  }, []);
  return route;
}
const roleFromRoute = (route) =>
  route.startsWith("/doctor") ? "doctor" : "patient";
function Brand({ light = false }) {
  return (
    <a
      className={`brand ${light ? "brand-light" : ""}`}
      href="#/patient"
      aria-label="PreConsult home"
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
function Button({ children, icon, className = "", busy, ...props }) {
  return (
    <button
      className={`button ${className}`}
      {...props}
      disabled={props.disabled || busy}
    >
      {busy ? (
        <span className="spinner" />
      ) : icon ? (
        <Icon name={icon} size={17} />
      ) : null}
      {children}
    </button>
  );
}
function ErrorNotice({ children }) {
  return children ? (
    <div className="notice error" role="alert">
      <Icon name="info" />
      <span>{children}</span>
    </div>
  ) : null;
}
function Loading({ label = "Loading your workspace…" }) {
  return (
    <div className="loading-state" role="status">
      <span className="spinner" />
      <p>{label}</p>
    </div>
  );
}
function Status({ status }) {
  return (
    <span className={`status status-${status}`}>
      <i />
      {statusLabel(status)}
    </span>
  );
}
function Empty({ title, children, action, icon = "file" }) {
  return (
    <div className="empty-state">
      <span className="empty-icon">
        <Icon name={icon} size={29} />
      </span>
      <h3>{title}</h3>
      <p>{children}</p>
      {action}
    </div>
  );
}
function Modal({ title, onClose, children, wide = false }) {
  const ref = useRef(null);
  useEffect(() => {
    const before = document.activeElement;
    const dialog = ref.current;
    dialog.showModal();
    return () => {
      dialog.close();
      before?.focus();
    };
  }, []);
  return (
    <dialog
      className={`modal ${wide ? "modal-wide" : ""}`}
      ref={ref}
      onCancel={(e) => {
        e.preventDefault();
        onClose();
      }}
      onClick={(e) => {
        if (e.target === ref.current) onClose();
      }}
      aria-labelledby="modal-title"
    >
      <div className="modal-heading">
        <h2 id="modal-title">{title}</h2>
        <button
          className="icon-button"
          onClick={onClose}
          aria-label="Close dialog"
        >
          <Icon name="close" />
        </button>
      </div>
      {children}
    </dialog>
  );
}

function Login({ role, config, onLogin }) {
  const [email, setEmail] = useState("");
  const [code, setCode] = useState("");
  const [sent, setSent] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [resendAt, setResendAt] = useState(0);
  const [seconds, setSeconds] = useState(0);
  useEffect(() => {
    const timer = setInterval(
      () => setSeconds(Math.max(0, Math.ceil((resendAt - Date.now()) / 1000))),
      1000,
    );
    return () => clearInterval(timer);
  }, [resendAt]);
  useEffect(() => {
    setSent(false);
    setError("");
    setCode("");
    setNotice("");
  }, [role]);
  async function send(event) {
    event?.preventDefault();
    setBusy(true);
    setError("");
    try {
      const result = await request("/auth/request-code", {
        method: "POST",
        body: { email: email.trim(), role },
      });
      setSent(true);
      setNotice(
        result.message || "A sign-in code has been sent to your email.",
      );
      setResendAt(Date.now() + 60000);
      setSeconds(60);
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  }
  async function verify(event) {
    event.preventDefault();
    setBusy(true);
    setError("");
    try {
      const result = await request("/auth/verify", {
        method: "POST",
        body: { email: email.trim(), code: code.trim(), role },
      });
      onLogin(result.user);
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  }
  return (
    <div className="auth-page">
      <div className="auth-story">
        <Brand light />
        <div className="story-copy">
          <span className="eyebrow">
            <span className="tiny-dot" /> A BETTER START TO YOUR CONSULTATION
          </span>
          <h1>
            More understanding.
            <br />
            <em>Better conversations.</em>
          </h1>
          <p>
            A little preparation makes room for what matters. Bring your health
            story together before you meet your doctor.
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
              <span>Your story, thoughtfully organised</span>
            </div>
          </div>
          <div className="story-points">
            <span>
              <Icon name="shield" size={18} /> You control what you share
            </span>
            <span>
              <Icon name="clock" size={18} /> Prepare at your own pace
            </span>
          </div>
        </div>
        <div className="auth-story-footer">
          Pre-consultation preparation · For non-emergency care
        </div>
      </div>
      <div className="auth-form-side">
        <nav className="portal-switch" aria-label="Choose your portal">
          <a href="#/patient" className={role === "patient" ? "active" : ""}>
            Patient portal
          </a>
          <a href="#/doctor" className={role === "doctor" ? "active" : ""}>
            Doctor portal
          </a>
        </nav>
        <div className="auth-form-wrap">
          <span className="overline">
            {role === "doctor"
              ? "CLINICIAN WORKSPACE"
              : "YOUR HEALTH, IN YOUR WORDS"}
          </span>
          <h2>
            {sent
              ? "Check your inbox."
              : role === "doctor"
                ? "Welcome, doctor."
                : "Let’s start with you."}
          </h2>
          <p className="auth-intro">
            {sent ? (
              <>
                Enter the verification code sent to <strong>{email}</strong>.
              </>
            ) : role === "doctor" ? (
              "Sign in to review patient-approved consultation summaries."
            ) : (
              "Sign in or create your account with an email verification code. No password to remember."
            )}
          </p>
          <ErrorNotice>{error}</ErrorNotice>
          {config && (!config.auth_configured || !config.mail_configured) && (
            <div className="notice warning">
              <Icon name="info" />
              <span>
                Email sign-in is not configured yet. The service administrator
                needs to finish email delivery setup.
              </span>
            </div>
          )}
          {sent ? (
            <form onSubmit={verify}>
              <label className="field-label" htmlFor="auth-code">
                Verification code
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
                placeholder="Enter your code"
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
                Verify & continue
                <Icon name="arrow" size={18} />
              </Button>
              <div className="auth-resend">
                <button
                  type="button"
                  className="text-button"
                  disabled={busy || seconds > 0}
                  onClick={send}
                >
                  {seconds > 0 ? `Resend code in ${seconds}s` : "Resend code"}
                </button>
                <button
                  type="button"
                  className="text-button"
                  onClick={() => {
                    setSent(false);
                    setCode("");
                    setError("");
                  }}
                >
                  Use another email
                </button>
              </div>
            </form>
          ) : (
            <form onSubmit={send}>
              <label className="field-label" htmlFor="auth-email">
                Email address
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
                    role === "doctor" ? "you@yourclinic.com" : "you@example.com"
                  }
                  required
                />
              </div>
              <Button type="submit" className="primary full" busy={busy}>
                Continue with email
                <Icon name="arrow" size={18} />
              </Button>
            </form>
          )}
          <div className="auth-assurance">
            <Icon name="lock" size={17} />
            <p>
              Your intake is shared with a doctor only after you review and
              approve it.
            </p>
          </div>
          {role === "doctor" && (
            <p className="field-hint">
              Doctor access is limited to clinicians authorised by the service
              administrator.
            </p>
          )}
        </div>
        <footer className="auth-footer">
          <span>English</span>
          <span>Built for a more informed visit</span>
        </footer>
      </div>
    </div>
  );
}

function Shell({ user, route, onLogout, children }) {
  const [menu, setMenu] = useState(false);
  const doctor = user.role === "doctor";
  const base = doctor ? "/doctor" : "/patient";
  useEffect(() => setMenu(false), [route]);
  return (
    <div className={`app-shell ${menu ? "menu-open" : ""}`}>
      <a
        className="skip-link"
        href="#main-content"
        onClick={(event) => {
          event.preventDefault();
          document.getElementById("main-content")?.focus();
        }}
      >
        Skip to content
      </a>
      <aside className="sidebar">
        <Brand />
        <div className="workspace-label">
          {doctor ? "CLINICIAN WORKSPACE" : "PATIENT WORKSPACE"}
        </div>
        <nav className="side-nav" aria-label="Main navigation">
          <a href={`#${base}`} className={route === base ? "active" : ""}>
            <Icon name="grid" />
            <span>{doctor ? "Patient overview" : "Overview"}</span>
          </a>
          {!doctor && (
            <a
              href="#/patient/new"
              className={route === "/patient/new" ? "active" : ""}
            >
              <Icon name="plus" />
              <span>New consultation</span>
            </a>
          )}
          <a
            href={`#${base}/history`}
            className={route.endsWith("/history") ? "active" : ""}
          >
            <Icon name="clock" />
            <span>{doctor ? "All submissions" : "Consultation history"}</span>
          </a>
          <a
            href={`#${base}/account`}
            className={route.endsWith("/account") ? "active" : ""}
          >
            <Icon name="person" />
            <span>My account</span>
          </a>
        </nav>
        <div className="side-note">
          <span className="side-note-icon">
            <Icon name={doctor ? "shield" : "heart"} size={21} />
          </span>
          <h4>
            {doctor ? "Patient-led sharing" : "Make space for your story."}
          </h4>
          <p>
            {doctor
              ? "You see only approved summaries shared with your account."
              : "Pause anytime. Your progress is saved as you go."}
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
            aria-label="Sign out"
            onClick={onLogout}
          >
            <Icon name="logout" size={19} />
          </button>
        </div>
      </aside>
      {menu && (
        <button
          className="sidebar-scrim"
          aria-label="Close navigation"
          onClick={() => setMenu(false)}
        />
      )}
      <div className="workspace">
        <header className="topbar">
          <button
            className="icon-button mobile-menu"
            aria-label="Open navigation"
            onClick={() => setMenu(!menu)}
          >
            <Icon name="menu" />
          </button>
          <div className="breadcrumb">
            {doctor ? "Doctor portal" : "Patient portal"}
            <span>/</span>
            <strong>
              {route.endsWith("/account")
                ? "My account"
                : route.endsWith("/new")
                  ? "New consultation"
                  : route.includes("/intake/")
                    ? "Consultation"
                    : route.endsWith("/history")
                      ? "History"
                      : "Overview"}
            </strong>
          </div>
          <span className="connection-tag">
            <i /> Private workspace
          </span>
        </header>
        <main id="main-content" tabIndex="-1">
          {children}
        </main>
        <footer className="workspace-footer">
          <span>PreConsult · ELEC5623 Group 9</span>
          <span>
            Preparation for care. Not a diagnosis or emergency service.
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
  const [query, setQuery] = useState("");
  const [filter, setFilter] = useState("all");
  const filtered = sessions.filter(
    (s) =>
      `${s.title || ""} ${s.patient_name || ""} ${s.patient_email || ""} ${(s.concerns || []).map((c) => c.title).join(" ")}`
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
              ? "Patient submissions"
              : history
                ? "Your consultations"
                : "Recent consultations"}
          </h2>
          <p>
            {doctor
              ? "Patient-approved information, ready for your review."
              : "Everything you’ve prepared, in one place."}
          </p>
        </div>
        <Button className="subtle" icon="clock" busy={busy} onClick={refresh}>
          Refresh
        </Button>
      </div>
      <div className="list-controls">
        <div className="search-field">
          <Icon name="search" size={18} />
          <input
            aria-label="Search consultations"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder={
              doctor
                ? "Search patient or concern…"
                : "Search your consultations…"
            }
          />
        </div>
        <select
          className="select"
          aria-label="Filter consultations"
          value={filter}
          onChange={(e) => setFilter(e.target.value)}
        >
          <option value="all">All statuses</option>
          {doctor ? (
            <>
              <option value="pending">Needs review</option>
              <option value="reviewed">Reviewed</option>
            </>
          ) : (
            <>
              <option value="active">In progress</option>
              <option value="review">Ready for review</option>
              <option value="approved">Shared with doctor</option>
              <option value="withdrawn">Sharing withdrawn</option>
              <option value="interrupted">Safety pause</option>
            </>
          )}
        </select>
      </div>
      {!sessions.length ? (
        <Empty
          title={
            doctor
              ? "Your workspace is ready"
              : "Your first consultation starts here"
          }
          icon={doctor ? "shield" : "file"}
          action={
            !doctor && (
              <Button
                className="primary"
                icon="plus"
                onClick={() => setRoute("/patient/new")}
              >
                Prepare a consultation
              </Button>
            )
          }
        >
          {doctor
            ? "When a patient approves a summary and shares it with your email, it will appear here."
            : "Tell us what’s on your mind. We’ll help organise the details for your doctor."}
        </Empty>
      ) : !filtered.length ? (
        <Empty title="No consultations found" icon="search">
          Try a different search or status filter.
        </Empty>
      ) : (
        <div className="consultation-list">
          <div className="list-header">
            <span>{doctor ? "PATIENT & CONCERN" : "CONSULTATION"}</span>
            <span>LAST UPDATED</span>
            <span>STATUS</span>
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
                      ? s.patient_name || s.patient_email || "Patient"
                      : s.title || "Consultation preparation"}
                  </strong>
                  <small>
                    {doctor
                      ? s.title ||
                        (s.concerns || []).map((c) => c.title).join(", ") ||
                        "Consultation preparation"
                      : (s.concerns || []).map((c) => c.title).join(" · ") ||
                        "Getting to know your concerns"}
                  </small>
                </span>
              </span>
              <span className="row-date">{dateLabel(s.updated_at)}</span>
              <span>
                {doctor && s.reviewed_at ? (
                  <span className="status status-reviewed">
                    <i />
                    Reviewed
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
          View all consultations <Icon name="arrow" size={16} />
        </a>
      )}
    </section>
  );
}

function Dashboard({ user, sessions, busy, error, refresh, history }) {
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
              ? "YOUR WORKSPACE"
              : doctor
                ? "CARE STARTS WITH UNDERSTANDING"
                : "A LITTLE PREPARATION. A BETTER VISIT."}
          </span>
          <h1>
            {history
              ? "Consultation history"
              : doctor
                ? `Welcome${user.name ? `, Dr ${user.name.replace(/^Dr\.?\s*/i, "")}` : " back"}.`
                : `Welcome${user.name ? `, ${user.name.split(" ")[0]}` : " back"}.`}
          </h1>
          <p>
            {history
              ? "Find, revisit and manage your consultation records."
              : doctor
                ? "A clearer picture of your patients, before the conversation begins."
                : "Let’s help your doctor see the whole picture."}
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
                <span className="eyebrow">YOUR NEXT STEP</span>
                <h2>
                  Good care starts
                  <br />
                  with your story.
                </h2>
                <p>
                  Share your concerns, add relevant documents, and create a
                  summary you can review before sharing.
                </p>
                <Button
                  className="cream"
                  onClick={() => setRoute("/patient/new")}
                >
                  Prepare a consultation
                  <Icon name="arrow" size={18} />
                </Button>
                <span className="welcome-footnote">
                  At your pace · Saved as you go
                </span>
              </div>
              <div className="welcome-visual" aria-hidden="true">
                <div className="visual-circle" />
                <div className="visual-document">
                  <span className="document-cross">+</span>
                  <span className="document-title">Your visit, prepared.</span>
                  <span className="document-rule" />
                  <span className="document-rule short" />
                  <span className="document-item">
                    <i />
                    Your concerns
                  </span>
                  <span className="document-item">
                    <i />
                    Your health context
                  </span>
                  <span className="document-item">
                    <i />
                    Your questions
                  </span>
                  <span className="document-complete">
                    <Icon name="check" size={14} /> Reviewed by you
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
                  {doctor ? "Shared submissions" : "Total consultations"}
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
                  {doctor ? "Awaiting your review" : "In preparation"}
                </span>
                <strong>{awaiting.toString().padStart(2, "0")}</strong>
              </div>
            </div>
            <div className="metric-card">
              <span className="metric-icon blue">
                <Icon name="check" />
              </span>
              <div>
                <span>{doctor ? "Reviewed" : "Shared with doctor"}</span>
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
          <h3>A thoughtful start, in three steps</h3>
          <div>
            <p>
              <span>01</span>
              <strong>Tell your story</strong>
              <small>Use text, your voice, or a document.</small>
            </p>
            <p>
              <span>02</span>
              <strong>Review the details</strong>
              <small>Check and correct your summary.</small>
            </p>
            <p>
              <span>03</span>
              <strong>Share when ready</strong>
              <small>You decide when your doctor sees it.</small>
            </p>
          </div>
        </div>
      )}
    </div>
  );
}

function NewIntake({ workflows, config, onCreated }) {
  const [selected, setSelected] = useState([]);
  const [query, setQuery] = useState("");
  const [category, setCategory] = useState("All concerns");
  const [model, setModel] = useState(config?.default_model || "gpt-6-sol");
  const [consent, setConsent] = useState(false);
  const [title, setTitle] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const categories = [
    "All concerns",
    ...new Set(workflows.map((w) => w.category).filter(Boolean)),
  ];
  const shown = workflows.filter(
    (w) =>
      (category === "All concerns" || w.category === category) &&
      `${w.title} ${w.description} ${w.category}`
        .toLowerCase()
        .includes(query.toLowerCase()),
  );
  async function create() {
    setBusy(true);
    setError("");
    try {
      const session = await request("/intakes", {
        method: "POST",
        body: {
          consent,
          model,
          workflow_ids: selected,
          title: title.trim() || undefined,
        },
      });
      onCreated(session);
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  }
  return (
    <div className="page new-page">
      <a className="back-link" href="#/patient">
        <Icon name="back" size={16} /> Back to overview
      </a>
      <div className="page-heading">
        <div>
          <span className="overline">LET’S GET READY FOR YOUR VISIT</span>
          <h1>What brings you here?</h1>
          <p>
            Choose any concerns that fit, or let the assistant guide you. You
            can discuss several together.
          </p>
        </div>
      </div>
      <div className="new-layout">
        <section>
          <button
            className={`auto-route-card ${selected.length === 0 ? "selected" : ""}`}
            onClick={() => setSelected([])}
          >
            <span className="auto-icon">
              <Icon name="sparkle" size={25} />
            </span>
            <span>
              <strong>Help me work it out</strong>
              <small>
                Describe things in your own words. We’ll find the right
                questions.
              </small>
            </span>
            <span className="selection-mark">
              {!selected.length && <Icon name="check" size={14} />}
            </span>
          </button>
          <div className="workflow-heading">
            <h2>Or choose your concerns</h2>
            <span>{workflows.length} care pathways</span>
          </div>
          <div className="list-controls">
            <div className="search-field">
              <Icon name="search" size={18} />
              <input
                value={query}
                onChange={(e) => setQuery(e.target.value)}
                aria-label="Search care pathways"
                placeholder="Search symptoms or concerns…"
              />
            </div>
            <select
              className="select"
              aria-label="Concern category"
              value={category}
              onChange={(e) => setCategory(e.target.value)}
            >
              {categories.map((c) => (
                <option key={c}>{c}</option>
              ))}
            </select>
          </div>
          <div className="workflow-grid">
            {shown.map((w, i) => (
              <button
                key={w.id}
                className={`workflow-card ${selected.includes(w.id) ? "selected" : ""}`}
                aria-pressed={selected.includes(w.id)}
                onClick={() =>
                  setSelected((previous) =>
                    previous.includes(w.id)
                      ? previous.filter((id) => id !== w.id)
                      : [...previous, w.id],
                  )
                }
              >
                <div className="workflow-card-top">
                  <span className={`pathway-icon pathway-${i % 4}`}>
                    <Icon
                      name={["activity", "heart", "person", "file"][i % 4]}
                      size={20}
                    />
                  </span>
                  <span className="selection-mark">
                    {selected.includes(w.id) && <Icon name="check" size={14} />}
                  </span>
                </div>
                <strong>{w.title}</strong>
                <p>
                  {w.description ||
                    "Prepare the relevant details for your doctor."}
                </p>
                <small>{w.category || "General care"}</small>
              </button>
            ))}
          </div>
          {!shown.length && (
            <Empty title="No matching pathways" icon="search">
              Try another search, or choose “Help me work it out”.
            </Empty>
          )}
        </section>
        <aside className="preparation-card">
          <span className="overline">YOUR CONSULTATION</span>
          <h2>A few things before we begin.</h2>
          <div className="selected-concerns">
            {selected.length ? (
              <>
                <span className="field-label">
                  {selected.length} concern{selected.length !== 1 ? "s" : ""}{" "}
                  selected
                </span>
                <div className="tag-list">
                  {selected.map((id) => (
                    <button
                      key={id}
                      className="tag removable"
                      onClick={() =>
                        setSelected(selected.filter((x) => x !== id))
                      }
                    >
                      {workflows.find((w) => w.id === id)?.title || id}
                      <Icon name="close" size={12} />
                    </button>
                  ))}
                </div>
              </>
            ) : (
              <p>
                <Icon name="sparkle" size={16} /> Guided by your story
              </p>
            )}
          </div>
          <label className="field-label" htmlFor="intake-title">
            Consultation title <span>(optional)</span>
          </label>
          <input
            id="intake-title"
            className="input"
            value={title}
            maxLength={120}
            onChange={(e) => setTitle(e.target.value)}
            placeholder="e.g. Preparing for my GP visit"
          />
          <label className="field-label" htmlFor="model">
            Assistant model
          </label>
          <select
            className="select full"
            id="model"
            value={model}
            onChange={(e) => setModel(e.target.value)}
          >
            {(
              config?.models || [
                { id: "gpt-6-sol", label: "GPT-6 Sol" },
                { id: "gpt-5.6-sol", label: "GPT-5.6 Sol" },
              ]
            ).map((m) => (
              <option key={m.id} value={m.id}>
                {m.label}
              </option>
            ))}
          </select>
          <div className="consent-information">
            <Icon name="shield" size={19} />
            <p>
              Your responses and uploaded files are processed with AI to prepare
              a summary. AI can make mistakes. Review all details before
              sharing. This service does not diagnose or replace clinical care.
            </p>
          </div>
          <label className="checkbox-label">
            <input
              type="checkbox"
              checked={consent}
              onChange={(e) => setConsent(e.target.checked)}
            />
            <span>
              I consent to AI processing of the health information I provide and
              understand that I control sharing with my doctor.
            </span>
          </label>
          <ErrorNotice>{error}</ErrorNotice>
          <Button
            className="primary full"
            busy={busy}
            disabled={!consent}
            onClick={create}
          >
            Start preparation
            <Icon name="arrow" size={17} />
          </Button>
          <p className="emergency-note">
            For severe or rapidly worsening symptoms, seek urgent medical help.
            In Australia, call 000 in an emergency.
          </p>
        </aside>
      </div>
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
  if (!text)
    return <p className="muted">A summary will appear after preparation.</p>;
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
          <summary>Unknown, skipped and uncollected information</summary>
          {gaps.map((line, i) => render(line, i + 1, gaps))}
        </details>
      )}
      {gapEnd > 0 &&
        lines.slice(gapEnd).map((line, i, list) => render(line, i, list))}
    </div>
  );
}

function VoiceInput({ onTranscript, disabled, onError }) {
  const [recording, setRecording] = useState(false);
  const [transcribing, setTranscribing] = useState(false);
  const [duration, setDuration] = useState(0);
  const recorder = useRef(null);
  const stream = useRef(null);
  const alive = useRef(true);
  useEffect(() => {
    alive.current = true;
    return () => {
      alive.current = false;
      if (recorder.current?.state === "recording") recorder.current.stop();
      stream.current?.getTracks().forEach((t) => t.stop());
    };
  }, []);
  useEffect(() => {
    if (!recording) return;
    const timer = setInterval(
      () =>
        setDuration((value) => {
          if (value >= 119) {
            recorder.current?.stop();
            return 120;
          }
          return value + 1;
        }),
      1000,
    );
    return () => clearInterval(timer);
  }, [recording]);
  async function start() {
    onError("");
    try {
      if (!navigator.mediaDevices?.getUserMedia || !window.MediaRecorder)
        throw new Error(
          "Voice input is not available in this browser. Use a recent browser on localhost or HTTPS, or type your response.",
        );
      stream.current = await navigator.mediaDevices.getUserMedia({
        audio: true,
      });
      const mimeType = [
        "audio/webm;codecs=opus",
        "audio/mp4",
        "audio/webm",
      ].find((t) => MediaRecorder.isTypeSupported(t));
      const media = new MediaRecorder(
        stream.current,
        mimeType ? { mimeType } : undefined,
      );
      recorder.current = media;
      const chunks = [];
      media.ondataavailable = (event) => {
        if (event.data.size) chunks.push(event.data);
      };
      media.onstop = async () => {
        stream.current?.getTracks().forEach((t) => t.stop());
        if (!alive.current) return;
        setRecording(false);
        setTranscribing(true);
        const form = new FormData();
        const type = media.mimeType || "audio/webm";
        form.append(
          "file",
          new Blob(chunks, { type }),
          `voice-note.${type.includes("mp4") ? "m4a" : "webm"}`,
        );
        try {
          const result = await request("/transcriptions", {
            method: "POST",
            body: form,
          });
          if (alive.current) {
            if (!result.text?.trim())
              onError(
                "No speech was detected. Please try again or type your response.",
              );
            else onTranscript(result.text);
          }
        } catch (err) {
          if (alive.current) onError(err.message);
        } finally {
          if (alive.current) setTranscribing(false);
        }
      };
      media.start();
      setDuration(0);
      setRecording(true);
    } catch (err) {
      stream.current?.getTracks().forEach((t) => t.stop());
      onError(
        err.name === "NotAllowedError"
          ? "Microphone access was denied. Allow access in your browser settings or type your response."
          : err.message,
      );
    }
  }
  return (
    <button
      type="button"
      className={`voice-button ${recording ? "recording" : ""}`}
      disabled={disabled || transcribing}
      onClick={() => (recording ? recorder.current?.stop() : start())}
      aria-label={
        recording ? "Stop recording and transcribe" : "Record a voice response"
      }
    >
      {transcribing ? (
        <span className="spinner" />
      ) : (
        <Icon name={recording ? "stop" : "mic"} size={18} />
      )}
      <span>
        {recording
          ? `Stop · ${Math.floor(duration / 60)}:${String(duration % 60).padStart(2, "0")}`
          : transcribing
            ? "Transcribing…"
            : "Use my voice"}
      </span>
    </button>
  );
}

function Attachments({
  session,
  readonly = false,
  onRefresh,
  onText,
  onError,
}) {
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
        <h3>Supporting documents</h3>
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
            aria-label="Upload supporting documents"
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
            <strong>{busy ? "Uploading…" : "Drop a file or browse"}</strong>
            <span>PDF, JPG, PNG or WebP · Up to 10 MB</span>
          </button>
          <p className="file-help">
            Files are shared with your approved summary. Use “Extract details”
            to review AI-read content before adding it to your story.
          </p>
        </>
      )}
      {!session.attachments?.length && !canEdit && (
        <p className="muted small">No supporting documents attached.</p>
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
                  <span>Open file</span>
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
                      "Reading…"
                    ) : (
                      <>
                        <Icon name="sparkle" size={13} />
                        Extract details
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
  const progress = progressFor(session);
  return (
    <section className="care-plan">
      <div className="small-heading">
        <h3>Your preparation plan</h3>
        <Icon name="sparkle" size={17} />
      </div>
      <div className="progress-heading">
        <span>Information gathered</span>
        <strong>{progress.percent}%</strong>
      </div>
      <div
        className="progress-track"
        role="progressbar"
        aria-label="Preparation progress"
        aria-valuenow={progress.percent}
        aria-valuemin={0}
        aria-valuemax={100}
      >
        <span style={{ width: `${progress.percent}%` }} />
      </div>
      <p className="progress-hint">
        {progress.total
          ? `${progress.completed} of ${progress.total} topics addressed`
          : "Your plan develops as you share."}
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
                  <strong>{concern.title}</strong>
                  <small>
                    {slots.length
                      ? `${done} of ${slots.length} topics addressed`
                      : "Details being gathered"}
                  </small>
                </div>
              </div>
            );
          })}
        </div>
      ) : (
        <p className="muted small">
          Start with what’s on your mind. The assistant will build a plan around
          your concerns.
        </p>
      )}
      {session.plan?.rationale && (
        <details className="plan-details">
          <summary>How this plan was chosen</summary>
          <p>{readable(session.plan.rationale)}</p>
        </details>
      )}
      <div className="plan-footer">
        <Icon name="info" size={15} />
        <p>
          You can say “I don’t know”, skip a question, or review at any time.
        </p>
      </div>
    </section>
  );
}

function IntakeChat({ session, onUpdate, refresh, config }) {
  const [text, setText] = useState("");
  const [notice, setNotice] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [busyAction, setBusyAction] = useState("");
  const [confirmReview, setConfirmReview] = useState(false);
  const end = useRef(null);
  const composer = useRef(null);
  useEffect(() => {
    end.current?.scrollIntoView({ behavior: "smooth", block: "nearest" });
  }, [session.messages?.length, busy]);
  async function send(action = "answer") {
    if (action === "answer" && !text.trim()) return;
    setBusy(true);
    setBusyAction(action);
    setError("");
    setNotice("");
    try {
      const next = await request(`/intakes/${session.id}/messages`, {
        method: "POST",
        body: { text: action === "answer" ? text.trim() : "", action },
      });
      onUpdate(next);
      setText("");
      composer.current?.focus();
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
      setBusyAction("");
    }
  }
  async function review() {
    setConfirmReview(false);
    setBusy(true);
    setBusyAction("review");
    setError("");
    try {
      onUpdate(
        await request(`/intakes/${session.id}/review`, { method: "POST" }),
      );
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
      setBusyAction("");
    }
  }
  function addText(value, type) {
    if (!value?.trim()) return;
    setText((previous) => (previous ? `${previous}\n\n${value}` : value));
    setNotice(
      `${type} added below. Check the wording, make any corrections, then send when ready.`,
    );
    composer.current?.focus();
  }
  const messages = session.messages || [];
  const currentShown = messages.some(
    (m) =>
      m.role === "assistant" &&
      m.text?.includes(session.current_question?.question || "\0"),
  );
  return (
    <>
      <div className="intake-layout">
        <section className="conversation-card">
          <div className="conversation-header">
            <span className="assistant-avatar">
              <Icon name="sparkle" size={19} />
            </span>
            <div>
              <h2>Your preparation assistant</h2>
              <p>One thoughtful question at a time</p>
            </div>
            <span className="live-label">
              <i />
              Private conversation
            </span>
          </div>
          <div
            className="conversation"
            tabIndex={0}
            role="region"
            aria-label="Preparation conversation"
            aria-live="polite"
            aria-relevant="additions"
          >
            <div className="conversation-date">
              TODAY · YOUR PRE-CONSULTATION STORY
            </div>
            {messages.length ? (
              messages.map((message, index) => (
                <div
                  className={`message message-${message.role}`}
                  key={message.id || index}
                >
                  {message.role === "assistant" && (
                    <span className="message-avatar">
                      <Icon name="sparkle" size={15} />
                    </span>
                  )}
                  <div>
                    <span className="message-author">
                      {message.role === "patient"
                        ? "You"
                        : "PreConsult assistant"}
                    </span>
                    <div className="message-bubble">{message.text}</div>
                    {message.created_at && (
                      <time>
                        {new Date(message.created_at).toLocaleTimeString(
                          "en-AU",
                          { hour: "numeric", minute: "2-digit" },
                        )}
                      </time>
                    )}
                  </div>
                </div>
              ))
            ) : (
              <div className="message message-assistant">
                <span className="message-avatar">
                  <Icon name="sparkle" size={15} />
                </span>
                <div>
                  <span className="message-author">PreConsult assistant</span>
                  <div className="message-bubble">
                    {session.current_question?.question ||
                      "What would you like your doctor to help you with? You can mention more than one concern."}
                  </div>
                </div>
              </div>
            )}
            {messages.length > 0 &&
              session.current_question?.question &&
              !currentShown && (
                <div className="message message-assistant">
                  <span className="message-avatar">
                    <Icon name="sparkle" size={15} />
                  </span>
                  <div>
                    <span className="message-author">Next question</span>
                    <div className="message-bubble">
                      {session.current_question.question}
                    </div>
                  </div>
                </div>
              )}
            {busy && (
              <div className="assistant-thinking" role="status">
                <span />
                <span />
                <span />
                {busyAction === "review"
                  ? "Preparing your review…"
                  : "Organising your response…"}
              </div>
            )}
            <div ref={end} />
          </div>
          <div className="composer-area">
            <ErrorNotice>{error}</ErrorNotice>
            {notice && (
              <div className="notice success" role="status">
                <Icon name="check" size={17} />
                <span>{notice}</span>
              </div>
            )}
            {session.ai_status?.mode === "unavailable" &&
              session.plan?.turns > 0 && (
                <div className="notice warning">
                  <Icon name="info" size={17} />
                  <span>
                    {session.ai_status.message ||
                      "The AI service is unavailable. Please try again shortly."}
                  </span>
                </div>
              )}
            <form
              onSubmit={(e) => {
                e.preventDefault();
                send();
              }}
            >
              <label htmlFor="response" className="sr-only">
                Your response
              </label>
              <textarea
                id="response"
                ref={composer}
                value={text}
                onChange={(e) => setText(e.target.value)}
                placeholder="Tell us in your own words…"
                rows={3}
                maxLength={12000}
                disabled={busy}
                onKeyDown={(e) => {
                  if (e.key === "Enter" && (e.metaKey || e.ctrlKey)) {
                    e.preventDefault();
                    send();
                  }
                }}
              />
              <div className="composer-actions">
                <VoiceInput
                  disabled={busy}
                  onTranscript={(value) =>
                    addText(value, "Your voice transcript")
                  }
                  onError={setError}
                />
                <Button
                  type="submit"
                  className="primary"
                  busy={busy && busyAction === "answer"}
                  disabled={busy || !text.trim()}
                >
                  Send response
                  <Icon name="arrow" size={16} />
                </Button>
              </div>
            </form>
            <div className="answer-shortcuts">
              <button
                className="text-button"
                disabled={busy}
                onClick={() => send("unknown")}
              >
                I don’t know
              </button>
              <span>·</span>
              <button
                className="text-button"
                disabled={busy}
                onClick={() => send("skip")}
              >
                Skip this question
              </button>
              <span className="keyboard-hint">⌘ / Ctrl + Enter to send</span>
            </div>
          </div>
          <div className="conversation-footer">
            <Icon name="lock" size={14} />
            <span>
              Saved securely to your account. Your doctor can’t see this yet.
            </span>
          </div>
        </section>
        <aside className="intake-aside">
          <CarePlan session={session} />
          <Attachments
            session={session}
            onRefresh={refresh}
            onText={(value) => addText(value, "Extracted document details")}
            onError={setError}
          />
          <div className="finish-card">
            <h3>Ready to bring it together?</h3>
            <p>
              You can review now, even with unanswered questions. Gaps will be
              made clear.
            </p>
            <Button
              className="secondary full"
              busy={busy && busyAction === "review"}
              disabled={busy}
              onClick={() => setConfirmReview(true)}
            >
              Finish & review
              <Icon name="arrow" size={16} />
            </Button>
          </div>
          <p className="model-caption">
            <Icon name="sparkle" size={13} />
            {config?.models?.find((m) => m.id === session.model)?.label ||
              session.model}
          </p>
        </aside>
      </div>
      {confirmReview && (
        <Modal
          title="Prepare your summary?"
          onClose={() => setConfirmReview(false)}
        >
          <p className="modal-copy">
            We’ll organise what you’ve shared into a draft for you to review.
            Any unanswered or uncertain details will be clearly marked.
          </p>
          <p className="modal-copy">
            Your doctor will only see it after you approve sharing.
          </p>
          <div className="modal-actions">
            <Button
              className="secondary"
              onClick={() => setConfirmReview(false)}
            >
              Keep preparing
            </Button>
            <Button className="primary" onClick={review}>
              Create my summary
            </Button>
          </div>
        </Modal>
      )}
    </>
  );
}

function SlotDetails({ session }) {
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
            <span>{concern.title}</span>
            <span>{Object.keys(concern.slots || {}).length} topics</span>
            <Icon name="chevron" size={16} />
          </summary>
          <dl>
            {Object.entries(concern.slots || {}).map(([key, slot]) => (
              <div key={key}>
                <dt>{slot.label || key.replace(/_/g, " ")}</dt>
                <dd>
                  {slot.value != null && slot.value !== "" ? (
                    readable(slot.value)
                  ) : (
                    <span className="muted">Not provided</span>
                  )}
                  <span
                    className={`slot-status slot-${slot.status?.toLowerCase()}`}
                  >
                    {slot.status === "FILLED"
                      ? "Reported"
                      : (slot.status || "MISSING")
                          .replace(/_/g, " ")
                          .toLowerCase()}
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

function Review({ session, config, doctor, onUpdate, refresh }) {
  const [correction, setCorrection] = useState("");
  const [doctorEmail, setDoctorEmail] = useState(
    session.doctor_email || config?.care_team?.[0]?.email || "",
  );
  const [confirmed, setConfirmed] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [withdraw, setWithdraw] = useState(false);
  const canApprove = !doctor && session.status === "review";
  async function correct(event) {
    event.preventDefault();
    setBusy(true);
    setError("");
    try {
      const updated = await request(`/intakes/${session.id}/review`, {
        method: "PATCH",
        body: { text: correction },
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
    setBusy(true);
    setError("");
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
      setError(err.message);
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
          { method: "POST" },
        ),
      );
      setNotice(
        doctor
          ? "This submission has been marked as reviewed."
          : kind === "review"
            ? "Your preparation is a private draft again. Check or correct it before sharing."
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
            A saved correction has not been reconciled with the summary. Sharing
            is paused. Retry the correction in the form below when the AI
            service is available, then review the revised summary.
          </span>
        </div>
      )}
      {session.status === "approved" && !doctor && (
        <div className="shared-banner">
          <span>
            <Icon name="check" size={25} />
          </span>
          <div>
            <h2>Your story is ready for your doctor.</h2>
            <p>
              You approved version {session.summary?.version}. Shared with{" "}
              {session.doctor_email || "your care team"}.
            </p>
          </div>
        </div>
      )}
      {session.status === "withdrawn" && (
        <div className="notice warning">
          <Icon name="shield" />
          <span>
            You withdrew sharing. Your doctor can no longer access this record
            in PreConsult.
          </span>
          {session.consent && (
            <Button
              className="secondary"
              busy={busy}
              onClick={() => action("review")}
            >
              Revise preparation
            </Button>
          )}
        </div>
      )}
      {session.status === "interrupted" && (
        <div className="notice error">
          <Icon name="info" />
          <span>
            This preparation was paused for safety. Follow the safety guidance
            below. For an emergency in Australia, call 000.
          </span>
        </div>
      )}
      <div className="review-layout">
        <section className="review-document">
          <div className="review-document-heading">
            <div>
              <span className="overline">
                {doctor
                  ? "PATIENT-APPROVED PRE-CONSULTATION SUMMARY"
                  : canApprove
                    ? "YOUR DRAFT · FOR YOUR REVIEW"
                    : "YOUR CONSULTATION SUMMARY"}
              </span>
              <h2>
                {doctor
                  ? session.patient_name || session.patient_email
                  : "Your story, brought together."}
              </h2>
              <p>
                {dateLabel(session.created_at)} <span>·</span> Version{" "}
                {session.summary?.version || 1}
                {doctor && (
                  <>
                    {" "}
                    <span>·</span> {session.patient_email}
                  </>
                )}
              </p>
            </div>
            <button
              className="icon-button print-button"
              onClick={() => window.print()}
              aria-label="Print summary"
            >
              <Icon name="print" />
            </button>
          </div>
          <div className="summary-disclaimer">
            <Icon name="info" size={17} />
            <p>
              AI-assisted, patient-reported information.{" "}
              {doctor
                ? "Verify details with the patient. This is not a diagnosis or treatment recommendation."
                : "Check for missing or incorrect details. This is not a diagnosis or treatment recommendation."}
            </p>
          </div>
          <SummaryText
            text={
              session.summary?.text ||
              (session.status === "interrupted"
                ? session.messages?.filter((m) => m.role === "assistant").at(-1)
                    ?.text
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
                    Details still to clarify ({session.summary.gaps.length})
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
            <h3>Detailed health information</h3>
            <p>Review the information gathered for each concern.</p>
          </div>
          <SlotDetails session={session} />
          {canApprove && (
            <form className="correction-form" onSubmit={correct}>
              <label htmlFor="correction">
                <Icon name="file" size={19} />
                Anything to correct or add?
              </label>
              <p>
                Describe the change, and we’ll revise the summary for another
                review.
              </p>
              <textarea
                id="correction"
                value={correction}
                onChange={(e) => setCorrection(e.target.value)}
                rows={3}
                placeholder="e.g. The pain started on Monday, not last week…"
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
                Update my summary
              </Button>
            </form>
          )}
        </section>
        <aside className="review-aside">
          {canApprove && (
            <form className="approval-card" onSubmit={approve}>
              <span className="approval-icon">
                <Icon name="shield" size={25} />
              </span>
              <h2>You’re in control.</h2>
              <p>
                When you’re happy with the details, choose your doctor and
                approve sharing.
              </p>
              <label className="field-label" htmlFor="doctor-email">
                Doctor’s email address
              </label>
              {config?.care_team?.length ? (
                <select
                  id="doctor-email"
                  className="select full"
                  value={doctorEmail}
                  onChange={(e) => setDoctorEmail(e.target.value)}
                  required
                >
                  <option value="">Choose your doctor</option>
                  {config.care_team.map((person) => (
                    <option value={person.email} key={person.email}>
                      {person.name ? `${person.name} · ` : ""}
                      {person.email}
                    </option>
                  ))}
                </select>
              ) : (
                <input
                  id="doctor-email"
                  className="input"
                  type="email"
                  placeholder="doctor@clinic.com"
                  value={doctorEmail}
                  onChange={(e) => setDoctorEmail(e.target.value)}
                  required
                />
              )}
              <p className="field-hint">
                Only this authorised clinician can access the shared record.
              </p>
              <label className="checkbox-label">
                <input
                  type="checkbox"
                  checked={confirmed}
                  onChange={(e) => setConfirmed(e.target.checked)}
                />
                <span>
                  I have reviewed this summary and approve sharing it and my
                  attached files with this doctor.
                </span>
              </label>
              <Button
                className="primary full"
                type="submit"
                disabled={
                  !confirmed ||
                  !doctorEmail.trim() ||
                  busy ||
                  !!correction.trim() ||
                  session.summary?.needs_reconciliation
                }
                busy={busy}
              >
                Approve & share
                <Icon name="arrow" size={16} />
              </Button>
              {correction.trim() && (
                <p className="field-hint">
                  Apply or clear your correction before approving.
                </p>
              )}
              <small>You can withdraw sharing later.</small>
            </form>
          )}
          {doctor && (
            <div className="approval-card">
              <span className="approval-icon">
                <Icon name="check" size={25} />
              </span>
              <h2>
                {session.reviewed_at
                  ? "Review complete"
                  : "Ready for your review"}
              </h2>
              <p>
                {session.reviewed_at
                  ? `Marked as reviewed ${dateLabel(session.reviewed_at, true)}.`
                  : "Review the patient’s summary, concerns and supporting documents before your consultation."}
              </p>
              {!session.reviewed_at && (
                <Button
                  className="primary full"
                  busy={busy}
                  icon="check"
                  onClick={() => action("reviewed")}
                >
                  Mark as reviewed
                </Button>
              )}
              <Button
                className="secondary full"
                icon="print"
                onClick={() => window.print()}
              >
                Print summary
              </Button>
            </div>
          )}
          <Attachments
            session={session}
            readonly={doctor || session.status !== "review"}
            onRefresh={refresh}
            onError={setError}
          />
          {session.status === "approved" && !doctor && (
            <div className="sharing-control">
              <h3>Sharing settings</h3>
              <p>
                Your summary and files are visible to{" "}
                <strong>{session.doctor_email}</strong>.
              </p>
              <Button
                className="secondary full"
                busy={busy}
                onClick={() => setWithdraw(true)}
              >
                Withdraw sharing
              </Button>
              <p className="field-hint">
                Withdrawal removes portal access. It cannot recall copies your
                doctor has already saved.
              </p>
            </div>
          )}
          <div className="review-meta">
            <Icon name="lock" size={16} />
            <span>
              {doctor
                ? "Patient approval is required for access."
                : "Your information is private to your account until you approve sharing."}
            </span>
          </div>
        </aside>
      </div>
      {withdraw && (
        <Modal
          title="Withdraw this shared summary?"
          onClose={() => setWithdraw(false)}
        >
          <p className="modal-copy">
            Your doctor will no longer be able to access this summary or its
            files in PreConsult. Copies already downloaded or added to clinical
            records cannot be recalled.
          </p>
          <div className="modal-actions">
            <Button className="secondary" onClick={() => setWithdraw(false)}>
              Keep sharing
            </Button>
            <Button className="danger" onClick={() => action("withdraw")}>
              Withdraw sharing
            </Button>
          </div>
        </Modal>
      )}
    </>
  );
}

function IntakePage({ id, user, config, onChanged }) {
  const [session, setSession] = useState(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);
  const [deleting, setDeleting] = useState(false);
  const [deleteOpen, setDeleteOpen] = useState(false);
  const mounted = useRef(true);
  const readGeneration = useRef(0);
  const doctor = user.role === "doctor";
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
  function update(data) {
    if (!mounted.current) return;
    readGeneration.current += 1;
    setSession(data);
    onChanged();
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
          Back to overview
        </a>
        <ErrorNotice>
          {error || "This consultation could not be found."}
        </ErrorNotice>
        <Button className="secondary" onClick={refresh}>
          Try again
        </Button>
      </div>
    );
  return (
    <div className="page intake-page">
      <a className="back-link" href={`#/${doctor ? "doctor" : "patient"}`}>
        <Icon name="back" size={16} />
        Back to overview
      </a>
      <div className="page-heading intake-heading">
        <div>
          <span className="overline">
            {doctor
              ? "CONSULTATION PREPARATION"
              : session.status === "active"
                ? "TELL YOUR STORY"
                : "REVIEW & SHARE"}
          </span>
          <h1>{session.title || "Your consultation"}</h1>
          <div className="intake-metadata">
            <Status status={session.status} />
            <span>Started {dateLabel(session.created_at)}</span>
          </div>
        </div>
        {!doctor && (
          <button
            className="icon-button delete-consultation"
            aria-label="Delete consultation"
            onClick={() => setDeleteOpen(true)}
          >
            <Icon name="trash" size={18} />
          </button>
        )}
      </div>
      <ErrorNotice>{error}</ErrorNotice>
      {!doctor && session.status === "active" ? (
        <IntakeChat
          key={session.id}
          session={session}
          config={config}
          onUpdate={update}
          refresh={refresh}
        />
      ) : (
        <Review
          key={session.id}
          session={session}
          config={config}
          doctor={doctor}
          onUpdate={update}
          refresh={refresh}
        />
      )}{" "}
      {deleteOpen && (
        <Modal
          title="Delete this consultation?"
          onClose={() => !deleting && setDeleteOpen(false)}
        >
          <p className="modal-copy">
            This permanently deletes the consultation, its messages and uploaded
            files from PreConsult. This action cannot be undone.
          </p>
          {session.status === "approved" && (
            <p className="modal-copy">
              It also removes your doctor’s access. Copies already saved by your
              doctor cannot be recalled.
            </p>
          )}
          <div className="modal-actions">
            <Button
              className="secondary"
              disabled={deleting}
              onClick={() => setDeleteOpen(false)}
            >
              Keep consultation
            </Button>
            <Button className="danger" busy={deleting} onClick={remove}>
              Delete consultation
            </Button>
          </div>
        </Modal>
      )}
    </div>
  );
}

function Account({ user, onUpdated, onLogout }) {
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
          <span className="overline">YOUR WORKSPACE</span>
          <h1>My account</h1>
          <p>A few details to make this space yours.</p>
        </div>
      </div>
      <section className="account-card">
        <h2>Personal details</h2>
        <ErrorNotice>{error}</ErrorNotice>
        {notice && (
          <div className="notice success" role="status">
            <Icon name="check" size={17} />
            {notice}
          </div>
        )}
        <form onSubmit={save}>
          <label className="field-label" htmlFor="profile-name">
            Your name
          </label>
          <input
            id="profile-name"
            className="input"
            value={name}
            onChange={(e) => setName(e.target.value)}
            placeholder="How would you like to be addressed?"
            maxLength={100}
            autoComplete="name"
          />
          <label className="field-label" htmlFor="profile-email">
            Email address
          </label>
          <input
            id="profile-email"
            className="input"
            value={user.email}
            readOnly
          />
          <p className="field-hint">
            Your verified email is used to sign in and identify your account.
          </p>
          <Button type="submit" className="primary" busy={busy}>
            Save changes
          </Button>
        </form>
      </section>
      <section className="account-card">
        <h2>Privacy & access</h2>
        <p>
          You sign in with a code delivered to your email. Keep access to your
          email account secure.
        </p>
        <p>
          {user.role === "doctor"
            ? "You can access only approved consultation records explicitly shared with your authorised email."
            : "You control sharing for each consultation. You can withdraw sharing or permanently delete a consultation from its detail page."}
        </p>
        <Button className="secondary" icon="logout" onClick={onLogout}>
          Sign out of this device
        </Button>
      </section>
    </div>
  );
}

export default function ProductApp() {
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
        document.querySelectorAll(".summary-text details:not([open])"),
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
    if (!user || currentGeneration !== authGeneration.current) return;
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
      setError(err.message);
    } finally {
      if (isCurrent()) setListBusy(false);
    }
  }, [user, currentGeneration]);
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
    if (user && roleFromRoute(route) !== user.role) setRoute(`/${user.role}`);
  }, [user, route]);
  async function logout() {
    try {
      await request("/auth/logout", { method: "POST" });
      adoptIdentity(null);
    } catch (err) {
      if (currentGeneration === authGeneration.current) setError(err.message);
    }
  }
  if (loading)
    return (
      <div className="boot-screen">
        <Brand />
        <Loading />
      </div>
    );
  if (bootError && !config)
    return (
      <div className="boot-screen">
        <Brand />
        <div className="connection-error">
          <h1>Let’s reconnect.</h1>
          <p>The PreConsult server could not be reached.</p>
          <ErrorNotice>{bootError}</ErrorNotice>
          <Button
            className="primary"
            onClick={() => {
              setBootError("");
              setLoading(true);
              setEpoch((x) => x + 1);
            }}
          >
            Try again
          </Button>
        </div>
      </div>
    );
  if (!user)
    return (
      <Login
        role={roleFromRoute(route)}
        config={config}
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
