#!/usr/bin/env node
/** Validate the complete published static dataset and its category contract. */
import { readFile, readdir } from 'node:fs/promises';
import { join, resolve } from 'node:path';
import assert from 'node:assert/strict';

const root = resolve(import.meta.dirname, '../docs/api/v1');
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
  const files = new Set((await readdir(productDir)).filter(f => f.endsWith('.json')).map(f => f.slice(0, -5)));
  const ids = new Set();
  const stripped = ['snapshot', 'locator'];
  for (const row of rows) {
    assert(!ids.has(row.id), `dup id ${row.id}`); ids.add(row.id);
    assert(row.brand && row.name && row.brand_id && ['family','model','configuration','package'].includes(row.kind), `${row.id}: bad row`);
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
    allPublished.add(row.id);
  }
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
    assert.equal(r.in_trusted, ids.has(r.id), `${r.id}: in_trusted flag wrong`);
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
  const files = (await readdir(productDir)).filter(file => file.endsWith('.json'));
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
console.log(`Static dataset smoke passed: ${total} products across ${categories.length} categories; ${parsedJsonFiles} JSON files parsed`);
