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
const names = ['facetControl','methodsDiffer','methodsFlag','categories','indexFor','detailFor','displayValue','initialState','categoryStateQuery','productUrl','validatedReturnQuery','returnWithIds','matchFacet','missingIssueUrl','correctionIssueUrl','renderTable','renderProduct','renderCompare','previewOverlay','revisionsMarkup','searchRows','extractIdentifiers','differingFields','cellValue','compareUrl','configTable','evidenceMarkup','valueWithContext','renderPage','reportMiss','loadPresets','presetCard','presetGallery','facetPass','facetActive','pdoVerdict','pdoSection','sizeGridRows','sizeGridMarkup','sendEvent','noteUnknown','pct','inPresetScope','provenance','pendingCorrection','kindBreakdown','fillRequestUrl','disagreeRow'];
const source = await readFile(resolve(root, 'docs/app.js'), 'utf8');
assert(source.includes('  renderRoute();\n})();'), 'Application bootstrap changed; update harness');
vm.runInContext(source.replace('  renderRoute();\n})();', `  globalThis.test = {${names.join(',')}};\n})();`), context);
vm.runInContext(await readFile(resolve(root, 'docs/pages.js'), 'utf8'), context);
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
assert.equal(previewRows.filter(r=>r.unreviewed).length, laptop.preview.only_preview, 'Preview-only rows flagged');
// preview-only brands = brands with unreviewed rows and no trusted row (set changes as policies are approved; Dell laptops became trusted 2026-11-26)
const trustedBrands = new Set(rows.map(r=>r.brand));
const previewOnly = [...new Set(previewRows.filter(r=>r.unreviewed).map(r=>r.brand))].filter(b=>!trustedBrands.has(b));
assert(previewOnly.length > 0, 'Preview-only brands visible when on');
assert(previewOnly.every(b=>!rows.some(r=>r.brand===b)), 'Preview-only brands hidden by default');
assert.match(ui.displayValue({status:'known',value:1.65,qualifier:'from'}, {unit:'kg',type:'number'}), /^from 1\.65 kg$/);
assert.match(ui.displayValue({status:'known',value:1000,display:'1 TB'}, {unit:'GB',type:'number'}), /^1 TB$/);
assert.doesNotMatch(ui.displayValue({status:'known',value:1000,display:'1 TB'}, {unit:'GB',type:'number'}), /GB/);
assert(rows.some(r=>r.specs['stor.size']?.display), 'Index display hints reach row specs');
const ps = ui.initialState(laptop, new URLSearchParams('preview=1'));
assert.equal(ps.preview, true); assert.equal(new URLSearchParams(ui.categoryStateQuery(ps)).get('preview'), '1');
assert.equal(ui.initialState(laptop, new URLSearchParams('')).preview, false);
assert.equal(ui.initialState(laptop, new URLSearchParams('')).sort, 'coverage');
// Critique 2 #1: preview is a strict union for every profile-driven category; accepted facts survive; candidates are text-labelled.
for (const id of ['laptops','monitors','power-strips','routers','ssds']) {
  const cat = categories.find(c=>c.id === id); Object.assign(cat, await json(`api/v1/${id}/schema.json`));
  const trustedRows = await ui.indexFor(cat), unionRows = await ui.indexFor(cat, true);
  const unionIds = new Set(unionRows.map(r=>r.id));
  assert(trustedRows.every(r=>unionIds.has(r.id)), `${id}: every trusted id survives preview`);
  assert.equal(unionRows.length, trustedRows.length + unionRows.filter(r=>r.unreviewed).length, `${id}: union = trusted + preview-only`);
  const byId = new Map(unionRows.map(r=>[r.id,r]));
  for (const r of trustedRows.slice(0, 400)) for (const [k,spec] of Object.entries(r.specs)) if (spec.status === 'known') assert.deepEqual(byId.get(r.id).specs[k].value, spec.value, `${id}: accepted value kept`);
  assert(!trustedRows.some(r=>r.unreviewed || r.candidates), `${id}: trusted listing untouched by preview merge`);
}
const withCand = previewRows.find(r=>Object.keys(r.candidates || {}).length);
if (withCand) { const key = Object.keys(withCand.candidates)[0]; const f = laptop.fields.find(x=>x.key===key) || {key,label:key,type:'text'}; assert.match(ui.cellValue(laptop, withCand, f), /Unreviewed candidate/, 'Candidate text-labelled in cell'); }

// Critique 2 #2: retail-title search.
assert(ui.extractIdentifiers('Lenovo Yoga 7 2-in-1 14AGP11 83TD000US laptop OLED').some(i=>i.value==='83TD000US'), 'MTM extracted from title');
const fixture = [{id:'t1',brand:'Lenovo',name:'Yoga 7 2-in-1 14AGP11',variant_label:'x',identifiers:[{scheme:'mtm',value:'83TD000US'}],search:[]},{id:'t2',brand:'Lenovo',name:'Yoga 7 2-in-1 14AGP11',identifiers:[{scheme:'mtm',value:'83TD0000US'}],search:[]},{id:'t3',brand:'Dell',name:'XPS',identifiers:[{scheme:'mtm',value:'9999'}],search:[]}];
const hit = ui.searchRows(fixture, 'Lenovo Yoga 7 2-in-1 14AGP11 83TD000US laptop OLED');
assert.equal(hit.matches.get('t1').rank, 0, 'Exact identifier from retail title ranks first');
assert(!hit.matches.has('t3'));
assert.equal(ui.searchRows(laptop.rows || rows, 'Lenovo 83JQ0001US').matches.get('lenovo-83jq0001us')?.rank, 0, 'Brand + MTM finds the record');
const near = ui.searchRows(rows, 'Lenovo Yoga 7 2-in-1 14AGP11 83TD000US laptop OLED');
assert(near.matches.size > 0 && [...near.matches.values()].every(m=>m.why), 'Near-miss title returns explained candidates, not an absence claim');
assert.equal(ui.searchRows(rows, 'zzqq nothing').matches.size, 0);
assert.equal(ui.searchRows(rows, '83JQ0001US').matches.size, 1);
const noHit = (() => { const st = ui.initialState(laptop, new URLSearchParams('q=zzqq%20k9k9k9')); elements.get('#results-table') || element('#results-table'); ui.renderTable(laptop, [], st, '', {found:ui.searchRows(rows, st.q), total:rows.length, baseCount:0}); return element('#results-table').innerHTML; })();
assert.match(noHit, /No match for this search/); assert.doesNotMatch(noHit, /Not in the catalogue/); assert.match(noHit, /Prepare GitHub issue draft/); assert.match(noHit, /Public if submitted/);

// Critique 2 #3/#4: configuration grid selects and launches comparison; differences span all tiers.
const sib = rows.filter(r=>r.parent_id==='lenovo-83jq');
assert(sib.length >= 4, '83JQ siblings indexed');
const diffs = ui.differingFields(laptop, sib);
assert(diffs.some(f=>f.key==='sw.os' || f.key==='input.pen'), 'Non-core differences (OS / pen) are disclosed');
const grid = ui.configTable(laptop, sib, diffs.slice(0,5), new Set(['lenovo-83jq0002us']), '', true);
assert.match(grid, /data-config="lenovo-83jq0002us"[^>]*checked/); assert.match(grid, /MTM \/ part number/); assert.match(grid, /83JQ000KUS/);
const launch = ui.compareUrl('laptops', ['lenovo-83jq0002us','lenovo-83jq000kus'], false, query, {model:'lenovo-83jq'});
assert.match(launch, /^#\/compare\/laptops\?ids=lenovo-83jq0002us%2Clenovo-83jq000kus/); assert.match(launch, /model=lenovo-83jq/);
await ui.renderCompare(laptop, new URLSearchParams({ids:'lenovo-83jq0002us,lenovo-83jq000kus',model:'lenovo-83jq',diff:'1',detail:'1'}), 0);
assert.match(element('main').innerHTML, /Back to model configurations/, 'Compare returns to the model');
const cmp = element('#comparison-table').innerHTML;
assert.match(cmp, /Claims differ/); assert.doesNotMatch(cmp, /No differences in the recorded schema/);
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

// Round 4 record semantics: alternatives with basis/mode/source, unknown + alternatives, headline qualifiers, revision applicability.
{
  const rec = async (cat, id) => json(`api/v1/${cat}/products/${id}.json`);
  const fieldOf = async (cat, key) => (await json(`api/v1/${cat}/schema.json`)).fields.find(f => f.key === key) || {key};
  const mon = await rec('monitors', 'asus-be249cgn');
  const pw = mon.specs['pwr.typical'];
  assert.equal(pw.status, 'unknown');
  const pwHtml = ui.valueWithContext(pw, await fieldOf('monitors', 'pwr.typical'), mon.sources);
  assert.match(pwHtml, /No single value/); assert.match(pwHtml, /not comparable/);
  assert.match(pwHtml, /ENERGY STAR on-mode test/); assert.match(pwHtml, /14\.83/); assert.match(pwHtml, /14\.93/);
  assert.equal((pwHtml.match(/class="alt-item"/g) || []).length, 2); assert.match(pwHtml, /href="https?:/);
  const hdr = await rec('monitors', 'acer-x27');
  const hdrHtml = ui.valueWithContext(hdr.specs['hdr.vesa_tier'], await fieldOf('monitors', 'hdr.vesa_tier'), hdr.sources);
  assert.match(hdrHtml, /DisplayHDR CTS: v1\.0/); assert.match(hdrHtml, /DisplayHDR CTS: v1\.2/); assert.match(hdrHtml, /True Black 400/);
  const synth = ui.valueWithContext({status:'known', value:100, qualifier:'up_to', alternatives:[{value:90, kind:'measured', qualifier:'approx', measurement_mode:'sustained', sources:['s1']}]}, {key:'x', unit:'W'}, [{id:'s1', url:'https://example.com/a', label:'Example'}]);
  assert.match(synth, /up to 100 W/); assert.match(synth, /approx\. 90 W/); assert.match(synth, /Mode: sustained/); assert.match(synth, /Measured/); assert.match(synth, />Example</);
  const ssd = await rec('ssds', 'samsung-mu-pc1t0h-am');
  assert.match(ui.displayValue({status:'known', value:7450, unit:'MB/s', qualifier:'up_to'}, {key:'perf.seq_read', unit:'MB/s'}), /up to 7,450 MB\/s/);
  assert.match(ui.valueWithContext(ssd.specs['perf.seq_read'], await fieldOf('ssds', 'perf.seq_read'), ssd.sources), /up to 1,050 MB\/s/);
  const tp = await rec('routers', 'tp-link-archer-ax10');
  const all = ui.valueWithContext(tp.specs['wifi.generation'], await fieldOf('routers', 'wifi.generation'), tp.sources);
  const unspec = ui.valueWithContext(tp.specs['wifi.ofdma'], await fieldOf('routers', 'wifi.ofdma'), tp.sources);
  assert.match(all, /Applies to all hardware revisions/); assert.match(unspec, /Revision not specified/);
  assert.doesNotMatch(pwHtml + hdrHtml + synth + all, /\[object Object\]|undefined/);
}

// Round 5 UI: port table, LiDAR facet alias, methods-differ labels.
{
  const pb = categories.find(c=>c.id === 'power-banks'); Object.assign(pb, await json('api/v1/power-banks/schema.json'));
  const rv = categories.find(c=>c.id === 'robot-vacuums'); Object.assign(rv, await json('api/v1/robot-vacuums/schema.json'));
  const portsField = pb.fields.find(f=>f.key === 'out.ports');
  const pbRec = await json('api/v1/power-banks/products/iniu-p73-e1.json');
  const portHtml = ui.displayValue(pbRec.specs['out.ports'], portsField);
  assert.match(portHtml, /port-table/); assert.match(portHtml, /<th scope="col">Connector<\/th>/); assert.match(portHtml, /Wireless/); assert.match(portHtml, /15 W/); assert.match(portHtml, /5V3A 9V3A/);
  assert.equal((portHtml.match(/<table/g)||[]).length, 1); assert.doesNotMatch(portHtml, /\[object Object\]|undefined/);
  assert(pb.fields.some(f=>f.label === 'All-ports simultaneous output') && pb.fields.some(f=>f.label === 'Best single-port output'), 'New field labels published');
  const navField = rv.fields.find(f=>f.key === 'nav.type');
  const navRow = v => ({specs:{'nav.type':{status:'known',value:v}}});
  assert.equal(ui.matchFacet(navRow('dtof'), navField, {'f_nav.type_value':'lidar'}), true, 'LiDAR filter includes dToF');
  assert.equal(ui.matchFacet(navRow('lidar'), navField, {'f_nav.type_value':'dtof'}), false, 'dToF filter stays strict');
  assert.equal(ui.matchFacet(navRow('vslam_camera'), navField, {'f_nav.type_value':'lidar'}), false);
  assert.match(ui.facetControl ? ui.facetControl(navField, [], {filters:{}}) : 'lidar (incl. dtof)', /lidar \(incl\. dtof\)/);
  const suction = rv.fields.find(f=>f.key === 'clean.suction_pa'), runtime = rv.fields.find(f=>f.key === 'bat.runtime_min');
  const k = (value, basis) => ({status:'known', value, basis});
  assert.equal(ui.methodsDiffer([k(30000,{claim_basis:'mfr_in_house_lab'}), k(25000,{claim_basis:'mfr_unstated'})], suction), true);
  assert.equal(ui.methodsDiffer([k(30000,{claim_basis:'mfr_unstated'}), k(25000,{})], suction), false, 'Missing basis equals unstated');
  assert.equal(ui.methodsDiffer([k(30000,{claim_basis:'mfr_in_house_lab'}), k(25000,{claim_basis:'mfr_in_house_lab'})], suction), false);
  assert.equal(ui.methodsDiffer([k(180,{claim_basis:'mfr_unstated',power_mode:'quiet'}), k(200,{claim_basis:'mfr_unstated',power_mode:'max'})], runtime), true, 'power_mode counts for runtime');
  assert.equal(ui.methodsDiffer([k(1,{claim_basis:'mfr_unstated'}), k(2,{claim_basis:'mfr_in_house_lab'})], {key:'x',conditions:[]}), false, 'Only claim_basis/power_mode fields');
  assert.match(ui.methodsFlag([k(1,{claim_basis:'mfr_in_house_lab'}), k(2,{})], suction), /methods differ/);
  await ui.renderCompare(rv, new URLSearchParams({ids:'dreame-aqua10-roller-ae,dreame-aqua10-roller'}), 0);
  const rvCmp = element('#comparison-table').innerHTML;
  assert.match(rvCmp, /methods-flag/); assert.match(rvCmp, /manufacturer in-house lab/);
  const rvRows = await ui.indexFor(rv);
  const pair = ['dreame-aqua10-roller-ae','dreame-aqua10-roller'].map(id => rvRows.find(r=>r.id === id));
  pair[0].specs['clean.suction_pa'] = {...pair[0].specs['clean.suction_pa'], basis:{claim_basis:'mfr_in_house_lab'}};
  const st = ui.initialState(rv, new URLSearchParams('cols=clean.suction_pa')); st.ids = pair.map(r=>r.id);
  element('#results-table'); ui.renderTable(rv, pair, st, '', {found:{identifiers:[],terms:[],matches:new Map()}, total:2, baseCount:2, compared:pair});
  assert.match(element('#results-table').innerHTML, /methods-flag/, 'Grid marks selected products whose basis differs');
  ui.renderTable(rv, pair, {...st, ids:[]}, '', {found:{identifiers:[],terms:[],matches:new Map()}, total:2, baseCount:2, compared:[]});
  const flagged = element('#results-table').innerHTML.match(/methods-flag/g) || [];
  assert.equal(flagged.length, 1, 'Grid flags only the non-default-basis cell, even with nothing selected; default cells get none');
  // Index carries basis: selecting rows must not fetch detail records to learn it.
  const detailsBefore = requests.filter(url=>url.includes('/robot-vacuums/products/')).length;
  const solo = ui.initialState(rv, new URLSearchParams('cols=clean.suction_pa')); element('#results-table');
  ui.renderTable(rv, [pair[1]], solo, '', {found:{identifiers:[],terms:[],matches:new Map()}, total:1, baseCount:1, compared:[]});
  assert.doesNotMatch(element('#results-table').innerHTML, /methods-flag/, 'A single row has nothing to differ from');
  assert.equal(requests.filter(url=>url.includes('/robot-vacuums/products/')).length, detailsBefore);
}

// Round 6 UI: bundles on a model, package detail pages.
{
  const ps = categories.find(c=>c.id === 'power-stations'); Object.assign(ps, await json('api/v1/power-stations/schema.json'));
  const model = await json('api/v1/power-stations/products/ecoflow-efdelta3.json');
  assert(model.bundles?.length, 'Fixture model has bundles');
  await ui.renderProduct(ps, 'ecoflow-efdelta3', new URLSearchParams(), 0);
  await new Promise(resolve => setTimeout(resolve, 20));
  const html = element('.detail-main').innerHTML;
  assert.match(html, /Sold as bundles/); assert.match(html, /D3-2/); assert.match(html, /2 × <a href="#\/product\/power-stations\/ecoflow-efdelta3/);
  assert.match(html, /1 × 100W Flexible Solar Panel|100W Flexible Solar Panel/); assert.match(html, /href="#\/product\/power-stations\/ecoflow-d3-2"/);
  assert.equal((html.match(/<table/g)||[]).length, 0, 'Bundles are a flat list');
  assert.doesNotMatch(html, /\[object Object\]|undefined/);
  await ui.renderProduct(ps, 'ecoflow-d3-2', new URLSearchParams(), 0);
  const pkg = element('main').innerHTML;
  assert.match(pkg, /2 × <a href=/); assert.match(pkg, /D3-2/); assert.match(pkg, /inherits no specs; see member models/);
  assert.doesNotMatch(pkg, /detail-grid|spec-table|\[object Object\]/);
}

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
  let categoryRows = await ui.indexFor(category);
  const pv = !categoryRows.length;          // r11 A2-appl: a category whose policies are all pending is preview-only
  if (pv) categoryRows = await ui.indexFor(category, true);
  await ui.renderProduct(category, categoryRows[0].id, new URLSearchParams(pv ? 'preview=1' : ''), 0);
  assert.match(element('main').innerHTML, /detail-grid/, `${category.id}: product rendered`);
  assert.doesNotMatch(element('main').innerHTML, /\[object Object\]/, `${category.id}: no object coercion`);
  await ui.renderCompare(category, new URLSearchParams({ids:categoryRows.slice(0,2).map(r=>r.id).join(','), ...(pv ? {preview:'1'} : {})}), 0);
  assert.match(element('#comparison-table').innerHTML, /compare-table/, `${category.id}: comparison rendered`);
}
// A3 r8 / A4: certification-only listings are opt-in, flat, off by default; preview never relabels them as unreviewed.
{
  const ap = categories.find(c=>c.id === 'air-purifiers');
  if (ap?.certification_only?.index?.length) {
    Object.assign(ap, await json('api/v1/air-purifiers/schema.json'));
    const def = await ui.indexFor(ap), withCert = await ui.indexFor(ap, false, true);
    assert.equal(withCert.length, def.length + ap.certification_only.count, 'certonly adds exactly the certification-only rows');
    assert(!def.some(r=>r.certonly), 'default listing excludes certification-only rows');
    assert(withCert.filter(r=>r.certonly).every(r=>!r.unreviewed), 'certification-only rows are trusted, not unreviewed');
    const pv = await ui.indexFor(ap, true), pvCert = await ui.indexFor(ap, true, true);
    assert(!pv.some(r=>r.unreviewed && r.in_trusted), 'preview without the toggle never labels trusted certonly rows unreviewed');
    assert.equal(pvCert.filter(r=>r.certonly).length, ap.certification_only.count, 'preview + certonly keeps every certonly row');
    assert(!pvCert.some(r=>r.certonly && r.unreviewed), 'preview + certonly: none unreviewed');
    assert.equal(ui.initialState(ap, new URLSearchParams('')).certonly, false, 'toggle off by default');
    assert.equal(ui.initialState(ap, new URLSearchParams('certonly=1')).certonly, true);
    assert.match(ui.categoryStateQuery(ui.initialState(ap, new URLSearchParams('certonly=1'))), /certonly=1/, 'toggle persists in the URL');
    const certRow = withCert.find(r=>r.certonly);
    await ui.renderProduct(ap, certRow.id, new URLSearchParams(), 0);
    assert.match(element('main').innerHTML, /Certification-only listing/, 'detail shows the certification-only note');
  }
  const lp = categories.find(c=>c.id === 'laptops');
  assert.equal(ui.initialState(lp, new URLSearchParams('certonly=1')).certonly, false, 'category without the rule ignores certonly');
}
// Legal pages, brand and contact placeholders (A4 site-legal).
{
  const site = await json('site.json');
  for (const kind of ['terms','privacy','sources','about']) {
    await ui.renderPage(kind, 0);
    const html = element('main').innerHTML;
    assert.match(html, new RegExp(site.legal_status), `${kind}: marked as draft`);
    assert.doesNotMatch(html, /\[object Object\]|undefined/, `${kind}: no coercion artefacts`);
    assert.doesNotMatch(html, /\$\d|per month|subscription|x402/i, `${kind}: no pricing or payment detail`);
  }
  await ui.renderPage('terms', 0);
  assert.match(element('main').innerHTML, /paid tier is coming later/i);
  await ui.renderPage('sources', 0);
  assert.match(element('main').innerHTML, /github\.com\/shrestha-pranav\/specsheet\/issues/, 'takedown contact falls back to GitHub issues while email_enabled is false');
  assert.doesNotMatch(element('main').innerHTML, /@knownspec\.com/, 'no placeholder-domain email published before the domain exists');
  assert.match(element('main').innerHTML, /ENERGY STAR/, 'sources list generated from the policy file');
  {
    const html = element('main').innerHTML;
    assert.doesNotMatch(html, /None listed/, 'sources: granted list is populated from sources.json (granted/facts_only shape)');
    assert.match(html, /Licensed with permission/); assert.match(html, /Shown as facts with links, not licensed by us/);
    assert.match(html, /Required attribution: “Source: U\.S\. EPA ENERGY STAR”/);
    assert.match(html, /within 7 days of a valid request/);
    assert.match(html, /Values under our licence/, 'sources: coverage table from coverage.json');
    for (const kind of ['terms','sources','about']) { await ui.renderPage(kind, 0); assert.doesNotMatch(element('main').innerHTML, /public domain/i, `${kind}: no public-domain claim`); }
    await ui.renderPage('terms', 0);
    assert.match(element('main').innerHTML, /grant no licence over them/);
    const rec = sources => ({record_format:true, sources});
    const spec = {sources:['a']};
    assert.match(ui.evidenceMarkup(rec([{id:'a', url:'https://data.energystar.gov/x', label:'ES', licence_grant:true}]), spec), />ODbL</, 'detail marker: granted source');
    assert.match(ui.evidenceMarkup(rec([{id:'a', url:'https://example.com/x', label:'Maker', licence_grant:false}]), spec), /facts only, source terms apply/, 'detail marker: facts only');
    assert.doesNotMatch(ui.evidenceMarkup(rec([{id:'a', url:'https://example.com/x', label:'Old'}]), spec), /licence-mark/, 'no marker without the flag');
  }
  assert(site.api_origin === '' || /^https:/.test(site.api_origin), 'api_origin empty (beacon off) or https');
  ui.reportMiss('laptops', 'zzz no such thing');   // no api_origin configured: must be a silent no-op
}

// D8 gate from index rows alone. `by` filters are judged with the app's own matchFacet semantics: strict miss and lenient miss = a known value rules it out.
function d8Gate(preset, all, facets, scope, minFill = preset.min_fill ?? 0.8, minBrands = preset.min_brands ?? scope.min_brands ?? 2) {
  const filters = preset.filters || {}, require = preset.require || [];
  const keys = [...new Set([...Object.keys(filters).filter(k => filters[k] !== '').map(k => k.match(/^f_(.+)_(min|max|value)$/)[1]), ...require])];
  const pool = all.filter(r => ui.inPresetScope(r, scope));
  const ruledOut = (r, key) => { const own = Object.fromEntries(Object.entries(filters).filter(([k]) => k.startsWith(`f_${key}_`))); const f = facets.filter(x => x.key === key); return !ui.facetPass(r, f, own, true); };
  const by = preset.scope?.by || [];
  const out = keys.map(key => { const pop = pool.filter(r => !by.some(b => b !== key && ruledOut(r, b)) && r.specs[key]?.status !== 'not_applicable'); return {key, pop, known:pop.filter(r => r.specs[key]?.status === 'known').length, total:pop.length}; });
  let covered = null;
  for (const k of out) { const have = new Set(k.pop.filter(r => r.specs[k.key]?.status === 'known' && r.brand).map(r => r.brand)); covered = covered ? new Set([...covered].filter(b => have.has(b))) : have; }
  const coveredList = [...(covered || [])].sort();
  return {pool, keys:out, covered:coveredList, passes:out.every(k => k.total && k.known / k.total >= minFill) && coveredList.length >= minBrands};
}
// ---- killer-query presets (A4, 2026-11-24): data-driven gallery, build-time fill gate, unknown-might-match, PDO pill, size grid, beacons off
{
  const data = await ui.loadPresets();
  assert(data.presets.length >= 6 && data.presets.length <= 14, 'presets: 6-14 cards from presets.json');
  const src = await json('presets.json');
  assert.deepEqual(data.presets.map(p => p.id), src.presets.map(p => p.id), 'built presets.json carries every source preset (no hard-coded list in app.js)');
  assert(!/ram-upgradable|no-pwm-usbc-monitor/.test(source), 'preset ids are data, never hard-coded in app.js');
  for (const preset of data.presets) {
    const cat = categories.find(c => c.id === preset.category);
    if (!cat.fields) Object.assign(cat, await json(`api/v1/${cat.schema}`));
    const all = await ui.indexFor(cat);
    const gateKeys = preset.gate.keys.map(k => k.key);
    const facets = cat.fields.filter(f => f.facet), filters = preset.filters || {};
    // The D8 gate must be re-derived from the index alone (independently of scripts/presets.py): tiers `t`, lifecycle, by-filters, not_applicable.
    const d = d8Gate(preset, all, facets, preset.gate.scope);
    for (const k of preset.gate.keys) { const mine = d.keys.find(item => item.key === k.key); assert.deepEqual([k.known, k.total], [mine.known, mine.total], `${preset.id}: ${k.key} known/in-scope population matches the index`); }
    assert.equal(d.pool.length, preset.gate.scope.in_scope, `${preset.id}: in_scope matches`);
    assert.equal(all.length, preset.gate.scope.category_total, `${preset.id}: category_total matches`);
    assert.deepEqual(d.covered, [...preset.gate.scope.covered_brands].sort(), `${preset.id}: covered brands match`);
    assert.equal(preset.gate.passes, d.passes, `${preset.id}: gate = every key >= min_fill and covered brands >= min_brands`);
    assert.equal(preset.gate.passes, preset.gate.fill >= preset.min_fill && preset.gate.scope.covered_brands.length >= preset.gate.min_brands);
    // Count parity with scripts/presets.py over the in-scope population: strict = matches, lenient = matches + unknown-might-match.
    const strict = d.pool.filter(r => ui.facetPass(r, facets, filters, false)).length, lenient = d.pool.filter(r => ui.facetPass(r, facets, filters, true)).length;
    assert.equal(strict, preset.count.matches, `${preset.id}: matches agree with build`);
    assert.equal(lenient - strict, preset.count.maybe, `${preset.id}: unknown-might-match agrees with build`);
    // r2: the app's "sources disagree" tag covers exactly presets.py's disagree bucket (conflicted status included), the rest read "Unknown value".
    const maybeRows = d.pool.filter(r => !ui.facetPass(r, facets, filters, false) && ui.facetPass(r, facets, filters, true));
    assert.equal(maybeRows.filter(r => ui.disagreeRow(r, facets, filters)).length, preset.count.disagree, `${preset.id}: sources-disagree rows agree with build`);
    assert.equal(preset.count.out_of_scope, all.length - d.pool.length, `${preset.id}: out_of_scope agrees`);
    const card = ui.presetCard(preset);
    if (preset.gate.passes) assert.match(card, new RegExp(`href="#/category/${preset.category}\\?preset=${preset.id}"`), `${preset.id}: passing card opens the preset`);
    else {
      assert.match(card, /Help fill this: \d+ of \d+ known/, `${preset.id}: failing card asks for help`);
      assert(!card.includes(`?preset=${preset.id}"><`) && !/class="preset-card"/.test(card), `${preset.id}: a failing preset is never a confident card`);
      assert(card.includes(preset.gate.label), `${preset.id}: names the missing field`);
      if (preset.gate.missing_brands.length) assert(card.includes(preset.gate.missing_brands[0].brand), `${preset.id}: names a brand we lack`);
    }
    assert(gateKeys.length > 0);
  }
  // Showcase row = passing presets only; failing ones sit in the help-us-fill row. The gate decides, never a hard-coded id.
  {
    const html = ui.presetGallery(data);
    const row = name => (html.split(`data-preset-row="${name}"`)[1] || '').split('data-preset-row=')[0];
    for (const p of data.presets) assert(row(p.gate.passes ? 'showcase' : 'help').includes(`data-preset="${p.id}"`) && !row(p.gate.passes ? 'help' : 'showcase').includes(`data-preset="${p.id}"`), `${p.id}: in the ${p.gate.passes ? 'showcase' : 'help-us-fill'} row`);
  }
  // A 0%-fill key always fails. Data-independent since A2 preset fill (2026-11-24) filled usb.usbc_inputs (was the live 0% example).
  for (const p of data.presets.filter(p => p.gate.keys.some(k => k.known === 0 && k.total > 0))) assert(!p.gate.passes, `${p.id}: a 0%-fill key fails the gate`);
  // D8 synthetic cases: unknown stays in, a key is not scoped by itself, min_brands=2 fails at 1 brand with 100% fill.
  const synth = {fields:[{key:'a', type:'number', facet:{kind:'range'}}, {key:'b', type:'bool', facet:{kind:'bool'}}]};
  const sf = synth.fields, mk = (brand, spec, extra = {}) => ({brand, t:['manufacturer'], lifecycle:'current', specs:spec, ...extra});
  const k = (value) => ({status:'known', value});
  const P = {id:'p', filters:{f_a_min:'10', f_b_value:'yes'}, scope:{by:['a']}};
  const sc = {sources:['manufacturer'], include_discontinued:false};
  let g = d8Gate(P, [mk('X', {a:k(20), b:k(true)}), mk('X', {a:k(5)}), mk('X', {})], sf, sc, 0.8, 1);
  assert.deepEqual(g.keys.map(i => [i.key, i.known, i.total]), [['a', 2, 3], ['b', 1, 2]], 'a=5 rules the row out of b (known), the row with unknown a stays in; a is not scoped by itself');
  assert.equal(d8Gate(P, [mk('X', {a:k(20), b:k(true)}), mk('X', {})], sf, sc, 0.8, 1).keys[1].total, 2, 'unknown a stays in the b population');
  assert.equal(d8Gate(P, [mk('X', {a:k(20), b:k(true)}), mk('X', {a:k(20), b:{status:'not_applicable'}})], sf, sc, 0.8, 1).keys[1].total, 1, 'not_applicable leaves the key denominator');
  const full = [mk('X', {a:k(20), b:k(true)}), mk('X', {a:k(30), b:k(true)})];
  assert.equal(d8Gate(P, [mk('X', {a:k(20)}), mk('Y', {a:k(30)})], sf, sc, 0.8, 1).passes, false, 'a 0%-fill key fails the gate');
  assert.equal(d8Gate(P, full, sf, sc, 0.8, 1).passes, true);assert.equal(d8Gate(P, full, sf, sc, 0.8, 2).passes, false, 'min_brands=2 fails at 1 brand even at 100% fill');
  assert.equal(d8Gate(P, [...full, mk('Y', {a:k(20), b:k(true)})], sf, sc, 0.8, 2).passes, true, 'two covered brands pass');
  assert.equal(d8Gate(P, [...full, mk('Y', {a:k(20)}, {t:['regulatory']})], sf, sc, 0.8, 1).pool.length, 2, 'row without a maker-tier source is out of scope');
  assert.equal(d8Gate(P, [...full, mk('Y', {a:k(20)}, {lifecycle:'discontinued'})], sf, sc, 0.8, 1).pool.length, 2, 'discontinued is out of scope');
  assert.equal(d8Gate(P, [...full, mk('Y', {a:k(20)}, {lifecycle:'unknown'})], sf, sc, 0.8, 1).pool.length, 3, 'unknown lifecycle stays in');
  // Synthetic: the gate is data, so a preset at exactly min_fill passes and 1 row short fails.
  const fake = fill => ({id:'x', category:'laptops', category_name:'Laptops', title:'T', count:{matches:3, maybe:1, total:10}, min_fill:0.8, gate:{passes:fill >= 0.8, fill, min_fill:0.8, label:'Field', known:Math.round(fill * 10), total:10, missing_brands:[{brand:'Acme', rows:2}], missing_brand_count:1, scope:{basis:'Maker pages. More.', sources:['manufacturer'], include_discontinued:false, in_scope:10, category_total:14, covered_brands:['Acme','Beta'], excluded:{source_tier:3, discontinued:1, by:{}}, not_covered:[{brand:'Gamma', rows:4, reason:'no maker source'}]}}});
  assert.match(ui.presetCard(fake(0.8)), /3 matches<\/strong>, 1 more unknown, might match/);
  assert.match(ui.presetCard(fake(0.7)), /Help fill this: 7 of 10 known.*Acme/s);
  for (const f of [0.8, 0.7]) assert.match(ui.presetCard(fake(f)), /Covers 2 brands: Acme, Beta · 10 of 14 laptops in scope/, 'every card carries the coverage line');
  assert.match(ui.presetCard(fake(0.8)), /Maker pages\./, 'and the basis');
  assert.equal(ui.pct(0.796), '79.6%', 'a failing 79.6% never displays as 80%');
  // The unknown filter: unknown is never no, and only unknown rows are "might match".
  const bool = {key:'b', type:'bool', facet:true}, unknownRow = {specs:{}}, noRow = {specs:{b:{status:'known', value:false}}}, yesRow = {specs:{b:{status:'known', value:true}}};
  assert.equal(ui.facetPass(unknownRow, [bool], {f_b_value:'yes'}, false), false); assert.equal(ui.facetPass(unknownRow, [bool], {f_b_value:'yes'}, true), true, 'unknown might match');
  assert.equal(ui.facetPass(noRow, [bool], {f_b_value:'yes'}, true), false, 'known No is never lenient');
  assert.equal(ui.facetPass(yesRow, [bool], {f_b_value:'yes'}, false), true);
  assert.equal(ui.facetPass(unknownRow, [bool], {f_b_value:'unknown'}, false), true, 'explicit unknown filter');
  // PDO pill
  const cfg = data.renderers.pdo_pill;
  const rec = (ports, pps) => ({specs:{'out.ports':{status:'known', value:ports}, ...(pps === undefined ? {} : {'pd.pps':{status:'known', value:pps}})}});
  assert.equal(ui.pdoVerdict(rec([{name:'C1', direction:'out', pps:'5-11V 6.1A'}]), cfg).overall, 'yes');
  assert.equal(ui.pdoVerdict(rec([{name:'C1', direction:'out', pps:'5-11V 3A'}, {name:'C2', direction:'out', pps:'3.3-11V 3A'}]), cfg).overall, 'no');
  assert.equal(ui.pdoVerdict(rec([{name:'C1', direction:'out', pps:'5-11V 3A'}, {name:'C2', direction:'out', pps:null}]), cfg).overall, 'unknown', 'a port without PPS data is unknown, not no');
  assert.equal(ui.pdoVerdict(rec([{name:'C1', direction:'out', pps:null}], false), cfg).overall, 'no', 'product states no PPS');
  assert.equal(ui.pdoVerdict({specs:{}}, cfg).overall, 'unknown');
  assert.match(ui.pdoSection({specs:{}}, cfg), /Unknown is not “No”/);
  // Size grid: unknown stays a count
  const grid = ui.sizeGridRows([{specs:{'gen.size_class':{status:'known', value:65}, 'panel.display_tech':{status:'known', value:'oled'}}}, {specs:{'gen.size_class':{status:'known', value:65}}}, {specs:{}}], data.renderers.size_grid);
  assert.equal(JSON.stringify(grid.map(g => g.size)), '[65,null]'); assert.equal(JSON.stringify(grid[0].panel), '[["oled",1],["unknown",1]]'); assert.equal(grid[0].zones.unknown, 2);
  assert.match(ui.sizeGridMarkup([{specs:{}}], data.renderers.size_grid), /Size unknown/);
  // Beacons: off until api_origin is set; the page-level helpers are silent no-ops and send text/plain when on
  assert.equal((await json('site.json')).api_origin, '', 'GitHub Pages: api_origin empty');
  assert.equal(ui.sendEvent('request_click', 'laptops'), false, 'event beacon is a no-op without api_origin');
  ui.noteUnknown('laptops', 'mem.soldered');
  assert(source.split('\n').some(line => line.includes('/v1/event`') && line.includes("type:'text/plain'")), 'event beacon sends text/plain');
  assert(!/localStorage\.setItem\([^)]*(preset|event)/.test(source) && !/document\.cookie/.test(source), 'no cookies or stored ids');
}
// ---- corrections flow (D9.2) + D10 provenance, kind breakdown and sources-disagree
{
  const src = (id, tier, extra = {}) => ({id, url:`https://example.com/${id}`, label:`Src ${id}`, tier, retrieved_at:'2026-11-20T00:00:00Z', ...extra});
  const issue = 'https://github.com/shrestha-pranav/specsheet/issues/12';
  const cases = [
    [{kind:'official', sources:['a']}, [src('a', 'manufacturer')], /^Maker$/],
    [{kind:'official', sources:['a']}, [src('a', 'crowd', {label:'Contributor photo of the product label (correction 12)', url:issue})], /^Maker label \(contributor photo\)$/],
    [{kind:'official', sources:['a']}, [src('a', 'regulatory', {label:'ENERGY STAR'})], /^Certified: ENERGY STAR$/],
    [{kind:'derived', sources:['a']}, [src('a', 'certifier', {label:'TÜV 5-star'})], /^Derived from TÜV 5-star$/],
    [{kind:'derived', sources:['a'], basis:{basis:'certification'}}, [src('a', 'manufacturer', {label:'Lenovo PSREF'})], /^Derived from a certification printed by Lenovo PSREF$/],
    [{kind:'measured', sources:['a'], measurement_mode:'advertised_by_device'}, [src('a', 'measurement', {label:'ChargerLAB (measured) (cited in correction 12)', evidence:issue})], /^Measured by ChargerLAB \(measured\), 2026-11-20$/],
    [{kind:'measured', sources:['a']}, [src('a', 'crowd', {url:issue})], /^Contributor measurement$/],
    [{kind:'reported', sources:['a']}, [src('a', 'retailer', {label:'Shop'})], /^Reported by Shop$/],
  ];
  for (const [spec, sources, want] of cases) assert.match(ui.provenance(spec, sources).text, want, `badge ${want}`);
  const tip = ui.provenance({kind:'measured', sources:['a'], measurement_mode:'advertised_by_device'}, [src('a', 'measurement', {evidence:issue})]).tip;
  assert.match(tip, /Method: advertised by device/); assert(tip.includes(issue), 'tooltip links the correction issue');
  const field = {key:'k', label:'K', type:'enum', enum:['x', 'y']};
  const detail = ui.valueWithContext({status:'known', value:'x', kind:'measured', sources:['a'], alternatives:[{value:'y', kind:'official', sources:['b']}]}, field, [src('a', 'measurement', {evidence:issue}), src('b', 'manufacturer')]);
  assert.match(detail, /prov-badge prov-measured/); assert.match(detail, /Maker/); assert.match(detail, /Correction evidence/, 'alternative or headline links the issue');
  // an open correction: no value, only the notice; trusted records (no corrections_pending) never show it
  assert.equal(ui.pendingCorrection({corrections_pending:[{key:'k', ref:'12'}]}, 'k').includes('A correction is under review (<a href="https://github.com/shrestha-pranav/specsheet/issues/12"'), true);
  assert.match(ui.pendingCorrection({corrections_pending:[{key:'k', ref:'a3'}]}, 'k'), /proposal a3/);
  assert.equal(ui.pendingCorrection({}, 'k'), ''); assert.equal(ui.pendingCorrection({corrections_pending:[{key:'other', ref:'1'}]}, 'k'), '');
  // D10 might-match: a disagreeing alternative of another kind on the other side of the filter is neither a match nor ruled out
  const bool = {key:'b', type:'bool', facet:true};
  const agree = {specs:{b:{status:'known', value:false}}}, split = {specs:{b:{status:'known', value:false, k:'official', alt:[{v:true, k:'measured'}]}}};
  const same = {specs:{b:{status:'known', value:false, alt:[{v:false, k:'measured'}]}}};
  assert.equal(ui.facetPass(agree, [bool], {f_b_value:'no'}, false), true);
  assert.equal(ui.facetPass(split, [bool], {f_b_value:'no'}, false), false, 'sources disagree: not a match');
  assert.equal(ui.facetPass(split, [bool], {f_b_value:'no'}, true), true, 'sources disagree: might match');
  assert.equal(ui.facetPass(split, [bool], {f_b_value:'yes'}, true), true, 'sources disagree the other way: might match, never ruled out');
  assert.equal(ui.facetPass(same, [bool], {f_b_value:'no'}, false), true, 'an agreeing alternative changes nothing');
  // r2, mirrors presets.py _verdict: same-side different value, conflicted status with no value, no headline but alternatives
  const num = {key:'n', type:'number', facet:{kind:'range'}}, f27 = {f_n_min:'27'};
  const sameSide = {specs:{n:{status:'known', value:27, alt:[{v:32, k:'measured'}]}}};
  assert.equal(ui.facetPass(sameSide, [num], f27, false), false, 'same side, different value: never matched silently');
  assert.equal(ui.disagreeRow(sameSide, [num], f27), true);
  const conflicted = {specs:{n:{status:'conflicted', value:null}}};
  assert.equal(ui.facetPass(conflicted, [num], f27, true), true, 'conflicted: might match');
  assert.equal(ui.disagreeRow(conflicted, [num], f27), true, 'conflicted reads "sources disagree", not "Unknown value"');
  const noHead = (alt) => ({x:{n:{alt}}, specs:{n:{status:'conflicted', value:null}}});
  assert.equal(ui.disagreeRow(noHead([{v:30}, {v:20}]), [num], f27), true, 'no headline, one alternative matches: disagree');
  assert.equal(ui.facetPass(noHead([{v:20}, {v:24}]), [num], f27, true), false, 'no headline, every alternative fails: ruled out');
  assert.equal(ui.disagreeRow({specs:{n:{status:'unknown', value:null}}}, [num], f27), false, 'plain unknown stays "Unknown value"');
  // preset card: per-kind fill breakdown and brands covered only by non-maker values
  const preset = {id:'p', category:'monitors', category_name:'Monitors', title:'T', count:{matches:3, maybe:2, disagree:1, total:5, out_of_scope:0},
    gate:{passes:true, fill:0.9, min_fill:0.8, key:'flk.pwm', label:'PWM', known:9, total:10, keys:[{key:'flk.pwm', label:'PWM', known:9, total:10, by_kind:{official:6, derived:2, measured:1}}],
      non_maker_brands:[{brand:'Acme', key:'flk.pwm', kinds:['measured']}], scope:{basis:'', in_scope:10, category_total:10, covered_brands:['Acme', 'Beta'], excluded:{}, not_covered:[]}}};
  const card = ui.presetCard(preset);
  assert.match(card, /PWM known 9\/10: 6 maker · 2 derived · 1 measured/); assert.match(card, /Covered only by non-maker values: Acme \(measured\)/);
  assert.match(card, /2 more might match \(1 unknown, 1 sources disagree\)/);
  const help = new URL(ui.fillRequestUrl({...preset, evidence_type:'E3', gate:{...preset.gate, passes:false}}));
  assert.equal(help.searchParams.get('template'), 'field-correction.yml'); assert.equal(help.searchParams.get('evidence_type'), 'E3');
  assert.equal(JSON.parse(help.searchParams.get('payload')).key, 'flk.pwm', 'help-fill links prefill the key');
  const corr = new URL(ui.correctionIssueUrl('e1', 'k', 'v', 'E1'));
  assert.deepEqual(Object.keys(JSON.parse(corr.searchParams.get('payload'))).sort(), ['build', 'entity_id', 'key', 'shown_value'], 'payload names the field only');
  assert.equal(corr.searchParams.get('evidence_type'), 'E1');
}
console.log(`Frontend behavior smoke passed: ${rows.length} laptop rows; shard loading, lazy detail cache, structured/literal ports, absence semantics, return state, private issue drafts.`);
