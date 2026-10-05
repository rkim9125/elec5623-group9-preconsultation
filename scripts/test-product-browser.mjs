#!/usr/bin/env node
/**
 * Real-browser acceptance test against the isolated synthetic fixture server.
 * Start: .venv/bin/python scripts/product-browser-server.py
 * Run:   node scripts/test-product-browser.mjs
 * No frontend route mocks, delivery bypasses in production code, or live providers.
 */
import assert from 'node:assert/strict';
import { createRequire } from 'node:module';
import { readFile, mkdir, writeFile, access, unlink } from 'node:fs/promises';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const require = createRequire(path.join(root, 'frontend/package.json'));
const { chromium } = require('playwright');
const { expect } = require('@playwright/test');
const AxeBuilder = require('@axe-core/playwright').default;
const base = process.env.PRECONSULT_TEST_URL || 'http://127.0.0.1:8001';
const target = new URL(base);
assert(['127.0.0.1', 'localhost'].includes(target.hostname) && target.port === '8001',
  'This test only operates on the isolated loopback fixture at port 8001.');
const output = path.join(root, 'docs/screenshots/v3');
await mkdir(output, { recursive: true });
const tokens = JSON.parse(await readFile(path.join(root, '.local/browser-test/sessions.json'), 'utf8'));
assert(tokens.patient && tokens.doctor, 'Start product-browser-server.py to seed synthetic sessions.');
const configResponse = await fetch(`${base}/api/v1/config`);
assert.equal(configResponse.status, 200, 'The isolated server must be running with a built frontend.');
const config = await configResponse.json();
assert.equal(config.ai_configured, false, 'Fixture must disable external AI providers.');
assert.equal(config.mail_configured, false, 'Fixture must disable external email delivery.');
const systemChrome = '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome';
let executablePath = process.env.PLAYWRIGHT_CHROMIUM_EXECUTABLE;
if (!executablePath) {
  try { await access(systemChrome); executablePath = systemChrome; } catch { /* Playwright browser fallback. */ }
}
const browser = await chromium.launch({ headless: true, ...(executablePath ? { executablePath } : {}) });
const checks = [];
const screenshots = [];
const pageErrors = [];
const accessibility = [];
const contexts = [];
let patientPage;
let doctorPage;
let intakeId;

function passed(name) { checks.push(name); console.log(`PASS ${name}`); }
async function identity(role, viewport = { width: 1440, height: 1024 }) {
  const context = await browser.newContext({ viewport, reducedMotion: 'reduce', locale: 'en-AU' });
  contexts.push(context);
  await context.addCookies([{ name: 'preconsult_session', value: tokens[role], url: base,
    httpOnly: true, secure: false, sameSite: 'Lax' }]);
  const page = await context.newPage();
  page.setDefaultTimeout(20000);
  page.on('pageerror', error => pageErrors.push(`${role}: ${error.message}`));
  return { context, page };
}
async function screenshot(page, name, fullPage = false) {
  await page.evaluate(() => window.scrollTo(0, 0));
  await page.screenshot({ path: path.join(output, name), fullPage, animations: 'disabled' });
  screenshots.push(name);
}
async function noOverflow(page, label) {
  // Let React finish a hash navigation and the browser settle a resized layout.
  await expect.poll(() => page.evaluate(() => document.documentElement.scrollWidth <= innerWidth + 1), { timeout: 3000 }).toBe(true).catch(() => {});
  const size = await page.evaluate(() => ({ viewport: innerWidth, document: document.documentElement.scrollWidth,
    offenders: [...document.querySelectorAll('main *')].filter(element => {
      const rect = element.getBoundingClientRect();
      return rect.width && rect.right > innerWidth + 2;
    }).slice(0, 8).map(element => ({ tag: element.tagName, class: element.className })) }));
  assert(size.document <= size.viewport + 1, `${label} has horizontal overflow: ${JSON.stringify(size)}`);
  passed(`${label}: no horizontal overflow`);
}
async function accessibilityCheck(page, label) {
  const result = await new AxeBuilder({ page }).withTags(['wcag2a', 'wcag2aa', 'wcag21aa']).analyze();
  const violations = result.violations.filter(item => ['serious', 'critical'].includes(item.impact)).map(item => ({
    id: item.id, impact: item.impact, description: item.help,
    nodes: item.nodes.map(node => ({ target: node.target, explanation: node.failureSummary }))
  }));
  accessibility.push({ page: label, violations });
  if (!violations.length) passed(`${label}: no serious or critical axe violations`);
  else console.log(`FAIL ${label}: ${violations.map(item => `${item.id} (${item.nodes.length} nodes)`).join(', ')}`);
}
async function responseFor(page, suffix, method, action) {
  const response = page.waitForResponse(value => new URL(value.url()).pathname === `/api/v1${suffix}` && value.request().method() === method);
  await action();
  const result = await response;
  assert(result.ok(), `${method} ${suffix}: ${result.status()} ${await result.text()}`);
  return result.status() === 204 ? null : result.json();
}
async function api(context, suffix, expected = 200) {
  const response = await context.request.get(`${base}/api/v1${suffix}`);
  assert.equal(response.status(), expected, `GET ${suffix}: ${await response.text()}`);
  return expected === 200 ? response.json() : null;
}
async function fillAnswer(page, testId, value) {
  const input = page.getByTestId(testId);
  if (!(await input.isVisible())) {
    const row = page.locator('.baseline-field').filter({ has: page.getByTestId(testId.replace(/^baseline-/, 'baseline-status-')) });
    await row.getByRole('button', { name: 'Add details or another answer', exact: true }).click();
  }
  await input.fill(value);
}

try {
  const patient = await identity('patient');
  const doctor = await identity('doctor');
  patientPage = patient.page;
  doctorPage = doctor.page;
  await patientPage.goto(`${base}/patient#/patient`);
  await expect(patientPage.getByRole('heading', { name: 'Welcome, Alex.' })).toBeVisible();
  await expect(patientPage.getByRole('heading', { name: 'Recent consultations' })).toBeVisible();
  await noOverflow(patientPage, 'Patient dashboard desktop');
  await screenshot(patientPage, '01-patient-dashboard-desktop.png', true);
  await accessibilityCheck(patientPage, 'Patient dashboard desktop');
  passed('Real patient cookie opens authenticated dashboard');

  await patientPage.getByRole('button', { name: 'Prepare a consultation' }).first().click();
  await expect(patientPage.getByRole('heading', { name: 'What brings you here?' })).toBeVisible();
  await expect(patientPage.locator('.workflow-card')).toHaveCount(30);
  await patientPage.locator('.workflow-card').filter({ has: patientPage.locator('strong', { hasText: /^Leg pain$/ }) }).click();
  await patientPage.locator('.workflow-card').filter({ has: patientPage.locator('strong', { hasText: /^Sleep difficulties$/ }) }).click();
  await patientPage.getByLabel('Your own concern', { exact: true }).fill('Work certificate');
  await patientPage.getByRole('button', { name: 'Add concern', exact: true }).click();
  await patientPage.getByLabel('Consultation title').fill('Routine GP visit · browser acceptance');
  await expect(patientPage.getByRole('button', { name: 'Continue to health information' })).toBeDisabled();
  await patientPage.getByRole('checkbox', { name: /I consent to AI processing/ }).check();
  await noOverflow(patientPage, 'Workflow selection desktop');
  await screenshot(patientPage, '02-workflow-selection-desktop.png');
  await accessibilityCheck(patientPage, 'Workflow selection desktop');
  const created = await responseFor(patientPage, '/intakes', 'POST', () => patientPage.getByRole('button', { name: 'Continue to health information' }).click());
  intakeId = created.id;
  assert.deepEqual(created.concerns.map(concern => concern.workflow_id).sort(), ['GENERAL', 'WF-01', 'WF-08']);
  assert.equal(created.consent, true);
  await expect(patientPage.getByRole('heading', { name: 'The essentials, all in one place.' })).toBeVisible();
  assert.equal(created.stage, 'baseline');
  assert.equal(created.current_question, null);
  passed('30 workflows render; multiple concerns start in a form rather than a chat');

  const form = await api(patient.context, `/intakes/${intakeId}/form`);
  assert.equal(form.groups.filter(group => group.id === 'shared').length, 1);
  await fillAnswer(patientPage, 'baseline-session-appointment_goal', 'I want to organise my leg and sleep concerns before my planned appointment.');
  await patientPage.getByTestId('baseline-session-current_medications').fill('Vitamin D 1000 IU daily.');
  await patientPage.getByTestId('baseline-status-session-allergies').selectOption('UNCERTAIN');
  await patientPage.getByTestId('baseline-status-session-relevant_history').selectOption('SKIPPED');
  for (const concern of created.concerns) {
    const group = patientPage.locator('.baseline-group-toggle').filter({ hasText: concern.title });
    if (await group.getAttribute('aria-expanded') !== 'true') await group.click();
    await patientPage.getByTestId(`baseline-${concern.id}-concern_description`).fill(concern.workflow_id === 'WF-01'
      ? 'A dull ache in my left calf after long walks for three weeks.'
      : concern.workflow_id === 'WF-08' ? 'I have difficulty falling asleep before early work meetings.'
      : 'I want to ask about a work certificate and employer paperwork.');
  }
  await expect(patientPage.getByText('All changes saved', { exact: true })).toBeVisible();
  const saved = await api(patient.context, `/intakes/${intakeId}`);
  assert.equal(saved.shared_slots.allergies.status, 'UNCERTAIN');
  assert.equal(saved.shared_slots.relevant_history.status, 'SKIPPED');
  assert.equal(saved.baseline.completed, false);
  await noOverflow(patientPage, 'Baseline form desktop');
  await screenshot(patientPage, '03-baseline-form-desktop.png');
  await accessibilityCheck(patientPage, 'Baseline form desktop');
  passed('Grouped form autosaves exact answers, unknown and declined states once');

  const followed = await responseFor(patientPage, `/intakes/${intakeId}/baseline`, 'PUT', () => patientPage.getByRole('button', { name: 'Continue to AI follow-up' }).click());
  assert.equal(followed.stage, 'followup');
  assert.equal(followed.baseline.completed, true);
  assert.equal(followed.current_question, null);
  await expect(patientPage.getByRole('heading', { name: 'A few relevant follow-ups' })).toBeVisible();
  passed('Unavailable AI never starts a repetitive baseline fallback interview');

  const tinyPng = Buffer.from('iVBORw0KGgoAAAANSUhEUgAAAAgAAAAICAIAAABLbSncAAAAFElEQVR4nGN0yIxnwAaYsIoOWgkA0xkBGBV7ZfkAAAAASUVORK5CYII=', 'base64');
  const attachment = await responseFor(patientPage, `/intakes/${intakeId}/attachments`, 'POST', () => patientPage.getByLabel('Upload supporting documents').setInputFiles({ name: 'synthetic-supporting-record.png', mimeType: 'image/png', buffer: tinyPng }));
  await expect(patientPage.getByText('synthetic-supporting-record.png', { exact: true })).toBeVisible();
  const fileResponse = await patient.context.request.get(`${base}${attachment.url}`);
  assert.equal(fileResponse.status(), 200);
  assert.deepEqual(await fileResponse.body(), tinyPng);
  await noOverflow(patientPage, 'Optional follow-up desktop');
  await screenshot(patientPage, '04-optional-followup-desktop.png');
  await accessibilityCheck(patientPage, 'Optional follow-up desktop');
  passed('Actual PNG upload, private download and attachment preview work');

  const draft = await responseFor(patientPage, `/intakes/${intakeId}/review`, 'POST', () => patientPage.getByRole('button', { name: 'Generate my summary' }).click());
  assert.equal(draft.status, 'review');
  assert(draft.summary.version >= 1);
  await expect(patientPage.getByRole('heading', { name: 'AI summary is currently unavailable', exact: true })).toBeVisible();
  assert.equal(draft.summary.synthesis.status, 'unavailable');
  passed('Summary outage is labelled honestly while recorded facts remain reviewable');
  const shareButton = patientPage.getByRole('button', { name: 'Approve & share' });
  await expect(shareButton).toBeDisabled();
  const doctorField = patientPage.getByLabel('Doctor’s email address');
  if (await doctorField.evaluate(element => element.tagName) === 'SELECT') await doctorField.selectOption('doctor@example.test');
  else await doctorField.fill('doctor@example.test');
  await patientPage.getByRole('checkbox', { name: /I have reviewed this summary/ }).check();
  const regenerated = await responseFor(patientPage, `/intakes/${intakeId}/review`, 'POST', () => patientPage.getByRole('button', { name: 'Generate AI summary', exact: true }).click());
  assert(regenerated.summary.version > draft.summary.version);
  await expect(patientPage.getByRole('checkbox', { name: /I have reviewed this summary/ })).not.toBeChecked();
  await expect(shareButton).toBeDisabled();
  await patientPage.getByRole('checkbox', { name: /I have reviewed this summary/ }).check();
  passed('Regeneration requires fresh patient confirmation of the new version');
  await noOverflow(patientPage, 'Patient summary desktop');
  await screenshot(patientPage, '04-patient-review-desktop.png');
  await accessibilityCheck(patientPage, 'Patient summary desktop');
  const approved = await responseFor(patientPage, `/intakes/${intakeId}/approve`, 'POST', () => shareButton.click());
  assert.equal(approved.status, 'approved');
  assert.equal(approved.doctor_email, 'doctor@example.test');
  await expect(patientPage.getByRole('heading', { name: 'Your story is ready for your doctor.' })).toBeVisible();
  passed('Draft review and explicit versioned approval share with selected clinician');

  await doctorPage.goto(`${base}/doctor#/doctor`);
  await expect(doctorPage.getByRole('heading', { name: /Welcome, Dr Jamie Taylor/ })).toBeVisible();
  const doctorRow = doctorPage.locator(`a[href="#/doctor/intake/${intakeId}"]`);
  await expect(doctorRow).toBeVisible();
  await noOverflow(doctorPage, 'Doctor dashboard desktop');
  await screenshot(doctorPage, '05-doctor-dashboard-desktop.png', true);
  await doctorRow.click();
  await expect(doctorPage.getByRole('heading', { name: 'Alex Morgan', exact: true })).toBeVisible();
  const clinicalRecord = await api(doctor.context, `/clinician/intakes/${intakeId}`);
  assert.equal(clinicalRecord.summary.approved_version, approved.summary.version);
  assert(!('messages' in clinicalRecord), 'Clinician must not receive raw patient chat history.');
  await expect(doctorPage.getByText('synthetic-supporting-record.png', { exact: true })).toBeVisible();
  await noOverflow(doctorPage, 'Doctor detail desktop');
  await screenshot(doctorPage, '06-doctor-summary-desktop.png');
  await accessibilityCheck(doctorPage, 'Doctor detail desktop');
  const reviewed = await responseFor(doctorPage, `/clinician/intakes/${intakeId}/reviewed`, 'POST', () => doctorPage.getByRole('button', { name: 'Mark as reviewed' }).click());
  assert(reviewed.reviewed_at);
  await expect(doctorPage.getByRole('heading', { name: 'Review complete' })).toBeVisible();
  passed('Doctor sees assigned approved record and marks it reviewed');

  await patientPage.setViewportSize({ width: 390, height: 844 });
  await patientPage.goto(`${base}/patient#/patient`);
  await expect(patientPage.getByRole('heading', { name: 'Welcome, Alex.' })).toBeVisible();
  await noOverflow(patientPage, 'Patient dashboard mobile');
  await screenshot(patientPage, '07-patient-dashboard-mobile.png', true);
  await accessibilityCheck(patientPage, 'Patient dashboard mobile');
  await patientPage.goto(`${base}/patient#/patient/intake/${intakeId}`);
  await expect(patientPage.getByRole('heading', { name: 'Your story is ready for your doctor.' })).toBeVisible();
  await noOverflow(patientPage, 'Patient summary mobile');
  await screenshot(patientPage, '08-patient-summary-mobile.png');
  await doctorPage.setViewportSize({ width: 390, height: 844 });
  await noOverflow(doctorPage, 'Doctor detail mobile');
  await screenshot(doctorPage, '09-doctor-summary-mobile.png');
  await accessibilityCheck(doctorPage, 'Doctor detail mobile');
  passed('Patient and doctor flows remain within a 390px mobile viewport');

  await patientPage.getByRole('button', { name: 'Withdraw sharing', exact: true }).click();
  const withdrawDialog = patientPage.getByRole('dialog', { name: 'Withdraw this shared summary?' });
  await expect(withdrawDialog).toBeVisible();
  const withdrawn = await responseFor(patientPage, `/intakes/${intakeId}/withdraw`, 'POST', () => withdrawDialog.getByRole('button', { name: 'Withdraw sharing', exact: true }).click());
  assert.equal(withdrawn.status, 'withdrawn');
  await expect(patientPage.getByText('You withdrew sharing. Your doctor can no longer access this record in PreConsult.')).toBeVisible();
  await api(doctor.context, `/clinician/intakes/${intakeId}`, 404);
  await api(doctor.context, `/intakes/${intakeId}/attachments/${attachment.id}`, 404);
  assert(!(await api(doctor.context, '/clinician/intakes')).some(record => record.id === intakeId));
  await doctorPage.reload();
  await expect(doctorPage.getByRole('alert')).toContainText('Shared intake not found');
  await expect(doctorPage.locator('.review-document')).toHaveCount(0);
  await screenshot(doctorPage, '10-doctor-access-revoked-mobile.png');
  passed('Patient withdrawal revokes clinician list, detail and attachment access');

  await patientPage.goto(`${base}/patient#/patient/new`);
  await expect(patientPage.getByRole('heading', { name: 'What brings you here?' })).toBeVisible();
  await patientPage.getByRole('button', { name: /Start without a category/ }).click();
  await patientPage.getByRole('checkbox', { name: /I consent to AI processing/ }).check();
  const general = await responseFor(patientPage, '/intakes', 'POST', () => patientPage.getByRole('button', { name: 'Continue to health information' }).click());
  assert.deepEqual(general.concerns.map(concern => concern.workflow_id), ['GENERAL']);
  await expect(patientPage.getByRole('heading', { name: 'The essentials, all in one place.' })).toBeVisible();
  await noOverflow(patientPage, 'Uncategorized baseline mobile');
  await accessibilityCheck(patientPage, 'Baseline form mobile');
  await screenshot(patientPage, '14-general-baseline-mobile.png');
  const lastKeystroke = 'Please save this goal before I leave the form.';
  await fillAnswer(patientPage, 'baseline-session-appointment_goal', lastKeystroke);
  await patientPage.getByRole('link', { name: 'Back to overview', exact: true }).click();
  await expect(patientPage.getByRole('heading', { name: 'Welcome, Alex.' })).toBeVisible();
  const flushed = await api(patient.context, `/intakes/${general.id}`);
  assert.equal(flushed.shared_slots.appointment_goal.value, lastKeystroke);
  passed('No-category route works and immediate in-app navigation preserves the last form edit');

  const liveRecordResponse = await patient.context.request.get(`${base}/api/v1/intakes/browser-live-summary`);
  if (liveRecordResponse.ok()) {
    const liveRecord = await liveRecordResponse.json();
    assert.equal(liveRecord.summary.synthesis.status, 'live');
    assert(liveRecord.summary.synthesis.sources.length > 0);
    await patientPage.setViewportSize({ width: 1440, height: 1024 });
    await patientPage.goto(`${base}/patient#/patient/intake/browser-live-summary`);
    await expect(patientPage.getByRole('heading', { name: 'Your situation, in plain language' })).toBeVisible();
    await patientPage.getByRole('button', { name: 'Clinician brief', exact: true }).click();
    await expect(patientPage.getByRole('heading', { name: 'Pre-consultation brief' })).toBeVisible();
    await patientPage.getByRole('button', { name: 'Patient overview', exact: true }).click();
    await screenshot(patientPage, '11-live-ai-patient-summary.png');
    await accessibilityCheck(patientPage, 'Live AI summary patient desktop');
    const source = patientPage.getByRole('button', { name: /^View \d+ supporting sources?$/ }).first();
    await source.click();
    await expect(patientPage.getByRole('dialog', { name: 'Supporting information' })).toBeVisible();
    await patientPage.getByRole('dialog').getByRole('button', { name: 'Done', exact: true }).click();
    passed('Genuine synthetic OpenAI summary renders patient/clinician views and source details');
    const liveDoctor = patientPage.getByLabel('Doctor’s email address');
    if (await liveDoctor.evaluate(element => element.tagName) === 'SELECT') await liveDoctor.selectOption('doctor@example.test');
    else await liveDoctor.fill('doctor@example.test');
    await patientPage.getByRole('checkbox', { name: /I have reviewed this summary/ }).check();
    const sharedLive = await responseFor(patientPage, '/intakes/browser-live-summary/approve', 'POST', () => patientPage.getByRole('button', { name: 'Approve & share' }).click());
    assert.deepEqual(sharedLive.summary.synthesis, liveRecord.summary.synthesis);
    await doctorPage.setViewportSize({ width: 1440, height: 1024 });
    await doctorPage.goto(`${base}/doctor#/doctor/intake/browser-live-summary`);
    await expect(doctorPage.getByRole('heading', { name: 'Pre-consultation brief' })).toBeVisible();
    const clinicalLive = await api(doctor.context, '/clinician/intakes/browser-live-summary');
    assert.deepEqual(clinicalLive.summary.synthesis, sharedLive.summary.synthesis);
    assert(!('messages' in clinicalLive));
    await screenshot(doctorPage, '12-live-ai-clinician-summary.png');
    await accessibilityCheck(doctorPage, 'Live AI summary clinician desktop');
    await patientPage.setViewportSize({ width: 390, height: 844 });
    await noOverflow(patientPage, 'Live AI summary patient mobile');
    await screenshot(patientPage, '13-live-ai-summary-mobile.png');
    passed('The exact approved AI synthesis reaches the assigned clinician');
  }

  assert(accessibility.every(result => result.violations.length === 0), `Serious/critical accessibility findings: ${accessibility.filter(result => result.violations.length).map(result => `${result.page}: ${result.violations.map(item => item.id).join(', ')}`).join('; ')}`);
  assert.deepEqual(pageErrors, [], 'The browser must not report uncaught JavaScript exceptions.');
  passed('No uncaught browser JavaScript errors');
  const report = { passed: true, ran_at: new Date().toISOString(), mode: 'isolated synthetic database; real UI and API; external providers disabled', checks, screenshots, accessibility };
  await writeFile(path.join(output, 'browser-test-report.json'), JSON.stringify(report, null, 2) + '\n');
  await Promise.all(['failure-patient.png', 'failure-doctor.png'].map(name => unlink(path.join(output, name)).catch(error => { if (error.code !== 'ENOENT') throw error; })));
  console.log(`Browser acceptance passed: ${checks.length} checks; ${screenshots.length} screenshots.`);
} catch (error) {
  for (const [label, page] of [['patient', patientPage], ['doctor', doctorPage]]) {
    if (page && !page.isClosed()) {
      await page.screenshot({ path: path.join(output, `failure-${label}.png`), fullPage: false }).catch(() => {});
    }
  }
  await writeFile(path.join(output, 'browser-test-report.json'), JSON.stringify({ passed: false, ran_at: new Date().toISOString(), checks, screenshots, accessibility, error: error.message, pageErrors }, null, 2) + '\n');
  throw error;
} finally {
  await Promise.all(contexts.map(context => context.close()));
  await browser.close();
}
