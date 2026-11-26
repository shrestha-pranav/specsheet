#!/usr/bin/env python3
"""Build the Worker query pack (--tier free, default out api-worker/pack) or the paid-tier export (--tier paid, default out
api-worker/r2-data) from the static API in docs/api/v1. Same layout for both tiers.

  python3 -I scripts/build_r2.py [--tier free|paid] [--docs docs/api/v1] [--releases releases] [--out DIR] [--policy data/source-policy.yaml]
                                 [--categories a,b] [--release ID]

Output tree (object keys == paths under --out; upload with api-worker/scripts/seed-local-r2.mjs locally,
or `wrangler r2 bulk put` / rclone to the real bucket, see api-worker/README.md):
  meta/manifest.json            release id + per-category counts/sizes (what the Worker trusts)
  index/<cat>.json              array of rows {id,kind,brand,name,variant_label,ids,lifecycle,v:{key:value},s?:{key:conflicted|not_applicable},a?:{key:[alt values]}} (known values only in v)
  schema/<cat>.json             fields {key,label,group,type,unit,enum,tier,facet,facet_kind,fill} for MCP list_categories_keys
  meta/presets.json             built docs presets (definitions, gate, counts) for MCP list_presets
  records/<cat>/<xx>.json       {id: record} shards, xx = sha1(id)[:2]  (provenance lookup for /v1/query)
  bulk/<cat>.jsonl.gz           one trusted record per line (/v1/bulk/<cat>.jsonl.gz)
  changes/<release>.json        per-category diff vs the previous snapshot; changes/index.json lists all releases

Only trusted data is exported (never preview/). Every record goes through the licensing gate (scripts/source_policy.py over
data/source-policy.yaml, the same module build.py uses): demo data, `media`, excluded categories, sources the tier disallows and
values no remaining source supports are removed (docs/ is already free-gated, so sources[] list supporters only). The docs build
must have been made with the same policy (sha256 check). A value that becomes withheld shows in `changes` as
{key, change: "withdrawn"} with no previous value. The release manifests in releases/ carry no per-record data, so diffs come from
snapshots under state/r2-snapshots/<tier>/ (gitignored): history begins at the first run of this script after a release, not
retroactively. Read-only on docs/. RELEASE=1 fails on values citing unlisted domains.
"""
import argparse, glob, gzip, hashlib, json, os, re, sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import source_policy  # noqa: E402  (the one policy reader)

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MAX_CHANGE_ROWS = 5000  # per category per release; the Worker truncates further


def jload(p):
    with open(p, encoding="utf-8") as f:
        return json.load(f)


def jdump(obj, path, **kw):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, separators=(",", ":"), sort_keys=True, **kw)


def known_values(rec):
    out = {}
    for key, sp in rec["specs"].items():
        if sp.get("status") == "known" and sp.get("value") is not None and not isinstance(sp["value"], dict):
            out[key] = sp["value"]
    return out


def gated_alts(rec):
    """D10 disagreeing alternatives {key: [values]} of a policy-GATED record (review-8 P1): same selection as v1_publish row_of x[k].alt
    (known headline; alternative of another kind with a different value), but taken from rec["specs"][k]["alternatives"] after
    pol.gate() dropped every alternative whose sources the tier disallows. The docs index x[*].alt is never read: a restricted-only
    alternative must not reach the pack, where it would flip Worker verdicts (disagree vs no) and leak through counts/statuses."""
    out, kv = {}, known_values(rec)   # only keys the row's v carries (the Worker reads a[k] beside v[k])
    for key in kv:
        sp = rec["specs"][key]
        pk = sp.get("kind") or "official"
        hv = json.dumps(sp["value"], sort_keys=True)
        vs = [a["value"] for a in sp.get("alternatives") or [] if a.get("sources") and a.get("kind") != pk
              and json.dumps(a.get("value"), sort_keys=True) != hv]
        if vs:
            out[key] = vs
    return out


def crowd_keys(rec):
    """D9.2: values that came through the corrections flow (a crowd source, or a page cited by a correction issue) -> {key: {kind, tier:
    crowd, source_tier}}, so /v1/changes marks every crowd-sourced change with its kind."""
    by = {s["id"]: s for s in rec.get("sources") or []}
    out = {}
    for key, sp in rec["specs"].items():
        if sp.get("status") != "known":
            continue
        cs = [by[x] for x in sp.get("sources") or [] if x in by and (by[x].get("tier") == "crowd" or by[x].get("evidence"))]
        if cs:
            out[key] = {"kind": sp.get("kind") or "official", "tier": "crowd", "source_tier": cs[0].get("tier")}
    return out


def withheld_keys(rec, pol):
    return sorted(k for k, sp in rec["specs"].items() if sp.get("status") == pol.withheld_status)


def build_category(cat, docs, pol, tier, out, shard_hex=2):
    prods, cov = {}, {"free": [0, 0], "granted": [0, 0], "paid": [0, 0]}
    for f in sorted(glob.glob(os.path.join(docs, cat["id"], "products", "*.json"))):
        raw = jload(f)
        rec = pol.gate(raw, tier)
        if rec is not None:
            prods[rec["id"]] = rec
            pol.note_published(rec)
        fr = rec if tier == "free" else pol.gate(raw, "free")
        if fr is not None:
            kn, gr = pol.count(fr)
            cov["free"][0] += 1; cov["free"][1] += kn; cov["granted"][0] += gr > 0; cov["granted"][1] += gr
        pr = rec if tier == "paid" else pol.gate(raw, "paid")
        if pr is not None:
            cov["paid"][0] += 1; cov["paid"][1] += pol.count(pr)[0]
    base = {}  # id -> index row skeleton (index shards, incl. the certification-only shard, are authoritative for the row set)
    for rel in (cat.get("index") or []) + ((cat.get("certification_only") or {}).get("index") or []):
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
        st = {k: sp["status"] for k, sp in rec["specs"].items() if sp.get("status") in ROW_STATUSES}
        if st:
            rows[-1]["s"] = st  # Worker per-filter status (conflicted / not_applicable); absent key = unknown
        alts = gated_alts(rec)  # review-8 P1: from the policy-gated record only, never the docs index x[*].alt
        if alts:
            rows[-1]["a"] = alts  # D10 disagreeing alternatives: the Worker reports "disagree" when they fall on the other side of a filter
    schema_meta = write_schema(cat, docs, rows, out)
    jdump(rows, os.path.join(out, "index", cat["id"] + ".json"))
    shards = {}
    for i in sorted(ids):
        if i in prods:
            shards.setdefault(hashlib.sha1(i.encode()).hexdigest()[:shard_hex], {})[i] = prods[i]
    for f in glob.glob(os.path.join(out, "records", cat["id"], "*.json")):  # a rebuild (or a new --shard-hex) leaves no stale shards
        os.remove(f)
    for xx, d in shards.items():
        jdump(d, os.path.join(out, "records", cat["id"], xx + ".json"))
    bulk = os.path.join(out, "bulk", cat["id"] + ".jsonl.gz")
    os.makedirs(os.path.dirname(bulk), exist_ok=True)
    with open(bulk, "wb") as raw, gzip.GzipFile(fileobj=raw, mode="wb", mtime=0) as gz:
        for i in sorted(ids):
            if i in prods:
                gz.write(json.dumps(prods[i], ensure_ascii=False, separators=(",", ":"), sort_keys=True).encode() + b"\n")
    withheld = {r["id"]: withheld_keys(prods[r["id"]], pol) for r in rows}
    crowd = {r["id"]: c for r in rows if (c := crowd_keys(prods[r["id"]]))}
    return rows, (withheld, crowd), cov, {"id": cat["id"], "count": len(rows), "legacy": bool(cat.get("legacy")),
                                 "keys": sorted({k for r in rows for k in r["v"]}),  # Worker filter/fields bound (D3.6)
                                 **schema_meta,
                                 "bulk": f"bulk/{cat['id']}.jsonl.gz", "bulk_bytes": os.path.getsize(bulk), "sha256": {
                                     "index": sha256_file(os.path.join(out, "index", cat["id"] + ".json")), "bulk": sha256_file(bulk)}}


ROW_STATUSES = ("conflicted", "not_applicable")


def write_schema(cat, docs, rows, out):
    """schema/<cat>.json for the Worker's list_categories_keys tool and per-filter status: key, label, group, type, unit, tier, facet,
    fill (known / rows in this pack). Returns the manifest fields (schema path, core keys). Fixture trees without a schema: nothing."""
    rel_in = cat.get("schema") or f"{cat['id']}/schema.json"   # manifest.json categories carry no schema path; categories.json does
    if not os.path.exists(os.path.join(docs, rel_in)):
        return {}
    sch = jload(os.path.join(docs, rel_in))
    n = len(rows) or 1
    fields = []
    for f in sch.get("fields") or []:
        k = f["key"]
        facet = f.get("facet")
        fields.append({"key": k, "label": f.get("label"), "group": f.get("group"), "type": f.get("type"), "unit": f.get("unit"),
                       "enum": f.get("enum"), "tier": f.get("tier"), "facet": bool(facet),
                       "facet_kind": facet.get("kind") if isinstance(facet, dict) else None,
                       "fill": round(sum(1 for r in rows if k in r["v"]) / n, 4)})
    rel = f"schema/{cat['id']}.json"
    jdump({"category": cat["id"], "rows": len(rows), "fields": fields}, os.path.join(out, rel))
    return {"schema": rel, "core": sorted(f["key"] for f in fields if f["tier"] == "core")}


def write_presets(docs, cats, out):
    """meta/presets.json: the built docs presets (scripts/presets.py output) for the MCP list_presets tool, restricted to pack categories.
    Definitions + gate + counts only; the Worker translates the app filters into its own filter grammar."""
    src = os.path.join(docs, "presets.json")
    if not os.path.exists(src):
        return None
    ids = {c["id"] for c in cats}
    keep = ("id", "category", "title", "filters", "require", "columns", "scope", "min_fill", "count")
    ps = [dict({k: p[k] for k in keep if k in p}, gate={k: p["gate"].get(k) for k in ("passes", "fill", "key", "label", "min_brands")})
          for p in jload(src).get("presets") or [] if p.get("category") in ids]
    rel = "meta/presets.json"
    jdump({"presets": ps}, os.path.join(out, rel))
    return rel


def match_catalogue(docs, ids, out):
    """match/catalogue.json for the Worker port of scripts/match.py (api-worker/src/match.ts): the matcher's own Catalogue, pre-tokenised
    by match.tokens() so both sides tokenise the catalogue identically, restricted to ids in this pack. Returns its sha256."""
    import match as M
    if not all(os.path.exists(os.path.join(docs, f)) for f in ("categories.json", "lookup/identifiers.json")):
        return None  # fixture trees without the matcher inputs: no catalogue, the Worker keeps match at 404
    C = M.Catalogue(docs)
    keep = {i: p for i, p in C.products.items() if i in ids}
    doc = {"format": "specsheet.match/1",
           "products": [[p["id"], p["category"], p["brand"], p["brand_id"], p["name"], sorted(p["toks"]), sorted(p["btoks"]),
                         [M.tokens(ph) for ph in p["phrases"]], 1 if re.search(r"(?i)pack|\b\d+\s*-?\s*count\b", " ".join(p["phrases"])) else 0]
                        for p in keep.values()],
           "brand_names": {n: sorted(b) for n, b in sorted(C.brand_names.items())},
           "ident": {k: v2 for k, v in sorted(C.ident.items()) if (v2 := [i for i in v if i in keep])},
           "aliases": {k: v2 for k, v in sorted(C.aliases.items()) if (v2 := [i for i in v if i in keep])},
           "mod_by_brand": {b: sorted(m) for b, m in sorted(C.mod_by_brand.items()) if m}}
    path = os.path.join(out, "match", "catalogue.json")
    jdump(doc, path)
    return sha256_file(path)


def sha256_file(p):
    with open(p, "rb") as f:
        return hashlib.sha256(f.read()).hexdigest()


def diff_rows(old, new, withheld=None, crowd=None):
    """old/new: {id: v}; withheld: {id: [keys now withheld by the source policy]}. Added/removed ids plus per-key [old,new] for changed
    rows. A key that was published and is now withheld is {key, change: "withdrawn"} with NO previous value (never re-publish it)."""
    withheld = withheld or {}
    added = sorted(set(new) - set(old))
    removed = sorted(set(old) - set(new))
    changed = []
    for i in sorted(set(new) & set(old)):
        if old[i] != new[i]:
            ks = sorted(set(old[i]) | set(new[i]))
            wd = set(withheld.get(i) or ())
            fields = {k: [old[i].get(k), new[i].get(k)] for k in ks if old[i].get(k) != new[i].get(k) and not (k in wd and k not in new[i])}
            w = [{"key": k, "change": "withdrawn"} for k in ks if k in wd and k in old[i] and k not in new[i]]
            cr = {k: (crowd or {}).get(i, {})[k] for k in fields if k in (crowd or {}).get(i, {})}
            changed.append(dict({"id": i, "fields": fields}, **({"withdrawn": w} if w else {}), **({"crowd": cr} if cr else {})))
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
    ap.add_argument("--tier", choices=source_policy.TIERS, default="paid")
    ap.add_argument("--out", default="", help="default api-worker/pack (free) | api-worker/r2-data (paid)")
    ap.add_argument("--policy", default="", help="default data/source-policy.yaml")
    ap.add_argument("--snapshots", default="", help="default state/r2-snapshots/<tier>")
    ap.add_argument("--categories", default="", help="comma list (dev seeding); default all trusted categories")
    ap.add_argument("--release", default="", help="override release id (tests)")
    ap.add_argument("--shard-hex", type=int, default=2, choices=(2, 3), help="record shard width in hex chars (the Worker pack uses 3: "
                    "smaller shards = less JSON parsed per /v1/query page); recorded in the manifest as shard_hex")
    ap.add_argument("--no-match", action="store_true", help="skip match/catalogue.json")
    a = ap.parse_args()
    a.out = a.out or os.path.join(ROOT, "api-worker/pack" if a.tier == "free" else "api-worker/r2-data")
    a.snapshots = a.snapshots or os.path.join(ROOT, "state/r2-snapshots", a.tier)
    pol = source_policy.load(a.policy or None)
    man = jload(os.path.join(a.docs, "manifest.json"))
    if man.get("policy_sha256") and man["policy_sha256"] != pol.sha256:
        raise SystemExit(f"{a.docs} was built with source policy {man.get('policy_version')} ({man['policy_sha256'][:12]}), not "
                         f"{pol.version} ({pol.sha256[:12]}): rebuild with scripts/build.py first")
    want = {c for c in a.categories.split(",") if c}
    cats = [c for c in man["categories"] if c["id"] not in pol.exclude_categories and not c.get("demo")
            and (not want or c["id"] in want)]
    release, created = latest_release(a.releases, a.release)
    created = created or man.get("generated_at")
    metas, snap, wsnap, covs = [], {}, {}, {}
    csnap = {}
    for c in cats:
        rows, (withheld, crowd), cov, meta = build_category(c, a.docs, pol, a.tier, a.out, a.shard_hex)
        csnap[c["id"]] = crowd
        metas.append(meta)
        covs[c["id"]] = cov
        snap[c["id"]] = {r["id"]: r["v"] for r in rows}
        wsnap[c["id"]] = withheld
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
            if prev.get("format") == 2:
                prev = prev["v"]
            entry["prev"] = pf[:-8]
        cats_diff = {}
        for cid, cur in snap.items():
            if prev is not None and cid in prev:
                d = diff_rows(prev[cid], cur, wsnap[cid], csnap[cid])
            elif prev is not None:
                d = diff_rows({}, cur, None, csnap[cid])  # new category since previous release
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
        json.dump({"format": 2, "v": snap, "w": wsnap}, f, separators=(",", ":"))
    brand = "specsheet"
    site = os.path.join(ROOT, "docs", "site.json")
    if os.path.exists(site):
        brand = jload(site).get("brand", brand)
    presets_rel = write_presets(a.docs, metas, a.out)
    match_sha = None if a.no_match else match_catalogue(a.docs, {i for s_ in snap.values() for i in s_}, a.out)
    jdump(dict({"release": release, "tier": a.tier, "built_at": created, "dataset_build": man.get("build"), "categories": metas,
                "shard_hex": a.shard_hex, "match": {"catalogue": "match/catalogue.json", "sha256": match_sha} if match_sha else None, "presets": presets_rel,
                "coverage": source_policy.coverage_table(covs),
                "note": f"{a.tier}-tier query pack: trusted records only, gated by data/source-policy.yaml"}, **pol.manifest_block(brand)),
          os.path.join(a.out, "meta", "manifest.json"))
    pol.check_unlisted(what="build_r2.py")
    print(f"release {release} ({a.tier}, policy {pol.version}): {len(metas)} categories -> {a.out}", file=sys.stderr)


if __name__ == "__main__":
    main()
