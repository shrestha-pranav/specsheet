#!/usr/bin/env node
/** Optional Playwright smoke. Serve docs with: python3 -m http.server 3999 -d docs */
import assert from 'node:assert/strict';
import { createRequire } from 'node:module';

let playwright;
try {
  const require = createRequire(import.meta.url);
  playwright = require(process.env.PLAYWRIGHT_MODULE || 'playwright');
} catch (error) {
  if (process.env.PLAYWRIGHT_REQUIRED === '1') throw error;
  console.log(`Browser smoke skipped: Playwright package unavailable (${error.code || error.message})`);
  process.exit(0);
}
let browser;
try {
  browser = await playwright.chromium.launch({headless:true, executablePath:process.env.PLAYWRIGHT_EXECUTABLE_PATH || undefined});
} catch (error) {
  if (process.env.PLAYWRIGHT_REQUIRED === '1') throw error;
  console.log(`Browser smoke skipped: Chromium launch unavailable (${String(error.message).split('\n')[0]})`);
  process.exit(0);
}
try {
  const base = process.env.SPECSHEET_BASE_URL || 'http://localhost:3999/';
  const page = await browser.newPage({viewport:{width:1366,height:900}});
  const errors = [];
  page.on('pageerror', error => errors.push(error.message));
  await page.goto(`${base}#/category/gan-chargers`, {waitUntil:'domcontentloaded'});
  await page.locator('#results-table tbody tr').first().waitFor();
  assert(await page.locator('#results-table tbody tr').count() > 0, 'Chargers table must render rows');
  await page.locator('#product-search').fill('anker');
  assert(await page.locator('#results-table tbody tr').count() > 0, 'Anker search must render rows');
  assert(page.url().includes('q=anker'), 'Search should persist in URL');
  await page.reload();
  await page.locator('#results-table tbody tr').first().waitFor();
  assert.equal(await page.locator('#product-search').inputValue(), 'anker', 'Search should survive reload');
  await page.locator('#results-table tbody tr [data-select]').nth(0).check();
  assert.equal(await page.evaluate(() => document.activeElement?.hasAttribute('data-select')), true, 'Selection should retain keyboard focus');
  await page.locator('#results-table tbody tr [data-select]').nth(1).check();
  await page.getByRole('link', {name:'Compare products'}).click();
  await page.locator('.compare-table tbody tr').first().waitFor();
  assert(await page.locator('.compare-table thead th').count() === 3, 'Comparison should show two products');
  await page.getByLabel('Show differences only').check();
  assert(page.url().includes('diff=1'), 'Differences toggle should persist in URL');
  await page.goto(`${base}#/category/power-strips-demo`, {waitUntil:'domcontentloaded'});
  await page.locator('#results-table tbody tr').first().waitFor();
  assert.equal(await page.locator('#results-table tbody tr').count(), 4, 'Demo category should render four products');
  assert(await page.getByText('Demo data').count() > 0, 'Demo category must be labelled');
  await page.locator('#facet-surge_protection').selectOption('yes');
  assert(await page.locator('#results-table tbody tr').count() > 0, 'Schema bool facet must filter demo products');
  await page.goto(`${base}#/product/power-strips-demo/demo-strip-4`, {waitUntil:'domcontentloaded'});
  await page.locator('.spec-table').first().waitFor();
  assert(await page.getByText('Fictional demo data').count() > 0, 'Demo product must be labelled');
  await page.locator('#theme').selectOption('dark');
  assert.equal(await page.locator('html').getAttribute('data-theme'), 'dark');
  await page.setViewportSize({width:390,height:844});
  await page.goto(`${base}#/category/gan-chargers`, {waitUntil:'domcontentloaded'});
  await page.locator('#results-table tbody tr').first().waitFor();
  assert.equal(await page.locator('.filter-rail > details').evaluate(el => el.open), false, 'Mobile filters should start collapsed');
  await page.goto(`${base}#/product/power-strips-demo/demo-strip-4`, {waitUntil:'domcontentloaded'});
  await page.locator('.spec-table').first().waitFor();
  assert(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth + 1), 'Mobile product page should not overflow viewport');
  await page.goto(`${base}#/category/gan-chargers`, {waitUntil:'domcontentloaded'});
  await page.locator('#results-table tbody tr').first().waitFor();
  assert(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth + 1), 'Mobile category should not overflow viewport');
  assert.equal(errors.length, 0, `Page errors: ${errors.join('; ')}`);
  await page.close();
  console.log('Browser smoke passed: rows, Anker search, URL state, compare, demo schema, dark theme, mobile bounds');
} finally {
  await browser.close();
}
