"""Publish step for profile-driven categories (ARCHITECTURE 15.6/15.8, team/briefs/a4-contract.md). Called from build.py.

Reads state/specsheet.sqlite (a projection of raw/ + data/decisions + data/_ids, written by scripts/import.py) and emits two
clearly separated datasets per category:

TRUSTED  <cat>/schema.json  <cat>/index.json|index-N.json  <cat>/facets.json  <cat>/products/<id>.json  (+ v0 compat products.json)
         Only claims with review_state=accepted (a human ledger line or a versioned policy; review P0-1), only APPROVED relations,
         inheritance over the approved parent graph in topological order with field-level rules from the profile, and inherited
         provenance re-pointed at the ancestor's real source (review P1-4). Facets and identifier lookup cover trusted rows only.
PREVIEW  preview/<cat>/index.json  preview/<cat>/products/<id>.json
         accepted + candidate claims (never rejected), proposed relations listed. Rows carry "review_scope": "preview". A preview
         detail is a DELTA: header + only the specs whose preview resolution differs from the trusted one (all specs when the
         entity has no trusted record).
Across categories: manifest.json (+ release: accepted digest, policy ids, coverage), lookup/identifiers.json, redirects.json.
"""
import collections, json, re, sqlite3
from pathlib import Path

import jsonschema
import yaml

import catmeta
import resolve as R

CODE = Path(__file__).resolve().parent.parent
ROOT = catmeta.ROOT                    # data root (research/, state/, data/); SPECSHEET_ROOT overrides it for fixture tests
DB = ROOT / "state" / "specsheet.sqlite"
SHARD_BYTES = 2_000_000
# Categories are NOT listed here: every category with an entity in the store and a research/<cat>/spec-profile.yaml is published, with
# its label, columns, market filter and variant label from research/<cat>/category.yaml (scripts/catmeta.py).
V0_TYPE = {"integer": "number", "object": "text", "date": "text"}
_REC = json.loads((CODE / "schemas" / "record.schema.json").read_text())
_PD = json.loads((CODE / "schemas" / "public-detail.schema.json").read_text())
DETAIL_VALIDATOR = jsonschema.Draft202012Validator(_PD, resolver=jsonschema.RefResolver.from_schema(_PD, store={_REC["$id"]: _REC}))


def validate_details(cat, details):
    """Every published detail (trusted + preview) must satisfy schemas/public-detail.schema.json (review P1-8); fail the build otherwise."""
    bad = []
    for d in details:
        e = next(iter(DETAIL_VALIDATOR.iter_errors(d)), None)
        if e is not None:
            bad.append(f"{d['id']}: {'/'.join(map(str, e.path))}: {e.message[:160]}")
    if bad:
        raise SystemExit(f"{cat}: {len(bad)} published details violate public-detail.schema.json, e.g. " + "; ".join(bad[:3]))


def lookup_norm(scheme, v):
    return v if scheme == "gtin" else re.sub(r"[\s.\-]", "", v.upper())


def dump(path, obj, compact=False):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, ensure_ascii=False, separators=(",", ":")) if compact else json.dumps(obj, indent=1, ensure_ascii=False) + "\n")


def fmt_storage(gb):
    return f"{gb / 1000:g} TB" if gb >= 1000 and gb % 1000 == 0 else f"{gb:g} GB"


def _fmt(r, spec, trim=None):
    v = r["value"]
    if isinstance(v, (int, float)) and not isinstance(v, bool):
        if r.get("display"):
            return r["display"]
        u = spec.get("unit") or ""
        if u == "GB" and v >= 1000 and v % 1000 == 0:
            return f"{v / 1000:g} TB"
        return f"{v:g} {u}".strip()
    t = re.sub(r"\s*[®™]", "", str(v))
    return t.split(",")[0][:trim] if trim else t


def variant_label(cfg, specdefs, e, specs):
    """category.yaml `variant_label`: {specs: [...]} joined with ' / ', or {entity_variant: {axis: template}} from the importer's variant record."""
    vl = cfg.get("variant_label")
    if not vl:
        return None
    if "entity_variant" in vl:
        v = json.loads(e["extra"]).get("variant") or {}
        if e["kind"] in ("configuration", "package") and v:
            t = vl["entity_variant"].get(v.get("axis"))
            return t.format(v.get("suffix") or v.get("value")) if t else (v.get("value") or v.get("suffix"))
        return None
    parts = [_fmt(specs[k], specdefs[k], (vl.get("trim") or {}).get(k)) for k in vl.get("specs", []) if specs.get(k, {}).get("status") == "known" and k in specdefs]
    return " / ".join(parts) or None


def load_profile(cat):
    return catmeta.load(cat)["profile"]


def schema_doc(cat, p, cfg):
    groups = [{"id": g["id"], "label": g["label"], "order": i} for i, g in enumerate(p["groups"])]
    prio = collections.Counter()
    fields = []
    for s in p["specs"]:
        prio[s["group"]] += 1
        f = s.get("facet")
        facet = None
        if f:
            fo = f if isinstance(f, dict) else {}
            kind = fo.get("kind") or {"number": "range", "integer": "range", "range": "range", "bool": "bool", "enum": "enum", "list": "multi", "text": "text"}.get(s["type"], "enum")
            facet = {"kind": kind, "path": fo.get("path"), "bins": fo.get("bins") or [], "unknown_bucket": fo.get("unknown_bucket", True),
                     "default_visible": bool(fo.get("default_visible", s.get("tier") == "core"))}
        fields.append({"key": s["key"], "label": s["label"], "group": s["group"], "type": s["type"], "unit": s.get("unit"), "display_unit": s.get("unit"),
                       "enum": s.get("enum"), "items": s.get("items"), "tier": s.get("tier", "detail"), "priority": prio[s["group"]] * 10,
                       "column": s["key"] in cfg["columns"], "display": s.get("display"), "facet": facet,
                       "conditions": s.get("conditions"), "headline_condition": s.get("headline_condition")})
    return {"id": cat, "schema_version": str(p["version"]), "groups": groups, "conditions": p.get("conditions", []), "fields": fields}


def view(ents, claims, absn, specdefs, parent_of, ok_states):
    """Resolve every entity for one review scope, then inherit along approved parent links (parents first)."""
    resolved = {}
    for eid in ents:
        specs = {}
        for k in set(claims[eid]) | set(absn[eid]):
            if k in specdefs:
                cs = [c for c in claims[eid].get(k, []) if c["review"] in ok_states]
                if not cs and not absn[eid].get(k):
                    continue
                r = R.resolve_spec(specdefs[k], cs, absn[eid].get(k, []))
                if r:
                    specs[k] = r
        resolved[eid] = specs
    order, cycles = R.topo(ents, parent_of)
    for eid in order:
        par = parent_of.get(eid)
        if not par or par not in ents:
            continue
        pk, ck = ents[par]["kind"], ents[eid]["kind"]
        for k, r in resolved[par].items():
            if r["status"] != "known" or k in resolved[eid] or not R.inheritable(specdefs[k], pk, ck):
                continue
            resolved[eid][k] = dict(r, inherited_from=r.get("inherited_from") or par)
    return resolved, cycles


def publish(api: Path, build_stats: dict):
    con = sqlite3.connect(DB)
    con.row_factory = sqlite3.Row
    meta = {r["k"]: r["v"] for r in con.execute("SELECT * FROM meta")}
    if meta.get("scope") == "partial":
        raise SystemExit("state/specsheet.sqlite is a partial (--source) import; refusing to publish it over the full release")
    manifest_cats, categories, lookup = [], [], collections.defaultdict(set)
    cats = [r[0] for r in con.execute("SELECT DISTINCT category FROM entities ORDER BY 1")]
    for cat in cats:
        cfg = catmeta.load(cat)
        p = cfg["profile"]
        sch = schema_doc(cat, p, cfg)
        specdefs = {s["key"]: s for s in p["specs"]}
        fields = {f["key"]: f for f in sch["fields"]}
        ents = {r["id"]: dict(r) for r in con.execute("SELECT * FROM entities WHERE category=?", (cat,))}
        idents, aliases, srcs, docs, rels = (collections.defaultdict(list) for _ in range(5))
        claims = collections.defaultdict(lambda: collections.defaultdict(list)); absn = collections.defaultdict(lambda: collections.defaultdict(list))
        for r in con.execute("SELECT i.* FROM identifiers i JOIN entities e ON e.id=i.entity_id WHERE e.category=?", (cat,)):
            idents[r["entity_id"]].append(dict(r))
        for r in con.execute("SELECT a.* FROM aliases a JOIN entities e ON e.id=a.entity_id WHERE e.category=?", (cat,)):
            aliases[r["entity_id"]].append(dict(r))
        for r in con.execute("SELECT s.* FROM entity_sources s JOIN entities e ON e.id=s.entity_id WHERE e.category=? ORDER BY s.entity_id, CAST(substr(s.sid,2) AS INT)", (cat,)):
            srcs[r["entity_id"]].append(dict(r))
        for r in con.execute("SELECT r.* FROM relations r JOIN entities e ON e.id=r.entity_id WHERE e.category=?", (cat,)):
            rels[r["entity_id"]].append(dict(r))
        for r in con.execute("SELECT c.id, c.entity_id, c.mapped_key, c.status, c.kind, c.cond, c.mmode, c.norm_ok, c.norm_value, c.display, c.raw, c.source, "
                             "c.review, c.supersedes FROM claims c JOIN entities e ON e.id=c.entity_id WHERE e.category=? AND c.mapped_key IS NOT NULL", (cat,)):
            claims[r["entity_id"]][r["mapped_key"]].append({
                "id": r["id"], "status": r["status"], "kind": r["kind"], "cond": json.loads(r["cond"] or "{}"), "mmode": r["mmode"], "ok": bool(r["norm_ok"]),
                "value": json.loads(r["norm_value"]) if r["norm_value"] is not None else None, "nx": json.loads(r["display"]) if r["display"] else {},
                "raw": r["raw"], "source": r["source"], "review": r["review"], "supersedes": r["supersedes"]})
        for r in con.execute("SELECT a.* FROM absences a JOIN entities e ON e.id=a.entity_id WHERE e.category=?", (cat,)):
            absn[r["entity_id"]][r["key"]].append(dict(r))
        for r in con.execute("SELECT d.* FROM documents d JOIN entities e ON e.id=d.entity_id WHERE e.category=?", (cat,)):
            docs[r["entity_id"]].append(dict(r))
        parent_of = {eid: e["parent_id"] for eid, e in ents.items() if e["parent_id"] in ents}

        trusted, cyc = view(ents, claims, absn, specdefs, parent_of, {"accepted"})
        preview, _ = view(ents, claims, absn, specdefs, parent_of, {"accepted", "candidate"})

        def selectable(eid, specs):
            return ents[eid]["kind"] != "family" and any(r["status"] in ("known", "conflicted") for r in specs.values()) \
                and catmeta.passes_market_filter(cfg, idents[eid])

        rows_t = [eid for eid in sorted(ents) if selectable(eid, trusted[eid])]
        rows_p = [eid for eid in sorted(ents) if selectable(eid, preview[eid])]
        dropped_us = sum(1 for eid, e in ents.items() if e["kind"] != "family" and preview[eid] and not catmeta.passes_market_filter(cfg, idents[eid]))
        pub = set(rows_t)
        anc = set()
        for eid in rows_t:
            for r in (ents[eid]["parent_id"], ents[eid]["family_id"]):
                while r and r in ents and r not in pub and r not in anc:
                    anc.add(r); r = ents[r]["parent_id"]
        files_t = pub | anc
        children = collections.defaultdict(list)
        for eid in files_t:
            if ents[eid]["parent_id"] in files_t:
                children[ents[eid]["parent_id"]].append(eid)

        def sources_for(eid, specs):
            """Own source table + one entry per ancestor source actually cited by an inherited spec (new local sid, ancestor's real URL)."""
            out = [{"id": s["sid"], "url": s["url"], "label": s["label"] or s["url"], "tier": s["tier"], "retrieved_at": s["retrieved_at"]} for s in srcs[eid]]
            n, remap = len(out), {}
            for k, r in specs.items():
                own = r.get("inherited_from")
                if not own:
                    continue
                table = {s["sid"]: s for s in srcs[own]}
                new = []
                for sid in r["sources"]:
                    key = (own, sid)
                    if key not in remap and sid in table:
                        n += 1; remap[key] = f"s{n}"; s = table[sid]
                        out.append({"id": remap[key], "url": s["url"], "label": s["label"] or s["url"], "tier": s["tier"], "retrieved_at": s["retrieved_at"], "via": own})
                    if key in remap:
                        new.append(remap[key])
                specs[k] = dict(r, sources=new)
            return out

        def header(eid, specs, scope):
            e = ents[eid]
            ids_out = [{"scheme": i["scheme"], "value": i["value"], "value_raw": i["value_raw"], "issuer": i["issuer"], "market": i["market"],
                        "package_level": i["package_level"], "role": i["role"]} for i in idents[eid]
                       if (i["scheme"] in ("mtm", "mfr_model", "mfr_sku", "gtin") or i["scheme"].startswith("x_")) and i["valid"]]
            ok_rel = ("approved",) if scope == "trusted" else ("approved", "proposed")
            relations = [{"type": r["type"], "target": r["target_id"], "status": r["status"], "method": r["method"], "decision": r["decision"]}
                         for r in rels[eid] if r["status"] in ok_rel and (scope != "trusted" or r["target_id"] in files_t)]
            lc = {"current": "current", "discontinued": "discontinued"}.get(e["lifecycle"], "unknown")
            model_str = next((i["value"] for i in idents[eid] if i["scheme"] in ("mtm", "mfr_model", "mfr_sku") and i["role"] == "key"), None)
            vl = variant_label(cfg, specdefs, e, specs)
            return {"record_format": "specsheet.record/1", "review_scope": scope, "id": eid, "category": cat, "kind": e["kind"],
                    "brand": {"id": e["brand"], "name": e["brand_name"]}, "name": e["name"] or eid, "variant_label": vl, "lifecycle": {"state": lc},
                    "identifiers": ids_out, "aliases": [{"text": a["text"], "kind": a["kind"]} for a in aliases[eid]], "relations": relations,
                    "family": (ents[e["family_id"]]["name"] if e["family_id"] in ents else None), "model": model_str, "variant": vl}

        core = [k for k, f in fields.items() if f["tier"] == "core"]
        keep_vs = {k for k, f in fields.items() if f["facet"] or f["column"]}

        def row_of(eid, d, specs, scope):
            e = ents[eid]
            v, s, x = {}, {}, {}
            for k in keep_vs:
                r = specs.get(k)
                if not r:
                    continue
                if r["status"] == "known":
                    v[k] = r["value"]
                    if r.get("display") or r.get("qualifier"):
                        x[k] = {f: r[f] for f in ("display", "qualifier") if r.get(f)}
                elif r["status"] != "not_yet_extracted":
                    s[k] = r["status"]
            keyids = [f"{i['scheme']}:{i['value']}" for i in idents[eid] if i["valid"] and (i["role"] == "key" or i["scheme"] == "gtin")]
            search = [d["name"].lower()] + [a["text"].lower() for a in aliases[eid]][:4] + [i.lower() for i in keyids] + [i["value_raw"].lower() for i in idents[eid] if i["role"] == "key"]
            row = {"id": eid, "kind": e["kind"], "brand": e["brand_name"], "brand_id": e["brand"], "name": d["name"], "variant_label": d["variant_label"], "family_id": e["family_id"],
                   "parent_id": e["parent_id"], "ids": keyids, "search": sorted(set(search)), "v": v, "s": s,
                   "completeness": {"core": [sum(1 for k in core if k in specs and specs[k]["status"] == "known"), len(core)]},
                   "lifecycle": d["lifecycle"]["state"], "demo": False}
            if x:
                row["x"] = x
            if scope == "preview":
                row["review_scope"] = "preview"; row["in_trusted"] = eid in pub
            return row

        out_rows, prev_rows, details, pdetails = [], [], {}, {}
        stats = collections.Counter()
        for eid in sorted(files_t):
            specs = {k: dict(v) for k, v in trusted[eid].items()}
            d = header(eid, specs, "trusted")
            ex = json.loads(ents[eid]["extra"])
            for r in specs.values():
                stats[r["status"]] += 1
            stats["inherited"] += sum(1 for r in specs.values() if r.get("inherited_from"))
            d.update({"contents": [], "options": [], "sources": sources_for(eid, specs), "media": [],
                      "documents": [{"url": x["url"], "kind": x["kind"], "label": x["label"] or x["kind"]} for x in docs[eid] if x["url"]],
                      "notes": ("Regional (non-US) packages sharing this configuration: %d. " % ex["regional_mtms"] if ex.get("regional_mtms") else "")
                               + "Values are manufacturer-published claims accepted by a recorded decision (data/decisions: ledger or versioned policy).",
                      "demo": False, "marketing_terms": [], "confidence": {"level": "unrated", "scope": "accepted"},
                      "identity_caveat": "Identity from manufacturer identifiers; links shown are approved (source-stated or human-reviewed)."})
            d["specs"] = {k: specs[k] for k in sorted(specs)}
            if children.get(eid):
                d["children"] = sorted(children[eid])
            details[eid] = d
            if eid in pub:
                out_rows.append(row_of(eid, d, specs, "trusted"))
                for i in idents[eid]:
                    if i["valid"] and not i["disputed"] and i["scheme"] in ("mtm", "mfr_model", "mfr_sku", "gtin"):
                        lookup[f"{i['scheme']}:{lookup_norm(i['scheme'], i['value'])}"].add(eid)
        for eid in rows_p:
            specs = {k: dict(v) for k, v in preview[eid].items()}
            d = header(eid, specs, "preview")
            srcs_out = sources_for(eid, specs)
            t = details.get(eid, {}).get("specs", {})
            delta = {k: specs[k] for k in sorted(specs) if json.dumps(t.get(k), sort_keys=True) != json.dumps(specs[k], sort_keys=True)}
            if not delta and eid in pub:
                continue
            d.update({"specs": delta, "sources": srcs_out, "trusted": eid in pub, "demo": False,
                      "notes": "PREVIEW: includes unreviewed candidate claims and proposed links. Not part of the trusted catalogue, facets or lookup."})
            pdetails[eid] = d
            prev_rows.append(row_of(eid, d, specs, "preview"))
            stats["preview_specs_delta"] += len(delta)

        validate_details(cat, list(details.values()) + list(pdetails.values()))
        folder = api / cat
        dump(folder / "schema.json", sch)
        (folder / "products").mkdir(parents=True, exist_ok=True)    # a category with zero trusted rows still has an (empty) products dir
        for eid, d in details.items():
            dump(folder / "products" / f"{eid}.json", d, compact=True)
        paths = write_shards(folder, out_rows)
        dump(folder / "facets.json", build_facets(fields, out_rows), compact=True)
        pfolder = api / "preview" / cat
        (pfolder / "products").mkdir(parents=True, exist_ok=True)
        for eid, d in pdetails.items():
            dump(pfolder / "products" / f"{eid}.json", d, compact=True)
        ppaths = write_shards(pfolder, prev_rows)
        # v0 compat: slim products.json (columns only) + fields the UI can drive
        compat_fields = [f for f in sch["fields"] if f["column"]]     # columns only (size budget: the UI reads index shards; this file is a v0 fallback)
        v0f = [{"key": f["key"], "label": f["label"], "group": f["group"], "type": V0_TYPE.get(f["type"], f["type"]) if f["type"] != "list" else "list", "unit": f["unit"],
                "facet": bool(f["facet"]), "priority": f["priority"], "column": f["column"]} for f in compat_fields]
        slim = []
        for r in out_rows:
            sp = {}
            for f in v0f:
                x = details[r["id"]]["specs"].get(f["key"])
                sp[f["key"]] = ({"value": x["value"], "status": x["status"], "sources": x["sources"], "confidence": None, "source_scope": x["source_scope"]} if x
                                else {"value": None, "status": "not_yet_extracted", "sources": [], "confidence": None, "source_scope": "none"})
            d = details[r["id"]]
            slim.append({"id": r["id"], "category": cat, "brand": r["brand"], "name": r["name"], "family": d["family"], "model": d["model"], "variant": d["variant"],
                         "identifiers": [{"scheme": i["scheme"], "value": i["value"], "issuer": i["issuer"], "market": i["market"], "package_level": i["package_level"]}
                                         for i in d["identifiers"] if i["role"] == "key"],
                         "specs": sp, "confidence": d["confidence"], "demo": False})
        dump(folder / "products.json", slim, compact=True)
        prev_entry = {"review_scope": "preview", "index": [f"preview/{cat}/{x}" for x in ppaths], "count": len(prev_rows),
                      "products": f"preview/{cat}/products/", "only_preview": sum(1 for r in prev_rows if not r["in_trusted"])}
        categories.append({"id": cat, "name": cfg["name"], "description": cfg["description"].strip(), "count": len(out_rows), "demo": False, "status": "accepted",
                           "schema": f"{cat}/schema.json", "index": [f"{cat}/{x}" for x in paths], "facets": f"{cat}/facets.json", "products": f"{cat}/products.json",
                           "fields": v0f, "preview": prev_entry})
        manifest_cats.append({"id": cat, "schema_version": sch["schema_version"], "count": len(out_rows), "index": [f"{cat}/{x}" for x in paths], "facets": f"{cat}/facets.json",
                              "demo": False, "preview": prev_entry})
        build_stats[cat] = {"rows": len(out_rows), "detail_files": len(details), "ancestor_only": len(anc), "us_filter_dropped": dropped_us, "shards": len(paths),
                            "preview_rows": len(prev_rows), "preview_only": prev_entry["only_preview"], "parent_cycles": len(cyc), "spec_status": dict(stats),
                            "kinds": dict(collections.Counter(r["kind"] for r in out_rows))}
    dump(api / "lookup" / "identifiers.json", {k: sorted(v) for k, v in sorted(lookup.items())}, compact=True)
    tomb = ROOT / "data" / "_ids" / "tombstones.jsonl"
    red = {}
    if tomb.exists():
        for ln in tomb.read_text().splitlines():
            if ln.strip():
                t = json.loads(ln); red[t["id"]] = {"replaced_by": t.get("replaced_by", []), "reason": t.get("reason", "")}
    dump(api / "redirects.json", red)
    cov = collections.defaultdict(dict)
    for r in con.execute("SELECT * FROM coverage"):
        cov[r["source_id"]][r["k"]] = r["v"]
    release = {"accepted_digest": meta.get("accepted_digest"), "policies": json.loads(meta.get("policies") or "[]"), "ledger_lines": int(meta.get("ledger_lines") or 0),
               "profiles": json.loads(meta.get("profiles") or "{}"), "coverage": cov}
    return categories, manifest_cats, release


def write_shards(folder, rows):
    rows.sort(key=lambda r: (r["brand"], r["name"], r["id"]))
    shards, cur, size = [], [], 0
    for r in rows:
        b = len(json.dumps(r, separators=(",", ":"))) + 1
        if cur and size + b > SHARD_BYTES:
            shards.append(cur); cur, size = [], 0
        cur.append(r); size += b
    shards.append(cur)
    paths = ["index.json"] if len(shards) == 1 else [f"index-{n}.json" for n in range(len(shards))]
    for pth, rws in zip(paths, shards):
        dump(folder / pth, rws, compact=True)
    return paths


def build_facets(fields, rows):
    out = {}
    for k, f in fields.items():
        if not f["facet"]:
            continue
        fa = f["facet"]
        kind = fa["kind"]
        c = collections.Counter(); nums = []
        unk = na = conf = nye = 0
        for r in rows:
            if k in r["v"]:
                v = r["v"][k]
                if kind == "range" and isinstance(v, (int, float)) and not isinstance(v, bool):
                    nums.append(v)
                elif isinstance(v, list):
                    for x in v:
                        c[str(x)] += 1
                elif isinstance(v, dict):
                    continue
                else:
                    c[json.dumps(v) if isinstance(v, bool) else str(v)] += 1
            elif k in r["s"]:
                st = r["s"][k]
                unk += st in ("unknown", "not_published"); na += st == "not_applicable"; conf += st == "conflicted"
            else:
                nye += 1
        e = {"kind": kind, "unknown": unk, "not_applicable": na, "conflicted": conf, "not_yet_extracted": nye}
        if kind == "range":
            e["min"] = min(nums) if nums else None; e["max"] = max(nums) if nums else None
            bins = fa["bins"]
            if nums and bins:
                edges = [min(nums)] + [b for b in bins if min(nums) < b < max(nums)] + [max(nums)]
                e["bins"] = [{"lo": lo, "hi": hi, "n": sum(1 for x in nums if lo <= x < hi or (hi == edges[-1] and x == hi))} for lo, hi in zip(edges, edges[1:])]
            else:
                e["bins"] = []
        else:
            e["counts"] = dict(c.most_common(60))
            e["distinct"] = len(c)
        out[k] = e
    return out
