import { chromium } from '../../../frontend/node_modules/@playwright/test/index.mjs';
import { readFile, writeFile } from 'node:fs/promises';
import { fileURLToPath } from 'node:url';
import path from 'node:path';
const dir = path.dirname(fileURLToPath(import.meta.url));
const root = path.dirname(dir);
const data = JSON.parse(await readFile(path.join(root,'testcases.json'),'utf8'));
const browser = await chromium.launch({headless:true,executablePath:'/Applications/Google Chrome.app/Contents/MacOS/Google Chrome'});
const ctx = await browser.newContext({viewport:{width:1360,height:1000},deviceScaleFactor:1});
const page = await ctx.newPage();
const errors=[];
page.on('pageerror',e=>errors.push(e.message));
await page.goto(new URL('../START-HERE.html',import.meta.url).href);
await page.screenshot({path:path.join(dir,'guide-desktop.png')});
const result={console_errors:errors,cases:[],screenshots:['source/guide-desktop.png','source/guide-mobile.png','source/guide-case02.png']};
for(const c of data.cases){
 const id=c.id.toLowerCase();
 await page.getByRole('tab',{name:new RegExp(c.id)}).click();
 const panel=page.locator('#'+id);
 const fields=await panel.locator('.question').count();
 if(fields!==c.steps.length)throw new Error('Field count mismatch '+id);
 for(const s of c.steps){
  const article=panel.locator('.question').nth(s.step-1);
  if(await article.locator('.answer').innerText()!==s.text)throw new Error('Text mismatch '+s.key);
 }
 if(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth))throw new Error('Desktop overflow');
 result.cases.push({id:c.id,fields,profile_fields:await panel.locator('.profile-row').count(),text_matches:true});
}
await page.locator('#tc02-baseline').scrollIntoViewIfNeeded();
await page.screenshot({path:path.join(dir,'guide-case02.png')});
// Verify copy handler receives exactly the source answer, without UI headings.
await page.evaluate(()=>Object.defineProperty(navigator,'clipboard',{configurable:true,value:{writeText:async value=>{window.__copied=value}}}));
await page.locator('#tc02 .question').first().getByRole('button',{name:'复制填写内容'}).click();
if(await page.evaluate(()=>window.__copied)!==data.cases[1].steps[0].text)throw new Error('Copy mismatch');
result.copy_handler_passed=true;
await page.getByRole('tab',{name:/TC02/}).focus();
await page.keyboard.press('ArrowLeft');
if(await page.getByRole('tab',{name:/TC01/}).getAttribute('aria-selected')!=='true')throw new Error('Keyboard tab failed');
result.keyboard_tabs_passed=true;
await page.setViewportSize({width:390,height:844});
await page.locator('#tc01-baseline').scrollIntoViewIfNeeded();
await page.screenshot({path:path.join(dir,'guide-mobile.png')});
for(const c of data.cases){
 await page.getByRole('tab',{name:new RegExp(c.id)}).click();
 if(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth))throw new Error('Mobile overflow '+c.id);
}
result.mobile_no_overflow=true;
if(errors.length)throw new Error(errors.join('\n'));
await writeFile(path.join(dir,'html-validation.json'),JSON.stringify(result,null,2)+'\n');
await browser.close();
console.log(JSON.stringify(result));
