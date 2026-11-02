import assert from 'node:assert/strict';
import {createRequire} from 'node:module';
import {readFile,writeFile} from 'node:fs/promises';
import path from 'node:path';
import {fileURLToPath} from 'node:url';
const here=path.dirname(fileURLToPath(import.meta.url));
const require=createRequire(path.resolve(here,'../../frontend/package.json'));
const {chromium}=require('playwright');const {expect}=require('@playwright/test');
const out=path.join(here,'runs/extended-20261102/browser');
const tokens=JSON.parse(await readFile(path.join(out,'tokens.json'),'utf8'));
const selected=JSON.parse(await readFile(path.join(out,'selected.json'),'utf8'));
const base='http://127.0.0.1:8012';
const browser=await chromium.launch({headless:true,executablePath:'/Applications/Google Chrome.app/Contents/MacOS/Google Chrome'});
const results=[],errors=[];
try {
 for(const row of selected){
  const contexts=[];
  for(const role of ['patient','doctor']){
   const ctx=await browser.newContext({viewport:{width:1440,height:1000}});contexts.push(ctx);
   await ctx.addCookies([{name:'preconsult_session',value:tokens[role],url:base,httpOnly:true,sameSite:'Lax'}]);
  }
  const p=await contexts[0].newPage(),d=await contexts[1].newPage();
  p.on('pageerror',e=>errors.push(e.message));d.on('pageerror',e=>errors.push(e.message));
  try {
   await p.goto(`${base}/patient#/patient/intake/${row.id}`);
   await expect(p.locator('.review-document')).toBeVisible();
   for(const width of [1440,390]){
    await p.setViewportSize({width,height:1000});
    await expect.poll(()=>p.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1)).toBe(true);
    await p.screenshot({path:path.join(out,`${row.family}-patient-${width}.png`),fullPage:true});
   }
   await p.setViewportSize({width:1440,height:1000});
   await p.getByRole('checkbox',{name:/I have reviewed this consultation record/}).check();
   const email=p.locator('#doctor-email'); if(await email.count()) await email.fill('doctor@example.test');
   await p.getByRole('button',{name:'Approve & share',exact:true}).click();
   await expect(p.locator('.shared-banner')).toBeVisible();
   await d.goto(`${base}/doctor#/doctor/intake/${row.id}`);
   await expect(d.locator('.review-document')).toBeVisible();
   const pr=await contexts[0].request.get(`${base}/api/v1/intakes/${row.id}`);
   const dr=await contexts[1].request.get(`${base}/api/v1/clinician/intakes/${row.id}`);
   assert.equal(dr.status(),200);const patient=await pr.json(),doctor=await dr.json();
   assert.deepEqual(doctor.summary.synthesis,patient.summary.synthesis);
   for(const width of [1440,390]){
    await d.setViewportSize({width,height:1000});
    await expect.poll(()=>d.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1)).toBe(true);
    await d.screenshot({path:path.join(out,`${row.family}-doctor-${width}.png`),fullPage:true});
   }
   results.push({...row,passed:true});
  }catch(e){results.push({...row,passed:false,error:e.message});}
  finally{for(const ctx of contexts) await ctx.close();}
  console.log(JSON.stringify(results.at(-1)));
 }
}finally{await browser.close();await writeFile(path.join(out,'report.json'),JSON.stringify({mode:'live-result replay; real API and DB; provider disabled during browser run',results,errors},null,2));}
if(results.some(r=>!r.passed)||errors.length)process.exitCode=1;
