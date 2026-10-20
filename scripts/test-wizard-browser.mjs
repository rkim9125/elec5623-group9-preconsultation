#!/usr/bin/env node
/**
 * Wizard acceptance test: isolated local API and synthetic account only.
 * Start: backend/.venv/bin/python scripts/product-browser-server.py
 * Run after frontend build: node scripts/test-wizard-browser.mjs
 * Audio capture/transcription are mocked; no microphone or external provider is used.
 */
import assert from "node:assert/strict";
import { createRequire } from "node:module";
import { access, mkdir, readFile, writeFile } from "node:fs/promises";
import path from "node:path";
import { fileURLToPath } from "node:url";

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const require = createRequire(path.join(root, "frontend/package.json"));
const { chromium } = require("playwright");
const { expect } = require("@playwright/test");
const AxeBuilder = require("@axe-core/playwright").default;
const base = process.env.PRECONSULT_TEST_URL || "http://127.0.0.1:8001";
const address = new URL(base);
assert(
  ["localhost", "127.0.0.1"].includes(address.hostname) &&
    address.port === "8001",
  "Only the isolated browser fixture on loopback port 8001 is allowed.",
);
const output = path.join(root, ".local/wizard-browser");
await mkdir(output, { recursive: true });
const tokens = JSON.parse(
  await readFile(path.join(root, ".local/browser-test/sessions.json"), "utf8"),
);
const config = await (await fetch(`${base}/api/v1/config`)).json();
assert.equal(config.ai_configured, false);
assert.equal(config.mail_configured, false);
assert.equal(config.default_model, "gpt-6-astra");
let executablePath = process.env.PLAYWRIGHT_CHROMIUM_EXECUTABLE;
if (!executablePath) {
  try {
    const chrome =
      "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome";
    await access(chrome);
    executablePath = chrome;
  } catch {
    /* bundled Chromium */
  }
}
const browser = await chromium.launch({
  headless: true,
  ...(executablePath ? { executablePath } : {}),
});
const context = await browser.newContext({
  viewport: { width: 1440, height: 1100 },
  locale: "en-AU",
  reducedMotion: "reduce",
});
await context.addCookies([
  {
    name: "preconsult_session",
    value: tokens.patient,
    url: base,
    httpOnly: true,
    sameSite: "Lax",
  },
]);
await context.addInitScript(() => {
  window.__audioTest = {
    requested: 0,
    stopped: 0,
    deny: false,
    failRecorder: false,
  };
  const getUserMedia = async () => {
    window.__audioTest.requested++;
    if (window.__audioTest.deny)
      throw new DOMException("Synthetic permission denial", "NotAllowedError");
    let stopped = false;
    return {
      getTracks: () => [
        {
          stop() {
            if (!stopped) {
              window.__audioTest.stopped++;
              stopped = true;
            }
          },
        },
      ],
    };
  };
  Object.defineProperty(navigator, "mediaDevices", {
    configurable: true,
    value: { getUserMedia },
  });
  window.MediaRecorder = class {
    static isTypeSupported(type) {
      return type === "audio/webm;codecs=opus";
    }
    constructor(stream, options) {
      if (window.__audioTest.failRecorder)
        throw new Error("Synthetic recorder initialization failure");
      this.stream = stream;
      this.mimeType = options?.mimeType || "audio/webm";
      this.state = "inactive";
    }
    start() {
      this.state = "recording";
    }
    stop() {
      if (this.state !== "recording") return;
      this.state = "inactive";
      setTimeout(() => {
        this.ondataavailable?.({
          data: new Blob(["synthetic audio"], { type: this.mimeType }),
        });
        this.onstop?.();
      }, 0);
    }
  };
  window.AudioContext = class {
    createAnalyser() {
      return {
        frequencyBinCount: 128,
        getByteTimeDomainData(data) {
          data.fill(144);
        },
      };
    }
    createMediaStreamSource() {
      return { connect() {} };
    }
    close() {
      return Promise.resolve();
    }
  };
});
const page = await context.newPage();
page.setDefaultTimeout(15000);
const checks = [],
  screenshots = [],
  pageErrors = [],
  accessibility = [],
  findings = [];
let transcriptionRequests = 0,
  createdCount = 0,
  nextTranscription = null;
page.on("pageerror", (error) => pageErrors.push(error.message));
page.on("request", (request) => {
  if (
    new URL(request.url()).pathname === "/api/v1/intakes" &&
    request.method() === "POST"
  )
    createdCount++;
});
await page.route("**/api/v1/transcriptions", async (route) => {
  transcriptionRequests++;
  const reply = nextTranscription;
  nextTranscription = null;
  assert(
    route.request().postData()?.includes('name="locale"'),
    "Audio submits the selected language.",
  );
  if (reply?.wait) await reply.wait;
  await route.fulfill({
    status: reply?.status || 200,
    json: reply?.json || {
      text: "A dull ache after walking for three weeks.",
    },
  });
  reply?.finished?.();
});
function pass(name) {
  checks.push(name);
  console.log(`PASS ${name}`);
}
async function api(suffix, method = "GET", body) {
  const response = await context.request.fetch(`${base}/api/v1${suffix}`, {
    method,
    headers: { Origin: base },
    ...(body === undefined ? {} : { data: body }),
  });
  assert(
    response.ok(),
    `${method} ${suffix}: ${response.status()} ${await response.text()}`,
  );
  return response.status() === 204 ? null : response.json();
}
async function screenshot(name) {
  await page.screenshot({
    path: path.join(output, name),
    animations: "disabled",
    fullPage: false,
  });
  screenshots.push(name);
}
async function noOverflow(label) {
  await expect
    .poll(() =>
      page.evaluate(
        () => document.documentElement.scrollWidth <= innerWidth + 1,
      ),
    )
    .toBe(true);
  pass(`${label}: no horizontal overflow`);
}
async function axe(label) {
  const result = await new AxeBuilder({ page })
    .withTags(["wcag2a", "wcag2aa", "wcag21aa"])
    .analyze();
  const violations = result.violations
    .filter((item) => ["serious", "critical"].includes(item.impact))
    .map(({ id, impact, help, nodes }) => ({
      id,
      impact,
      help,
      nodes: nodes.map(({ target, failureSummary }) => ({
        target,
        failureSummary,
      })),
    }));
  accessibility.push({ page: label, violations });
  if (!violations.length)
    pass(`${label}: no serious or critical accessibility findings`);
}
async function goNew() {
  await page.goto(`${base}/patient#/patient/new`);
  await expect(page.locator(".custom-chat-card")).toBeVisible();
}
async function createSelected(id) {
  await goNew();
  await page.locator(`[data-topic-id="${id}"]`).click();
  await page.locator(".wizard-consent input").check();
  const response = page.waitForResponse(
    (item) =>
      new URL(item.url()).pathname === "/api/v1/intakes" &&
      item.request().method() === "POST",
  );
  await page.getByRole("button", { name: "Let’s begin", exact: true }).click();
  const result = await response;
  assert(result.ok(), await result.text());
  const intake = await result.json();
  await expect(page.locator(".wizard-question-card")).toBeVisible();
  return intake;
}
async function savedValue(id, key, value, concernId = "session") {
  await expect
    .poll(async () => {
      const intake = await api(`/intakes/${id}`);
      return concernId === "session"
        ? intake.shared_slots[key]?.value
        : intake.concerns.find((item) => item.id === concernId)?.slots[key]
            ?.value;
    })
    .toBe(value);
}

try {
  assert.equal(
    (await api("/auth/me")).user.id,
    "browser-test-patient",
    "Only the fixture patient may be mutated.",
  );
  await api("/auth/profile", "PUT", {});
  await goNew();
  await expect(page.locator("html")).toHaveAttribute("lang", "en");
  await expect(page.locator(".workflow-card")).toHaveCount(30);
  assert(
    await page
      .locator(".custom-chat-card")
      .evaluate(
        (element) =>
          !!(
            element.compareDocumentPosition(
              document.querySelector(".workflow-grid"),
            ) & Node.DOCUMENT_POSITION_FOLLOWING
          ),
      ),
  );
  await expect(
    page.getByRole("heading", { name: "How are you feeling today?" }),
  ).toBeVisible();
  await screenshot("01-topic-selection-desktop.png");
  await noOverflow("Topic selection 1440px");
  await axe("Topic selection");
  pass("Custom chat is the first entry, followed by all 30 symptom workflows");

  const englishHeading = await page.locator(".wizard-hero h1").innerText();
  for (const locale of ["zh-CN", "zh-TW", "ko", "ja"]) {
    await page.locator(".language-switcher select").selectOption(locale);
    await expect(page.locator("html")).toHaveAttribute("lang", locale);
    await expect(page.locator(".wizard-hero h1"))
      .not.toHaveText(englishHeading, { timeout: 1500 })
      .catch(() => findings.push(`${locale}: topic hero remains English`));
    await expect(page.locator(".workflow-card")).toHaveCount(30);
  }
  await page.reload();
  await expect(page.locator("html")).toHaveAttribute("lang", "ja");
  await page.locator(".language-switcher select").selectOption("en");
  if (!findings.length)
    pass("All five locales render and the language choice survives reload");

  await page.getByRole("button", { name: "Add profile", exact: true }).click();
  const modal = page.getByRole("dialog");
  await modal.getByLabel("When were you born?").fill("1990-04-25");
  await modal.getByRole("button", { name: "Continue", exact: true }).click();
  await modal.getByRole("button", { name: "Female", exact: true }).click();
  await modal.getByRole("button", { name: "Continue", exact: true }).click();
  await modal.getByRole("button", { name: "O", exact: true }).click();
  await expect(
    modal.getByRole("group", { name: "Rh factor (optional)" }),
  ).toBeVisible();
  await modal.getByRole("button", { name: "Continue", exact: true }).click();
  for (const value of [
    "Childhood asthma, no current symptoms.",
    "Appendectomy in 2005.",
    "Father has diabetes.",
    "Please use large text.",
  ]) {
    await expect(modal.locator("textarea")).toHaveCount(1);
    await modal.locator("textarea").fill(value);
    await modal.getByRole("button", { name: "Continue", exact: true }).click();
  }
  await screenshot("02-profile-review-desktop.png");
  await modal
    .getByRole("button", { name: "Save profile", exact: true })
    .click();
  await expect(modal).toHaveCount(0);
  const profile = (await api("/auth/profile")).profile;
  assert.equal(profile.date_of_birth, "1990-04-25");
  assert.equal(
    profile.blood_group,
    "O",
    "Knowing only ABO must not infer an Rh factor.",
  );
  assert.equal(
    profile.medical_history,
    "Childhood asthma, no current symptoms.",
  );
  assert(profile.updated_at && profile.field_updated_at.medical_history);
  await page.reload();
  await expect(
    page.getByText("Your background is already here", { exact: true }),
  ).toBeVisible();
  pass("Seven-step profile saves structured background and survives reload");

  await page.locator(".custom-chat-card").focus();
  await page.keyboard.press("Enter");
  await expect(
    page.getByRole("heading", { name: "Tell us what’s on your mind." }),
  ).toBeFocused();
  await page.locator(".advanced-options summary").click();
  await expect(page.getByLabel("Assistant model")).toHaveValue("gpt-6-astra");
  await page.getByLabel("Assistant model").selectOption("gpt-6-sol");
  await page.getByLabel("Assistant model").selectOption("gpt-6-astra");
  await page.locator(".advanced-options summary").click();
  pass(
    "Keyboard opens custom chat and advanced options default to gpt-6-astra",
  );

  const responseInput = page.getByRole("textbox", {
    name: "Your response",
    exact: true,
  });
  await responseInput.fill("My own words.");
  await expect(
    page.getByRole("button", { name: "Record a voice response", exact: true }),
  ).toBeDisabled();
  await expect(
    page.getByRole("button", { name: "Start conversation", exact: true }),
  ).toBeDisabled();
  assert.equal(await page.evaluate(() => window.__audioTest.requested), 0);
  await page.locator(".wizard-consent input").check();
  pass(
    "Voice capture waits for processing consent; typed text remains editable",
  );
  await page
    .getByRole("button", { name: "Record a voice response", exact: true })
    .click();
  await expect(page.locator(".voice-composer")).toHaveAttribute(
    "data-phase",
    "recording",
  );
  await expect(
    page.getByRole("button", { name: "Transcribe recording", exact: true }),
  ).toHaveCount(0);
  await expect(
    page.getByRole("button", { name: "Send response", exact: true }),
  ).toHaveCount(0);
  await expect
    .poll(() =>
      page
        .locator(".voice-wave span")
        .evaluateAll(
          (elements) =>
            elements.filter((element) => parseFloat(element.style.height) > 3)
              .length,
        ),
    )
    .toBeGreaterThan(6);
  await expect(
    page.getByRole("button", { name: "Start conversation", exact: true }),
  ).toBeDisabled();
  await screenshot("03-recording-desktop.png");
  await page.setViewportSize({ width: 360, height: 800 });
  await page.locator(".voice-composer").scrollIntoViewIfNeeded();
  await noOverflow("Recording composer 360px");
  await screenshot("03b-recording-mobile.png");
  await page.setViewportSize({ width: 1440, height: 1100 });
  await page
    .getByRole("button", { name: "Cancel recording", exact: true })
    .click();
  await expect(responseInput).toHaveValue("My own words.");
  assert.equal(transcriptionRequests, 0);
  assert.equal(await page.evaluate(() => window.__audioTest.stopped), 1);
  pass(
    "Cancel recording releases the microphone and preserves typed text without upload",
  );

  await page
    .getByRole("button", { name: "Record a voice response", exact: true })
    .click();
  await page
    .getByRole("button", { name: "Stop recording", exact: true })
    .click();
  await expect(responseInput).toHaveValue(
    "My own words.\nA dull ache after walking for three weeks.",
  );
  await expect(page.locator(".voice-composer")).toHaveAttribute(
    "data-phase",
    "idle",
  );
  assert.equal(transcriptionRequests, 1);
  assert.equal(await page.evaluate(() => window.__audioTest.stopped), 2);
  assert.equal(createdCount, 0, "Transcription must not submit an intake.");
  await responseInput.fill(
    "Edited transcript: leg ache after long walks for three weeks.",
  );
  await expect(
    page.getByRole("button", { name: "Start conversation", exact: true }),
  ).toBeEnabled();
  await expect(
    page.getByRole("button", { name: "Use transcript", exact: true }),
  ).toHaveCount(0);
  await screenshot("04-transcript-filled-desktop.png");
  pass(
    "Stop automatically transcribes once, releases the microphone, and leaves editable text without submitting",
  );

  const requestsBeforeRetry = transcriptionRequests;
  const microphonesBeforeRetry = await page.evaluate(
    () => window.__audioTest.requested,
  );
  const stoppedBeforeRetry = await page.evaluate(
    () => window.__audioTest.stopped,
  );
  nextTranscription = {
    status: 503,
    json: { detail: "Synthetic transcription unavailable. Please retry." },
  };
  await page
    .getByRole("button", { name: "Record a voice response", exact: true })
    .click();
  await page
    .getByRole("button", { name: "Stop recording", exact: true })
    .click();
  await expect(page.locator(".voice-composer")).toHaveAttribute(
    "data-phase",
    "stopped",
  );
  await expect(
    page.getByText("Synthetic transcription unavailable. Please retry.", {
      exact: true,
    }),
  ).toBeVisible();
  assert.equal(transcriptionRequests, requestsBeforeRetry + 1);
  assert.equal(
    await page.evaluate(() => window.__audioTest.stopped),
    stoppedBeforeRetry + 1,
    "Failed automatic transcription must leave the microphone released.",
  );
  await page
    .getByRole("button", { name: "Retry transcription", exact: true })
    .click();
  await expect(responseInput).toHaveValue(
    "Edited transcript: leg ache after long walks for three weeks.\nA dull ache after walking for three weeks.",
  );
  assert.equal(transcriptionRequests, requestsBeforeRetry + 2);
  assert.equal(
    await page.evaluate(() => window.__audioTest.requested),
    microphonesBeforeRetry + 1,
    "Retry must reuse the captured audio without reopening the microphone.",
  );
  assert.equal(createdCount, 0, "Retry must not submit the patient's text.");
  await responseInput.fill(
    "Edited transcript: leg ache after long walks for three weeks.",
  );
  pass(
    "A failed automatic transcription can retry the same recording and preserves typed text",
  );

  let releaseTranscription;
  let finishTranscription;
  const transcriptionFinished = new Promise((resolve) => {
    finishTranscription = resolve;
  });
  nextTranscription = {
    wait: new Promise((resolve) => {
      releaseTranscription = resolve;
    }),
    finished: finishTranscription,
    json: { text: "This cancelled transcript must never appear." },
  };
  const requestsBeforeCancel = transcriptionRequests;
  const stoppedBeforeCancel = await page.evaluate(
    () => window.__audioTest.stopped,
  );
  await page
    .getByRole("button", { name: "Record a voice response", exact: true })
    .click();
  await page
    .getByRole("button", { name: "Stop recording", exact: true })
    .click();
  await expect(page.locator(".voice-composer")).toHaveAttribute(
    "data-phase",
    "transcribing",
  );
  await expect.poll(() => transcriptionRequests).toBe(requestsBeforeCancel + 1);
  assert.equal(
    await page.evaluate(() => window.__audioTest.stopped),
    stoppedBeforeCancel + 1,
    "The microphone must already be released while transcription is pending.",
  );
  await expect(
    page.getByRole("button", { name: "Start conversation", exact: true }),
  ).toBeDisabled();
  const abortedTranscription = page.waitForEvent("requestfailed", {
    predicate: (request) =>
      new URL(request.url()).pathname === "/api/v1/transcriptions",
  });
  await page
    .getByRole("button", { name: "Cancel recording", exact: true })
    .click();
  releaseTranscription();
  await Promise.all([abortedTranscription, transcriptionFinished]);
  await page.evaluate(
    () =>
      new Promise((resolve) =>
        requestAnimationFrame(() => requestAnimationFrame(resolve)),
      ),
  );
  await expect(page.locator(".voice-composer")).toHaveAttribute(
    "data-phase",
    "idle",
  );
  await expect(responseInput).toHaveValue(
    "Edited transcript: leg ache after long walks for three weeks.",
  );
  assert.equal(transcriptionRequests, requestsBeforeCancel + 1);
  assert.equal(
    createdCount,
    0,
    "Cancelling transcription must not submit an intake.",
  );
  pass(
    "Cancelling a pending transcription aborts it and ignores its late response",
  );

  await page.evaluate(() => {
    window.__audioTest.deny = true;
  });
  await page
    .getByRole("button", { name: "Record a voice response", exact: true })
    .click();
  await expect(
    page.getByText(
      "Microphone access was denied. Allow access in your browser or type your answer.",
      { exact: true },
    ),
  ).toBeVisible();
  await expect(responseInput).toHaveValue(
    "Edited transcript: leg ache after long walks for three weeks.",
  );
  await page.evaluate(() => {
    window.__audioTest.deny = false;
  });
  const stoppedBeforeFailure = await page.evaluate(
    () => window.__audioTest.stopped,
  );
  await page.evaluate(() => {
    window.__audioTest.failRecorder = true;
  });
  await page
    .getByRole("button", { name: "Record a voice response", exact: true })
    .click();
  await expect(
    page.getByText("Synthetic recorder initialization failure", {
      exact: true,
    }),
  ).toBeVisible();
  assert.equal(
    await page.evaluate(() => window.__audioTest.stopped),
    stoppedBeforeFailure + 1,
    "Recorder startup failure must release an already-acquired microphone stream.",
  );
  await page.evaluate(() => {
    window.__audioTest.failRecorder = false;
  });
  await page.locator(".wizard-consent input").check();
  const chatResponse = page.waitForResponse(
    (item) =>
      /\/intakes\/[^/]+\/messages$/.test(new URL(item.url()).pathname) &&
      item.request().method() === "POST",
  );
  await page
    .getByRole("button", { name: "Start conversation", exact: true })
    .click();
  const chatResult = await chatResponse;
  assert(chatResult.ok(), await chatResult.text());
  const chat = await chatResult.json();
  assert.equal(chat.mode, "chat");
  assert(
    chat.messages.some(
      (item) =>
        item.text ===
        "Edited transcript: leg ache after long walks for three weeks.",
    ),
  );
  await expect(page.locator(".wizard-question-card")).toHaveCount(0);
  await expect(page.locator(".conversation-workspace")).toBeVisible();
  await screenshot("04b-custom-conversation-desktop.png");
  pass(
    "Custom concern starts directly in chat; microphone denial leaves text input usable",
  );

  const intake = await createSelected("WF-01");
  assert.equal(intake.model, "gpt-6-astra");
  assert.equal(intake.profile_snapshot.date_of_birth, "1990-04-25");
  assert.equal(intake.shared_slots.relevant_history.status, "FILLED");
  assert.equal(intake.shared_slots.current_medications.status, "MISSING");
  assert.equal(intake.shared_slots.allergies.status, "MISSING");
  await expect(page.locator(".wizard-question-card")).toHaveCount(1);
  await expect(page.locator(".wizard-question-card textarea")).toHaveCount(1);
  await expect(page.locator(".profile-prefilled")).toBeVisible();
  const concern = intake.concerns[0];
  const firstHeading = await page.locator("#wizard-question").innerText();
  assert.equal(firstHeading, "Please briefly describe your leg discomfort.");
  const formFields = (await api(`/intakes/${intake.id}/form`)).groups.flatMap(
    (group) => group.fields,
  );
  const sequential = formFields
    .filter((field) => !field.review_only)
    .map((field) => field.key);
  assert(sequential.includes("additional_information"));
  assert(
    !sequential.some((key) =>
      ["relevant_history", "patient_worry", "clinician_questions"].includes(
        key,
      ),
    ),
  );
  pass(
    "The first symptom question is concrete and repeated background prompts merge into one optional step",
  );
  const requestsBeforeWizard = transcriptionRequests;
  const stoppedBeforeWizard = await page.evaluate(
    () => window.__audioTest.stopped,
  );
  const createdBeforeWizard = createdCount;
  const wizardInput = page.locator(".wizard-question-card textarea");
  const continueWizard = page
    .locator(".wizard-actions")
    .getByRole("button", { name: "Continue", exact: true });
  await wizardInput.fill("My typed description.");
  await savedValue(
    intake.id,
    "concern_description",
    "My typed description.",
    concern.id,
  );
  let releaseWizardTranscription;
  nextTranscription = {
    wait: new Promise((resolve) => {
      releaseWizardTranscription = resolve;
    }),
  };
  await page
    .getByRole("button", { name: "Record a voice response", exact: true })
    .click();
  await expect(continueWizard).toBeDisabled();
  await page
    .getByRole("button", { name: "Stop recording", exact: true })
    .click();
  await expect(page.locator(".voice-composer")).toHaveAttribute(
    "data-phase",
    "transcribing",
  );
  await expect(continueWizard).toBeDisabled();
  releaseWizardTranscription();
  const combinedWizardAnswer =
    "My typed description.\nA dull ache after walking for three weeks.";
  await expect(wizardInput).toHaveValue(combinedWizardAnswer);
  await expect(page.locator(".voice-composer")).toHaveAttribute(
    "data-phase",
    "idle",
  );
  await expect(continueWizard).toBeEnabled();
  await expect(
    page.getByRole("textbox", { name: "Reviewed transcript", exact: true }),
  ).toHaveCount(0);
  await expect(
    page.getByRole("button", { name: "Use transcript", exact: true }),
  ).toHaveCount(0);
  assert.equal(transcriptionRequests, requestsBeforeWizard + 1);
  assert.equal(
    await page.evaluate(() => window.__audioTest.stopped),
    stoppedBeforeWizard + 1,
  );
  assert.equal(createdCount, createdBeforeWizard);
  await expect(page.locator("#wizard-question")).toHaveText(firstHeading);
  await savedValue(
    intake.id,
    "concern_description",
    combinedWizardAnswer,
    concern.id,
  );
  nextTranscription = { json: { text: "It improves when I rest." } };
  await page
    .getByRole("button", { name: "Record a voice response", exact: true })
    .click();
  await page
    .getByRole("button", { name: "Stop recording", exact: true })
    .click();
  await expect(wizardInput).toHaveValue(
    `${combinedWizardAnswer}\nIt improves when I rest.`,
  );
  await savedValue(
    intake.id,
    "concern_description",
    `${combinedWizardAnswer}\nIt improves when I rest.`,
    concern.id,
  );
  assert.equal(transcriptionRequests, requestsBeforeWizard + 2);
  assert.equal(createdCount, createdBeforeWizard);
  await expect(page.locator("#wizard-question")).toHaveText(firstHeading);
  pass(
    "Wizard Stop fills and saves the editable answer without confirmation; repeated recording preserves prior text and does not advance or submit",
  );
  await page
    .locator(".wizard-question-card textarea")
    .fill("A dull ache in the left calf after long walks.");
  await savedValue(
    intake.id,
    "concern_description",
    "A dull ache in the left calf after long walks.",
    concern.id,
  );
  await page
    .locator(".wizard-actions")
    .getByRole("button", { name: "Continue", exact: true })
    .focus();
  await page.keyboard.press("Enter");
  await expect(page.locator("#wizard-question")).not.toHaveText(firstHeading);
  await expect(page.locator("#wizard-question")).toBeFocused();
  await screenshot("05-guided-question-desktop.png");
  await noOverflow("Wizard 1440px");
  await axe("Single-question wizard");
  pass(
    "Wizard presents one question at a time, autosaves, and moves keyboard focus",
  );

  await page
    .getByRole("button", { name: "Review saved details", exact: true })
    .click();
  await expect(page.locator(".wizard-question-card textarea")).toHaveValue(
    /Childhood asthma/,
  );
  await page
    .locator(".wizard-question-card textarea")
    .fill("Visit-only correction to the medical history.");
  await savedValue(
    intake.id,
    "relevant_history",
    "Visit-only correction to the medical history.",
  );
  assert.equal(
    (await api("/auth/profile")).profile.medical_history,
    "Childhood asthma, no current symptoms.",
  );
  await page.locator(".wizard-support summary").click();
  await page
    .locator(".wizard-jump")
    .filter({ hasText: "Medicines and supplements" })
    .click();
  await page
    .locator(".wizard-question-card textarea")
    .fill("Synthetic short course medicine, this visit only.");
  await savedValue(
    intake.id,
    "current_medications",
    "Synthetic short course medicine, this visit only.",
  );
  await page
    .locator(".wizard-jump")
    .filter({ hasText: "Allergies and reactions" })
    .click();
  await page
    .locator(".wizard-question-card textarea")
    .fill("Synthetic previous reaction to a medicine.");
  await savedValue(
    intake.id,
    "allergies",
    "Synthetic previous reaction to a medicine.",
  );
  pass(
    "Autofilled history remains editable without rewriting the persistent profile",
  );

  const nextIntake = await createSelected("WF-08");
  assert.equal(nextIntake.shared_slots.current_medications.status, "MISSING");
  assert.equal(nextIntake.shared_slots.allergies.status, "MISSING");
  assert(
    nextIntake.shared_slots.relevant_history.value.includes("Childhood asthma"),
  );
  assert(
    !nextIntake.shared_slots.relevant_history.value.includes(
      "Visit-only correction",
    ),
  );
  pass(
    "A second visit reuses stable profile history but never stale medicines or allergies",
  );

  await page.locator(".wizard-support summary").click();
  await page
    .locator(".wizard-jump")
    .filter({ hasText: "Medicines and supplements" })
    .click();
  await expect(page.locator(".previous-answer-value")).toHaveText(
    "Synthetic short course medicine, this visit only.",
  );
  await expect(page.locator(".wizard-question-card textarea")).toHaveValue("");
  assert.equal(
    (await api(`/intakes/${nextIntake.id}`)).shared_slots.current_medications
      .status,
    "MISSING",
  );
  await page
    .getByRole("button", {
      name: "Use this answer for this visit",
      exact: true,
    })
    .click();
  await savedValue(
    nextIntake.id,
    "current_medications",
    "Synthetic short course medicine, this visit only.",
  );
  await page
    .locator(".wizard-question-card textarea")
    .fill("Updated medicine list for this visit.");
  await savedValue(
    nextIntake.id,
    "current_medications",
    "Updated medicine list for this visit.",
  );
  await page
    .locator(".wizard-jump")
    .filter({ hasText: "Allergies and reactions" })
    .click();
  await expect(page.locator(".previous-answer-value")).toHaveText(
    "Synthetic previous reaction to a medicine.",
  );
  await expect(page.locator(".wizard-question-card textarea")).toHaveValue("");
  await screenshot("05b-previous-answer-desktop.png");
  await page
    .getByRole("button", {
      name: "Use this answer for this visit",
      exact: true,
    })
    .click();
  await savedValue(
    nextIntake.id,
    "allergies",
    "Synthetic previous reaction to a medicine.",
  );
  await page
    .locator(".wizard-jump")
    .filter({ hasText: "Anything else for your doctor" })
    .click();
  await expect(page.locator("#wizard-question")).toHaveText(
    "Anything else you would like your doctor to know?",
  );
  await expect(page.locator(".remembered-details")).toBeVisible();
  await page
    .locator(".wizard-jump")
    .filter({ hasText: "In your own words" })
    .first()
    .click();
  pass(
    "Dated medicine and allergy history only fills after an explicit click, remains editable, and merged context is optional",
  );

  const typed = "Patient-entered text stays in its original language.";
  await page.locator(".wizard-question-card textarea").fill(typed);
  await page.locator(".language-switcher select").selectOption("zh-CN");
  await expect(page.locator(".wizard-question-card textarea")).toHaveValue(
    typed,
  );
  await page.locator(".language-switcher select").selectOption("en");
  await savedValue(
    nextIntake.id,
    "concern_description",
    typed,
    nextIntake.concerns[0].id,
  );
  await page.setViewportSize({ width: 360, height: 800 });
  await noOverflow("Wizard 360px");
  await page.evaluate(() => window.scrollTo(0, 0));
  const mobileComposer = await page
    .locator(".wizard-question-card .voice-composer")
    .boundingBox();
  assert(
    mobileComposer.y + mobileComposer.height <= 800,
    "Voice composer is visible within the first mobile viewport.",
  );
  pass("The voice composer appears in the first 360px mobile viewport");
  await screenshot("06-wizard-mobile.png");
  await page
    .locator(".wizard-actions")
    .getByRole("button", { name: "Review answers", exact: true })
    .click();
  await expect(page.locator(".wizard-review")).toBeVisible();
  await noOverflow("Wizard review 360px");
  await screenshot("07-review-mobile.png");
  await page
    .getByRole("button", {
      name: "Continue to AI analysis & follow-up",
      exact: true,
    })
    .click();
  await expect(page.locator(".wizard-review")).toHaveCount(0);
  pass(
    "Language switching preserves authored text and mobile wizard reaches review",
  );

  await goNew();
  await noOverflow("Topic selection 360px");
  await screenshot("08-topics-mobile.png");
  await page.getByRole("button", { name: "Edit profile", exact: true }).click();
  await expect(
    page.getByRole("dialog").getByLabel("When were you born?"),
  ).toHaveValue("1990-04-25");
  await noOverflow("Profile wizard 360px");
  await screenshot("09-profile-mobile.png");
  await axe("Profile wizard mobile");
  await page.getByRole("button", { name: "Close dialog", exact: true }).click();

  let batchSubmissions = 0;
  page.on("request", (request) => {
    if (
      new URL(request.url()).pathname.endsWith("/followup/answers") &&
      request.method() === "POST"
    )
      batchSubmissions++;
  });
  await page.goto(`${base}/#/patient/intake/browser-followup-batch`);
  const batchCard = page.locator(".followup-question");
  const nextQuestion = () =>
    page.getByRole("button", { name: "Next question", exact: true });
  const previousQuestion = () =>
    page.getByRole("button", { name: "Previous question", exact: true });
  const reviewFollowup = () =>
    page.getByRole("button", { name: "Review answers", exact: true });
  const submitFollowup = () =>
    page.getByRole("button", {
      name: "Submit answers & continue",
      exact: true,
    });
  await expect(batchCard).toHaveCount(1);
  await expect(
    page.getByText("Question 1 of 3", { exact: true }),
  ).toBeVisible();
  await expect(nextQuestion()).toBeDisabled();
  await expect(submitFollowup()).toHaveCount(0);
  await expect(
    page.locator('.followup-option[aria-pressed="true"]'),
  ).toHaveCount(0);
  await expect(batchCard.locator(".followup-letter")).toHaveText([
    "A",
    "B",
    "C",
  ]);
  await batchCard.locator(".followup-option").first().click();
  await expect(batchCard.locator("textarea")).toHaveValue("Improving overall");
  await batchCard
    .locator("textarea")
    .fill("Improving on some days, but it varies.");
  await expect
    .poll(
      async () =>
        (await api("/intakes/browser-followup-batch")).followup_batch
          .draft_answers?.[0]?.value,
    )
    .toBe("Improving on some days, but it varies.");
  await page.reload();
  await expect(
    page.getByText("Question 2 of 3", { exact: true }),
  ).toBeVisible();
  await previousQuestion().click();
  await expect(batchCard.locator("textarea")).toHaveValue(
    "Improving on some days, but it varies.",
  );
  await nextQuestion().click();
  await expect(
    page.getByText("Question 2 of 3", { exact: true }),
  ).toBeVisible();
  let releaseFollowupTranscription;
  nextTranscription = {
    wait: new Promise((resolve) => {
      releaseFollowupTranscription = resolve;
    }),
    json: { text: "Mild most days." },
  };
  await batchCard
    .getByRole("button", { name: "Start voice input", exact: true })
    .click();
  await expect(nextQuestion()).toBeDisabled();
  await expect(previousQuestion()).toBeDisabled();
  await batchCard
    .getByRole("button", { name: "Stop recording", exact: true })
    .click();
  await expect(batchCard.locator(".voice-composer")).toHaveAttribute(
    "data-phase",
    "transcribing",
  );
  await expect(nextQuestion()).toBeDisabled();
  await expect(previousQuestion()).toBeDisabled();
  releaseFollowupTranscription();
  await expect(batchCard.locator("textarea")).toHaveValue("Mild most days.");
  await expect(nextQuestion()).toBeEnabled();
  await expect(previousQuestion()).toBeEnabled();
  await expect(
    batchCard.getByRole("button", { name: "Use transcript", exact: true }),
  ).toHaveCount(0);
  await expect
    .poll(
      async () =>
        (await api("/intakes/browser-followup-batch")).followup_batch
          .draft_answers?.[1]?.value,
    )
    .toBe("Mild most days.");
  assert.equal(batchSubmissions, 0, "Transcription only saves the answer draft.");
  await batchCard
    .getByRole("button", { name: "I don’t know", exact: true })
    .click();
  await nextQuestion().click();
  await expect(
    page.getByText("Question 3 of 3", { exact: true }),
  ).toBeVisible();
  await expect(batchCard.locator(".followup-option")).toHaveCount(0);
  await expect(reviewFollowup()).toBeDisabled();
  nextTranscription = {
    json: { text: "I need more breaks when I walk." },
  };
  await batchCard
    .getByRole("button", { name: "Start voice input", exact: true })
    .click();
  await expect(reviewFollowup()).toBeDisabled();
  await batchCard
    .getByRole("button", { name: "Stop recording", exact: true })
    .click();
  await expect(batchCard.locator("textarea")).toHaveValue(
    "I need more breaks when I walk.",
  );
  await expect(reviewFollowup()).toBeEnabled();
  await expect(
    batchCard.getByRole("button", { name: "Use transcript", exact: true }),
  ).toHaveCount(0);
  assert.equal(batchSubmissions, 0);
  await batchCard
    .locator("textarea")
    .fill("I take more breaks on longer walks.");
  pass(
    "Follow-up voice directly fills and saves each answer, unlocks Next/Review, and remains editable without confirmation or automatic submission",
  );
  await previousQuestion().click();
  await expect(
    batchCard.getByRole("button", { name: "I don’t know", exact: true }),
  ).toHaveAttribute("aria-pressed", "true");
  await nextQuestion().click();
  await expect(batchCard.locator("textarea")).toHaveValue(
    "I take more breaks on longer walks.",
  );
  await expect
    .poll(
      async () =>
        (
          await api("/intakes/browser-followup-batch")
        ).followup_batch.draft_answers?.filter(
          (answer) => answer.status !== "MISSING",
        ).length,
    )
    .toBe(3);
  const pendingBatch = await api("/intakes/browser-followup-batch");
  assert.equal(pendingBatch.followup_batch.status, "pending");
  assert.equal(
    pendingBatch.concerns[0].slots.symptom_course.status,
    "MISSING",
    "Drafts must not become submitted patient facts.",
  );
  assert.equal(
    batchSubmissions,
    0,
    "Question steps must never submit the batch.",
  );
  await reviewFollowup().click();
  await expect(page.locator(".followup-review")).toBeVisible();
  await expect(batchCard).toHaveCount(0);
  await expect(page.locator(".followup-review-answer")).toHaveCount(3);
  await page.reload();
  await expect(page.locator(".followup-review")).toBeVisible();
  await expect(page.locator(".followup-review")).toContainText(
    "Improving on some days, but it varies.",
  );
  await page.locator(".language-switcher select").selectOption("zh-CN");
  await expect(page.locator(".journey-navigation")).toContainText(
    "AI 分析与追问",
  );
  await expect(page.locator(".followup-review")).toContainText(
    "Improving on some days, but it varies.",
  );
  await page.locator(".language-switcher select").selectOption("en");
  await page
    .getByRole("button", { name: "Edit answer 1", exact: true })
    .click();
  await expect(batchCard).toHaveCount(1);
  await expect(batchCard.locator("textarea")).toHaveValue(
    "Improving on some days, but it varies.",
  );
  await noOverflow("Follow-up question wizard 360px");
  await screenshot("10-followup-mobile.png");
  await page.setViewportSize({ width: 1440, height: 1100 });
  await screenshot("11-followup-desktop.png");
  await axe("Follow-up question wizard");
  await reviewFollowup().click();
  await expect(page.locator(".followup-review-answer")).toHaveCount(3);
  await axe("Follow-up answer review");
  assert.equal(
    batchSubmissions,
    0,
    "Reviewing and editing answers must not submit them.",
  );
  await submitFollowup().click();
  await expect
    .poll(async () => (await api("/intakes/browser-followup-batch")).status)
    .toBe("review");
  const finishedBatch = await api("/intakes/browser-followup-batch");
  assert.equal(batchSubmissions, 1);
  assert.equal(finishedBatch.followup_batch.round, 1);
  assert.equal(finishedBatch.followup_batch.status, "answered");
  assert.equal(
    finishedBatch.concerns[0].slots.symptom_course.value,
    "Improving on some days, but it varies.",
  );
  pass(
    "Follow-up wizard shows one question per step, restores drafts, retains back/next answers, blocks voice navigation, reviews all answers and submits once directly to summary",
  );
  assert.deepEqual(pageErrors, [], "No uncaught browser errors.");
  assert.deepEqual(
    findings,
    [],
    "All requested languages translate the main entry experience.",
  );
  assert(
    accessibility.every((item) => item.violations.length === 0),
    `Accessibility failures: ${JSON.stringify(accessibility.filter((item) => item.violations.length))}`,
  );
  pass("No uncaught browser errors or serious accessibility findings");
  await writeFile(
    path.join(output, "report.json"),
    JSON.stringify(
      {
        passed: true,
        checks,
        screenshots,
        accessibility,
        transcriptionRequests,
        mode: "Synthetic DB; real UI/API; mocked microphone and transcription only",
      },
      null,
      2,
    ),
  );
  console.log(
    `Wizard acceptance passed: ${checks.length} checks; ${screenshots.length} screenshots.`,
  );
} catch (error) {
  await screenshot("failure.png").catch(() => {});
  await writeFile(
    path.join(output, "report.json"),
    JSON.stringify(
      {
        passed: false,
        checks,
        screenshots,
        accessibility,
        pageErrors,
        findings,
        error: error.stack,
      },
      null,
      2,
    ),
  );
  throw error;
} finally {
  await context.close();
  await browser.close();
}
