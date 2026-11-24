#!/usr/bin/env python3
"""Build the paid-tier data set for api-worker/ (Cloudflare R2 layout) from the static API in docs/api/v1.

  python3 -I scripts/build_r2.py [--docs docs/api/v1] [--releases releases] [--out api-worker/r2-data]
                                 [--categories a,b] [--release ID]

Output tree (object keys == paths under --out; upload with api-worker/scripts/seed-local-r2.mjs locally,
or `wrangler r2 bulk put` / rclone to the real bucket, see api-worker/README.md):
  meta/manifest.json            release id + per-category counts/sizes (what the Worker trusts)
  index/<cat>.json              array of rows {id,kind,brand,name,variant_label,ids,lifecycle,v:{key:value}} (known values only)
  records/<cat>/<xx>.json       {id: record} shards, xx = sha1(id)[:2]  (provenance lookup for /v1/query)
  bulk/<cat>.jsonl.gz           one trusted record per line (/v1/bulk/<cat>.jsonl.gz)
  changes/<release>.json        per-category diff vs the previous snapshot; changes/index.json lists all releases

Only trusted data is exported (never preview/). api-worker/licensing-exclusions.json removes demo data, `media`
and every spec whose sources are all on an excluded domain (research/data-licensing.md). The release manifests in
releases/ carry no per-record data, so diffs come from snapshots under state/r2-snapshots/ (gitignored): history
begins at the first run of this script after a release, not retroactively. Stdlib only; read-only on docs/.
"""
import argparse, glob, gzip, hashlib, json, os, sys, urllib.parse

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MAX_CHANGE_ROWS = 5000  # per category per release; the Worker truncates further


def jload(p):
    with open(p, encoding="utf-8") as f:
        return json.load(f)


def jdump(obj, path, **kw):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, separators=(",", ":"), sort_keys=True, **kw)


def domain_excluded(url, domains):
    host = (urllib.parse.urlparse(url).hostname or "").lower()
    return any(host == d or host.endswith("." + d) for d in domains)


def clean_record(rec, cfg):
    """Apply licensing exclusions. Returns None if the record must not be exported."""
    if cfg.get("exclude_demo_records") and rec.get("demo"):
        return None
    doms = [d.lower() for d in cfg.get("exclude_source_domains", [])]
    bad_ids = {s["id"] for s in rec.get("sources", []) if domain_excluded(s.get("url", ""), doms)}
    rec = dict(rec)
    for k in cfg.get("drop_record_fields", []):
        rec.pop(k, None)
    rec["sources"] = [s for s in rec.get("sources", []) if s["id"] not in bad_ids]
    specs = {}
    for key, sp in (rec.get("specs") or {}).items():
        srcs = sp.get("sources") or []
        if srcs and all(s in bad_ids for s in srcs):
            continue  # value only attested by an excluded source
        if bad_ids and srcs:
            sp = dict(sp, sources=[s for s in srcs if s not in bad_ids])
        specs[key] = sp
    rec["specs"] = specs
    if "documents" in rec:
        rec["documents"] = [d for d in rec["documents"] if not domain_excluded(d.get("url", ""), doms)]
    return rec


def known_values(rec):
    out = {}
    for key, sp in rec["specs"].items():
        if sp.get("status") == "known" and sp.get("value") is not None and not isinstance(sp["value"], dict):
            out[key] = sp["value"]
    return out


def build_category(cat, docs, cfg, out):
    prods = {}
    for f in sorted(glob.glob(os.path.join(docs, cat["id"], "products", "*.json"))):
        rec = clean_record(jload(f), cfg)
        if rec is not None:
            prods[rec["id"]] = rec
    base = {}  # id -> index row skeleton (index shards are authoritative for the row set)
    for rel in cat.get("index") or []:
        for r in jload(os.path.join(docs, rel)):
            base[r["id"]] = r
    rows = []
    ids = base.keys() if base else prods.keys()
    for i in sorted(ids):
        rec = prods.get(i)
        if rec is None:
            continue
        b = base.get(i, {})
        brand = rec.get("brand")
        rows.append({
            "id": i, "kind": rec.get("kind") or b.get("kind"),
            "brand": brand.get("name") if isinstance(brand, dict) else brand,
            "name": rec.get("name"), "variant_label": rec.get("variant_label"),
            "ids": b.get("ids") or [f'{x.get("scheme")}:{x.get("value")}' for x in rec.get("identifiers", [])],
            "lifecycle": b.get("lifecycle") or (rec.get("lifecycle") or {}).get("state"),
            "v": known_values(rec),
        })
    jdump(rows, os.path.join(out, "index", cat["id"] + ".json"))
    shards = {}
    for i in sorted(ids):
        if i in prods:
            shards.setdefault(hashlib.sha1(i.encode()).hexdigest()[:2], {})[i] = prods[i]
    for xx, d in shards.items():
        jdump(d, os.path.join(out, "records", cat["id"], xx + ".json"))
    bulk = os.path.join(out, "bulk", cat["id"] + ".jsonl.gz")
    os.makedirs(os.path.dirname(bulk), exist_ok=True)
    with open(bulk, "wb") as raw, gzip.GzipFile(fileobj=raw, mode="wb", mtime=0) as gz:
        for i in sorted(ids):
            if i in prods:
                gz.write(json.dumps(prods[i], ensure_ascii=False, separators=(",", ":"), sort_keys=True).encode() + b"\n")
    return rows, {"id": cat["id"], "count": len(rows), "legacy": bool(cat.get("legacy")),
                  "bulk": f"bulk/{cat['id']}.jsonl.gz", "bulk_bytes": os.path.getsize(bulk)}


def diff_rows(old, new):
    """old/new: {id: v}. Added/removed ids plus per-key [old,new] for changed rows."""
    added = sorted(set(new) - set(old))
    removed = sorted(set(old) - set(new))
    changed = []
    for i in sorted(set(new) & set(old)):
        if old[i] != new[i]:
            ks = sorted(set(old[i]) | set(new[i]))
            changed.append({"id": i, "fields": {k: [old[i].get(k), new[i].get(k)] for k in ks if old[i].get(k) != new[i].get(k)}})
    return {"added": added[:MAX_CHANGE_ROWS], "removed": removed[:MAX_CHANGE_ROWS], "changed": changed[:MAX_CHANGE_ROWS],
            "counts": {"added": len(added), "removed": len(removed), "changed": len(changed)}}


def latest_release(releases_dir, override):
    if override:
        return override, None
    last = None
    p = os.path.join(releases_dir, "index.jsonl")
    if os.path.exists(p):
        for line in open(p):
            if line.strip():
                last = json.loads(line)["release"]
    if last is None:
        return "unreleased", None
    mp = os.path.join(releases_dir, last + ".json")
    return last, (jload(mp).get("created_at") if os.path.exists(mp) else None)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--docs", default=os.path.join(ROOT, "docs/api/v1"))
    ap.add_argument("--releases", default=os.path.join(ROOT, "releases"))
    ap.add_argument("--out", default=os.path.join(ROOT, "api-worker/r2-data"))
    ap.add_argument("--exclusions", default=os.path.join(ROOT, "api-worker/licensing-exclusions.json"))
    ap.add_argument("--snapshots", default=os.path.join(ROOT, "state/r2-snapshots"))
    ap.add_argument("--categories", default="", help="comma list (dev seeding); default all trusted categories")
    ap.add_argument("--release", default="", help="override release id (tests)")
    a = ap.parse_args()
    cfg = jload(a.exclusions)
    man = jload(os.path.join(a.docs, "manifest.json"))
    want = {c for c in a.categories.split(",") if c}
    cats = [c for c in man["categories"] if c["id"] not in cfg.get("exclude_categories", []) and not c.get("demo")
            and (not want or c["id"] in want)]
    release, created = latest_release(a.releases, a.release)
    created = created or man.get("generated_at")
    metas, snap = [], {}
    for c in cats:
        rows, meta = build_category(c, a.docs, cfg, a.out)
        metas.append(meta)
        snap[c["id"]] = {r["id"]: r["v"] for r in rows}
        print(f'{c["id"]}: {meta["count"]} rows, bulk {meta["bulk_bytes"]} B', file=sys.stderr)
    # diff vs previous snapshot (only when this is a new release and the category sets are comparable)
    os.makedirs(a.snapshots, exist_ok=True)
    prev_files = sorted(f for f in os.listdir(a.snapshots) if f.endswith(".json.gz") and f != release + ".json.gz")
    idx_path = os.path.join(a.out, "changes", "index.json")
    history = jload(idx_path) if os.path.exists(idx_path) else []
    if not any(h["release"] == release for h in history):
        entry = {"release": release, "created_at": created, "baseline": not prev_files, "counts": {}}
        prev = None
        if prev_files:
            pf = max(prev_files, key=lambda f: os.path.getmtime(os.path.join(a.snapshots, f)))
            with gzip.open(os.path.join(a.snapshots, pf), "rt") as f:
                prev = json.load(f)
            entry["prev"] = pf[:-8]
        cats_diff = {}
        for cid, cur in snap.items():
            if prev is not None and cid in prev:
                d = diff_rows(prev[cid], cur)
            elif prev is not None:
                d = diff_rows({}, cur)  # new category since previous release
            else:
                continue
            if any(d["counts"].values()):
                cats_diff[cid] = d
                entry["counts"][cid] = d["counts"]
        jdump({"release": release, "created_at": created, "prev": entry.get("prev"), "categories": cats_diff},
              os.path.join(a.out, "changes", release + ".json"))
        history.append(entry)
        history.sort(key=lambda h: h["release"])
        jdump(history, idx_path)
    with gzip.open(os.path.join(a.snapshots, release + ".json.gz"), "wt") as f:
        json.dump(snap, f, separators=(",", ":"))
    jdump({"release": release, "built_at": created, "dataset_build": man.get("build"), "categories": metas,
           "note": "paid-tier export: trusted records only, licensing exclusions applied"}, os.path.join(a.out, "meta", "manifest.json"))
    print(f"release {release}: {len(metas)} categories -> {a.out}", file=sys.stderr)


if __name__ == "__main__":
    main()
