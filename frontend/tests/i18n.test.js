import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync, readdirSync } from "node:fs";
import {
  resources,
  translate,
  readLocale,
  setLocale,
  message,
  messageText,
  missingKeys,
} from "../src/i18n/core.js";
import { getCopy } from "../src/copy.js";
import { initial, summary, describe, example } from "../src/model.js";
import { formatDate, recordSummary } from "../src/account/domain.js";

test("catalogs cover the same keys and interpolation parameters", () => {
  assert.deepEqual(
    Object.keys(resources.en).sort(),
    Object.keys(resources.ko).sort(),
  );
  for (const key of Object.keys(resources.en)) {
    assert.ok(resources.en[key].trim());
    assert.ok(resources.ko[key].trim());
    assert.doesNotMatch(resources.en[key], /[가-힣]/, key);
    const params = (value) =>
      [...value.matchAll(/\{(\w+)\}/g)].map((m) => m[1]).sort();
    assert.deepEqual(params(resources.en[key]), params(resources.ko[key]), key);
  }
});
test("static translation calls and question definitions have complete resources", () => {
  const files = readdirSync(new URL("../src/", import.meta.url), {
    recursive: true,
  });
  for (const file of files.filter((f) => /\.(js|jsx)$/.test(f))) {
    const source = readFileSync(
      new URL(`../src/${file}`, import.meta.url),
      "utf8",
    );
    for (const match of source.matchAll(
      /\b(?:tr|message)\(\s*["']([^"']+)["']/g,
    ))
      assert.ok(resources.en[match[1]], `${file}: ${match[1]}`);
    if (file.startsWith("doctor/"))
      for (const match of source.matchAll(/\bt\(\s*["']([^"']+)["']/g))
        assert.ok(
          resources.en[
            `${file === "doctor/Calendar.jsx" ? "calendar" : "doctor"}.${match[1]}`
          ],
          `${file}: ${match[1]}`,
        );
  }
  missingKeys.clear();
  for (const locale of ["en", "ko"]) {
    getCopy(locale);
    example(locale);
    summary(initial(), locale);
  }
  assert.deepEqual([...missingKeys], []);
});
test("missing or invalid preferences fall back to English, including inaccessible storage", () => {
  for (const value of [null, "", "fr", "English", "en"])
    assert.equal(readLocale({ getItem: () => value }), "en");
  assert.equal(readLocale({ getItem: () => "ko" }), "ko");
  assert.equal(
    readLocale({
      getItem: () => {
        throw new Error("blocked");
      },
    }),
    "en",
  );
  assert.equal(
    translate("en", "missing.test.key"),
    "This message is unavailable.",
  );
  assert.equal(
    translate("ko", "missing.test.key"),
    "안내를 표시할 수 없습니다.",
  );
  missingKeys.clear();
});
test("existing message descriptors re-render without changing stored content", () => {
  const error = message("enter.your.name");
  const before = structuredClone(error);
  setLocale("en");
  assert.equal(messageText(error), "Enter your name.");
  setLocale("ko");
  assert.equal(messageText(error), "이름을 입력해 주세요.");
  assert.deepEqual(error, before);
});
test("summary translates labels and marked choices, never free text or stored values", () => {
  const data = initial();
  data.reasons = ["내 증상 / My symptoms"];
  data.onset = { status: "answered", value: "오늘부터", option: "오늘부터" };
  data.course = { status: "answered", value: "반복돼요", option: null };
  data.medicines = {
    status: "answered",
    items: [{ name: "가상 medicine", detail: "" }],
  };
  const before = structuredClone(data);
  const en = summary(data, "en");
  const ko = summary(data, "ko");
  assert.match(en[1].text, /Started: Today/);
  assert.match(en[1].text, /Changes: 반복돼요/);
  assert.match(en[3].text, /가상 medicine · Details unknown/);
  assert.equal(en[0].text, ko[0].text);
  assert.equal(describe({ status: "unknown" }, "en"), "Not sure");
  assert.equal(describe({ status: "none" }, "en"), "None");
  assert.equal(describe({ status: "unasked" }, "en"), "Not asked yet");
  assert.deepEqual(data, before);
});
test("date labels use the chosen locale while keeping the Seoul time zone", () => {
  const date = "2026-01-01T00:00:00Z";
  setLocale("en");
  const en = formatDate(date);
  setLocale("ko");
  const ko = formatDate(date);
  assert.match(en, /January/);
  assert.match(ko, /1월/);
  assert.match(en, /09:00/);
  assert.match(ko, /09:00/);
  assert.equal(date, "2026-01-01T00:00:00Z");
});

test("legacy handoff views translate only verified structure without changing the snapshot", () => {
  const data = initial();
  data.reasons = ["Original words"];
  const record = { data, snapshot: { sections: summary(data, "ko") } };
  const before = structuredClone(record);
  assert.equal(recordSummary(record, "en")[0].title, "Reason for visit");
  assert.match(recordSummary(record, "en")[1].text, /Not asked yet/);
  assert.deepEqual(record, before);
  record.data.reasons = ["Different words"];
  assert.equal(recordSummary(record, "en")[0].text, "1. Original words");
});
