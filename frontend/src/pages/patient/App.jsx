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
import { ko as t } from "../../copy.js";
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
    document.title = `${step === "start" ? "시작 안내" : t.stages[group(step)]} · ${t.brand}`;
    setNotice("");
  }, [step]);
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
  const answer = (status, value = "") =>
    update(step, { ...data[step], status, value });
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
        "방문 이유를 적어 주세요. 비어 있는 추가 항목은 삭제할 수 있어요.",
      );
    if (
      data[step]?.status === "answered" &&
      !data[step].items &&
      !data[step].value.trim()
    )
      return fail(
        "직접 설명을 적거나 아래에서 모름·답변 원하지 않음을 선택해 주세요.",
      );
    if (
      ["medicines", "allergies"].includes(step) &&
      data[step].status === "answered" &&
      !data[step].items.length
    )
      return fail("항목을 추가하거나 없음·모름을 선택해 주세요.");
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
      "진료노트 — 데모 문진 요약\n실제 병원에 전송되지 않았습니다.\n\n" +
      summary(data)
        .map((s) => s.title + "\n" + s.text)
        .join("\n\n");
    const url = URL.createObjectURL(
      new Blob([text], { type: "text/plain;charset=utf-8" }),
    );
    const a = document.createElement("a");
    a.href = url;
    a.download = "진료노트-데모-요약.txt";
    a.click();
    URL.revokeObjectURL(url);
    setNotice("요약 텍스트를 다운로드했습니다.");
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
      ? "진료 전에,\n차근차근 정리해요."
      : step === "reason"
        ? "어떤 이유로 방문하시나요?"
        : field?.title ||
          (step === "medicines"
            ? "현재 복용하는 약이 있나요?"
            : step === "allergies"
              ? "알고 있는 알레르기가 있나요?"
              : step === "review"
                ? "진료 전에 한 번 확인해 주세요."
                : "전달 시뮬레이션 완료");
  const modes = (none = false) => (
    <div className="alternatives">
      {[
        ...(none ? [["none", "없음"]] : []),
        ["unknown", "모름"],
        ["declined", "답변 원하지 않음"],
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
          {step === "medicines" ? "복용약 유무" : "알레르기 유무"}
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
          있어요 · 직접 입력
        </Choice>
        {modes(true)}
      </fieldset>
      {a.status === "answered" && (
        <div className="items">
          {a.items.map((item, i) => (
            <div className="item" key={i}>
              <div className="row">
                <h3>
                  {step === "medicines" ? "복용약" : "알레르기"} {i + 1}
                </h3>
                <button
                  type="button"
                  className="text-button"
                  aria-label={`${i + 1}번 항목 삭제`}
                  onClick={() => {
                    update(step, {
                      ...a,
                      items: a.items.filter((_, j) => i !== j),
                    });
                    setNotice("항목을 삭제했습니다.");
                    requestAnimationFrame(() =>
                      document.querySelector(".items .add")?.focus(),
                    );
                  }}
                >
                  삭제
                </button>
              </div>
              {["name", "detail"].map((k) => (
                <div className="input-group" key={k}>
                  <label htmlFor={`${step}-${i}-${k}`}>
                    {k === "name"
                      ? step === "medicines"
                        ? "약 이름"
                        : "알레르기 원인"
                      : step === "medicines"
                        ? "용량·복용 방법"
                        : "경험한 반응"}{" "}
                    <span className="muted">(모르면 비워 두세요)</span>
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
              setNotice("새 항목이 추가되었습니다.");
              requestAnimationFrame(() =>
                document
                  .getElementById(`${step}-${a.items.length}-name`)
                  ?.focus(),
              );
            }}
          >
            ＋ {step === "medicines" ? "복용약" : "알레르기"} 추가
          </button>
        </div>
      )}
    </>
  );
  const errors = error && (
    <p role="alert" id="form-error" className="error">
      {error}
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
        본문으로 이동
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
        <span className="demo-badge">
          <span />
          체험용 데모
        </span>
      </header>
      <div className="account-intake-bar">
        {account ? (
          <>
            <span>{account.user.name} · 계정 문진 작성 중</span>
            <button
              className="text-button"
              onClick={() => {
                onAccountSave(data, step);
                go("/intakes");
              }}
            >
              저장하고 내 문진으로 →
            </button>
          </>
        ) : (
          <>
            <span>계정 없이 문진을 체험하고 있어요</span>
            <RouteLink to="/login">로그인 · 내 진료노트 →</RouteLink>
          </>
        )}
      </div>
      <div className="app-layout">
        <aside className="navigation">
          <div className="nav-caption">나의 진료 준비</div>
          <ol aria-label="문진 단계">
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
                      ? "작성 중"
                      : completed.includes(i)
                        ? "작성 완료"
                        : ""}
                  </small>
                </span>
              </li>
            ))}
          </ol>
          <div className="nav-note">
            <span aria-hidden="true">♧</span>
            <p>
              내 속도에 맞춰 작성하세요.
              <br />
              이전 답변은 언제든
              <br className="desktop" /> 수정할 수 있어요.
            </p>
          </div>
        </aside>
        <main id="main" className="workspace">
          <div className="topline">
            <span>
              {step === "start"
                ? "시작 안내"
                : step === "done"
                  ? "작성 완료"
                  : `${String(current + 1).padStart(2, "0")} / ${t.stages[current]}`}
            </span>
            <span className="save-state">
              {storageError ? "이 탭에 저장할 수 없음" : "✓ 이 탭에 임시 저장"}
            </span>
          </div>
          <div className="page-content" key={step}>
            <div className="eyebrow">
              {step === "start"
                ? "PRE-VISIT NOTE"
                : step === "done"
                  ? "READY FOR YOUR VISIT"
                  : editing
                    ? "답변 수정"
                    : "MY VISIT NOTE"}
            </div>
            <h1 ref={heading} tabIndex={-1}>
              {title}
            </h1>
            {step === "start" ? (
              <>
                <p className="lead">
                  증상부터 궁금한 점까지.
                  <br />
                  진료 중 나누고 싶은 이야기를 미리 적어 보세요.
                </p>
                <div className="intro-list">
                  <div>
                    <span>01</span>
                    <p>
                      <strong>내 이야기를 적어요</strong>
                      <small>짧은 질문에 선택하거나 직접 답해 주세요.</small>
                    </p>
                  </div>
                  <div>
                    <span>02</span>
                    <p>
                      <strong>요약을 확인하고 고쳐요</strong>
                      <small>작성한 내용을 한눈에 살펴볼 수 있어요.</small>
                    </p>
                  </div>
                  <div>
                    <span>03</span>
                    <p>
                      <strong>전달 과정을 체험해요</strong>
                      <small>실제 의료진이나 병원에는 전송되지 않아요.</small>
                    </p>
                  </div>
                </div>
                <div className="info-note">
                  <strong>가상 정보로만 체험해 주세요</strong>
                  <p>
                    이 버전에서는 이 탭을 사용하는 사람만 내용을 볼 수 있어요.
                    실제 개인정보는 입력하지 마세요. 의료 판단·진단을 제공하지
                    않습니다.
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
                      setData(example());
                      navigate("reason");
                      setNotice("가상 방문 이유를 불러왔습니다.");
                    }}
                  >
                    가상 예시로 체험하기 ↗
                  </button>
                </div>
              </>
            ) : step === "reason" ? (
              <>
                <p className="lead">
                  가장 이야기하고 싶은 문제부터 적어 주세요.
                  <br />
                  정확한 의학 용어를 몰라도 괜찮아요.
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
                            ? "가장 먼저 이야기할 문제"
                            : "추가로 이야기할 문제"}{" "}
                          <span className="muted">
                            {i === 0 ? "필수" : i + 1}
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
                                setNotice("문제의 우선순위를 올렸습니다.");
                              }}
                            >
                              ↑ 우선순위
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
                              삭제
                            </button>
                          </div>
                        )}
                      </div>
                      <textarea
                        id={`reason-${i}`}
                        rows={4}
                        maxLength={3000}
                        placeholder="예: 며칠 전부터 머리가 아파요. 오후에 특히 불편해요."
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
                            ? "이 문제를 중심으로 추가 질문을 드릴게요."
                            : "추가 문제는 요약에 함께 기록합니다."}
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
                    ＋ 다른 문제 추가
                  </button>
                  {errors}
                  <div className="actions">
                    <button
                      type="button"
                      className="secondary"
                      onClick={() => navigate(editing ? "review" : "start")}
                    >
                      {editing ? "요약으로" : "← 이전"}
                    </button>
                    <button disabled={busy} className="primary">
                      {busy ? "요약 정리 중…" : editing ? t.editReturn : t.next}
                      <span>→</span>
                    </button>
                  </div>
                </form>
              </>
            ) : field || ["medicines", "allergies"].includes(step) ? (
              <>
                <p className="lead">
                  {field?.subtitle ||
                    "여러 개라면 하나씩 추가해 주세요. 정확히 몰라도 괜찮아요."}
                </p>
                {field && (
                  <details className="help">
                    <summary>왜 물어보나요?</summary>
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
                      {field.options?.map((v) => (
                        <Choice
                          name={step}
                          value={v}
                          selected={a.status === "answered" && a.value === v}
                          key={v}
                          onChange={() => answer("answered", v)}
                        >
                          {v}
                        </Choice>
                      ))}
                      <label className="input-label" htmlFor="free-answer">
                        {field.options ? "내 말로 설명하기" : field.label}
                      </label>
                      <textarea
                        id="free-answer"
                        rows={field.options ? 2 : 4}
                        maxLength={3000}
                        placeholder={
                          field.placeholder ||
                          "선택지에 없다면 직접 적어 주세요."
                        }
                        value={
                          a.status === "answered" &&
                          !field.options?.includes(a.value)
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
                      {editing ? "요약으로" : "← 이전"}
                    </button>
                    <button className="primary" disabled={busy}>
                      {busy ? "요약 정리 중…" : editing ? t.editReturn : t.next}
                      <span>→</span>
                    </button>
                  </div>
                  <p className="footnote">
                    답을 선택하지 않고 계속하면 ‘미응답’으로 기록돼요.
                  </p>
                </form>
              </>
            ) : step === "review" ? (
              <>
                <p className="lead">
                  직접 알려주신 내용만 정리했어요.
                  <br />
                  빠지거나 다른 내용이 있으면 수정해 주세요.
                </p>
                <div className="review-notice">
                  가상 문진 요약 <span>의료적 판단이 포함되지 않습니다</span>
                </div>
                <div className="summary">
                  {summary(data).map((s) => (
                    <section key={s.title}>
                      <div className="row">
                        <h2>{s.title}</h2>
                        {s.step && (
                          <button
                            className="text-button"
                            aria-label={`${s.title} 수정`}
                            onClick={() => edit(s.step)}
                          >
                            수정 ↗
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
                              {t.fields[k].label} 수정
                            </button>
                          ))}
                        </div>
                      )}
                    </section>
                  ))}
                </div>
                {data.reasons.some((value) => !value.trim()) && (
                  <div className="info-note">
                    <strong>방문 이유에 비어 있는 항목이 있어요</strong>
                    <p>내용을 적거나 비어 있는 추가 항목을 삭제해 주세요.</p>
                    <button
                      className="text-button"
                      onClick={() => edit("reason")}
                    >
                      방문 이유 확인 →
                    </button>
                  </div>
                )}
                {incomplete.length > 0 && (
                  <div className="info-note">
                    <strong>아직 확인하지 않은 질문이 있어요</strong>
                    <p>
                      수정으로 새로 필요한 질문도 한 번 확인해 주세요. 답변하지
                      않고 계속할 수도 있어요.
                    </p>
                    <button
                      className="text-button"
                      onClick={() => edit(incomplete[0])}
                    >
                      미확인 질문으로 →
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
                  <span>요약을 읽었으며, 내가 작성한 내용과 일치합니다.</span>
                </label>
                <p className="footnote">
                  답변을 수정하면 이 확인은 해제됩니다.
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
                      ? "전달 과정 체험 중…"
                      : data.sent
                        ? "시뮬레이션 완료 화면 보기"
                        : "확인하고 전달 시뮬레이션"}
                    <span>→</span>
                  </button>
                </div>
                <p className="footnote">
                  실제 의료진이나 병원에 전송되지 않습니다.
                </p>
              </>
            ) : (
              <>
                <div className="completion-mark" aria-hidden="true">
                  ✓
                </div>
                <p className="lead">
                  작성한 이야기가 요약으로 정리됐어요.
                  <br />
                  실제 의사나 병원에 전송된 내용은 없습니다.
                </p>
                <div className="info-note">
                  <strong>다음 진료를 위한 나의 메모</strong>
                  <p>
                    요약을 다시 확인하거나 텍스트로 내려받을 수 있어요. 예약이나
                    접수는 진행되지 않았습니다.
                  </p>
                </div>
                <div className="actions">
                  <button className="primary" onClick={download}>
                    요약 텍스트 다운로드 ↓
                  </button>
                  <button
                    className="secondary"
                    onClick={() => navigate("review")}
                  >
                    요약 다시 보기
                  </button>
                </div>
              </>
            )}
          </div>
          <footer className="workspace-footer">
            <span>내 이야기가, 더 잘 전해지도록.</span>
            <span>진료노트</span>
          </footer>
        </main>
        <aside className="context">
          <div className="context-label">
            {step === "start" ? "작성 전 알아두세요" : "나의 문진 메모"}
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
              <h2>기억에만 맡기지 않도록</h2>
              <p>
                증상, 복용약, 알레르기와
                <br />
                궁금한 점을 함께 정리해요.
              </p>
              <div className="context-divider" />
              <p className="small">
                답이 떠오르지 않으면
                <br />
                ‘모름’을 선택해도 괜찮아요.
              </p>
            </>
          ) : (
            <>
              <h2>먼저 나누고 싶은 이야기</h2>
              <p className="preview-text">
                {data.reasons[0] || "방문 이유를 작성하면 여기에 표시됩니다."}
              </p>
              <div className="context-divider" />
              <dl>
                <dt>증상 시작</dt>
                <dd>{describe(data.onset)}</dd>
                <dt>복용약</dt>
                <dd>
                  {data.medicines.status === "answered"
                    ? `${data.medicines.items.length}개 입력`
                    : describe(data.medicines)}
                </dd>
              </dl>
              <p className="small">
                작성한 답변은 마지막 단계에서
                <br />한 번에 확인하고 수정할 수 있어요.
              </p>
            </>
          )}
        </aside>
      </div>
      <footer className="bottom">
        <span>데모 · 실제 의료 서비스가 아닙니다</span>
        <div>
          <details>
            <summary>데모 테스트</summary>
            <button
              onClick={() => {
                mock.failOnce();
                setNotice("다음 요약 또는 전달 요청이 한 번 실패합니다.");
              }}
            >
              다음 응답 실패시키기
            </button>
          </details>
          <button
            ref={resetButton}
            className="text-button"
            onClick={() => setResetOpen(true)}
          >
            데모 데이터 초기화
          </button>
        </div>
      </footer>
      <div className="sr-only" aria-live="polite" role="status">
        {busy
          ? "요청 처리 중입니다."
          : notice ||
            (storageError
              ? "임시 저장이 불가능합니다. 새로고침하면 답변이 사라질 수 있습니다."
              : `${title} 화면입니다.`)}
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
            <h2 id="reset-title">작성한 데모 데이터를 지울까요?</h2>
            <p>이 탭의 답변과 검토 상태를 초기화합니다.</p>
            <div className="actions">
              <button
                autoFocus
                className="secondary"
                onClick={() => {
                  setResetOpen(false);
                  resetButton.current?.focus();
                }}
              >
                취소
              </button>
              <button
                className="primary"
                onClick={() => {
                  setData(initial());
                  setEditing(false);
                  setResetOpen(false);
                  navigate("start");
                  setNotice("데모 데이터를 초기화했습니다.");
                }}
              >
                초기화
              </button>
            </div>
          </div>
        </div>
      )}
    </>
  );
}
