#!/usr/bin/env node
/** Real UI/API acceptance of illustrated inputs; synthetic fixture on port 8001 only. */
import assert from 'node:assert/strict';
import { createRequire } from 'node:module';
import { readFile, writeFile, mkdir, access, unlink } from 'node:fs/promises';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const require = createRequire(path.join(root, 'frontend/package.json'));
const { chromium } = require('playwright');
const { expect } = require('@playwright/test');
const AxeBuilder = require('@axe-core/playwright').default;
const base = 'http://127.0.0.1:8001';
const output = path.join(root, 'docs/screenshots/v3');
await mkdir(output, { recursive: true });
const tokens = JSON.parse(await readFile(path.join(root, '.local/browser-test/sessions.json'), 'utf8'));
const config = await (await fetch(`${base}/api/v1/config`)).json();
assert.equal(config.ai_configured, false);
assert.equal(config.mail_configured, false);
let executablePath = process.env.PLAYWRIGHT_CHROMIUM_EXECUTABLE;
if (!executablePath) {
  const chrome = '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome';
  try { await access(chrome); executablePath = chrome; } catch { /* use installed Playwright */ }
}
const browser = await chromium.launch({ headless: true, ...(executablePath ? { executablePath } : {}) });
const context = await browser.newContext({ viewport: { width: 1440, height: 1050 }, reducedMotion: 'reduce' });
await context.addCookies([{ name: 'preconsult_session', value: tokens.patient, url: base, httpOnly: true, sameSite: 'Lax' }]);
const page = await context.newPage();
page.setDefaultTimeout(15000);
const checks = [], screenshots = [], accessibility = [], errors = [];
page.on('pageerror', error => errors.push(error.message));
function pass(message) { checks.push(message); console.log(`PASS ${message}`); }
async function api(suffix, data, method = 'POST') {
  const response = await context.request.fetch(`${base}/api/v1${suffix}`, {
    method: data === undefined ? 'GET' : method,
    headers: { Origin: base }, ...(data === undefined ? {} : { data }),
  });
  assert(response.ok(), `${suffix}: ${response.status()} ${await response.text()}`);
  return response.json();
}
async function capture(name) {
  await page.screenshot({ path: path.join(output, name), animations: 'disabled' });
  screenshots.push(name);
}
async function scan(label) {
  assert(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth + 1), `${label}: horizontal overflow`);
  const results = await new AxeBuilder({ page }).withTags(['wcag2a', 'wcag2aa', 'wcag21aa']).analyze();
  const violations = results.violations.filter(item => ['serious', 'critical'].includes(item.impact)).map(item => ({ id: item.id, nodes: item.nodes.map(node => ({ target: node.target, explanation: node.failureSummary })) }));
  accessibility.push({ page: label, violations });
  assert.equal(violations.length, 0, `${label}: ${JSON.stringify(violations)}`);
  pass(`${label}: no overflow or serious/critical accessibility findings`);
}
const field = (owner, key) => page.locator('.baseline-field').filter({ has: page.getByTestId(`baseline-status-${owner}-${key}`) });
async function openGroup(title) {
  const toggle = page.locator('.baseline-group-toggle').filter({ hasText: title });
  if (await toggle.getAttribute('aria-expanded') !== 'true') await toggle.click();
}
async function savedValue(intake, owner, key, predicate) {
  await expect.poll(async () => {
    const record = await api(`/intakes/${intake}`);
    const slot = record.concerns.find(concern => concern.id === owner).slots[key];
    return predicate(slot);
  }, { timeout: 10000 }).toBe(true);
}
try {
  await page.goto(`${base}/#/patient/new`);
  await expect(page.locator('.workflow-card')).toHaveCount(30);
  const iconMarkup = await page.locator('.workflow-card svg').evaluateAll(nodes => nodes.map(node => node.innerHTML));
  assert(new Set(iconMarkup).size >= 20, 'Topic catalogue must use specific illustrations rather than a few cycling symbols.');
  const sidebarColor = await page.locator('.sidebar').evaluate(element => getComputedStyle(element).backgroundColor);
  const rgb = sidebarColor.match(/[\d.]+/g).slice(0, 3).map(Number);
  assert(rgb.every(channel => channel > 200), `Sidebar must use the new light surface: ${sidebarColor}`);
  await page.getByRole('heading', { name: 'Browse consultation topics' }).evaluate(element => element.scrollIntoView({ block: 'start' }));
  await capture('15-topic-icons-light-theme.png');
  pass('All 30 topics render with a light sidebar and topic-specific icon vocabulary');
  const record = await api('/intakes', { consent: true, workflow_ids: ['WF-01', 'WF-02', 'WF-05', 'WF-08', 'WF-14', 'WF-20'], title: 'Illustrated preparation · synthetic acceptance' });
  const form = await api(`/intakes/${record.id}/form`);
  const leg = record.concerns.find(item => item.workflow_id === 'WF-01');
  const sleep = record.concerns.find(item => item.workflow_id === 'WF-08');
  const locationKey = 'leg.pain_site';
  const locationMetadata = form.groups.find(group => group.id === leg.id).fields.find(item => item.key === locationKey).presentation;
  assert.equal(locationMetadata.kind, 'body_map');
  const calf = locationMetadata.options.find(option => option.region === 'left_calf');
  const knee = locationMetadata.options.find(option => option.region === 'right_knee');
  assert(calf && knee, 'Leg diagram must expose unambiguous patient-left and patient-right landmarks.');
  // A legacy narrative is deliberately written before the UI sees the guided field.
  const legacyText = 'Near a small mark on my shin; this wording must stay exactly as I wrote it.';
  await api(`/intakes/${record.id}/baseline`, { answers: [{ concern_id: leg.id, key: 'leg.pain_character', value: legacyText, status: 'FILLED' }], complete: false, revision: record.revision }, 'PUT');
  await page.goto(`${base}/#/patient/intake/${record.id}`);
  await expect(page.getByRole('heading', { name: 'The essentials, all in one place.' })).toBeVisible();
  await openGroup(leg.title);
  const site = field(leg.id, locationKey);
  await expect(site.locator('.answer-choice[aria-pressed="true"], .body-map-region[aria-pressed="true"]')).toHaveCount(0);
  const legacyInput = page.getByTestId(`baseline-${leg.id}-leg.pain_character`);
  await expect(legacyInput).toBeVisible();
  await expect(legacyInput).toHaveValue(legacyText);
  pass('Guided questions start unselected and preserve an existing free-text answer visibly');

  await site.getByRole('button', { name: 'Back', exact: true }).click();
  const calfRegion = site.locator('svg [role="button"]').filter({ hasText: calf.label });
  // Accessible name works for both SVG title/aria-label implementations.
  const calfTarget = await calfRegion.count() ? calfRegion.first() : site.locator('svg').getByRole('button', { name: calf.label, exact: true });
  await calfTarget.focus();
  await page.keyboard.press('Enter');
  await expect(calfTarget).toHaveAttribute('aria-pressed', 'true');
  await site.locator('button.answer-choice').filter({ hasText: knee.label }).click();
  await savedValue(record.id, leg.id, locationKey, slot => slot.status === 'FILLED' && slot.value.includes(calf.value) && slot.value.includes(knee.value));
  pass('Keyboard diagram selection and labelled choices save both precise patient-side locations');
  const details = page.getByTestId(`baseline-${leg.id}-${locationKey}`);
  if (!(await details.isVisible())) await site.getByRole('button', { name: /add.*details|write.*answer|own.*words/i }).click();
  await details.fill('Mostly after a long walk, in my own words.');
  await savedValue(record.id, leg.id, locationKey, slot => slot.value.includes(calf.value) && slot.value.includes(knee.value) && slot.value.includes('Mostly after a long walk'));
  await page.reload();
  await openGroup(leg.title);
  await expect(page.getByTestId(`baseline-${leg.id}-${locationKey}`)).toHaveValue('Mostly after a long walk, in my own words.');
  await expect(field(leg.id, locationKey).locator('button.answer-choice').filter({ hasText: calf.label })).toHaveAttribute('aria-pressed', 'true');
  await expect(page.getByTestId(`baseline-${leg.id}-leg.pain_character`)).toHaveValue(legacyText);
  pass('Autosave and reload retain selected regions, added detail, and untouched legacy narrative');
  await field(leg.id, locationKey).scrollIntoViewIfNeeded();
  await capture('16-interactive-leg-map-desktop.png');
  await scan('Interactive leg map desktop');

  await page.getByTestId(`baseline-status-${leg.id}-${locationKey}`).selectOption('UNCERTAIN');
  await savedValue(record.id, leg.id, locationKey, slot => slot.status === 'UNCERTAIN' && slot.value.includes(calf.value));
  await page.getByTestId(`baseline-status-${leg.id}-${locationKey}`).selectOption('SKIPPED');
  await savedValue(record.id, leg.id, locationKey, slot => slot.status === 'SKIPPED' && slot.value == null);
  await page.getByTestId(`baseline-status-${leg.id}-${locationKey}`).selectOption('MISSING');
  await expect(field(leg.id, locationKey).locator('.answer-choice[aria-pressed="true"], .body-map-region[aria-pressed="true"]')).toHaveCount(0);
  await field(leg.id, locationKey).locator('button.answer-choice').filter({ hasText: calf.label }).click();
  await savedValue(record.id, leg.id, locationKey, slot => slot.status === 'FILLED' && slot.value.includes(calf.value) && !slot.value.includes(knee.value));
  pass('Unknown stays uncertain; declining clears choices; a fresh answer contains only the new selection');

  await openGroup(sleep.title);
  const sleepField = form.groups.find(group => group.id === sleep.id).fields.find(item => item.key === 'symptom_frequency');
  const frequency = field(sleep.id, sleepField.key);
  assert.equal(sleepField.presentation.multiple, false);
  const [first, second] = sleepField.presentation.options;
  await frequency.locator('button.answer-choice').filter({ hasText: first.label }).click();
  await frequency.locator('button.answer-choice').filter({ hasText: second.label }).click();
  await expect(frequency.locator('button.answer-choice[aria-pressed="true"]')).toHaveCount(1);
  await savedValue(record.id, sleep.id, sleepField.key, slot => (slot.value || '').includes(second.value) && !(slot.value || '').includes(first.value));
  await frequency.scrollIntoViewIfNeeded();
  await capture('17-sleep-choice-cards.png');
  pass('Single-choice frequency replaces the previous option without contradictory answers');

  for (const workflow of ['WF-02', 'WF-05', 'WF-14', 'WF-20']) {
    const concern = record.concerns.find(item => item.workflow_id === workflow);
    await openGroup(concern.title);
    const mapField = form.groups.find(group => group.id === concern.id).fields.find(item => item.presentation?.kind === 'body_map');
    assert(mapField, `${workflow} must have its own illustrated location field`);
    const widget = field(concern.id, mapField.key);
    await expect(widget.locator('svg.body-map-drawing')).toBeVisible();
    await widget.scrollIntoViewIfNeeded();
    await capture(`18-map-${workflow}.png`);
    await scan(`${workflow} illustrated location`);
  }
  await page.setViewportSize({ width: 390, height: 844 });
  await field(leg.id, locationKey).getByRole('button', { name: 'Back', exact: true }).click();
  await field(leg.id, locationKey).scrollIntoViewIfNeeded();
  await capture('19-interactive-map-mobile.png');
  await scan('Interactive body map mobile');
  await frequency.scrollIntoViewIfNeeded();
  await capture('20-choice-cards-mobile.png');
  await scan('Choice cards mobile');
  const finalRecord = await api(`/intakes/${record.id}`);
  const savedSite = finalRecord.concerns.find(item => item.id === leg.id).slots[locationKey];
  assert.equal(savedSite.evidence.span, savedSite.value);
  assert.equal(savedSite.evidence.source, 'patient_form');
  assert.equal(finalRecord.concerns.find(item => item.id === leg.id).slots['leg.pain_character'].value, legacyText);
  pass('Recorded selection evidence is the exact patient-authored value, with legacy text unchanged');
  assert.deepEqual(errors, []);
  const report = { passed: true, ran_at: new Date().toISOString(), checks, screenshots, accessibility, errors };
  await writeFile(path.join(output, 'guided-forms-report.json'), JSON.stringify(report, null, 2) + '\n');
  await unlink(path.join(output, 'guided-forms-failure.png')).catch(error => { if (error.code !== 'ENOENT') throw error; });
  console.log(`Guided forms acceptance passed: ${checks.length} checks.`);
} catch (error) {
  await capture('guided-forms-failure.png').catch(() => {});
  await writeFile(path.join(output, 'guided-forms-report.json'), JSON.stringify({ passed: false, checks, screenshots, accessibility, errors, error: error.message }, null, 2) + '\n');
  throw error;
} finally {
  await context.close();
  await browser.close();
}
