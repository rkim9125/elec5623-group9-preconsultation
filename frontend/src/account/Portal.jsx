import { useEffect, useRef, useState, useSyncExternalStore } from "react";
import IntakeApp from "../pages/patient/App.jsx";
import { accountService as api } from "./service.js";
import { useRoute, go, RouteLink } from "./router.jsx";
import { demoUsers, DEMO_PASSWORD, safeReturn } from "./domain.js";
import "./portal.css";
const nav = [["/my", "마이페이지"]];
function Loading() {
  return (
    <div className="account-loading" role="status">
      <span className="loading-dot" />
      데모 정보를 확인하고 있어요.
    </div>
  );
}
function Intro({ eyebrow, title, children, action }) {
  const ref = useRef(null);
  useEffect(() => {
    ref.current?.focus();
    document.title = `${title} · 진료노트`;
  }, [title]);
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
        본문으로 이동
      </a>
      <header className="header">
        <RouteLink to={user ? "/my" : "start"} className="brand">
          <span className="brand-symbol" aria-hidden="true">
            ✳
          </span>
          진료노트<span className="brand-sub">진료 전, 내 이야기 정리</span>
        </RouteLink>
        <div className="portal-header-end">
          <span className="demo-badge">
            <span />
            체험용 데모
          </span>
          {user && (
            <button
              className="text-button"
              onClick={() => {
                api.logout();
                go("/login", { replace: true });
              }}
            >
              로그아웃
            </button>
          )}
        </div>
      </header>
      {user ? (
        <div className="portal-layout">
          <aside className="portal-nav">
            <p className="nav-caption">나의 진료 준비</p>
            <nav aria-label="환자 계정 메뉴">
              {nav.map(([to, text], i) => (
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
              <small>가상 환자 계정</small>
              <RouteLink to="start">비로그인 문진으로 ↗</RouteLink>
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
        <span>데모 · 실제 계정과 병원에 연결되지 않습니다.</span>
        <span>진료노트</span>
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
    if (signup && !values.name.trim()) err.name = "이름을 입력해 주세요.";
    if (!values.email.trim()) err.email = "이메일을 입력해 주세요.";
    else if (!/^\S+@\S+\.\S+$/.test(values.email.trim()))
      err.email = "이름@example.test 형식으로 입력해 주세요.";
    if (!values.password) err.password = "비밀번호를 입력해 주세요.";
    else if (signup && !/(?=.*[A-Za-z])(?=.*\d).{8,}/.test(values.password))
      err.password = "영문과 숫자를 포함해 8자 이상 입력해 주세요.";
    if (signup && values.password !== values.confirm)
      err.confirm = "비밀번호가 일치하지 않습니다. 다시 확인해 주세요.";
    if (signup && !values.confirm)
      err.confirm = "비밀번호를 한 번 더 입력해 주세요.";
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
              aria-label={visible ? "비밀번호 숨기기" : "비밀번호 표시"}
              aria-pressed={visible}
              onClick={() => setVisible((x) => !x)}
            >
              {visible ? "숨기기" : "표시"}
            </button>
          )}
        </div>
        {errors[key] && (
          <p className="field-error" id={`${key}-error`} role="alert">
            {errors[key]}
          </p>
        )}
      </div>
    );
  }
  return (
    <>
      <div className="auth-panel">
        <Intro
          eyebrow="MY PRE-VISIT NOTE"
          title={signup ? "내 진료노트 시작하기" : "다시 만나 반가워요"}
        >
          {signup
            ? "가상 정보로 계정을 만들고 문진을 관리해 보세요."
            : "예약과 작성한 문진을 한곳에서 확인하세요."}
        </Intro>
        {authMessage && (
          <p className="info-note" role="status">
            {authMessage}
          </p>
        )}
        {new URLSearchParams(location.hash.split("?")[1]).has("registered") && (
          <p className="info-note" role="status">
            데모 가입이 완료됐어요. 가입한 이메일과 비밀번호로 로그인해 주세요.
            이메일 인증은 진행하지 않습니다.
          </p>
        )}
        <form onSubmit={submit} noValidate>
          {signup && field("name", "이름", "text", "name")}
          {field("email", "이메일", "email", "username")}
          {signup && (
            <p id="password-hint" className="password-hint">
              데모 비밀번호: 영문과 숫자를 포함해 8자 이상. 실제 사용하는
              비밀번호는 입력하지 마세요.
            </p>
          )}
          {field(
            "password",
            "비밀번호",
            "password",
            signup ? "new-password" : "current-password",
          )}
          {signup &&
            field("confirm", "비밀번호 확인", "password", "new-password")}
          {errors.form && (
            <p className="error" role="alert" tabIndex={-1}>
              {errors.form}
            </p>
          )}
          <button disabled={busy} className="primary auth-submit">
            {busy ? "처리 중…" : signup ? "회원가입" : "로그인"}
            <span aria-hidden="true">→</span>
          </button>
          <p className="auth-switch">
            {signup ? "이미 계정이 있나요?" : "처음 이용하시나요?"}{" "}
            <RouteLink
              to={`/${signup ? "login" : "signup"}?returnTo=${encodeURIComponent(returnTo)}`}
            >
              {signup ? "로그인" : "회원가입"}
            </RouteLink>
          </p>
          <div className="sr-only" role="status">
            {busy ? "요청 처리 중입니다." : notice}
          </div>
        </form>
        <RouteLink className="guest-link" to="start">
          계정 없이 문진 체험하기 ↗
        </RouteLink>
      </div>
      <aside className="auth-context">
        <span className="context-label">체험 계정 안내</span>
        <div className="paper-icon" aria-hidden="true">
          <span>✳</span>
          <i />
          <i />
          <i />
          <b>✓</b>
        </div>
        <h2>내 진료 준비를, 한곳에</h2>
        <p>
          서로 다른 기록과 빈 화면을
          <br />
          가상 계정으로 살펴보세요.
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
                  `${u.name}의 체험용 이메일과 비밀번호를 입력했습니다.`,
                );
              }}
            >
              <strong>
                {u.name}
                <small>
                  {["예약·문진 기록", "다른 환자의 기록", "빈 상태"][i]}
                </small>
              </strong>
              <span>{u.email}</span>
            </button>
          ))}
        </div>
        <p className="demo-password">
          공통 비밀번호 <code>{DEMO_PASSWORD}</code>
        </p>
        <p className="footnote">
          새로 가입한 계정은 새로고침 전까지 체험할 수 있어요. 실제 인증
          서비스가 아닙니다.
        </p>
        <details>
          <summary>데모 테스트</summary>
          <button
            className="text-button"
            onClick={() => {
              api.failOnce();
              setNotice("다음 가입 또는 로그인 요청이 한 번 실패합니다.");
            }}
          >
            다음 인증 요청 실패
          </button>
        </details>
      </aside>
    </>
  );
}
function NotFound() {
  return (
    <>
      <Intro eyebrow="NOT FOUND" title="기록을 찾을 수 없어요">
        주소가 올바르지 않거나 이 계정에서 볼 수 없는 기록입니다.
      </Intro>
      <RouteLink className="secondary" to="/my">
        마이페이지로
      </RouteLink>
    </>
  );
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
  return <Shell user={auth.user} path={path}>{path === "/my" ? <><Intro eyebrow="MY ACCOUNT" title={`${auth.user.name}님, 안녕하세요.`}>데모 계정에 로그인했습니다.</Intro><p>{auth.user.email}</p></> : <NotFound />}</Shell>;
}
