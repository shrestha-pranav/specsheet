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
let total = 0;
for (const category of categories) {
  assert(category.id && category.name && typeof category.demo === 'boolean');
  assert(Array.isArray(category.fields) && category.fields.length > 0);
  const fields = new Map();
  for (const field of category.fields) {
    assert(field.key && field.label && field.group && allowedTypes.has(field.type));
    assert(typeof field.facet === 'boolean' && Number.isFinite(field.priority));
    assert(!fields.has(field.key), `Duplicate field ${field.key}`);
    fields.set(field.key, field);
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
      }
    }
    assert.equal(Object.keys(detail.specs).length, fields.size, `${row.id}: missing schema fields`);
    total++;
  }
  for (const file of files) assert(ids.has(file.slice(0,-5)), `${category.id}: orphan detail ${file}`);
  console.log(`${category.id}: ${index.length} products, ${fields.size} fields`);
}
assert.equal(total, categories.reduce((sum, category) => sum + category.count, 0));
console.log(`Static dataset smoke passed: ${total} products across ${categories.length} categories; ${parsedJsonFiles} JSON files parsed`);
