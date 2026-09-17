import { useEffect, useRef, useState, useSyncExternalStore } from "react";
import IntakeApp from "../pages/patient/App.jsx";
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
} from "./domain.js";
import "./portal.css";
const nav = [
  ["/my", "마이페이지"],
  ["/appointments", "예약 현황"],
  ["/account", "계정 정보"],
];
const titleOf = (r) =>
  r.data.reasons.find((x) => x.trim()) || "방문 이유 작성 전";
function Status({ kind, children }) {
  return <span className={`account-status status-${kind}`}>{children}</span>;
}
function Loading() {
  return (
    <div className="account-loading" role="status">
      <span className="loading-dot" />
      데모 정보를 확인하고 있어요.
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
  return (
    <div className="account-error" role="alert">
      <h2>정보를 불러오지 못했어요</h2>
      <p>{error.message}</p>
      <button className="secondary" onClick={retry}>
        다시 시도
      </button>
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
                {new Intl.DateTimeFormat("ko-KR", {
                  timeZone: "Asia/Seoul",
                  month: "short",
                }).format(new Date(a.startsAt))}
              </span>
              <strong>
                {new Intl.DateTimeFormat("ko-KR", {
                  timeZone: "Asia/Seoul",
                  day: "numeric",
                })
                  .format(new Date(a.startsAt))
                  .replace("일", "")}
              </strong>
            </div>
            <div className="record-main">
              <h3>
                {a.hospital} <span>· {a.department}</span>
              </h3>
              <p>{formatDate(a.startsAt)}</p>
              <small>{a.clinician || "담당 의료진 미정"}</small>
            </div>
            <div className="record-state">
              <Status kind={a.status}>{appointmentLabels[a.status]}</Status>
              <small>{r ? intakeLabels[r.status] : "문진 미작성"}</small>
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
function IntakeRows({items, appointments}) {
 return <div className="record-list">{items.map(r => <div className="intake-row" key={r.id}><div className="record-main"><h3>{titleOf(r)}</h3><p>{appointments.find(a => a.id === r.appointmentId)?.hospital || '예약 미연결'}</p><small>최종 수정 {formatDate(r.updatedAt)}</small></div><Status kind={r.status}>{intakeLabels[r.status]}</Status></div>)}</div>;
}
function RecordsPage({ path, scope, bundle, refresh }) {
  const [appointmentFilter, setAppointmentFilter] = useState("upcoming"),
    [confirmReset, setConfirmReset] = useState(false);
  const { appointments, intakes } = bundle;
  const recent = [...intakes].sort(
    (a, b) => Date.parse(b.updatedAt) - Date.parse(a.updatedAt),
  );
  const next = sortAppointments(appointments, "upcoming")[0];
  const testControls = (
    <details className="account-test">
      <summary>데모 테스트</summary>
      <div>
        <button
          onClick={() => {
            api.failOnce();
            refresh();
          }}
        >
          조회 실패 체험
        </button>
        <button
          onClick={() => {
            api.slowOnce();
            refresh();
          }}
        >
          느린 조회 체험
        </button>
        <button onClick={() => api.expire()}>세션 만료 체험</button>
      </div>
    </details>
  );
  let content;
  if (path === "/my") {
    const draft = recent.find((r) => r.status === "draft");
    content = (
      <>
        <Intro
          eyebrow="MY CARE SPACE"
          title={`${api.getSnapshot().user.name}님, 안녕하세요.`}
        >
          다음 진료와 준비한 이야기를 확인해 보세요.
        </Intro>
        <section className="home-next">
          <div className="section-heading">
            <h2>다가오는 진료</h2>
            <RouteLink to="/appointments">예약 전체 보기 ↗</RouteLink>
          </div>
          {next ? (
            <>
              <div className="next-top">
                <div>
                  <Status kind="scheduled">예약 확정</Status>
                  <h2>
                    {next.hospital}
                    <span>{next.department}</span>
                  </h2>
                  <p>
                    {formatDate(next.startsAt)} <small>한국 시간</small>
                  </p>
                  <p>{next.clinician || "담당 의료진 미정"}</p>
                </div>
                <div className="next-date" aria-hidden="true">
                  {new Intl.DateTimeFormat("ko-KR", {
                    timeZone: "Asia/Seoul",
                    day: "numeric",
                  }).format(new Date(next.startsAt))}
                  <small>다음 진료일</small>
                </div>
              </div>
              <RouteLink className="primary" to={`/appointments/${next.id}`}>
                예약 확인<span>→</span>
              </RouteLink>
            </>
          ) : (
            <Empty title="예정된 예약이 없어요">
              이 데모에서는 예약을 새로 만들지 않습니다. 예약 없이도 문진을
              작성할 수 있어요.
            </Empty>
          )}
        </section>
        <section className="home-section">
          <div className="section-heading">
            <h2>이어 작성할 문진</h2>
          </div>
          {draft ? (
            <IntakeRows items={[draft]} appointments={appointments} />
          ) : (
            <div className="inline-empty">
              <p>작성 중인 문진이 없어요.</p>
            </div>
          )}
        </section>
        <section className="home-section">
          <div className="section-heading">
            <h2>최근 문진</h2>
          </div>
          {recent.filter((r) => r.id !== draft?.id).length ? (
            <IntakeRows
              items={recent.filter((r) => r.id !== draft?.id).slice(0, 3)}
              appointments={appointments}
            />
          ) : (
            <p className="inline-empty">
              {recent.length
                ? "이어서 작성할 문진 외에 최근 기록이 없어요."
                : "아직 작성한 문진이 없습니다. 첫 문진을 작성하면 여기에 표시돼요."}
            </p>
          )}
        </section>
      </>
    );
  } else if (path === "/appointments") {
    const items = sortAppointments(appointments, appointmentFilter);
    content = (
      <>
        <Intro eyebrow="APPOINTMENTS" title="예약 현황">
          예약 시간은 모두 한국 시간(Asia/Seoul)으로 표시합니다.
        </Intro>
        <div className="filter-tabs" role="group" aria-label="예약 분류">
          {[
            ["upcoming", "예정"],
            ["past", "지난 예약"],
            ["cancelled", "취소"],
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
          {items.length}개의 예약
        </p>
        {items.length ? (
          <AppointmentRows items={items} intakes={intakes} />
        ) : (
          <Empty
            title={
              appointments.length
                ? "해당하는 예약이 없어요"
                : "등록된 예약이 없어요"
            }
          >
            이 화면은 가상 예약 조회용입니다. 예약 없이 작성한 문진도 내
            문진에서 관리할 수 있어요.
          </Empty>
        )}
        <p className="footnote">
          시간이 지난 예약도 실제 진료 완료 정보가 없으면 ‘예약 확정’ 상태를
          유지합니다.
        </p>
      </>
    );
  } else if (path === "/account") {
    const user = api.getSnapshot().user;
    content = (
      <>
        <Intro eyebrow="ACCOUNT" title="계정 정보">
          이름과 이메일을 확인할 수 있어요.
        </Intro>
        <dl className="detail-facts">
          <div>
            <dt>이름</dt>
            <dd>{user.name}</dd>
          </div>
          <div>
            <dt>이메일</dt>
            <dd>{user.email}</dd>
          </div>
          <div>
            <dt>계정 유형</dt>
            <dd>가상 데모 계정</dd>
          </div>
        </dl>
        <div className="info-note">
          실제 보안 인증이 아닙니다. 회원가입에 입력한 비밀번호는 브라우저
          저장소에 보관하지 않습니다.
        </div>
        <div className="actions">
          <button
            className="primary"
            onClick={() => {
              api.logout();
              go("/login", { replace: true });
            }}
          >
            로그아웃
          </button>
        </div>
        <div className="reset-zone">
          <h2>현재 계정의 데모 기록 초기화</h2>
          <p>
            이 계정의 예약과 문진만 비웁니다. 다른 계정과 비로그인 문진은
            유지됩니다.
          </p>
          {confirmReset ? (
            <div role="alert">
              <p>이 계정의 가상 기록을 모두 지울까요?</p>
              <button
                className="secondary"
                onClick={() => {
                  api.resetCurrent(scope);
                  refresh();
                }}
              >
                기록 초기화 확인
              </button>
              <button
                className="text-button"
                onClick={() => setConfirmReset(false)}
              >
                취소
              </button>
            </div>
          ) : (
            <button
              className="text-button"
              onClick={() => setConfirmReset(true)}
            >
              데모 기록 초기화
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
          ← 예약 현황
        </RouteLink>
        <Intro eyebrow="APPOINTMENT DETAILS" title={a.hospital}>
          {a.department} · 예약 상세
        </Intro>
        <Status kind={a.status}>{appointmentLabels[a.status]}</Status>
        <dl className="detail-facts">
          <div>
            <dt>예약 일시</dt>
            <dd>
              {formatDate(a.startsAt)}
              <small>한국 시간(Asia/Seoul)</small>
            </dd>
          </div>
          <div>
            <dt>진료과</dt>
            <dd>{a.department}</dd>
          </div>
          <div>
            <dt>담당 의료진</dt>
            <dd>{a.clinician || "아직 정해지지 않았어요"}</dd>
          </div>
        </dl>
        {appointmentGroup(a) === "past" && a.status === "scheduled" && (
          <p className="info-note">
            예약 시간이 지났습니다. 실제 진료 완료 여부는 확인되지 않았어요.
          </p>
        )}
        <section className="home-section">
          <div className="section-heading">
            <h2>이 예약의 문진</h2>
          </div>
          {r ? (
            <>
              <IntakeRows items={[r]} appointments={appointments} />
              <p className="footnote">
                예약 상태와 문진 전달 상태는 별도로 관리합니다.
              </p>
            </>
          ) : (
            <div className="inline-empty">
              <p>
                {a.status === "cancelled"
                  ? "취소된 예약에는 새 문진을 작성할 수 없어요."
                  : "아직 연결된 문진이 없어요. 방문 이유부터 정리해 보세요."}
              </p>
            </div>
          )}
        </section>
      </>
    ) : (
      <NotFound />
    );
  } else content = <NotFound />;
  return (
    <>
      {content}
      <div className="portal-page-bottom">
        <span>나의 이야기가, 더 잘 전해지도록.</span>
        {testControls}
      </div>
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
  return (
    <ProtectedContent
      key={`${auth.epoch}:${path}`}
      path={path}
      user={auth.user}
      scope={{ userId: auth.user.id, epoch: auth.epoch }}
    />
  );
}
