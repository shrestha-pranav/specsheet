#!/usr/bin/env node
/** Validate the complete published static dataset and its category contract. */
import { readFile, readdir } from 'node:fs/promises';
import { join, resolve } from 'node:path';
import assert from 'node:assert/strict';

const root = resolve(import.meta.dirname, '../docs/api/v1');
const listJson = async dir => (await readdir(dir).catch(e => { if (e.code === 'ENOENT') return []; throw e; })).filter(f => f.endsWith('.json'));
const parse = async path => JSON.parse(await readFile(path, 'utf8'));
let parsedJsonFiles = 0;
async function parseAllJson(directory) {
  for (const entry of await readdir(directory, {withFileTypes:true})) {
    const path = join(directory, entry.name);
    if (entry.isDirectory()) await parseAllJson(path);
    else if (entry.name.endsWith('.json')) { await parse(path); parsedJsonFiles++; }
  }
}
await parseAllJson(root);
const categories = await parse(join(root, 'categories.json'));
assert(Array.isArray(categories) && categories.length >= 2, 'Expected multiple categories');
const allowedTypes = new Set(['number','bool','enum','text','range','list']);
const allowedStatuses = new Set(['known','unknown','conflicted','not_yet_extracted','not_applicable']);
const v1Statuses = new Set([...allowedStatuses, 'not_published']);
const v1Types = new Set(['number','integer','bool','enum','text','range','list','object','date']);
let total = 0;
const manifest = await parse(join(root, 'manifest.json'));
const build = await parse(join(root, 'build.json'));
assert.equal(manifest.build, build.build, 'manifest.build must equal build.json');
assert.equal(manifest.record_format, 'specsheet.record/1');
const lookup = await parse(join(root, 'lookup', 'identifiers.json'));
await parse(join(root, 'redirects.json'));
const allPublished = new Set();

// v1 (profile-driven) category: contract in team/briefs/a4-contract.md
async function checkV1(category) {
  const entry = manifest.categories.find(c => c.id === category.id);
  assert(entry, `${category.id}: missing from manifest`);
  assert.equal(entry.count, category.count);
  assert.deepEqual(entry.index, category.index);
  const schema = await parse(join(root, category.id, 'schema.json'));
  assert.equal(schema.id, category.id);
  assert(Array.isArray(schema.groups) && schema.groups.length > 0);
  const groupIds = new Set(schema.groups.map(g => g.id));
  const fields = new Map();
  for (const f of schema.fields) {
    assert(f.key && f.label && groupIds.has(f.group) && v1Types.has(f.type), `${category.id}/${f.key}: bad field`);
    assert(f.facet === null || (typeof f.facet === 'object' && ['range','enum','multi','bool','text'].includes(f.facet.kind)), `${category.id}/${f.key}: facet must be object|null`);
    assert(!fields.has(f.key), `dup field ${f.key}`);
    fields.set(f.key, f);
  }
  const rows = [];
  for (const path of category.index) rows.push(...await parse(join(root, path)));
  assert.equal(rows.length, category.count, `${category.id}: index rows vs count`);
  const facets = await parse(join(root, category.facets));
  for (const [k, fc] of Object.entries(facets)) assert(fields.has(k) && fields.get(k).facet, `${category.id}: facet ${k} not a faceted field`);
  const productDir = join(root, category.id, 'products');
  const files = new Set((await listJson(productDir)).map(f => f.slice(0, -5)));
  const ids = new Set();
  const rowKinds = new Map(rows.map(r => [r.id, r.kind]));
  const stripped = ['snapshot', 'locator'];
  for (const row of rows) {
    assert(!ids.has(row.id), `dup id ${row.id}`); ids.add(row.id);
    assert(row.brand && row.name && row.brand_id && ['family','model','configuration','package','revision'].includes(row.kind), `${row.id}: bad row`);
    assert(Array.isArray(row.ids) && Array.isArray(row.search) && row.v && row.s && Array.isArray(row.completeness.core), `${row.id}: row shape`);
    for (const k of Object.keys(row.v)) assert(fields.has(k), `${row.id}: v key ${k} not in schema`);
    for (const [k, st] of Object.entries(row.s)) { assert(fields.has(k), `${row.id}: s key ${k}`); assert(v1Statuses.has(st) && st !== 'known', `${row.id}/${k}: s status ${st}`); assert(!(k in row.v), `${row.id}/${k}: in both v and s`); }
    const d = await parse(join(productDir, `${row.id}.json`));
    assert.equal(d.id, row.id); assert.equal(d.category, category.id); assert.equal(d.record_format, 'specsheet.record/1');
    assert(d.brand?.id && d.brand?.name && Array.isArray(d.identifiers) && Array.isArray(d.aliases) && Array.isArray(d.relations) && Array.isArray(d.sources) && d.demo === false, `${row.id}: detail shape`);
    const sids = new Set(d.sources.map(s => s.id));
    assert.equal(sids.size, d.sources.length, `${row.id}: dup source ids`);
    for (const s of d.sources) { assert(/^https?:\/\//.test(s.url), `${row.id}: source url`); assert(!('snapshot' in s), `${row.id}: private snapshot leaked`); }
    for (const [k, sp] of Object.entries(d.specs)) {
      assert(fields.has(k), `${row.id}: undefined spec ${k}`);
      assert(v1Statuses.has(sp.status), `${row.id}/${k}: status ${sp.status}`);
      assert(sp.sources.every(x => sids.has(x)), `${row.id}/${k}: dangling source`);
      for (const bad of stripped) assert(!(bad in sp), `${row.id}/${k}: private field ${bad}`);
      if (sp.status !== 'known' && sp.status !== 'conflicted') assert.equal(sp.value, null, `${row.id}/${k}: absence needs null value`);
      if (sp.status === 'known') {
        const t = fields.get(k).type;
        assert(sp.value !== null && sp.value !== undefined, `${row.id}/${k}: known empty`);
        if (t === 'number' || t === 'integer') assert.equal(typeof sp.value, 'number', `${row.id}/${k}: expected number`);
        if (t === 'bool') assert.equal(typeof sp.value, 'boolean', `${row.id}/${k}: expected boolean`);
        if (t === 'list') assert(Array.isArray(sp.value), `${row.id}/${k}: expected list`);
        if (t === 'enum' && fields.get(k).enum) assert(fields.get(k).enum.includes(sp.value), `${row.id}/${k}: enum value ${sp.value}`);
        if (k in row.v) assert.deepEqual(row.v[k], sp.value, `${row.id}/${k}: index/detail value`);
      } else if (sp.status !== 'not_yet_extracted' && (k in row.s)) assert.equal(row.s[k], sp.status, `${row.id}/${k}: index/detail status`);
      if (sp.status === 'conflicted') assert(Array.isArray(sp.alternatives) && sp.alternatives.length > 1, `${row.id}/${k}: conflicted needs alternatives`);
    }
    if (row.kind === 'revision') assert(row.parent_id, `${row.id}: revision row needs parent_id`);
    allPublished.add(row.id);
  }
  // r8: certification-only entities (profile index_rows) are a separate compact shard: detail file + lookup, never a default index row.
  const certIds = new Set();
  if (category.certification_only) {
    assert.deepEqual(entry.certification_only, category.certification_only, `${category.id}: manifest/categories certification_only mismatch`);
    const crows = [];
    for (const path of category.certification_only.index) crows.push(...await parse(join(root, path)));
    assert.equal(crows.length, category.certification_only.count, `${category.id}: certonly rows vs count`);
    const certKeys = new Set(category.certification_only.certification_keys);
    for (const r of crows) {
      assert(!ids.has(r.id) && !certIds.has(r.id), `${r.id}: certonly row also a default row or duplicated`); certIds.add(r.id);
      assert.equal(r.scope, 'certification_only', `${r.id}: certonly row scope`);
      assert(r.brand && r.name && Array.isArray(r.ids) && Array.isArray(r.search) && r.v, `${r.id}: certonly row shape`);
      for (const k of Object.keys(r.v)) assert(certKeys.has(k), `${r.id}: certonly row carries non-certification key ${k}`);
      const d = await parse(join(productDir, `${r.id}.json`));
      assert.equal(d.index_scope, 'certification_only', `${r.id}: detail index_scope`);
      for (const [k, sp] of Object.entries(d.specs)) if (sp.status === 'known' || sp.status === 'conflicted') assert(certKeys.has(k), `${r.id}: substantive ${k} on a certonly entity`);
      allPublished.add(r.id);
    }
  }
  for (const row of rows) assert(!certIds.has(row.id), `${row.id}: default row is certonly`);
  // trusted vs preview separation (review P0-1): trusted details carry review_scope=trusted and only approved relations;
  // preview rows/details live under preview/<cat>/, are flagged, and never feed facets or the identifier lookup.
  assert(category.preview && Array.isArray(category.preview.index), `${category.id}: preview entry missing`);
  assert.deepEqual(entry.preview, category.preview, `${category.id}: manifest/categories preview mismatch`);
  const prows = [];
  for (const path of category.preview.index) prows.push(...await parse(join(root, path)));
  assert.equal(prows.length, category.preview.count, `${category.id}: preview rows vs count`);
  const lookupIds = new Set(Object.values(lookup).flat());
  for (const r of prows) {
    assert.equal(r.review_scope, 'preview', `${r.id}: preview row not flagged`);
    assert.equal(r.in_trusted, ids.has(r.id) || certIds.has(r.id), `${r.id}: in_trusted flag wrong`);
    assert.equal(!!r.certonly, certIds.has(r.id), `${r.id}: preview certonly flag wrong`);
    if (!r.in_trusted) assert(!lookupIds.has(r.id), `${r.id}: preview-only entity leaked into lookup`);
    const pd = await parse(join(root, category.preview.products, `${r.id}.json`));
    assert.equal(pd.review_scope, 'preview'); assert.equal(pd.trusted, r.in_trusted);
    const psids = new Set(pd.sources.map(s => s.id));
    for (const [k, sp] of Object.entries(pd.specs)) { assert(fields.has(k), `${r.id}: preview spec ${k}`); assert(sp.sources.every(x => psids.has(x)), `${r.id}/${k}: preview dangling source`); }
  }
  for (const id of files) {
    const d = await parse(join(productDir, `${id}.json`));
    assert.equal(d.review_scope, 'trusted', `${id}: trusted detail must say review_scope=trusted`);
    for (const r of d.relations) assert.equal(r.status, 'approved', `${id}: non-approved relation in trusted record`);
    for (const r of d.relations) assert(files.has(r.target), `${id}: relation target ${r.target} not published`);
    for (const c of d.children || []) assert(files.has(c), `${id}: child ${c} not published`);
    if (d.kind === 'revision') {
      const par = d.relations.find(r => r.type === 'variant_of');
      assert(par, `${id}: revision without variant_of relation`);
      const pd = await parse(join(productDir, `${par.target}.json`));
      assert((pd.revisions || []).some(r => r.id === id), `${id}: not listed in ${par.target}.revisions`);
      assert(!rowKinds.has(id) || rowKinds.get(id) === 'revision', `${id}: revision row kind`);
    }
    if (d.revisions) {
      assert(d.kind !== 'revision' && d.revisions.length > 0, `${id}: revisions[] on a ${d.kind}`);
      const seen = new Set();
      for (const rv of d.revisions) {
        assert(!seen.has(rv.id) && files.has(rv.id), `${id}: revision ${rv.id} dup or unpublished`); seen.add(rv.id);
        assert(rv.label && rv.name && Array.isArray(rv.differs) && Array.isArray(rv.sources), `${id}/${rv.id}: revision entry shape`);
        const rd = await parse(join(productDir, `${rv.id}.json`));
        assert.equal(rd.kind, 'revision', `${rv.id}: kind`);
        assert(d.children.includes(rv.id), `${id}: revision ${rv.id} not in children`);
        assert(rd.relations.some(r => r.type === 'variant_of' && r.target === id), `${rv.id}: no variant_of ${id}`);
        const rsids = new Set(rv.sources.map(s => s.id));
        for (const [k, sp] of Object.entries(rv.specs)) {
          assert(fields.has(k), `${rv.id}: revision spec ${k}`);
          assert(!sp.inherited_from, `${rv.id}/${k}: inherited spec in revisions[]`);
          assert(sp.sources.every(x => rsids.has(x)), `${rv.id}/${k}: revision entry dangling source`);
          assert.deepEqual(rd.specs[k]?.value, sp.value, `${rv.id}/${k}: entry/detail value`);
        }
        for (const k of rv.differs) assert(k in rv.specs, `${rv.id}: differs key ${k} not an own spec`);
      }
    }
  }
  console.log(`${category.id}: ${rows.length} trusted rows + ${prows.length} preview rows (${files.size} detail files, ${schema.fields.length} fields, ${Object.keys(facets).length} facets, ${category.index.length} index shard(s))`);
  total += rows.length;
}

for (const category of categories) {
  assert(category.id && category.name && typeof category.demo === 'boolean');
  if (category.index) { await checkV1(category); continue; }
  assert(Array.isArray(category.fields) && category.fields.length > 0);
  const fields = new Map();
  for (const field of category.fields) {
    assert(field.key && field.label && field.group && allowedTypes.has(field.type));
    assert(typeof field.facet === 'boolean' && Number.isFinite(field.priority));
    assert(!fields.has(field.key), `Duplicate field ${field.key}`);
    fields.set(field.key, field);
    if (field.display?.kind === 'object_table') {
      assert.equal(field.type, 'list', `${category.id}/${field.key}: object table must be a list`);
      assert(Array.isArray(field.display.columns) && field.display.columns.length > 0);
      for (const column of field.display.columns) assert(column.key && column.label, `${category.id}/${field.key}: incomplete object column`);
    }
    if (field.display?.kind === 'delimited_list') assert.equal(field.display.separator, 'semicolon_newline');
  }
  const schema = await parse(join(root, category.id, 'schema.json'));
  assert.equal(schema.id, category.id);
  assert.deepEqual(schema.fields, category.fields);
  const index = await parse(join(root, category.products));
  assert(Array.isArray(index));
  assert.equal(index.length, category.count, `Index count for ${category.id}`);
  const productDir = join(root, category.id, 'products');
  const files = await listJson(productDir);
  assert.equal(files.length, category.count, `Detail count for ${category.id}`);
  const ids = new Set();
  for (const row of index) {
    assert(!ids.has(row.id), `Duplicate product id ${row.id}`);
    ids.add(row.id);
    assert.equal(row.category, category.id);
    assert.equal(row.demo, category.demo);
    assert(row.brand && row.name);
    assert(Array.isArray(row.identifiers));
    assert(row.specs && typeof row.specs === 'object');
    const detail = await parse(join(productDir, `${row.id}.json`));
    for (const key of ['id','category','brand','name','family','model','variant','identifiers','specs','confidence','demo']) {
      assert.deepEqual(detail[key], row[key], `${row.id}: detail/index ${key}`);
    }
    for (const key of ['sources','media','documents','marketing_terms']) assert(Array.isArray(detail[key]), `${row.id}: ${key}`);
    const sourceIds = new Set(detail.sources.map(source => source.id));
    assert.equal(sourceIds.size, detail.sources.length, `${row.id}: duplicate source IDs`);
    for (const source of detail.sources) assert(/^https?:\/\//.test(source.url), `${row.id}: invalid source URL`);
    for (const [key, spec] of Object.entries(detail.specs)) {
      assert(fields.has(key), `${row.id}: undefined spec key ${key}`);
      assert(allowedStatuses.has(spec.status), `${row.id}/${key}: invalid status`);
      assert(Array.isArray(spec.sources), `${row.id}/${key}: sources missing`);
      assert(spec.sources.every(id => sourceIds.has(id)), `${row.id}/${key}: dangling source ID`);
      if (['unknown','not_yet_extracted','not_applicable'].includes(spec.status)) assert.equal(spec.value, null, `${row.id}/${key}: absence must have null value`);
      if (spec.status === 'known') {
        assert(spec.value !== null && spec.value !== undefined, `${row.id}/${key}: known value empty`);
        const type = fields.get(key).type;
        if (type === 'number') assert.equal(typeof spec.value, 'number', `${row.id}/${key}: expected number`);
        if (type === 'bool') assert.equal(typeof spec.value, 'boolean', `${row.id}/${key}: expected boolean`);
        if (type === 'list') assert(Array.isArray(spec.value), `${row.id}/${key}: expected list`);
        if (type === 'range') assert(typeof spec.value.min === 'number' && typeof spec.value.max === 'number', `${row.id}/${key}: expected numeric range`);
        const display = fields.get(key).display;
        if (display?.kind === 'object_table') for (const [index, item] of spec.value.entries()) {
          assert(item && typeof item === 'object' && !Array.isArray(item), `${row.id}/${key}[${index}]: object required`);
          for (const column of display.columns) assert(Object.hasOwn(item, column.key), `${row.id}/${key}[${index}]: missing ${column.key}`);
        }
        if (display?.kind === 'delimited_list') assert.equal(typeof spec.value, 'string', `${row.id}/${key}: delimited text required`);
      }
    }
    assert.equal(Object.keys(detail.specs).length, fields.size, `${row.id}: missing schema fields`);
    total++;
  }
  for (const file of files) assert(ids.has(file.slice(0,-5)), `${category.id}: orphan detail ${file}`);
  console.log(`${category.id}: ${index.length} products, ${fields.size} fields`);
}
for (const [key, list] of Object.entries(lookup)) for (const id of list) assert(allPublished.has(id), `lookup ${key} -> unpublished ${id}`);
assert.equal(total, categories.reduce((sum, category) => sum + category.count, 0));

// Round 5 UI contract: the frontend shell relies on these published facts (data is not changed by the shell).
{
  const sch = async id => parse(join(root, id, 'schema.json'));
  const pb = (await sch('power-banks')).fields, rv = (await sch('robot-vacuums')).fields;
  const f = (list, key) => list.find(x => x.key === key);
  assert.deepEqual(f(pb, 'out.ports').items.fields.map(x => x.key), ['name','type','direction','max_w','fixed_pdos','pps'], 'port table columns');
  assert.equal(f(pb, 'out.max_total_w').label, 'All-ports simultaneous output');
  assert.equal(f(pb, 'out.max_single_port_w').label, 'Best single-port output');
  assert(['lidar','dtof'].every(v => f(rv, 'nav.type').enum.includes(v)), 'LiDAR alias needs lidar and dtof enum values');
  for (const key of ['clean.suction_pa','bat.runtime_min','noise.db']) assert(f(rv, key).conditions.includes('claim_basis'), `${key} carries claim_basis`);
  for (const key of ['bat.runtime_min','noise.db']) assert(f(rv, key).conditions.includes('power_mode'), `${key} carries power_mode`);
  const rvRows = await parse(join(root, 'robot-vacuums', 'products', 'dreame-aqua10-roller.json'));
  assert(rvRows.specs['clean.suction_pa'].basis?.claim_basis, 'suction basis present in detail records');
}
{
  const src = await parse(resolve(root, '..', '..', 'sources.json'));
  assert(Array.isArray(src.granted) && src.granted.length > 0 && Array.isArray(src.facts_only), 'sources.json has granted/facts_only');
  assert(!('public_domain' in src) && !JSON.stringify(src).includes('public_domain'), 'sources.json has no public_domain field');
  assert(src.granted.every(item => item.attribution), 'every granted source carries an attribution line');
  const cov = await parse(join(root, 'coverage.json'));
  assert(Object.values(cov.categories).some(item => item.granted.values > 0), 'coverage.json reports granted values');
  for (const item of Object.values(cov.categories)) assert(item.granted.values <= item.free.values, 'granted <= free');
}
{
  // Killer-query presets: computed at build time from the real index (scripts/presets.py), never hand-written.
  const presets = await parse(join(root, 'presets.json'));
  assert(presets.presets.length >= 6 && presets.presets.length <= 9, 'presets: 6-9 killer queries');
  for (const p of presets.presets) {
    assert(categories.some(c => c.id === p.category), `preset ${p.id}: known category`);
    assert(p.gate && typeof p.gate.passes === 'boolean' && p.gate.keys.length, `preset ${p.id}: gate computed`);
    assert.equal(p.gate.passes, p.gate.fill >= p.min_fill && p.gate.scope.covered_brands.length >= p.gate.min_brands, `preset ${p.id}: gate = fill >= min_fill and enough covered brands`);
    assert(p.gate.scope.in_scope <= p.gate.scope.category_total && p.gate.keys.every(k => k.total <= p.gate.scope.in_scope), `preset ${p.id}: populations sit inside the scope`);
    if (!p.gate.passes) assert(p.gate.label && p.gate.known <= p.gate.total, `preset ${p.id}: failing preset names its missing field`);
  }
}
console.log(`Static dataset smoke passed: ${total} products across ${categories.length} categories; ${parsedJsonFiles} JSON files parsed`);
