// Loads r2-data/ (built by ../scripts/build_r2.py) into the LOCAL simulated R2 bucket used by `wrangler dev`.
// No Cloudflare account involved: miniflare writes under .wrangler/state (same --persist-to as `npm run dev`).
// usage: node scripts/seed-local-r2.mjs [r2-data-dir] [persist-dir]
import { Miniflare } from "miniflare";
import { readdirSync, readFileSync, statSync } from "node:fs";
import { join, relative, resolve } from "node:path";

const root = resolve(import.meta.dirname, "..");
const src = resolve(process.argv[2] ?? join(root, "r2-data"));
const persist = resolve(process.argv[3] ?? join(root, ".wrangler/state"));
const BUCKET = "specsheet-data"; // must equal bucket_name in wrangler.jsonc

const mf = new Miniflare({
  modules: true, script: "export default { fetch() { return new Response('seed'); } }",
  compatibilityDate: "2026-08-01", r2Buckets: { DATA: BUCKET }, r2Persist: join(persist, "v3/r2"),
});
const bucket = await mf.getR2Bucket("DATA");
const walk = (d) => readdirSync(d).flatMap((n) => (statSync(join(d, n)).isDirectory() ? walk(join(d, n)) : [join(d, n)]));
let n = 0;
for (const f of walk(src)) {
  const key = relative(src, f).split("\\").join("/");
  await bucket.put(key, readFileSync(f), { httpMetadata: { contentType: key.endsWith(".gz") ? "application/gzip" : "application/json" } });
  n++;
}
await mf.dispose();
console.log(`seeded ${n} objects from ${src} into ${persist}/v3/r2 (bucket ${BUCKET})`);
