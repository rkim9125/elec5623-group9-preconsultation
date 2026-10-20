import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync, readdirSync } from "node:fs";
import {
  languages,
  LOCALE_STORAGE_KEY,
  productResources,
  readProductLocale,
  translateProduct,
} from "../src/product/translations.js";
import { uiTranslationRows } from "../src/product/uiTranslations.js";
import { clinicalTranslationRows } from "../src/product/clinicalTranslations.js";
import { workflowTranslationRows } from "../src/product/workflowTranslations.js";
import { topicTranslationRows } from "../src/product/topicTranslations.js";
import { reportTranslationRows } from "../src/product/reportTranslations.js";
import { fieldLabelTranslationRows } from "../src/product/fieldLabelTranslations.js";
import { portalTranslationRows } from "../src/product/portalTranslations.js";
import {
  parseGuidedAnswer,
  serializeGuidedAnswer,
} from "../src/product/answerValues.js";

test("all five product languages have complete, nonempty catalogue rows and matching interpolation", () => {
  assert.deepEqual(
    languages.map(({ id }) => id),
    ["en", "zh-CN", "zh-TW", "ko", "ja"],
  );
  const params = (text) =>
    [...text.matchAll(/\{(\w+)\}/g)].map((match) => match[1]).sort();
  for (const row of [
    ...uiTranslationRows,
    ...clinicalTranslationRows,
    ...workflowTranslationRows,
    ...topicTranslationRows,
    ...reportTranslationRows,
    ...fieldLabelTranslationRows,
    ...portalTranslationRows,
  ]) {
    assert.equal(row.length, 5, row[0]);
    for (const translated of row) {
      assert.ok(translated.trim(), row[0]);
      assert.deepEqual(params(translated), params(row[0]), row[0]);
    }
  }
});

test("English is the default and all five selected languages survive preference loading", () => {
  for (const { id } of languages) {
    assert.equal(
      readProductLocale({
        getItem: (key) => (key === LOCALE_STORAGE_KEY ? id : null),
      }),
      id,
    );
  }
  for (const unsupported of [null, "", "fr", "English", "zh", "__proto__"]) {
    assert.equal(readProductLocale({ getItem: () => unsupported }), "en");
  }
  assert.equal(
    readProductLocale({
      getItem: () => {
        throw new Error("blocked");
      },
    }),
    "en",
  );
});

test("all direct static translation calls in the product have a complete catalogue entry", () => {
  const directory = new URL("../src/product/", import.meta.url);
  for (const file of readdirSync(directory).filter((name) =>
    name.endsWith(".jsx"),
  )) {
    const source = readFileSync(new URL(file, directory), "utf8");
    for (const match of source.matchAll(/\bt\(\s*"((?:[^"\\]|\\.)*)"/g)) {
      const key = JSON.parse(`"${match[1]}"`);
      for (const { id } of languages)
        assert.ok(productResources[id][key], `${file}: ${id}: ${key}`);
    }
  }
});

test("all thirty source workflow titles are translated in every supported language", () => {
  const source = readFileSync(
    new URL("../../backend/app/product/workflows.py", import.meta.url),
    "utf8",
  );
  const titles = [...source.matchAll(/'title': '([^']+)'/g)].map(
    (match) => match[1],
  );
  assert.equal(titles.length, 30);
  for (const title of titles)
    for (const { id } of languages.slice(1)) {
      assert.ok(productResources[id][title], `${id}: ${title}`);
      assert.notEqual(translateProduct(id, title), title);
    }
});

test("source keys interpolate safely and unknown text retains its exact wording", () => {
  assert.equal(
    translateProduct("zh-CN", "{count} selected", { count: 3 }),
    "已选择 3 项",
  );
  assert.equal(
    translateProduct("ko", "{count} selected", { count: 2 }),
    "2개 선택됨",
  );
  const narrative = "My knee hurts after 私の散歩 — patient wording";
  for (const { id } of languages)
    assert.equal(translateProduct(id, narrative), narrative);
  assert.equal(translateProduct("invalid", "Hello"), "Hello");
  assert.equal(translateProduct("en", "constructor"), "constructor");
  assert.equal(translateProduct("__proto__", "Hello"), "Hello");
});

test("changing displayed choice labels does not change canonical answers", () => {
  const options = [
    { value: "Sharp", label: "Sharp" },
    { value: "Aching", label: "Aching" },
  ];
  const answer = { selected: ["Sharp"], details: "My own details 我的描述" };
  const serialized = serializeGuidedAnswer(answer);
  for (const { id } of languages) {
    const localized = options.map((option) => ({
      ...option,
      label: translateProduct(id, option.label),
    }));
    assert.deepEqual(parseGuidedAnswer(serialized, localized), {
      ...answer,
      structured: true,
    });
  }
});
