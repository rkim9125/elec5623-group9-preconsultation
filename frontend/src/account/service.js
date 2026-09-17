import {
  ACCOUNT_KEY,
  SESSION_KEY,
  DEMO_PASSWORD,
  demoUsers,
  seedDatabase,
  intakeStatus,
} from "./domain.js";
import { initial, summary } from "../model.js";
const fault = (code, message) => Object.assign(new Error(message), { code });
const clone = (value) => structuredClone(value);
export function createAccountService({
  storage,
  delay = 400,
  now = () => Date.now(),
} = {}) {
  let state = { status: "checking", user: null, epoch: 0, message: "" };
  const listeners = new Set(),
    registered = new Map(),
    credentials = new Map();
  let memoryDb = null,
    failNext = false,
    slowNext = false;
  const emit = () => listeners.forEach((fn) => fn());
  function database() {
    if (memoryDb) return memoryDb;
    try {
      const db = JSON.parse(storage?.getItem(ACCOUNT_KEY));
      if (db?.version === 1) return db;
    } catch {
      /* unavailable storage uses memory */
    }
    return seedDatabase(now());
  }
  function persist(db) {
    memoryDb = db;
    const durable = db;
    try {
      if (!storage) return false;
      storage.setItem(ACCOUNT_KEY, JSON.stringify(durable));
      return true;
    } catch {
      return false;
    }
  }
  const boot = database();
  boot.intakes = boot.intakes.filter((i) =>
    demoUsers.some((u) => u.id === i.userId),
  );
  persist(boot);
  const users = () => [...demoUsers, ...registered.values()];
  function clearSession(message = "") {
    state = {
      status: "anonymous",
      user: null,
      epoch: state.epoch + 1,
      message,
    };
    try {
      storage?.removeItem(SESSION_KEY);
    } catch {
      /* in-memory fallback */
    }
    failNext = false;
    slowNext = false;
    emit();
  }
  function assertScope(scope) {
    if (state.status === "authenticated" && state.expiresAt <= now())
      clearSession("세션이 만료되었어요. 다시 로그인해 주세요.");
    if (
      state.status !== "authenticated" ||
      scope?.epoch !== state.epoch ||
      scope.userId !== state.user.id
    )
      throw fault(
        "SESSION_EXPIRED",
        "세션이 만료되었어요. 다시 로그인해 주세요.",
      );
  }
  async function wait(scope, canFail = true) {
    const shouldFail = canFail && failNext;
    if (canFail) failNext = false;
    const ms = slowNext ? 1800 : delay;
    slowNext = false;
    await new Promise((r) => setTimeout(r, ms));
    if (scope) assertScope(scope);
    if (shouldFail)
      throw fault(
        "LOAD_FAILED",
        "데모 요청을 처리하지 못했어요. 다시 시도해 주세요.",
      );
  }
  async function verifier(password, salt) {
    const bytes = new TextEncoder().encode(salt + password);
    return Array.from(
      new Uint8Array(await crypto.subtle.digest("SHA-256", bytes)),
    )
      .map((x) => x.toString(16).padStart(2, "0"))
      .join("");
  }
  const api = {
    subscribe(fn) {
      listeners.add(fn);
      return () => listeners.delete(fn);
    },
    getSnapshot() {
      return state;
    },
    scope() {
      if (!state.user) throw fault("SESSION_EXPIRED", "로그인이 필요합니다.");
      return { userId: state.user.id, epoch: state.epoch };
    },
    async restore() {
      const epoch = state.epoch;
      await wait(null, false);
      if (state.epoch !== epoch) return;
      let session;
      try {
        session = JSON.parse(storage?.getItem(SESSION_KEY));
      } catch {
        /* invalid demo session */
      }
      const user = demoUsers.find((u) => u.id === session?.userId);
      if (user && session.expiresAt > now()) {
        state = {
          status: "authenticated",
          user,
          epoch: epoch + 1,
          expiresAt: session.expiresAt,
          message: "",
        };
        emit();
      } else
        clearSession(
          session ? "세션이 만료되었어요. 다시 로그인해 주세요." : "",
        );
    },
    async login(email, password, signal) {
      const epoch = state.epoch;
      await wait();
      if (state.epoch !== epoch || signal?.aborted)
        throw fault("STALE", "로그인 요청이 취소되었습니다.");
      const user = users().find((u) => u.email === email.trim().toLowerCase());
      let valid = false;
      if (user) {
        const credential = credentials.get(user.id);
        valid = credential
          ? (await verifier(password, credential.salt)) === credential.hash
          : demoUsers.some((u) => u.id === user.id) &&
            password === DEMO_PASSWORD;
      }
      if (!valid)
        throw fault("LOGIN_FAILED", "이메일 또는 비밀번호를 확인해 주세요.");
      if (state.epoch !== epoch || signal?.aborted)
        throw fault("STALE", "로그인 요청이 취소되었습니다.");
      state = {
        status: "authenticated",
        user: clone(user),
        expiresAt: now() + 3600000,
        epoch: epoch + 1,
        message: "",
      };
      try {
        storage?.setItem(
          SESSION_KEY,
          JSON.stringify({ userId: user.id, expiresAt: now() + 3600000 }),
        );
      } catch {
        /* session lasts until reload */
      }
      emit();
      return clone(user);
    },
    async signup({ name, email, password }, signal) {
      await wait();
      if (signal?.aborted) throw fault("STALE", "가입 요청이 취소되었습니다.");
      email = email.trim().toLowerCase();
      if (users().some((u) => u.email === email))
        throw fault(
          "EMAIL_EXISTS",
          "이미 사용 중인 데모 이메일입니다. 다른 이메일을 입력해 주세요.",
        );
      if (
        !name.trim() ||
        !/^\S+@\S+\.\S+$/.test(email) ||
        !/(?=.*[A-Za-z])(?=.*\d).{8,}/.test(password)
      )
        throw fault(
          "INVALID",
          "이름·이메일과 데모 비밀번호 조건을 확인해 주세요.",
        );
      const id = crypto.randomUUID(),
        salt = crypto.randomUUID();
      const hash = await verifier(password, salt);
      if (users().some((u) => u.email === email))
        throw fault("EMAIL_EXISTS", "이미 사용 중인 데모 이메일입니다.");
      if (signal?.aborted) throw fault("STALE", "가입 요청이 취소되었습니다.");
      registered.set(id, { id, name: name.trim(), email });
      credentials.set(id, { salt, hash });
      return { id, name: name.trim(), email };
    },
    logout() {
      clearSession();
      memoryDb = null;
    },
    expire() {
      clearSession("세션이 만료되었어요. 다시 로그인해 주세요.");
      memoryDb = null;
    },
    failOnce() {
      failNext = true;
    },
    slowOnce() {
      slowNext = true;
    },
    async load(scope) {
      await wait(scope);
      const db = database();
      return clone({
        appointments: db.appointments.filter((a) => a.userId === scope.userId),
        intakes: db.intakes.filter((i) => i.userId === scope.userId),
      });
    },
    startIntake(scope, appointmentId = null) {
      assertScope(scope);
      const db = database();
      if (appointmentId) {
        const appointment = db.appointments.find(
          (a) => a.id === appointmentId && a.userId === scope.userId,
        );
        if (!appointment) throw fault("NOT_FOUND", "예약을 찾을 수 없어요.");
        const existing = db.intakes.find(
          (i) => i.userId === scope.userId && i.appointmentId === appointmentId,
        );
        if (existing) return clone(existing);
        if (appointment.status === "cancelled")
          throw fault(
            "CANCELLED",
            "취소된 예약에는 새 문진을 작성할 수 없어요.",
          );
      }
      const record = {
        id: crypto.randomUUID(),
        userId: scope.userId,
        appointmentId,
        data: initial(),
        step: "reason",
        status: "draft",
        updatedAt: new Date(now()).toISOString(),
      };
      db.intakes.unshift(record);
      persist(db);
      return clone(record);
    },
    saveIntake(scope, id, data, step) {
      assertScope(scope);
      const db = database();
      const index = db.intakes.findIndex(
        (i) => i.id === id && i.userId === scope.userId,
      );
      if (index < 0) throw fault("NOT_FOUND", "문진을 찾을 수 없어요.");
      const old = db.intakes[index];
      if (old.snapshot) return { record: clone(old), saved: true };
      if (
        data.sent &&
        (!data.approved ||
          intakeStatus({ ...data, sent: false }, "review") !== "completed")
      )
        throw fault(
          "REVIEW_REQUIRED",
          "문진을 확인하고 요약을 다시 승인해 주세요.",
        );
      if (
        JSON.stringify(old.data) === JSON.stringify(data) &&
        old.step === step
      )
        return { record: clone(old), saved: true };
      const record = {
        ...old,
        data: clone(data),
        step,
        status: intakeStatus(data, step),
        updatedAt: new Date(now()).toISOString(),
      };
      if (data.sent)
        record.snapshot = { sections: summary(data), sentAt: record.updatedAt };
      db.intakes[index] = record;
      const saved = persist(db);
      return { record: clone(record), saved };
    },
    importGuest(scope, data, step) {
      assertScope(scope);
      if (!data?.reasons?.some((s) => s.trim()))
        throw fault("EMPTY", "가져올 방문 이유가 없어요.");
      const db = database();
      const existing = db.intakes.find(
        (i) =>
          i.userId === scope.userId && i.importedGuest === JSON.stringify(data),
      );
      if (existing) return clone(existing);
      const record = {
        id: crypto.randomUUID(),
        userId: scope.userId,
        appointmentId: null,
        data: clone(data),
        step: step || "reason",
        status: intakeStatus(data, step),
        updatedAt: new Date(now()).toISOString(),
        importedGuest: JSON.stringify(data),
      };
      if (data.sent)
        record.snapshot = { sections: summary(data), sentAt: record.updatedAt };
      db.intakes.unshift(record);
      persist(db);
      return clone(record);
    },
    resetCurrent(scope) {
      assertScope(scope);
      const db = database();
      db.intakes = db.intakes.filter((i) => i.userId !== scope.userId);
      db.appointments = db.appointments.filter(
        (a) => a.userId !== scope.userId,
      );
      persist(db);
    },
  };
  return api;
}
let storage;
try {
  storage = globalThis.sessionStorage;
} catch {
  /* blocked storage */
}
export const accountService = createAccountService({ storage });
