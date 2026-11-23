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
const names = ['facetControl','methodsDiffer','methodsFlag','categories','indexFor','detailFor','displayValue','initialState','categoryStateQuery','productUrl','validatedReturnQuery','returnWithIds','matchFacet','missingIssueUrl','correctionIssueUrl','renderTable','renderProduct','renderCompare','previewOverlay','revisionsMarkup','searchRows','extractIdentifiers','differingFields','cellValue','compareUrl','configTable','evidenceMarkup','valueWithContext'];
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
  const categoryRows = await ui.indexFor(category);
  await ui.renderProduct(category, categoryRows[0].id, new URLSearchParams(), 0);
  assert.match(element('main').innerHTML, /detail-grid/, `${category.id}: product rendered`);
  assert.doesNotMatch(element('main').innerHTML, /\[object Object\]/, `${category.id}: no object coercion`);
  await ui.renderCompare(category, new URLSearchParams({ids:categoryRows.slice(0,2).map(r=>r.id).join(',')}), 0);
  assert.match(element('#comparison-table').innerHTML, /compare-table/, `${category.id}: comparison rendered`);
}
console.log(`Frontend behavior smoke passed: ${rows.length} laptop rows; shard loading, lazy detail cache, structured/literal ports, absence semantics, return state, private issue drafts.`);
