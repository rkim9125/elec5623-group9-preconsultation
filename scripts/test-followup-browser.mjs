#!/usr/bin/env node
// Synthetic UI fixture only: API requests never reach a patient DB or provider.
import assert from "node:assert/strict";
import { createServer } from "node:http";
import { readFile, mkdir } from "node:fs/promises";
import { createRequire } from "node:module";
import { dirname, resolve, extname } from "node:path";
import { fileURLToPath } from "node:url";
const root = resolve(dirname(fileURLToPath(import.meta.url)), "..");
const require = createRequire(resolve(root, "frontend/package.json"));
const { chromium } = require("playwright");
const { expect } = require("@playwright/test");
const AxeBuilder = require("@axe-core/playwright").default;
const output = resolve(root, ".local/followup-browser");
await mkdir(output, { recursive: true });
const base = "http://127.0.0.1:8013";
const server = createServer(async (req, res) => {
  try {
    const pathname = new URL(req.url, base).pathname;
    const file = pathname.startsWith("/assets/") ? pathname : "/index.html";
    const data = await readFile(resolve(root, "frontend/dist", `.${file}`));
    res.setHeader(
      "Content-Type",
      { ".html": "text/html", ".js": "text/javascript", ".css": "text/css" }[
        extname(file)
      ] || "application/octet-stream",
    );
    res.end(data);
  } catch {
    res.statusCode = 404;
    res.end();
  }
});
await new Promise((done) => server.listen(8013, "127.0.0.1", done));
const browser = await chromium.launch({
  headless: true,
  executablePath:
    process.env.PLAYWRIGHT_CHROMIUM_EXECUTABLE ||
    "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
});
const context = await browser.newContext({
  viewport: { width: 1440, height: 1050 },
  reducedMotion: "reduce",
});
const page = await context.newPage();
const errors = [];
page.on("pageerror", (error) => errors.push(error.message));
const seed = () => ({
  id: "synthetic-followup",
  title: "Synthetic appointment",
  locale: "en",
  mode: "wizard",
  stage: "followup",
  status: "active",
  revision: 1,
  consent: true,
  created_at: "2026-10-21T00:00:00Z",
  patient_name: "Synthetic patient",
  baseline: { completed: true },
  concerns: [],
  shared_slots: {},
  attachments: [],
  messages: [],
  assistant: { mode: "live" },
  followup_batch: {
    id: "batch-one",
    locale: "en",
    status: "pending",
    round: 1,
    overview: "A few details will help organise your consultation summary.",
    questions: Array.from({ length: 5 }, (_, i) => ({
      id: `q${i}`,
      question: `Synthetic question ${i + 1}?`,
      why: "This helps make the summary clear.",
      options:
        i === 3
          ? []
          : ["Today", "This week", "Longer ago"].map((value, n) => ({
              id: String.fromCharCode(65 + n),
              label: value,
              value,
            })),
    })),
  },
});
let session = seed(),
  failDraft = false,
  submitCount = 0,
  reviewCount = 0,
  submitted;
await page.route("**/api/v1/**", async (route) => {
  const path = new URL(route.request().url()).pathname.replace("/api/v1", "");
  const body = route.request().postDataJSON();
  let json;
  if (path === "/config")
    json = {
      ai_configured: false,
      mail_configured: false,
      default_model: "gpt-6-astra",
      models: [],
      care_team: [],
    };
  else if (path === "/auth/me")
    json = {
      user: {
        id: "synthetic",
        role: "patient",
        email: "synthetic@example.test",
        name: "Synthetic patient",
      },
    };
  else if (path === "/workflows") json = [];
  else if (path === "/intakes") json = [session];
  else if (path.endsWith("/locale")) {
    session.locale = body.locale;
    if (session.followup_batch) session.followup_batch.locale = body.locale;
    session.revision++;
    json = session;
  }
  else if (path.endsWith("/followup/draft")) {
    if (failDraft)
      return route.fulfill({
        status: 503,
        json: { detail: "Synthetic draft failure" },
      });
    assert.equal(body.batch_id, session.followup_batch.id);
    session.followup_batch.draft_answers = body.answers;
    session.revision++;
    json = session;
  } else if (path.endsWith("/followup/answers")) {
    submitCount++;
    submitted = body;
    session.followup_batch.status = "answered";
    session.followup_batch.answers = body.answers;
    session.followup_batch.draft_answers = [];
    session.revision++;
    json = session;
  } else if (path.endsWith("/review")) {
    reviewCount++;
    session.status = "review";
    session.stage = "review";
    session.summary = { text: "Synthetic summary for UI testing.", version: 1 };
    json = session;
  } else if (path.endsWith("/followup")) {
    session.followup_batch = seed().followup_batch;
    json = session;
  } else if (path === "/intakes/synthetic-followup") json = session;
  else
    return route.fulfill({
      status: 404,
      json: { detail: "Unexpected synthetic route" },
    });
  await route.fulfill({ json: structuredClone(json) });
});
const open = async () => {
  await page.goto(`${base}/#/patient/intake/synthetic-followup`);
  await page.waitForSelector(".followup-main");
};
try {
  await open();
  const card = page.locator(".followup-question");
  const next = () =>
    page.getByRole("button", { name: "Next question", exact: true });
  const previous = () =>
    page.getByRole("button", { name: "Previous question", exact: true });
  const reviewAnswers = () =>
    page.getByRole("button", { name: "Review answers", exact: true });
  const submit = () =>
    page.getByRole("button", {
      name: "Submit answers & continue",
      exact: true,
    });
  const atQuestion = async (number) => {
    await expect(card).toHaveCount(1);
    await expect(
      card.getByRole("heading", {
        name: `Synthetic question ${number}?`,
        exact: true,
      }),
    ).toBeVisible();
    await expect(
      page.getByText(`Question ${number} of 5`, { exact: true }),
    ).toBeVisible();
    await expect(submit()).toHaveCount(0);
    assert.equal(
      submitCount,
      0,
      "Moving between steps must never submit the batch.",
    );
  };
  await atQuestion(1);
  await expect(next()).toBeDisabled();
  await expect(page.locator(".followup-option.selected")).toHaveCount(0);
  await card.getByRole("button", { name: "A Today", exact: true }).click();
  await expect(page.locator("#followup-answer-0")).toHaveValue("Today");
  await page.locator("#followup-answer-0").fill("Today after lunch");
  await expect
    .poll(() => session.followup_batch.draft_answers?.[0]?.value)
    .toBe("Today after lunch");
  await page.reload();
  await atQuestion(2);
  await previous().click();
  await atQuestion(1);
  await expect(page.locator("#followup-answer-0")).toHaveValue(
    "Today after lunch",
  );

  failDraft = true;
  await page
    .locator("#followup-answer-0")
    .fill("A saved draft must survive a failure");
  await expect(page.getByRole("alert")).toContainText(
    "Synthetic draft failure",
  );
  if (await next().isEnabled()) await next().click();
  await atQuestion(1);
  await page
    .getByRole("link", { name: "Back to overview", exact: true })
    .click();
  await expect(page.locator("#followup-answer-0")).toHaveValue(
    "A saved draft must survive a failure",
  );
  assert(page.url().includes("/intake/synthetic-followup"));
  failDraft = false;
  await page.getByRole("button", { name: "Try again", exact: true }).click();
  await expect
    .poll(() => session.followup_batch.draft_answers?.[0]?.value)
    .toBe("A saved draft must survive a failure");

  await next().click();
  await atQuestion(2);
  await card.getByRole("button", { name: "I don’t know", exact: true }).click();
  await next().click();
  await atQuestion(3);
  await card
    .getByRole("button", { name: "Skip this question", exact: true })
    .click();
  await next().click();
  await atQuestion(4);
  await expect(card.locator(".followup-option")).toHaveCount(0);
  await page
    .locator("#followup-answer-3")
    .fill("A free text answer without suggested choices");
  await previous().click();
  await atQuestion(3);
  await expect(
    card.getByRole("button", { name: "Skip this question", exact: true }),
  ).toHaveAttribute("aria-pressed", "true");
  await next().click();
  await atQuestion(4);
  await expect(page.locator("#followup-answer-3")).toHaveValue(
    "A free text answer without suggested choices",
  );
  await next().click();
  await atQuestion(5);
  await expect(reviewAnswers()).toBeDisabled();
  await card.getByRole("button", { name: "B This week", exact: true }).click();
  await page.evaluate(() => window.scrollTo(0, 0));
  await page.screenshot({
    path: resolve(output, "01-followup-desktop.png"),
    fullPage: true,
  });
  const checkAccessibility = async () => {
    const accessibility = await new AxeBuilder({ page })
      .include(".followup-main")
      .withTags(["wcag2a", "wcag2aa"])
      .analyze();
    assert.deepEqual(
      accessibility.violations.map(({ id, nodes }) => ({
        id,
        targets: nodes.map((node) => node.target),
      })),
      [],
    );
  };
  await checkAccessibility();
  await reviewAnswers().click();
  await expect(page.locator(".followup-review")).toBeVisible();
  await expect(card).toHaveCount(0);
  await expect(page.locator(".followup-review-answer")).toHaveCount(5);
  await expect(page.locator(".followup-review")).toContainText(
    "A saved draft must survive a failure",
  );
  await expect(submit()).toBeEnabled();
  assert.equal(submitCount, 0, "Reviewing answers must not submit them.");
  await expect
    .poll(
      () =>
        session.followup_batch.draft_answers?.filter(
          (x) => x.status !== "MISSING",
        ).length,
    )
    .toBe(5);
  await page.reload();
  await expect(page.locator(".followup-review")).toBeVisible();
  await expect(page.locator(".followup-review-answer")).toHaveCount(5);
  await page
    .getByRole("button", { name: "Edit answer 1", exact: true })
    .click();
  await atQuestion(1);
  await expect(page.locator("#followup-answer-0")).toHaveValue(
    "A saved draft must survive a failure",
  );
  await page
    .locator("#followup-answer-0")
    .fill("An answer edited after reviewing the set");
  await reviewAnswers().click();
  await expect(page.locator(".followup-review")).toContainText(
    "An answer edited after reviewing the set",
  );
  await page.evaluate(() => window.scrollTo(0, 0));
  await page.screenshot({
    path: resolve(output, "03-followup-review-desktop.png"),
    fullPage: true,
  });
  await checkAccessibility();
  await page.setViewportSize({ width: 390, height: 844 });
  await expect
    .poll(() =>
      page.evaluate(() => document.documentElement.scrollWidth <= innerWidth),
    )
    .toBe(true);
  await page.screenshot({
    path: resolve(output, "04-followup-review-mobile.png"),
    fullPage: true,
  });
  await checkAccessibility();
  await page.setViewportSize({ width: 1440, height: 1050 });
  await submit().click();
  await expect.poll(() => reviewCount).toBe(1);
  assert.equal(submitCount, 1);
  assert.equal(submitted.answers.length, 5);
  assert.equal(
    submitted.answers[0].value,
    "An answer edited after reviewing the set",
  );
  assert.equal(submitted.answers[1].status, "UNCERTAIN");
  assert.equal(submitted.answers[2].status, "SKIPPED");

  session = seed();
  session.followup_batch.id = "batch-two";
  session.followup_batch.round = 2;
  session.followup_batch.second_round_reason =
    "Please clarify two conflicting statements about the same medicine.";
  session.followup_batch.questions = session.followup_batch.questions.slice(
    0,
    1,
  );
  await page.reload();
  await expect(page.locator(".followup-exception")).toContainText(
    session.followup_batch.second_round_reason,
  );
  await expect(page.locator(".followup-question")).toHaveCount(1);
  for (const [locale, label] of [
    ["zh-CN", "AI 分析与追问"],
    ["zh-TW", "AI 分析與追問"],
    ["ko", "AI 분석 및 추가 질문"],
    ["ja", "AI分析と追加の質問"],
  ]) {
    await page.locator(".language-switcher select").selectOption(locale);
    await expect(page.locator(".followup-intro .overline")).toHaveText(label);
  }
  await page.locator(".language-switcher select").selectOption("zh-CN");
  await page.setViewportSize({ width: 390, height: 844 });
  await page.evaluate(() => window.scrollTo(0, 0));
  await expect
    .poll(() =>
      page.evaluate(() => document.documentElement.scrollWidth <= innerWidth),
    )
    .toBe(true);
  await page.screenshot({
    path: resolve(output, "02-followup-mobile.png"),
    fullPage: false,
  });
  assert(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= innerWidth,
    ),
  );
  await checkAccessibility();

  session = seed();
  session.followup_batch.status = "dismissed";
  session.followup_batch.invalidated_reason = "baseline_changed";
  session.followup_batch.draft_answers = [
    {
      question_id: "q0",
      value: "An earlier draft, never submitted",
      status: "FILLED",
    },
  ];
  await page.locator(".language-switcher select").selectOption("en");
  await page.reload();
  await expect(
    page.getByRole("heading", {
      name: "Your health information has changed.",
      exact: true,
    }),
  ).toBeVisible();
  await expect(
    page.getByText("All follow-up answers saved", { exact: true }),
  ).toHaveCount(0);
  await page
    .getByText("Earlier draft answers (not submitted)", { exact: true })
    .click();
  await expect(
    page.getByText("An earlier draft, never submitted", { exact: true }),
  ).toBeVisible();
  await expect(page.getByText("baseline_changed", { exact: true })).toHaveCount(
    0,
  );

  session = seed();
  delete session.followup_batch;
  session.current_question = { key: "onset", question: "Old serial question" };
  session.messages = [
    {
      role: "patient",
      text: "An earlier saved answer",
      created_at: session.created_at,
    },
  ];
  await page.locator(".language-switcher select").selectOption("en");
  await page.reload();
  await expect(
    page.getByRole("button", {
      name: "Prepare follow-up questions",
      exact: true,
    }),
  ).toBeVisible();
  await page.getByText("Your saved conversation", { exact: true }).click();
  await expect(
    page.getByText("An earlier saved answer", { exact: true }),
  ).toBeVisible();
  await page
    .getByRole("button", { name: "Prepare follow-up questions", exact: true })
    .click();
  await expect(page.locator(".followup-question")).toHaveCount(1);
  await expect(
    page.getByText("Question 1 of 5", { exact: true }),
  ).toBeVisible();
  assert.deepEqual(errors, []);
  console.log(
    "Passed: one question per wizard step, required completion, back/next answer retention, first-unanswered draft reload, review/edit/reload, failed-save navigation guard, final-only batch submit/review, exception rationale, five languages, mobile layout, dismissed draft preservation, legacy migration, WCAG 2 A/AA scans; no browser errors.",
  );
} finally {
  await browser.close();
  server.closeAllConnections();
  await new Promise((done) => server.close(done));
}
