#!/usr/bin/env node
/** Synthetic report acceptance. Real auth/sharing/PDF; explicitly mocked AI UI states. */
import assert from 'node:assert/strict';
import { createRequire } from 'node:module';
import { readFile, writeFile, mkdir } from 'node:fs/promises';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const require = createRequire(path.join(root, 'frontend/package.json'));
const { chromium } = require('playwright');
const { expect } = require('@playwright/test');
const AxeBuilder = require('@axe-core/playwright').default;
const base = 'http://127.0.0.1:8001';
const out = path.join(root, '.local/assessment-browser');
await mkdir(out, {recursive:true, mode:0o700});
const tokens = JSON.parse(await readFile(path.join(root, '.local/browser-test/sessions.json'), 'utf8'));
const cfg = await (await fetch(base + '/api/v1/config')).json();
assert.equal(cfg.ai_configured, false);
assert.equal(cfg.mail_configured, false);
const browser = await chromium.launch({headless:true, executablePath: process.env.PLAYWRIGHT_CHROMIUM_EXECUTABLE || '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome'});
const contexts = [];
const checks = [], errors = [], axe = [];
function pass(name, type='real API') {checks.push({name,type}); console.log(`PASS [${type}] ${name}`);}
async function pageFor(role, width=1440) {
  const context = await browser.newContext({viewport:{width,height:1000}, reducedMotion:'reduce', acceptDownloads:true});
  contexts.push(context);
  await context.addCookies([{name:'preconsult_session',value:tokens[role],url:base,httpOnly:true,sameSite:'Lax'}]);
  const page = await context.newPage();
  page.on('pageerror', error=>errors.push(error.message));
  page.setDefaultTimeout(15000);
  return {context,page};
}
async function accessible(page, label) {
  const result = await new AxeBuilder({page}).withTags(['wcag2a','wcag2aa','wcag21aa']).analyze();
  const violations = result.violations.filter(v=>['serious','critical'].includes(v.impact)).map(v=>({id:v.id,nodes:v.nodes.map(n=>n.target)}));
  axe.push({label,violations});
  assert.deepEqual(violations,[],label);
  assert(await page.evaluate(()=>document.documentElement.scrollWidth <= innerWidth), 'Horizontal overflow: '+label);
}
const intakeUrl = '/api/v1/intakes/browser-assessment';
try {
  const patient=await pageFor('patient');
  const doctor=await pageFor('doctor');
  const before=await doctor.context.request.get(base+intakeUrl+'/report.pdf');
  assert.equal(before.status(),404);
  await patient.page.goto(base+'/#/patient/intake/browser-assessment');
  await expect(patient.page.getByRole('heading',{name:'AI diagnosis & consultation guidance',exact:true})).toBeVisible();
  await expect(patient.page.getByRole('heading',{name:'Possible diagnoses to discuss',exact:true})).toBeVisible();
  assert.equal(await patient.page.locator('.assessment-files article').count(),2);
  const seedResponse=await patient.context.request.get(base+intakeUrl);
  const seed=await seedResponse.json();
  assert(seed.ai_report && !JSON.stringify(seed.ai_report).includes('storage_path'));
  await accessible(patient.page,'patient desktop');
  await patient.page.screenshot({path:path.join(out,'patient-report.png'),fullPage:true});
  await patient.page.screenshot({path:path.join(out,'patient-first-screen.png')});
  pass('Current live-generated report and two attachment reviews visible to owner');
  await patient.page.locator('.assessment-overview .source-link').click();
  await expect(patient.page.getByRole('dialog')).toBeVisible();
  await expect(patient.page.getByRole('heading',{name:'Supporting information',exact:true})).toBeVisible();
  await accessible(patient.page,'source modal');
  await patient.page.keyboard.press('Escape');
  pass('Source references open readable accessible evidence');

  // Exercise the new download error path, then download the actual server PDF.
  await patient.page.route('**/api/v1/intakes/browser-assessment/report.pdf', route=>route.fulfill({status:409,contentType:'application/json',body:JSON.stringify({detail:'A supporting attachment is missing or unreadable.'})}));
  await patient.page.getByRole('button',{name:'Download complete PDF',exact:true}).click();
  await expect(patient.page.getByText('A supporting attachment is missing or unreadable.',{exact:true})).toBeVisible();
  await patient.page.unroute('**/api/v1/intakes/browser-assessment/report.pdf');
  pass('Missing attachment export error is visible and retry remains available','UI simulation');
  const pendingDownload=patient.page.waitForEvent('download');
  await patient.page.getByRole('button',{name:'Download complete PDF',exact:true}).click();
  const download=await pendingDownload;
  const pdfPath=path.join(out,'patient-complete-report.pdf');
  await download.saveAs(pdfPath);
  assert.equal((await readFile(pdfPath)).subarray(0,5).toString(),'%PDF-');
  pass('Patient downloads actual complete PDF');

  // Force only AI-availability display, never enable a provider in this fixture.
  await patient.page.route('**/api/v1/config',async route=>{
    const response=await route.fetch(); const value=await response.json();
    await route.fulfill({response,json:{...value,ai_configured:true}});
  });
  let postCount=0;
  let finishAI;
  let aiWait=new Promise(resolve=>{finishAI=resolve;});
  await patient.page.route('**/api/v1/intakes/browser-assessment/ai-report',async route=>{
    if(route.request().method()!=='POST') return route.continue();
    postCount++;
    await aiWait;
    await route.fulfill({status:502,contentType:'application/json',body:JSON.stringify({detail:'Synthetic provider outage. Retry the assessment.'})});
  });
  await patient.page.reload();
  await expect(patient.page.getByRole('button',{name:'Regenerate AI assessment',exact:true})).toBeEnabled();
  assert.equal(postCount,0);
  await patient.page.getByRole('button',{name:'Regenerate AI assessment',exact:true}).click();
  await expect(patient.page.getByText('Updating the AI assessment…',{exact:true})).toBeVisible();
  await expect(patient.page.getByRole('heading',{name:'Possible diagnoses to discuss',exact:true})).toBeVisible();
  await expect(patient.page.getByRole('button',{name:'Approve & share',exact:true})).toBeDisabled();
  finishAI();
  await expect(patient.page.getByText('Synthetic provider outage. Retry the assessment.',{exact:true})).toBeVisible();
  assert.equal(postCount,1);
  await expect(patient.page.getByRole('button',{name:'Regenerate AI assessment',exact:true})).toBeEnabled();
  pass('No generation on refresh; explicit regeneration keeps prior report and shows retryable failure','UI simulation');
  await patient.page.unroute('**/api/v1/intakes/browser-assessment/ai-report');

  // Real sharing preserves the existing assessment and enables only this doctor.
  await patient.page.locator('#doctor-email').selectOption('doctor@example.test');
  await patient.page.locator('.approval-card input[type=checkbox]').check();
  await patient.page.getByRole('button',{name:'Approve & share',exact:true}).click();
  await expect(patient.page.getByText('Shared with doctor',{exact:true}).first()).toBeVisible();
  const shared=await (await doctor.context.request.get(base+'/api/v1/clinician/intakes/browser-assessment')).json();
  assert.equal(shared.ai_report.generated_at,seed.ai_report.generated_at);
  assert(!('messages' in shared));
  await doctor.page.goto(base+'/#/doctor/intake/browser-assessment');
  await expect(doctor.page.getByRole('heading',{name:'AI diagnosis & consultation guidance',exact:true})).toBeVisible();
  await accessible(doctor.page,'doctor desktop');
  await doctor.page.screenshot({path:path.join(out,'doctor-report.png'),fullPage:true});
  await doctor.page.screenshot({path:path.join(out,'doctor-first-screen.png')});
  const doctorDownload=doctor.page.waitForEvent('download');
  await doctor.page.getByRole('button',{name:'Download complete PDF',exact:true}).click();
  await (await doctorDownload).saveAs(path.join(out,'doctor-complete-report.pdf'));
  pass('Approval preserves report; assigned doctor sees and downloads same report');

  const mobile=await pageFor('patient',390);
  await mobile.page.goto(base+'/#/patient/intake/browser-assessment');
  await expect(mobile.page.getByRole('heading',{name:'AI diagnosis & consultation guidance',exact:true})).toBeVisible();
  await accessible(mobile.page,'patient mobile');
  await mobile.page.screenshot({path:path.join(out,'patient-mobile.png'),fullPage:true});
  pass('Report has no horizontal overflow or serious accessibility errors on mobile');

  const revoke=await patient.context.request.post(base+intakeUrl+'/withdraw',{headers:{Origin:base}});
  assert.equal(revoke.status(),200);
  assert.equal((await doctor.context.request.get(base+intakeUrl+'/report.pdf')).status(),404);
  assert.equal((await doctor.context.request.get(base+intakeUrl+'/ai-report')).status(),404);
  assert.equal((await doctor.context.request.get(base+'/api/v1/clinician/intakes/browser-assessment')).status(),404);
  pass('Withdrawal revokes clinician report, record and PDF access');

  const createdResponse=await patient.context.request.post(base+'/api/v1/intakes',{
    headers:{Origin:base},data:{consent:true,workflow_ids:['WF-01'],title:'Synthetic automatic report check'},
  });
  assert.equal(createdResponse.status(),201);
  const created=await createdResponse.json();
  const completed=await patient.context.request.put(base+`/api/v1/intakes/${created.id}/baseline`,{
    headers:{Origin:base},data:{answers:[],complete:true},
  });
  assert.equal(completed.status(),200);
  let autoCalls=0;
  let finishAuto;
  const autoWait=new Promise(resolve=>{finishAuto=resolve;});
  await patient.page.route(`**/api/v1/intakes/${created.id}/ai-report`,async route=>{
    autoCalls++;
    await autoWait;
    await route.fulfill({status:503,contentType:'application/json',body:JSON.stringify({detail:'Synthetic assessment temporarily unavailable.'})});
  });
  await patient.page.goto(base+`/#/patient/intake/${created.id}`);
  await patient.page.getByRole('button',{name:'Generate my summary',exact:true}).click();
  await expect(patient.page.getByText('Preparing your AI assessment…',{exact:true})).toBeVisible();
  await expect(patient.page.getByRole('heading',{name:'Patient preparation summary',exact:true})).toBeVisible();
  assert.equal(autoCalls,1);
  finishAuto();
  await expect(patient.page.getByText('Synthetic assessment temporarily unavailable.',{exact:true})).toBeVisible();
  await expect(patient.page.getByRole('button',{name:'Retry AI assessment',exact:true})).toBeEnabled();
  await patient.page.reload();
  await expect(patient.page.getByRole('button',{name:'Generate AI assessment',exact:true})).toBeEnabled();
  assert.equal(autoCalls,1);
  pass('New summary automatically starts one assessment; failure preserves summary and refresh does not retry','real summary API + simulated AI');
  assert.deepEqual(errors,[]);
  await writeFile(path.join(out,'report.json'),JSON.stringify({passed:true,checks,accessibility:axe,pageErrors:errors},null,2));
  console.log(`${checks.length} checks; ${axe.length} accessibility scans; no page errors.`);
} finally {
  for(const context of contexts) await context.close();
  await browser.close();
}
