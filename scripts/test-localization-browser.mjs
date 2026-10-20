#!/usr/bin/env node
// Synthetic API fixtures only; no real account, database, provider or email calls.
import assert from "node:assert/strict";
import { createServer } from "node:http";
import { readFile } from "node:fs/promises";
import { createRequire } from "node:module";
import { dirname, resolve, extname } from "node:path";
import { fileURLToPath } from "node:url";
import { translateProduct } from "../frontend/src/product/translations.js";
const root = resolve(dirname(fileURLToPath(import.meta.url)), "..");
const require = createRequire(resolve(root, "frontend/package.json"));
const { chromium } = require("playwright");
const { expect } = require("@playwright/test");
const base = "http://127.0.0.1:8015";
const server = createServer(async (req, res) => {
  try {
    const path = new URL(req.url, base).pathname;
    const file = path.startsWith("/assets/") ? path : "/index.html";
    res.setHeader("Content-Type", { ".html": "text/html", ".js": "text/javascript", ".css": "text/css" }[extname(file)] || "application/octet-stream");
    res.end(await readFile(resolve(root, "frontend/dist", `.${file}`)));
  } catch { res.statusCode = 404; res.end(); }
});
await new Promise((done) => server.listen(8015, "127.0.0.1", done));
const browser = await chromium.launch({ headless: true, executablePath: process.env.PLAYWRIGHT_CHROMIUM_EXECUTABLE || "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome" });
const page = await browser.newPage({ viewport: { width: 1440, height: 1050 } });
const errors = [], calls = [];
page.on("pageerror", (e) => errors.push(e.message));
const t = (locale, source) => translateProduct(locale, source);
const dynamic = {
  en: ["How is your knee feeling this week?", "It feels about the same", "Your knee discomfort is unchanged this week."],
  "zh-CN": ["这周膝盖的感觉如何？", "感觉与之前差不多", "这周您的膝盖不适与之前相近。"],
  "zh-TW": ["這週膝蓋的感覺如何？", "感覺與之前差不多", "這週您的膝蓋不適與之前相近。"],
  ko: ["이번 주 무릎은 어떤가요?", "이전과 비슷해요", "이번 주 무릎 불편감은 이전과 비슷합니다."],
  ja: ["今週、膝の調子はいかがですか？", "以前と同じくらいです", "今週の膝の不快感は以前と同じ程度です。"],
};
let session = {
  id: "synthetic-locale", title: "Leg pain", locale: "zh-CN", mode: "wizard", stage: "followup", status: "active", revision: 1, consent: true,
  patient_name: "Synthetic patient", created_at: "2026-10-21T00:00:00Z", updated_at: "2026-10-21T00:00:00Z", baseline: { completed: true },
  concerns: [{ id: "leg", title: "Leg pain", workflow_id: "WF-01", slots: { symptom_onset: { label: "Symptom onset", status: "FILLED", value: "Patient original wording stays exact" } } }],
  shared_slots: {}, attachments: [], messages: [], assistant: { mode: "live" },
  // Deliberately legacy: same session locale, but old English questions have no locale.
  followup_batch: { id: "same-batch", status: "pending", questions: [
    { id: "q1", question: dynamic.en[0], why: "This helps make the summary clear.", options: [{ id: "A", label: dynamic.en[1], value: "same" }] },
    { id: "q2", question: "What else should we know?", options: [] },
  ], draft_answers: [] },
};
let failLocale = false, assessmentLocale;
await page.route("**/api/v1/**", async (route) => {
  const path = new URL(route.request().url()).pathname.replace("/api/v1", "");
  const body = route.request().postDataJSON();
  calls.push({ path, body });
  let json;
  if (path === "/config") json = { ai_configured: true, mail_configured: false, models: [], default_model: "gpt-6-astra", care_team: [] };
  else if (path === "/auth/me") json = { user: { id: "synthetic", role: "patient", email: "synthetic@example.test", name: "Synthetic patient" } };
  else if (path === "/workflows") json = [];
  else if (path === "/intakes") json = [session];
  else if (path.endsWith("/locale")) {
    if (failLocale) return route.fulfill({ status: 503, json: { detail: "Synthetic language failure" } });
    session.locale = body.locale;
    session.followup_batch.locale = body.locale;
    session.followup_batch.questions[0].question = dynamic[body.locale][0];
    session.followup_batch.questions[0].options[0].label = dynamic[body.locale][1];
    session.revision++;
    json = session;
  } else if (path.endsWith("/followup/draft")) {
    session.followup_batch.draft_answers = body.answers;
    session.revision++;
    json = session;
  } else if (path.endsWith("/ai-report")) {
    assessmentLocale = body.locale;
    session.ai_report = { status: "ready", locale: body.locale, localization_version: 2, overview: { text: dynamic[body.locale][2], source_ids: [] }, sources: [], possible_diagnoses: [], limitations: [] };
    json = session.ai_report;
  } else if (path === "/intakes/synthetic-locale") json = session;
  else return route.fulfill({ status: 404, json: { detail: `Unexpected synthetic route ${path}` } });
  await route.fulfill({ json: structuredClone(json) });
});
await page.addInitScript(() => localStorage.setItem("preconsultation.locale", "zh-CN"));
try {
  await page.goto(`${base}/#/patient/intake/synthetic-locale`);
  await expect(page.locator("h1")).toHaveText("腿痛");
  await expect(page.locator(".followup-question h3")).toHaveText(dynamic["zh-CN"][0]);
  assert.equal(calls.filter((c) => c.path.endsWith("/locale")).length, 1, "Legacy questions localize even if session language already matches.");
  await page.locator(".followup-option").click();
  await expect(page.locator(".followup-question textarea")).toHaveValue(dynamic["zh-CN"][1]);
  await page.locator(".language-switcher select").selectOption("ko");
  await expect(page.locator(".followup-question")).toHaveCount(1);
  await expect(page.locator("h1")).toHaveText(t("ko", "Leg pain"));
  const koIndex = calls.findIndex((c) => c.path.endsWith("/locale") && c.body.locale === "ko");
  assert.ok(calls.slice(0, koIndex).some((c) => c.path.endsWith("/followup/draft") && c.body.answers[0].value === "same"), "Canonical choice is saved before changing language.");
  assert.equal(session.followup_batch.id, "same-batch");
  assert.equal(session.followup_batch.draft_answers[0].value, "same");
  // The remounted wizard correctly returns to the first unanswered question.
  await page.getByRole("button", { name: t("ko", "Previous question"), exact: true }).click();
  await expect(page.locator(".followup-question textarea")).toHaveValue(dynamic.ko[1]);
  await page.locator(".followup-question textarea").fill("My own words: no medication changes");
  failLocale = true;
  await page.locator(".language-switcher select").selectOption("ja");
  await expect(page.getByText(t("ja", "We could not update the consultation language. Your answers are saved. Please try again."), { exact: true })).toBeVisible();
  await expect(page.locator(".followup-question")).toHaveCount(0);
  assert.equal(session.followup_batch.draft_answers[0].value, "My own words: no medication changes");
  failLocale = false;
  await page.getByRole("button", { name: t("ja", "Try again"), exact: true }).click();
  await expect(page.locator(".followup-question")).toHaveCount(1);
  for (const locale of ["zh-TW", "en", "zh-CN"]) {
    await page.locator(".language-switcher select").selectOption(locale);
    await expect(page.locator("h1")).toHaveText(t(locale, "Leg pain"));
    await expect(page.locator(".followup-question")).toHaveCount(1);
  }
  session.status = "review"; session.stage = "review"; session.followup_batch.status = "answered";
  session.summary = { version: 1, text: "合成测试记录", synthesis: { status: "live", patient_overview: [{ text: "OLD ENGLISH SUMMARY MUST NOT DISPLAY", source_ids: [] }], sources: [] } };
  session.ai_report = { status: "ready", overview: { text: "OLD ENGLISH REPORT MUST NOT DISPLAY" }, localization_outdated: true };
  await page.reload();
  await expect(page.getByText("OLD ENGLISH SUMMARY MUST NOT DISPLAY", { exact: true })).toHaveCount(0);
  await expect(page.getByText("OLD ENGLISH REPORT MUST NOT DISPLAY", { exact: true })).toHaveCount(0);
  await expect(page.getByRole("button", { name: t("zh-CN", "Approve & share"), exact: true })).toBeDisabled();
  await expect(page.getByRole("button", { name: t("zh-CN", "Download complete PDF"), exact: true })).toBeDisabled();
  await page.getByRole("button", { name: t("zh-CN", "Generate AI assessment"), exact: true }).click();
  await expect(page.getByText(dynamic["zh-CN"][2], { exact: true })).toBeVisible();
  assert.equal(assessmentLocale, "zh-CN");
  session.status = "approved";
  session.ai_report = { status: "ready", overview: { text: "Approved original assessment" }, localization_outdated: true, sources: [], possible_diagnoses: [], limitations: [] };
  session.summary.synthesis.patient_overview[0].text = "Approved original summary";
  await page.reload();
  await expect(page.getByText("Approved original assessment", { exact: true })).toBeVisible();
  await expect(page.getByText("Approved original summary", { exact: true })).toBeVisible();
  assert.ok(await page.getByText(t("zh-CN", "This shared report keeps the language approved by the patient. Withdraw sharing before preparing a new version in another language."), { exact: true }).count() >= 1);
  await page.goto(`${base}/#/patient/history`);
  await expect(page.locator(".consultation-row strong")).toHaveText("腿痛");
  await page.getByRole("textbox", { name: t("zh-CN", "Search consultations") }).fill("腿痛");
  await expect(page.locator(".consultation-row")).toHaveCount(1);
  assert.deepEqual(errors, []);
  console.log("Passed: canonical titles and translated search; legacy same-locale migration; five-language switching; save-before-language-change; stable batch IDs and exact draft preservation; localized option display with canonical payload; failed translation hides stale questions and retries; stale English summary/report withheld; assessment locale propagated; stale share/export blocked; approved original reports retained with notice; no browser errors.");
} finally {
  await browser.close(); server.closeAllConnections(); await new Promise((done) => server.close(done));
}
