#!/usr/bin/env node
// The UI and generated reports use the same authored terms and symptom names.
import { writeFile } from 'node:fs/promises';
import { productResources } from '../frontend/src/product/translations.js';
const locales = ['zh-CN', 'zh-TW', 'ko', 'ja'];
const rows = Object.fromEntries(Object.keys(productResources.en).sort().map(key =>
  [key, locales.map(locale => productResources[locale][key])],
));
await writeFile(new URL('../backend/app/product/locale_catalogue.json', import.meta.url),
  JSON.stringify({ generated_by: 'scripts/build-backend-locales.mjs', locales, rows }, null, 2) + '\n');
console.log(`Generated ${Object.keys(rows).length} authored backend translations.`);
