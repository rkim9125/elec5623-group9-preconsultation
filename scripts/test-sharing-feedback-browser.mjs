#!/usr/bin/env node
/**
 * Focused, synthetic UI regression for approval error feedback. Serves only the
 * built frontend; every API request is intercepted. No patient DB, live email,
 * authentication bypass in product code, or external provider is involved.
 * Run after building: node scripts/test-sharing-feedback-browser.mjs
 */
import assert from "node:assert/strict";
import { createServer } from "node:http";
import { access, mkdir, readFile, writeFile } from "node:fs/promises";
import { createRequire } from "node:module";
import { dirname, extname, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const root = resolve(dirname(fileURLToPath(import.meta.url)), "..");
const require = createRequire(resolve(root, "frontend/package.json"));
const { chromium } = require("playwright");
const { expect } = require("@playwright/test");
const output = resolve(root, ".local/sharing-feedback-browser");
await mkdir(output, { recursive: true });
const server = createServer(async (req, res) => {
  try {
    const pathname = new URL(req.url, "http://127.0.0.1").pathname;
    if (pathname.startsWith("/api/")) {
      res.writeHead(500, { "Content-Type": "application/json" });
      res.end(JSON.stringify({ detail: "Unexpected unmocked API request" }));
      return;
    }
    const file = pathname.startsWith("/assets/") ? pathname : "/index.html";
    const data = await readFile(resolve(root, "frontend/dist", `.${file}`));
    res.setHeader("Content-Type", {
      ".html": "text/html", ".js": "text/javascript", ".css": "text/css",
    }[extname(file)] || "application/octet-stream");
    res.end(data);
  } catch {
    res.statusCode = 404;
    res.end();
  }
});
await new Promise((done) => server.listen(0, "127.0.0.1", done));
const base = `http://127.0.0.1:${server.address().port}`;
let executablePath = process.env.PLAYWRIGHT_CHROMIUM_EXECUTABLE;
if (!executablePath) {
  const systemChrome = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome";
  try { await access(systemChrome); executablePath = systemChrome; } catch { /* bundled browser */ }
}
const browser = await chromium.launch({ headless: true, ...(executablePath ? { executablePath } : {}) });
const checks = [];
const errors = [];
let failure;
function passed(name) { checks.push(name); console.log(`PASS ${name}`); }

try {
  for (const viewport of [{ width: 1440, height: 900 }, { width: 390, height: 844 }]) {
    const label = viewport.width === 390 ? "Mobile" : "Desktop";
    const context = await browser.newContext({ viewport, reducedMotion: "reduce" });
    try {
      await context.addInitScript(() => localStorage.setItem("preconsultation.locale", "zh-CN"));
      const page = await context.newPage();
      page.on("pageerror", (error) => errors.push(error.message));
      page.setDefaultTimeout(15000);
      let session = {
        id: "synthetic-sharing-feedback", title: "Synthetic sharing feedback check",
        patient_id: "synthetic-sharing-patient", patient_name: "Synthetic patient",
        patient_email: "patient@example.test", locale: "zh-CN", mode: "wizard",
        status: "review", stage: "review", revision: 1, consent: true,
        created_at: "2026-10-21T00:00:00Z", baseline: { completed: true },
        concerns: [], shared_slots: {}, messages: [], attachments: [],
        summary: {
          version: 1, gaps: [],
          text: Array.from({ length: 24 }, (_, index) => `Synthetic recorded detail ${index + 1}.`).join("\n\n"),
          synthesis: { status: "unavailable" },
        },
      };
      const original = structuredClone(session);
      let approvalCount = 0;
      let responseKind = "no-doctors";
      const submitted = [];
      const unexpected = [];
      await context.route("**/api/v1/**", async (route) => {
        const pathname = new URL(route.request().url()).pathname.replace("/api/v1", "");
        let json;
        if (pathname === "/config") {
          // Remains false for the entire scenario to prove a clinician who
          // registers after page load can still be checked by the server.
          json = { ai_configured: false, mail_configured: false, doctor_configured: false,
            care_team: [], models: [], default_model: "gpt-6-astra" };
        } else if (pathname === "/auth/me") {
          json = { user: { id: session.patient_id, role: "patient", name: session.patient_name, email: session.patient_email } };
        } else if (pathname === "/workflows") json = [];
        else if (pathname === "/intakes") json = [session];
        else if (pathname === `/intakes/${session.id}`) json = session;
        else if (pathname === `/intakes/${session.id}/approve`) {
          assert.equal(route.request().method(), "POST");
          approvalCount++;
          submitted.push(route.request().postDataJSON());
          if (responseKind !== "success") {
            await route.fulfill({ status: 422, json: { detail: responseKind === "no-doctors"
              ? "No clinician has registered yet. A clinician can register with any separate email address."
              : "Select a registered clinician to receive this summary." } });
            return;
          }
          session = { ...session, status: "approved", revision: 2,
            doctor_email: submitted.at(-1).doctor_email, shared_at: "2026-10-21T00:15:00Z",
            summary: { ...session.summary, approved_version: 1, approved_at: "2026-10-21T00:15:00Z" } };
          json = session;
        } else {
          unexpected.push(pathname);
          await route.fulfill({ status: 404, json: { detail: "Unexpected synthetic route" } });
          return;
        }
        await route.fulfill({ json: structuredClone(json) });
      });
      await page.goto(`${base}/#/patient/intake/${session.id}`);
      const card = page.locator(".approval-card").filter({ has: page.locator("#doctor-email") });
      const email = card.locator("#doctor-email");
      const submit = card.getByRole("button", { name: "批准并分享", exact: true });
      await email.fill("not-registered@example.test");
      await card.getByRole("checkbox").check();
      await expect(submit).toBeEnabled();
      await submit.scrollIntoViewIfNeeded();
      await submit.click();
      const error = card.locator("#approval-error");
      await expect(error).toBeVisible();
      await expect(error).toBeFocused();
      await expect(error).toContainText(/医生/);
      await expect(error).not.toContainText("No clinician");
      assert(await error.evaluate((element) => {
        const rect = element.getBoundingClientRect();
        return rect.top >= 0 && rect.bottom <= innerHeight;
      }), "Approval error must be scrolled into the visible viewport.");
      assert.equal(approvalCount, 1);
      assert.deepEqual(session, original, "Failed sharing must preserve the entire draft.");
      assert.equal(await page.locator('[role="alert"]').count(), 1, "Approval failure belongs beside the action without a duplicate distant alert.");
      await page.screenshot({ path: resolve(output, `${label.toLowerCase()}-inline-error.png`), animations: "disabled" });
      passed(`${label}: no-doctor 422 appears in Chinese beside the button, focused and visible; one request and unchanged draft`);

      await email.fill("still-not-registered@example.test");
      await expect(error).toHaveCount(0);
      responseKind = "unknown-doctor";
      await submit.click();
      await expect(error).toBeFocused();
      await expect(error).toContainText(/尚未注册.*医生账号/);
      await expect(error).not.toContainText("Select a registered");
      assert.equal(approvalCount, 2);
      assert.deepEqual(session, original);
      passed(`${label}: editing the email clears the error; another rejection is localised and leaves the draft unchanged`);

      await email.fill("doctor@example.test");
      await expect(error).toHaveCount(0);
      responseKind = "success";
      await submit.click();
      await expect(page.locator(".shared-banner")).toBeVisible();
      await expect(page.locator(".shared-banner")).toContainText("doctor@example.test");
      assert.equal(approvalCount, 3, "Each click must issue exactly one approval request.");
      assert.deepEqual(submitted.at(-1), { version: 1, doctor_email: "doctor@example.test" });
      assert.equal(session.status, "approved");
      assert.equal(session.summary.text, original.summary.text);
      assert.deepEqual(unexpected, []);
      passed(`${label}: retry succeeds after registration even with stale no-doctors config; exactly one request per click`);
    } finally {
      await context.close();
    }
  }
  assert.deepEqual(errors, [], "No browser runtime errors.");
} catch (error) {
  failure = error;
} finally {
  await writeFile(resolve(output, "report.json"), JSON.stringify({ checks, errors,
    failure: failure ? String(failure.stack || failure) : null }, null, 2));
  await browser.close();
  await new Promise((done) => server.close(done));
}
if (failure) throw failure;
console.log(`Completed ${checks.length} focused sharing feedback checks.`);
