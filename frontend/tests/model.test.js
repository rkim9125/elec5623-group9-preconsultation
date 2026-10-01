import { test } from "node:test";
import assert from "node:assert/strict";
import {
  initial,
  change,
  activeSteps,
  summary,
  describe,
} from "../src/model.js";
import { createMockService } from "../src/api/mock.js";
const answered = (value) => ({ status: "answered", value });
test("conditional frequency is activated, cleared, and excluded when parent changes", () => {
  let d = change(initial(), "course", answered("반복돼요"));
  assert.ok(activeSteps(d).includes("frequency"));
  d = change(d, "frequency", answered("하루에 여러 번"));
  d = change(d, "course", answered("비슷해요"));
  assert.equal(d.frequency.status, "unasked");
  assert.ok(!activeSteps(d).includes("frequency"));
  assert.ok(!summary(d)[1].text.includes("빈도"));
  d = change(d, "course", answered("반복돼요"));
  assert.equal(d.frequency.status, "unasked");
});
test("none, unknown, declined, unanswered, unasked remain distinct", () => {
  const values = ["none", "unknown", "declined", "unanswered", "unasked"].map(
    (status) => describe({ status, value: "" }),
  );
  assert.equal(new Set(values).size, 5);
  assert.equal(describe(answered("")), "미응답");
});
test("all changes revoke approval and completion without resetting unrelated fields", () => {
  let d = {
    ...initial(),
    approved: true,
    sent: true,
    history: answered("과거 수술"),
  };
  d = change(d, "onset", answered("오늘부터"));
  assert.equal(d.approved, false);
  assert.equal(d.sent, false);
  assert.equal(d.history.value, "과거 수술");
  assert.equal(d.revision, 1);
});
test("changed primary reason clears symptom answers but preserves medicine/history", () => {
  let d = initial();
  d.onset = answered("오늘부터");
  d.history = answered("고혈압");
  d = change(d, "reasons", ["새 문제"]);
  assert.equal(d.onset.status, "unasked");
  assert.equal(d.history.value, "고혈압");
});
test("medicine/allergy add edit delete and missing names are reflected in summary", () => {
  for (const key of ["medicines", "allergies"]) {
    let d = initial();
    d = change(d, key, {
      status: "answered",
      items: [
        { name: "가상 A", detail: "매일" },
        { name: "", detail: "" },
      ],
    });
    assert.match(describe(d[key]), /이름 모름/);
    assert.match(summary(d).at(-1).text, /세부 정보 모름/);
    d = change(d, key, {
      ...d[key],
      items: [{ name: "가상 B", detail: "수정됨" }],
    });
    assert.match(describe(d[key]), /가상 B/);
    assert.ok(!describe(d[key]).includes("가상 A"));
  }
});
test("mock fails once, retry preserves snapshot and revision", async () => {
  const api = createMockService(5);
  const d = initial();
  api.failOnce();
  await assert.rejects(api.request("summary", d));
  const pending = api.request("summary", d);
  d.revision = 7;
  const result = await pending;
  assert.equal(result.revision, 0);
  assert.equal(result.sections.length, 7);
});
test("only explicit onset at start of reason is copied without inferring", async () => {
  const { extractExplicitOnset } = await import("../src/api/mock.js");
  assert.equal(
    extractExplicitOnset("며칠 전부터 머리가 아파요."),
    "며칠 전부터",
  );
  assert.equal(
    extractExplicitOnset("어제는 괜찮았는데 언제부터인지 몰라요."),
    null,
  );
});
