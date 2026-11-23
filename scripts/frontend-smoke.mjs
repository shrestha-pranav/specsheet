#!/usr/bin/env node
// Dependency-free behavioral checks. This does not replace rendered browser testing.
import assert from 'node:assert/strict';
import {readFile} from 'node:fs/promises';
import {resolve} from 'node:path';
import vm from 'node:vm';

const root = resolve(import.meta.dirname, '..');
const json = async path => JSON.parse(await readFile(resolve(root, 'docs', path), 'utf8'));
const requests = [];
const elements = new Map();
function element(key) {
  if (!elements.has(key)) elements.set(key, {innerHTML:'', value:'', dataset:{}, addEventListener(){}, focus(){}, scrollIntoView(){}, insertAdjacentHTML(position, html){this.innerHTML += html;}, querySelector:element, querySelectorAll:()=>[]});
  return elements.get(key);
}
const context = vm.createContext({
  URL, URLSearchParams, console, setTimeout, clearTimeout,
  document:{getElementById:element, querySelector: selector => selector.startsWith('meta') ? {content:'test-build'} : element(selector), documentElement:{dataset:{}}},
  window:{addEventListener(){}}, location:{hash:''}, history:{replaceState(){}},
  localStorage:{getItem(){return null;}, setItem(){throw Error('Unexpected storage write');}},
  matchMedia:()=>({matches:false,addEventListener(){}}),
  fetch:async url => {requests.push(url); try { const body = await json(url.split('?')[0]); return {ok:true,json:async()=>body}; } catch (error) { if (error.code === 'ENOENT') return {ok:false,status:404}; throw error; }}
});
const names = ['categories','indexFor','detailFor','displayValue','initialState','categoryStateQuery','productUrl','validatedReturnQuery','returnWithIds','matchFacet','missingIssueUrl','correctionIssueUrl','renderTable','renderProduct','renderCompare','previewOverlay','revisionsMarkup'];
const source = await readFile(resolve(root, 'docs/app.js'), 'utf8');
assert(source.includes('  renderRoute();\n})();'), 'Application bootstrap changed; update harness');
vm.runInContext(source.replace('  renderRoute();\n})();', `  globalThis.test = {${names.join(',')}};\n})();`), context);
const ui = context.test;
const categories = await ui.categories();
assert(!categories.some(c=>c.id === 'power-strips-demo'), 'Demo category must be hidden');
assert(categories.some(c=>c.id === 'power-strips'), 'Real power strips must be visible');
const laptop = categories.find(c=>c.id === 'laptops');
Object.assign(laptop, await json('api/v1/laptops/schema.json'));
const rows = await ui.indexFor(laptop);
assert.equal(rows.length, laptop.count, 'All laptop shards loaded');
assert(laptop.index.length > 1, 'Real multi-shard fixture expected');
assert(!requests.some(url=>url.includes('/products/')), 'Listing must not eagerly fetch details');
assert(requests.every(url=>url.includes('?v=test-build')), 'Fetches must be build-versioned');
const first = rows[0];
await ui.detailFor(laptop.id, first.id);
await ui.detailFor(laptop.id, first.id);
assert.equal(requests.filter(url=>url.includes('/products/')).length, 1, 'Details loaded on demand and cached');

const port = laptop.fields.find(f=>f.key === 'port.usbc_list');
const structured = ui.displayValue({status:'known',value:[{side:'left',protocol:'USB4',usb_gbps:40,pd_in_w:{min:5,max:100},pd_out_w:null,dp_alt:'DP 2.1'},{side:'right',protocol:'USB 3.2',usb_gbps:10,pd_in_w:null,pd_out_w:15,dp_alt:null}]}, port);
assert.match(structured, /<table/);
assert.equal((structured.match(/<tr>/g)||[]).length, 3, 'Header and two separate port rows');
assert.match(structured, /Gbps/);
assert.match(structured, /Unknown/);
assert.doesNotMatch(structured, /\[object Object\]/);
const literal = ui.displayValue({status:'known',value:['2x USB-C (USB4, PD input)','1x USB-C (data only)']}, port);
assert.equal((literal.match(/<li>/g)||[]).length, 2, 'Literal port statements stay separate');
assert.match(ui.displayValue({status:'known',value:['<script>']}, port), /&lt;script&gt;/);
for (const status of ['unknown','conflicted','not_applicable','not_yet_extracted','not_published']) {
  assert.doesNotMatch(ui.displayValue({status,value:null}, {type:'bool'}), />No</);
  assert.equal(ui.matchFacet({specs:{flag:{status,value:null}}}, {key:'flag',type:'bool',facet:{kind:'bool'}}, {f_flag_value:'no'}), false);
}
assert.match(ui.displayValue({status:'known',value:false}, {type:'bool'}), />No</);

const state = ui.initialState(laptop, new URLSearchParams('q=Yoga&brand=Lenovo&page=2&ids=a,b&cols=cpu.model&sort=name&dir=desc'));
const query = ui.categoryStateQuery(state);
assert.equal(new URLSearchParams(query).get('page'), '2');
const productParams = new URLSearchParams(ui.productUrl(laptop.id,first.id,query).split('?')[1]);
assert.equal(ui.validatedReturnQuery(laptop,productParams),query,'Visible return restores working query');
assert.equal(new URLSearchParams(ui.returnWithIds(laptop,query,['a'])).get('ids'),'a');

// Opt-in preview: trusted by default, preview-only rows appear (marked) only when asked; qualifiers/display hints render.
assert(laptop.preview, 'laptops exposes a preview index');
assert(!rows.some(r=>r.unreviewed), 'Trusted listing has no unreviewed rows');
const previewRows = await ui.indexFor(laptop, true);
assert.equal(previewRows.length, laptop.preview.count, 'Preview index loads');
assert.equal(previewRows.filter(r=>r.unreviewed).length, laptop.preview.only_preview, 'Preview-only rows flagged');
assert(['Dell','Apple'].every(b=>previewRows.some(r=>r.brand===b && r.unreviewed)), 'Preview-only brands visible when on');
assert(!rows.some(r=>r.brand==='Dell'), 'Preview-only brands hidden by default');
assert.match(ui.displayValue({status:'known',value:1.65,qualifier:'from'}, {unit:'kg',type:'number'}), /^from 1\.65 kg$/);
assert.match(ui.displayValue({status:'known',value:1000,display:'1 TB'}, {unit:'GB',type:'number'}), /^1 TB$/);
assert.doesNotMatch(ui.displayValue({status:'known',value:1000,display:'1 TB'}, {unit:'GB',type:'number'}), /GB/);
assert(rows.some(r=>r.specs['stor.size']?.display), 'Index display hints reach row specs');
const ps = ui.initialState(laptop, new URLSearchParams('preview=1'));
assert.equal(ps.preview, true); assert.equal(new URLSearchParams(ui.categoryStateQuery(ps)).get('preview'), '1');
assert.equal(ui.initialState(laptop, new URLSearchParams('')).preview, false);
assert.equal(ui.initialState(laptop, new URLSearchParams('')).sort, 'coverage');
const onlyPreview = previewRows.find(r=>r.unreviewed);
const pd = await ui.detailFor(laptop.id, onlyPreview.id, true);
assert(pd.previewOnly, 'Preview-only detail loads from the preview tree');
await assert.rejects(ui.detailFor(laptop.id, onlyPreview.id, false), /404/, 'Trusted mode never serves preview records');

// Revisions: only differing claims, source badges, honest empty state, no revision rows in listings.
const rcat = categories.find(c=>c.id === 'routers'); Object.assign(rcat, await json('api/v1/routers/schema.json'));
const rrows = await ui.indexFor(rcat);
assert(!rrows.some(r=>r.kind==='revision'), 'Revision rows never listed as products');
const modelWithRevs = (await Promise.all(rrows.map(r=>ui.detailFor('routers', r.id)))).find(d=>d.revisions?.some(r=>r.differs?.length>1));
assert(modelWithRevs, 'A router model with revisions exists');
const rev = ui.revisionsMarkup(rcat, modelWithRevs);
assert.match(rev, /Hardware revisions/); assert.match(rev, /source-tier/);
assert.equal((rev.match(/<tr><th scope="row">/g)||[]).length, modelWithRevs.revisions.length, 'One row per revision');
assert.doesNotMatch(rev, /\[object Object\]|undefined/);
assert.match(ui.revisionsMarkup(rcat, {specs:{}, revisions:[{id:'x-v1',label:'V1',specs:{},sources:[],differs:[]}]}), /Nothing known beyond the model/);
assert.equal(ui.revisionsMarkup(rcat, {specs:{}}), '');

const beforeIssue = requests.length;
const issue = new URL(ui.missingIssueUrl('laptops','83DK0002US'));
assert.equal(issue.hostname,'github.com');
assert.equal(issue.searchParams.get('template'),'missing-product.yml');
const payload = JSON.parse(issue.searchParams.get('payload'));
assert.equal(payload.category,'laptops');
assert.equal(payload.query,'83DK0002US');
assert.equal(payload.build,'test-build');
assert(payload.query_norm);
const correction = new URL(ui.correctionIssueUrl(first.id,'cpu.model','Shown value'));
assert.equal(correction.searchParams.get('template'),'field-correction.yml');
assert.equal(requests.length,beforeIssue,'Constructing draft links sends no request');
// Exercise complete template generation against real v1 and legacy detail shapes.
// DOM layout and post-render disclosure behavior still require browser verification.
for (const category of categories) {
  if (category.index) Object.assign(category, await json(`api/v1/${category.id}/schema.json`));
  const categoryRows = await ui.indexFor(category);
  await ui.renderProduct(category, categoryRows[0].id, new URLSearchParams(), 0);
  assert.match(element('main').innerHTML, /detail-grid/, `${category.id}: product rendered`);
  assert.doesNotMatch(element('main').innerHTML, /\[object Object\]/, `${category.id}: no object coercion`);
  await ui.renderCompare(category, new URLSearchParams({ids:categoryRows.slice(0,2).map(r=>r.id).join(',')}), 0);
  assert.match(element('#comparison-table').innerHTML, /compare-table/, `${category.id}: comparison rendered`);
}
console.log(`Frontend behavior smoke passed: ${rows.length} laptop rows; shard loading, lazy detail cache, structured/literal ports, absence semantics, return state, private issue drafts.`);
