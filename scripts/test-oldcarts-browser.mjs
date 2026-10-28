#!/usr/bin/env node
/** Isolated real UI/API regression. Only organize responses are mocked.
 * No real identities, email, audio or paid model requests are made.
 * Start: backend/.venv/bin/python scripts/product-browser-server.py
 * Then build frontend and run this script with Node.
 */
import assert from 'node:assert/strict';
import { createRequire } from 'node:module';
import { readFile, writeFile, mkdir, access, unlink } from 'node:fs/promises';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { translateProduct } from '../frontend/src/product/translations.js';
import { serializeGuidedAnswer } from '../frontend/src/product/answerValues.js';

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const require = createRequire(path.join(root, 'frontend/package.json'));
const { chromium } = require('playwright');
const { expect } = require('@playwright/test');
const AxeBuilder = require('@axe-core/playwright').default;
const base = process.env.PRECONSULT_TEST_URL || 'http://127.0.0.1:8001';
const address = new URL(base);
assert(['127.0.0.1', 'localhost'].includes(address.hostname) && address.port === '8001', 'Only isolated loopback port 8001 is allowed.');
const output = path.join(root, '.local/oldcarts-browser');
await mkdir(output, { recursive: true });
const tokens = JSON.parse(await readFile(path.join(root, '.local/browser-test/sessions.json'), 'utf8'));
const config = await (await fetch(`${base}/api/v1/config`)).json();
assert.equal(config.ai_configured, false, 'The isolated fixture must disable paid providers.');
assert.equal(config.mail_configured, false);
let executablePath = process.env.PLAYWRIGHT_CHROMIUM_EXECUTABLE;
if (!executablePath) {
  const chrome = '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome';
  try { await access(chrome); executablePath = chrome; } catch { /* bundled Playwright */ }
}
const browser = await chromium.launch({ headless: true, ...(executablePath ? { executablePath } : {}) });
const context = await browser.newContext({ viewport: { width: 1440, height: 1050 }, reducedMotion: 'reduce' });
await context.addCookies([{ name: 'preconsult_session', value: tokens.patient, url: base, httpOnly: true, sameSite: 'Lax' }]);
const page = await context.newPage();
page.setDefaultTimeout(15000);
const checks = [], screenshots = [], accessibility = [], pageErrors = [];
let organizeRequests = 0;
page.on('pageerror', error => pageErrors.push(error.message));
function pass(name) { checks.push(name); console.log(`PASS ${name}`); }
async function api(suffix, method = 'GET', data) {
  const response = await context.request.fetch(`${base}/api/v1${suffix}`, { method, headers: { Origin: base }, ...(data === undefined ? {} : { data }) });
  assert(response.ok(), `${method} ${suffix}: ${response.status()} ${await response.text()}`);
  return response.status() === 204 ? null : response.json();
}
async function create(workflow = 'WF-01', locale = 'en') {
  return api('/intakes', 'POST', { consent: true, workflow_ids: [workflow], locale, title: `Synthetic OLDCARTS ${workflow} ${locale}` });
}
async function open(record, locale = 'en') {
  await page.goto(`${base}/#/patient`);
  await page.evaluate(value => localStorage.setItem('preconsultation.locale', value), locale);
  await page.goto(`${base}/#/patient/intake/${record.id}`);
  await page.reload();
  await expect(page.locator('.wizard-question-card')).toBeVisible();
  await expect(page.locator('.wizard-question-card #wizard-question')).toHaveCount(1);
}
async function jump(label) {
  const support = page.locator('.wizard-support');
  if ((await support.getAttribute('open')) === null) await support.locator(':scope > summary').click();
  await support.locator('.wizard-jump').filter({ hasText: new RegExp(`^${label.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')}$`) }).click();
  await expect(page.locator('.wizard-question-card')).toBeVisible();
}
async function saveCheck(id, owner, key, value) {
  await expect.poll(async () => (await api(`/intakes/${id}`)).concerns.find(c => c.id === owner).slots[key].value).toBe(value);
}
async function capture(name) {
  await page.screenshot({ path: path.join(output, name), animations: 'disabled', fullPage: false });
  screenshots.push(name);
}
async function scan(label) {
  await expect.poll(() => page.evaluate(() => document.documentElement.scrollWidth <= innerWidth + 1)).toBe(true);
  const result = await new AxeBuilder({ page }).withTags(['wcag2a', 'wcag2aa', 'wcag21aa']).analyze();
  const violations = result.violations.filter(v => ['serious', 'critical'].includes(v.impact)).map(({ id, impact, help, nodes }) => ({ id, impact, help, nodes: nodes.map(n => ({ target: n.target, explanation: n.failureSummary })) }));
  accessibility.push({ page: label, violations });
  assert.equal(violations.length, 0, `${label}: ${JSON.stringify(violations)}`);
  pass(`${label}: no horizontal overflow or serious/critical axe findings`);
}
async function review(locale = 'en') {
  await page.locator('.wizard-actions .text-button').filter({ hasText: translateProduct(locale, 'Review answers') }).click();
  await expect(page.locator('.wizard-review')).toBeVisible();
}

if (process.argv.includes('--mobile-only')) {
  try {
    assert.equal((await api('/auth/me')).user.id, 'browser-test-patient');
    const record = await create();
    const owner = record.concerns[0].id;
    await api(`/intakes/${record.id}/baseline`, 'PUT', { revision: record.revision, complete: false, answers: [
      { concern_id: owner, key: 'severity', status: 'FILLED', value: serializeGuidedAnswer({ selected: ['Moderate', '7/10'], details: '' }) },
      { concern_id: owner, key: 'leg.pain_character', status: 'UNCERTAIN', value: null },
      { concern_id: owner, key: 'aggravating_factors', status: 'SKIPPED', value: null },
      { concern_id: owner, key: 'relieving_factors', status: 'FILLED', value: 'Rest eases it.' },
    ] });
    await page.setViewportSize({ width: 390, height: 844 });
    await open(record);
    await review();
    const story = page.getByTestId('symptom-story');
    await story.locator(':scope > summary').click();
    await story.scrollIntoViewIfNeeded();
    for (const row of await story.locator('.symptom-story-row').all()) {
      const edit = row.locator('.symptom-story-edit-cell');
      if (!await edit.count()) continue;
      const [label, action] = await Promise.all([row.locator('dt').boundingBox(), edit.boundingBox()]);
      assert(action.x > label.x && Math.abs(action.y - label.y) < 3, 'Mobile edit action must align beside the dimension label, not above it.');
    }
    pass('Mobile edit actions align beside their dimension labels');
    await capture('04-symptom-story-mobile.png');
    await scan('Mobile symptom story after CSS layout fix');
    await story.getByRole('button', { name: 'Edit Intensity for Leg pain', exact: true }).click();
    await capture('05-intensity-mobile.png');
    await scan('Mobile intensity after CSS layout fix');
    assert.equal(pageErrors.length, 0, pageErrors.join('\n'));
    await writeFile(path.join(output, 'mobile-review.json'), `${JSON.stringify({ passed: true, ran_at: new Date().toISOString(), mode: 'Real UI and isolated API; synthetic direct answers; no model or email calls', checks, screenshots, accessibility, pageErrors }, null, 2)}\n`);
    console.log(`Verified ${checks.length} focused mobile checks.`);
  } finally {
    await browser.close();
  }
} else {
try {
  assert.equal((await api('/auth/me')).user.id, 'browser-test-patient');
  const success = await create();
  const successOwner = success.concerns[0].id;
  const narrative = 'My left knee has a dull ache that started three weeks ago. It is moderate, occurs in the evening, gets worse on stairs, and eases with rest.';
  const successPath = `**/api/v1/intakes/${success.id}/baseline/organize`;
  await page.route(successPath, async route => {
    organizeRequests++;
    const saved = await api(`/intakes/${success.id}`);
    assert.equal(saved.concerns[0].slots.concern_description.value, narrative, 'Description must be persisted before organization.');
    // Deterministic model result. Save through the real API so subsequent form
    // reloads and edit/navigation checks exercise actual persisted data.
    const values = { 'leg.pain_site': 'Left knee', symptom_onset: 'Three weeks ago', 'leg.pain_character': 'Dull ache',
      symptom_frequency: 'In the evening', aggravating_factors: 'Stairs make it worse.', relieving_factors: 'Rest eases it.', severity: 'Moderate' };
    const updated = await api(`/intakes/${success.id}/baseline`, 'PUT', { revision: saved.revision, complete: false,
      answers: Object.entries(values).map(([key, value]) => ({ concern_id: successOwner, key, value, status: 'FILLED' })) });
    await route.fulfill({ json: { ...updated, ai_status: { mode: 'live', message: 'Deterministic synthetic organization fixture; no model call.' } } });
  });
  await open(success);
  await page.locator('.wizard-question-card textarea').fill(narrative);
  await page.locator('.wizard-actions button.primary').click();
  await expect(page.locator('#wizard-question')).toHaveText('How does the pain affect your everyday activities?');
  assert.equal(organizeRequests, 1);
  await expect(page.getByText('We’ve filled in details from your description. You can check or change them at any time.', { exact: true })).toBeVisible();
  pass('Description is saved before organize; real persisted prefills skip known fields and land on the next missing question');
  await capture('01-organized-next-question.png');
  await jump('Severity');
  await expect(page.locator('.symptom-step-context')).toContainText('Intensity');
  await expect(page.locator('.wizard-question-card textarea')).toHaveValue('Moderate');
  await page.locator('.wizard-question-card textarea').fill('');
  await page.getByRole('button', { name: 'Mild', exact: true }).click();
  await saveCheck(success.id, successOwner, 'severity', serializeGuidedAnswer({ selected: ['Mild'], details: '' }));
  pass('A prefilled answer remains editable and the one-question wizard shows its dimension cue');
  await page.unroute(successPath);

  const failure = await create();
  const fallbackText = 'My right calf aches after walking, and I want to explain it in my own words.';
  await page.route(`**/api/v1/intakes/${failure.id}/baseline/organize`, route => route.fulfill({ status: 503, json: { detail: 'Synthetic model outage' } }));
  await open(failure);
  await page.locator('.wizard-question-card textarea').fill(fallbackText);
  await page.locator('.wizard-actions button.primary').click();
  await expect(page.locator('#wizard-question')).toHaveText('Where in your leg do you feel the pain?');
  await expect(page.getByText('Your description is saved. Continue at your own pace; you can review every answer.', { exact: true })).toBeVisible();
  await jump('In your own words');
  await expect(page.locator('.wizard-question-card textarea')).toHaveValue(fallbackText);
  await saveCheck(failure.id, failure.concerns[0].id, 'concern_description', fallbackText);
  pass('Organization failure advances to manual questions while preserving the saved editable narrative');

  const controls = await create();
  const owner = controls.concerns[0].id;
  await open(controls);
  await jump('What makes it worse');
  await page.getByRole('button', { name: 'Movement', exact: true }).click();
  await page.getByRole('button', { name: 'Nothing noticed', exact: true }).click();
  await expect(page.getByRole('button', { name: 'Movement', exact: true })).toHaveAttribute('aria-pressed', 'false');
  await page.getByRole('button', { name: 'Standing', exact: true }).click();
  await expect(page.getByRole('button', { name: 'Nothing noticed', exact: true })).toHaveAttribute('aria-pressed', 'false');
  await page.getByRole('button', { name: 'Prefer not to answer', exact: true }).click();
  await jump('What helps');
  await page.getByRole('button', { name: 'Rest', exact: true }).click();
  await page.getByRole('button', { name: 'Nothing noticed', exact: true }).click();
  await expect(page.getByRole('button', { name: 'Rest', exact: true })).toHaveAttribute('aria-pressed', 'false');
  await page.getByRole('button', { name: 'Rest', exact: true }).click();
  await expect(page.getByRole('button', { name: 'Nothing noticed', exact: true })).toHaveAttribute('aria-pressed', 'false');
  pass('Aggravating and relieving choices make explicit-none mutually exclusive with positive observations');
  await jump('Severity');
  await page.getByRole('button', { name: 'Moderate', exact: true }).click();
  const painToggle = page.getByRole('button', { name: 'Add a pain number (optional)', exact: true });
  assert.equal(await painToggle.count(), 1, 'Pain workflows should expose an optional numerical scale.');
  await painToggle.click();
  await expect(page.locator('.pain-number-options button')).toHaveCount(11);
  await page.getByRole('button', { name: 'Pain level 7 out of 10', exact: true }).click();
  await expect(page.getByRole('button', { name: 'Moderate', exact: true })).toHaveAttribute('aria-pressed', 'true');
  await expect(page.getByRole('button', { name: 'Pain level 7 out of 10', exact: true })).toHaveAttribute('aria-pressed', 'true');
  pass('Optional 0–10 pain number supplements the selected qualitative intensity');
  await capture('02-intensity-desktop.png');
  await scan('Desktop intensity step');
  await jump('Leg · pain character');
  await page.getByRole('button', { name: 'I’m not sure', exact: true }).click();
  await expect.poll(async () => (await api(`/intakes/${controls.id}`)).concerns[0].slots['leg.pain_character'].status).toBe('UNCERTAIN');
  await review();
  const story = page.getByTestId('symptom-story');
  await story.locator(':scope > summary').click();
  await expect(story.locator('.story-filled')).not.toHaveCount(0);
  await expect(story.locator('.story-uncertain')).toHaveCount(1);
  await expect(story.locator('.story-skipped')).toHaveCount(1);
  await expect(story.locator('.story-missing')).not.toHaveCount(0);
  await expect(story.locator('.symptom-story-gap')).toContainText('You can still continue.');
  await expect(story).not.toContainText('Standing makes it worse.');
  pass('Symptom story distinguishes recorded, unknown, skipped and missing details without exposing refused text');
  await capture('03-symptom-story-desktop.png');
  await scan('Desktop symptom story');
  await page.setViewportSize({ width: 390, height: 844 });
  await story.scrollIntoViewIfNeeded();
  await capture('04-symptom-story-mobile.png');
  await scan('Mobile symptom story');
  await story.getByRole('button', { name: 'Edit Intensity for Leg pain', exact: true }).click();
  await expect(page.locator('.wizard-question-card')).toBeVisible();
  await capture('05-intensity-mobile.png');
  await scan('Mobile intensity step');

  await page.setViewportSize({ width: 1440, height: 1050 });
  for (const locale of ['en', 'zh-CN', 'zh-TW', 'ko', 'ja']) {
    const localized = await create('WF-01', locale);
    await open(localized, locale);
    await jump(translateProduct(locale, 'Severity'));
    await expect(page.locator('.symptom-step-context')).toContainText(translateProduct(locale, 'Intensity'));
    await review(locale);
    const localizedStory = page.getByTestId('symptom-story');
    await expect(localizedStory.locator('summary')).toContainText(translateProduct(locale, 'Your symptom story'));
    await localizedStory.locator('summary').click();
    await expect(localizedStory.locator('.symptom-story-list')).toContainText(translateProduct(locale, 'What makes it worse'));
    await expect(localizedStory.locator('.symptom-story-list')).toContainText(translateProduct(locale, 'Not yet recorded'));
    if (locale !== 'en') await expect(localizedStory.locator('.symptom-story-list')).not.toContainText('Not yet recorded');
    await capture(`06-story-${locale}.png`);
    pass(`${locale}: core dimension cues, symptom-story labels and missing statuses are localized`);
  }
  const reviewOnly = await create('WF-24');
  await open(reviewOnly);
  assert.equal((await api(`/intakes/${reviewOnly.id}`)).symptom_history[0].applicable, false);
  await review();
  await expect(page.getByTestId('symptom-story')).toHaveCount(0);
  await expect(page.locator('.wizard-review-list')).not.toContainText('What makes it worse');
  pass('A blood-pressure review without current symptoms has no forced symptom-history panel or extra questions');
  assert.equal(pageErrors.length, 0, pageErrors.join('\n'));
  const report = { passed: true, ran_at: new Date().toISOString(), mode: 'Real UI and isolated API/database; deterministic organize success and outage responses mocked; email and paid providers disabled', checks, screenshots, accessibility, pageErrors };
  await writeFile(path.join(output, 'report.json'), `${JSON.stringify(report, null, 2)}\n`);
  await unlink(path.join(output, 'failure.png')).catch(() => {});
  console.log(`Verified ${checks.length} checks; report: ${path.join(output, 'report.json')}`);
} catch (error) {
  await capture('failure.png').catch(() => {});
  await writeFile(path.join(output, 'report.json'), `${JSON.stringify({ passed: false, ran_at: new Date().toISOString(), error: error.stack, checks, screenshots, accessibility, pageErrors }, null, 2)}\n`);
  throw error;
} finally {
  await browser.close();
}
}
