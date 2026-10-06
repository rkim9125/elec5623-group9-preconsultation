#!/usr/bin/env node
/**
 * Focused portal/session regressions against the isolated synthetic fixture.
 * Start product-browser-server.py after building the frontend, then run this.
 * Real-cookie scenarios use actual APIs. Explicitly labelled UI simulations
 * intercept OTP/config responses and never send email or call an AI provider.
 * The final logout revokes the fixture patient token: restart the fixture before
 * running another acceptance suite that uses that token.
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
const target = new URL(base);
assert(
  ["127.0.0.1", "localhost"].includes(target.hostname) && target.port === "8001",
  "Only the isolated loopback fixture at port 8001 may be used.",
);
const output = path.join(root, ".local/portal-tests");
await mkdir(output, { recursive: true, mode: 0o700 });
const tokens = JSON.parse(
  await readFile(path.join(root, ".local/browser-test/sessions.json"), "utf8"),
);
assert(tokens.patient && tokens.doctor, "Start the isolated fixture first.");
const configResponse = await fetch(`${base}/api/v1/config`);
assert.equal(configResponse.status, 200);
const fixtureConfig = await configResponse.json();
assert.equal(fixtureConfig.ai_configured, false, "Live AI must be disabled.");
assert.equal(fixtureConfig.mail_configured, false, "Live mail must be disabled.");

let executablePath = process.env.PLAYWRIGHT_CHROMIUM_EXECUTABLE;
if (!executablePath) {
  const systemChrome = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome";
  try { await access(systemChrome); executablePath = systemChrome; } catch { /* bundled browser */ }
}
const browser = await chromium.launch({ headless: true, ...(executablePath ? { executablePath } : {}) });
const contexts = [];
const checks = [];
const screenshots = [];
const errors = [];
const accessibility = [];
const emailFor = (role) => `${role}@example.test`;
const otherRole = (role) => role === "patient" ? "doctor" : "patient";
const cookie = (role) => ({
  name: "preconsult_session", value: tokens[role], url: base,
  httpOnly: true, secure: false, sameSite: "Lax",
});
function passed(name, kind = "real-api") {
  checks.push({ name, kind });
  console.log(`PASS [${kind}] ${name}`);
}
async function makePage(role, viewport = { width: 1440, height: 1024 }) {
  const context = await browser.newContext({ viewport, reducedMotion: "reduce", locale: "en-AU" });
  contexts.push(context);
  if (role) await context.addCookies([cookie(role)]);
  const page = await context.newPage();
  page.setDefaultTimeout(15000);
  page.on("pageerror", (error) => errors.push(error.message));
  const intakeRequests = [];
  page.on("request", (request) => {
    if (/^\/api\/v1\/(?:clinician\/)?intakes(?:\/|$)/.test(new URL(request.url()).pathname)) {
      intakeRequests.push({ method: request.method(), pathname: new URL(request.url()).pathname });
    }
  });
  return { context, page, intakeRequests };
}
async function mismatch(page, desired, current) {
  await expect(page.getByRole("heading", { name: `Switch to the ${desired} portal?`, exact: true })).toBeVisible();
  await expect(page.getByText(emailFor(current), { exact: true })).toBeVisible();
  await expect(page.getByRole("button", { name: `Sign out and continue to ${desired} sign-in`, exact: true })).toBeVisible();
  await expect(page.getByRole("link", { name: `Return to ${current} portal`, exact: true })).toBeVisible();
  await expect(page.locator(".app-shell")).toHaveCount(0);
  await expect(page.locator(".review-document, .session-list, .baseline-form")).toHaveCount(0);
}
async function currentIdentity(context, role) {
  const response = await context.request.get(`${base}/api/v1/auth/me`);
  assert.equal(response.status(), 200);
  const body = await response.json();
  assert.equal(body.user.role, role);
  assert.equal(body.user.email, emailFor(role));
}
async function capture(page, name) {
  await page.screenshot({ path: path.join(output, name), fullPage: true, animations: "disabled" });
  screenshots.push(name);
}
async function checkA11y(page, label) {
  const result = await new AxeBuilder({ page }).withTags(["wcag2a", "wcag2aa", "wcag21aa"]).analyze();
  const violations = result.violations
    .filter((item) => ["serious", "critical"].includes(item.impact))
    .map((item) => ({ id: item.id, impact: item.impact, nodes: item.nodes.map((node) => node.target) }));
  accessibility.push({ label, violations });
  assert.deepEqual(violations, [], `${label}: accessibility violations`);
  assert(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth + 1), `${label}: horizontal overflow`);
  passed(`${label}: no serious/critical axe violations or horizontal overflow`);
}
async function mockPublicConfig(context, changes = {}) {
  await context.route("**/api/v1/config", (route) => route.fulfill({
    json: { ...fixtureConfig, auth_configured: true, mail_configured: true, care_team: [], ...changes },
  }));
}
function deferred() {
  let resolve;
  const promise = new Promise((done) => { resolve = done; });
  return { promise, resolve };
}

let failure = null;
try {
  for (const current of ["patient", "doctor"]) {
    const desired = otherRole(current);
    const run = await makePage(current);
    for (const suffix of [`/${desired}`, `/#/${desired}`, `/#/${desired}/intake/arbitrary-target`]) {
      run.intakeRequests.length = 0;
      const requested = `${base}${suffix}`;
      await run.page.goto(requested);
      await mismatch(run.page, desired, current);
      assert.equal(run.page.url(), requested, "The requested portal URL must be preserved.");
      assert.deepEqual(run.intakeRequests, [], "Mismatch must not fetch intake lists or records.");
      await currentIdentity(run.context, current);
      passed(`${current} session on ${suffix}: explicit switch screen, unchanged identity and URL, no intake fetch`);
    }
    if (current === "patient") {
      await capture(run.page, "01-doctor-portal-switch-desktop.png");
      await checkA11y(run.page, "Doctor portal switch desktop");
    } else {
      await run.page.setViewportSize({ width: 390, height: 844 });
      await capture(run.page, "02-patient-portal-switch-mobile.png");
      await checkA11y(run.page, "Patient portal switch mobile");
    }
    await run.page.getByRole("link", { name: `Return to ${current} portal`, exact: true }).click();
    await expect(run.page.locator(".app-shell")).toBeVisible();
    await expect(run.page).toHaveURL(new RegExp(`#/${current}$`));
    await currentIdentity(run.context, current);
    passed(`${current} portal return keeps the existing session`);
    if (current === "doctor") {
      await run.page.getByRole("button", { name: "Open navigation", exact: true }).click();
      await expect(run.page.getByRole("link", { name: "PreConsult home" })).toHaveAttribute("href", "#/doctor");
      await run.page.getByRole("link", { name: "PreConsult home" }).click();
      await expect(run.page.locator(".app-shell")).toBeVisible();
      await expect(run.page).toHaveURL(/#\/doctor$/);
      passed("Doctor brand link stays in the doctor portal");
    }
  }

  const swapped = await makePage("patient");
  await swapped.page.goto(`${base}/#/patient`);
  await expect(swapped.page.locator(".app-shell")).toBeVisible();
  await swapped.context.addCookies([cookie("doctor")]);
  await swapped.page.evaluate(() => window.dispatchEvent(new Event("focus")));
  await mismatch(swapped.page, "patient", "doctor");
  await expect(swapped.page).toHaveURL(/#\/patient$/);
  await currentIdentity(swapped.context, "doctor");
  passed("Focus reconciles a cookie role change and removes the old workspace");
  await swapped.page.getByRole("link", { name: "Return to doctor portal", exact: true }).click();
  await expect(swapped.page.locator(".app-shell")).toBeVisible();
  await swapped.context.addCookies([cookie("patient")]);
  await swapped.page.evaluate(() => document.dispatchEvent(new Event("visibilitychange")));
  await mismatch(swapped.page, "doctor", "patient");
  await expect(swapped.page).toHaveURL(/#\/doctor$/);
  passed("Visibility reconciliation also preserves the requested portal");

  const unavailable = await makePage();
  await mockPublicConfig(unavailable.context, { doctor_configured: false });
  await unavailable.page.goto(`${base}/#/doctor`);
  await expect(unavailable.page.getByText(/Doctor access is not set up yet\./)).toBeVisible();
  await expect(unavailable.page.getByRole("button", { name: "Continue with email", exact: true })).toBeDisabled();
  passed("An unconfigured doctor allowlist is explained before attempting sign-in", "ui-simulation");

  const unavailableSharing = await makePage("patient");
  await mockPublicConfig(unavailableSharing.context, { doctor_configured: false });
  const createdResponse = await unavailableSharing.context.request.post(`${base}/api/v1/intakes`, {
    headers: { Origin: base },
    data: { consent: true, workflow_ids: ["WF-01"], title: "Synthetic portal configuration check" },
  });
  assert.equal(createdResponse.status(), 201);
  const draft = await createdResponse.json();
  const reviewedResponse = await unavailableSharing.context.request.post(`${base}/api/v1/intakes/${draft.id}/review`, { headers: { Origin: base } });
  assert.equal(reviewedResponse.status(), 200);
  await unavailableSharing.page.goto(`${base}/#/patient/intake/${draft.id}`);
  await expect(unavailableSharing.page.getByText(/Sharing is not available yet\./)).toBeVisible();
  await unavailableSharing.page.getByLabel("Doctor’s email address", { exact: true }).fill("doctor@example.test");
  await unavailableSharing.page.getByRole("checkbox", { name: /I have reviewed this summary/ }).check();
  await expect(unavailableSharing.page.getByRole("button", { name: "Approve & share", exact: true })).toBeDisabled();
  passed("An unconfigured allowlist disables sharing even after email and consent are entered", "ui-simulation");

  // Delayed provider replies are UI simulations, not authentication bypasses.
  const delayedSend = await makePage();
  await mockPublicConfig(delayedSend.context);
  const sendStarted = deferred();
  const sendRelease = deferred();
  const sendFinished = deferred();
  await delayedSend.context.route("**/api/v1/auth/request-code", async (route) => {
    sendStarted.resolve();
    await sendRelease.promise;
    await route.fulfill({ json: { message: "Synthetic code reply for a stale request." } });
    sendFinished.resolve();
  });
  await delayedSend.page.goto(`${base}/#/patient`);
  await delayedSend.page.getByLabel("Email address", { exact: true }).fill("synthetic@example.test");
  await delayedSend.page.getByRole("button", { name: "Continue with email", exact: true }).click();
  await sendStarted.promise;
  await delayedSend.page.getByRole("link", { name: "Doctor portal", exact: true }).click();
  await expect(delayedSend.page.getByRole("heading", { name: "Welcome, doctor.", exact: true })).toBeVisible();
  sendRelease.resolve();
  await sendFinished.promise;
  await delayedSend.page.evaluate(() => new Promise((resolve) => requestAnimationFrame(() => requestAnimationFrame(resolve))));
  await expect(delayedSend.page.getByLabel("Email address", { exact: true })).toBeVisible();
  await expect(delayedSend.page.getByLabel("Verification code", { exact: true })).toHaveCount(0);
  await expect(delayedSend.page).toHaveURL(/#\/doctor$/);
  passed("A delayed OTP send for the previous portal cannot advance the new login", "ui-simulation");

  const delayedVerify = await makePage();
  await mockPublicConfig(delayedVerify.context);
  await delayedVerify.context.route("**/api/v1/auth/request-code", (route) => route.fulfill({ json: { message: "Synthetic code reply." } }));
  const verifyStarted = deferred();
  const verifyRelease = deferred();
  const verifyFinished = deferred();
  await delayedVerify.context.route("**/api/v1/auth/verify", async (route) => {
    verifyStarted.resolve();
    await verifyRelease.promise;
    await route.fulfill({ json: { user: { id: "synthetic-stale-login", role: "patient", email: "synthetic@example.test", name: "Synthetic" } } });
    verifyFinished.resolve();
  });
  await delayedVerify.page.goto(`${base}/#/patient`);
  await delayedVerify.page.getByLabel("Email address", { exact: true }).fill("synthetic@example.test");
  await delayedVerify.page.getByRole("button", { name: "Continue with email", exact: true }).click();
  await delayedVerify.page.getByLabel("Verification code", { exact: true }).fill("123456");
  await delayedVerify.page.getByRole("button", { name: "Verify & continue", exact: true }).click();
  await verifyStarted.promise;
  await delayedVerify.page.getByRole("link", { name: "Doctor portal", exact: true }).click();
  await expect(delayedVerify.page.getByRole("heading", { name: "Welcome, doctor.", exact: true })).toBeVisible();
  verifyRelease.resolve();
  await verifyFinished.promise;
  await delayedVerify.page.evaluate(() => new Promise((resolve) => requestAnimationFrame(() => requestAnimationFrame(resolve))));
  await expect(delayedVerify.page.getByRole("heading", { name: "Welcome, doctor.", exact: true })).toBeVisible();
  await expect(delayedVerify.page.locator(".app-shell")).toHaveCount(0);
  await expect(delayedVerify.page).toHaveURL(/#\/doctor$/);
  assert.deepEqual(delayedVerify.intakeRequests, []);
  passed("A delayed OTP verification cannot adopt an identity from the previous portal", "ui-simulation");

  // LAST: actual logout invalidates the shared synthetic patient fixture token.
  const logout = await makePage("patient");
  const requested = `${base}/#/doctor/intake/arbitrary-target`;
  await logout.page.goto(requested);
  await mismatch(logout.page, "doctor", "patient");
  const loggedOut = logout.page.waitForResponse((response) => new URL(response.url()).pathname === "/api/v1/auth/logout" && response.request().method() === "POST");
  await logout.page.getByRole("button", { name: "Sign out and continue to doctor sign-in", exact: true }).click();
  assert.equal((await loggedOut).status(), 204);
  await expect(logout.page.getByRole("heading", { name: "Welcome, doctor.", exact: true })).toBeVisible();
  await expect(logout.page.getByLabel("Email address", { exact: true })).toBeVisible();
  assert.equal(logout.page.url(), requested);
  assert.equal((await logout.context.request.get(`${base}/api/v1/auth/me`)).status(), 401);
  await logout.context.addCookies([cookie("patient")]);
  assert.equal((await logout.context.request.get(`${base}/api/v1/auth/me`)).status(), 401, "The old server session must be revoked.");
  passed("Explicit switching logs out on the server and keeps the full doctor URL for sign-in");
  passed("The previous patient session token is revoked, not just hidden in the UI");
  await capture(logout.page, "03-doctor-sign-in-after-switch.png");

  assert.deepEqual(errors, [], "Unexpected browser JavaScript errors.");
  passed("No browser JavaScript errors");
} catch (error) {
  failure = { message: error.message, stack: error.stack };
  console.error(error);
} finally {
  await writeFile(path.join(output, "report.json"), JSON.stringify({
    passed: failure === null, checks, screenshots, accessibility, pageErrors: errors, failure,
    generatedAt: new Date().toISOString(),
    scope: "Synthetic fixture only; delayed OTP checks are explicitly mocked UI race simulations. No live providers.",
  }, null, 2), { mode: 0o600 });
  await Promise.allSettled(contexts.map((context) => context.close()));
  await browser.close();
}
if (failure) process.exitCode = 1;
