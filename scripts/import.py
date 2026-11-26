#!/usr/bin/env python3
"""raw/ + data/ (decisions, id registry) -> working store state/specsheet.sqlite. ARCHITECTURE 15.4/15.5/15.8.

  python3 -I scripts/import.py [--db PATH] [--data DIR] [--reparse] [--source ID ... --db OTHER] [--seed-ids OLD.sqlite]

The sqlite is a PROJECTION: deleting it and re-running reproduces the same entity ids, links, claims and review states, because
the only other inputs are git-tracked: data/_ids/registry.jsonl (anchor -> id, append-only), data/_ids/tombstones.jsonl,
data/decisions/policies.yaml (versioned auto-accept policies) and data/decisions/ledger.jsonl (human decisions).
--source restricts ingestion and therefore REFUSES to overwrite the default store (write a scratch --db instead).

Identity (scripts/identity.py, review P0-3): matching on scoped keys (scheme, issuer, normalised value, market, level). A package
GTIN is an alias that never merges models/configurations; GTINs are check-digit validated (invalid -> raw alias only); a GTIN on
two unrelated entities is an identity_conflict (excluded from lookup). An observation whose keys hit two existing entities is
quarantined unless the ledger approved that merge. Every mint/attach/quarantine/proposal is an identity_events row.
Links: source-stated hierarchy (PSREF MT/product, ASUS model column, page-listed variants) is approved by policy
rel/source-stated-hierarchy@1; suffix inference (power-strip colour/pack/OEM suffixes) only PROPOSES a relation.
Claims (review P0-2): the full validated claim document is stored (`doc`), plus indexed key/conditions/kind/measurement, the
profile-normalised value (normalize.py; review P1-5) and review_state/decision from the ledger or a policy (decisions.py).
Claim ids are content hashes over stable evidence identity (source id, ref, locator, key, value, unit, conditions, kind,
measurement, extractor name) - not over record-local source tokens or the extractor version.
Regional Lenovo MTMs (review P1-6): every observed MTM is kept in `regional_observations` (+ `coverage`), evidence by reference
(snapshot + MTM in raw/); only US MTMs become published entities for now.
Review 2 (round 4): anchors carry the level (identity.py v2, legacy registry lines migrated by recorded kind; ambiguity, kind changes and
rebind attempts become identity_conflicts rows); policies are content-locked (decisions.py check_lock) and relation rules are checked
against the parser that produced the link; HTML entities in names/aliases/claim literals are decoded once here (dehtml); the meta table
records the release inputs (raw snapshot digest, parser fingerprints, profile/normaliser/code/policy/ledger/registry digests).
"""
import argparse, collections, hashlib, html, json, os, re, sqlite3, sys, time
from pathlib import Path

CODE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(CODE / "crawler" / "adapters"))
sys.path.insert(0, str(CODE / "scripts"))
import catmeta  # noqa: E402
ROOT = catmeta.ROOT                  # data root (SPECSHEET_ROOT overrides it for fixture tests)
import jsonschema  # noqa: E402
import yaml  # noqa: E402
import _contract as C  # noqa: E402
import _cpu  # noqa: E402
import _lcell  # noqa: E402
import bundles as B  # noqa: E402
import tvcert as TC  # noqa: E402
import xwalk as XW  # noqa: E402
import docattach as DA  # noqa: E402
import docspec_attach as DS  # noqa: E402
import docspec_r3 as DS3  # noqa: E402
import docspec_r7tv as DS7  # noqa: E402
import imgattach as IA  # noqa: E402
import hubattach as HA  # noqa: E402
import corrections as CR  # noqa: E402
import registry  # noqa: E402
import identity as I  # noqa: E402
import normalize as N  # noqa: E402
from decisions import Decisions  # noqa: E402

DB_DEFAULT = ROOT / "state" / "specsheet.sqlite"
COLORS = ["DBL", "HPK", "BK", "GY", "WH", "PK", "TL", "BLK", "WHT"]
COLORS_TL = ["CW", "B", "W"]
PACKS = ["MP2", "MP3", "MP4", "2PK", "3PK", "4PK", "5PK", "6PK", "10PK"]
STAGE_FIX = {"mapping": "table", "html_table": "table", "spec_html": "table", "socrata_json": "feed", "psref_json": "feed", "next_data": "feed"}     # adapter-local stage names -> schema enum


def slug(v):
    return re.sub(r"[^a-z0-9]+", "-", str(v).lower()).strip("-")


def canon(obj):
    return json.dumps(obj, sort_keys=True, ensure_ascii=False, separators=(",", ":"))


def canon_cond(c):
    return {k: (sorted(v, key=str) if isinstance(v, list) else v) for k, v in sorted((c or {}).items())}


class Ent:
    def __init__(self, category, kind, brand):
        self.id = None; self.idhint = None; self.category = category; self.kind = kind; self.brand = brand; self.name = None
        self.parent = None; self.family = None
        self.keys = set()        # scoped keys (identity.key tuples)
        self.idents = {}         # (scheme, norm|raw) -> ident dict (published identifiers, key + alias)
        self.aliases = {}
        self.claims = []         # (claim, obs) obs = (source_id, ref, snapshot)
        self.absences = []
        self.srcs = {}           # snapshot -> source dict
        self.extra = {}
        self.lifecycle = None
        self.documents = []
        self.obs = set()
        self.rels = []           # (type, target Ent, method)


class World:
    def __init__(self, category, dec, events, meta=None):
        self.category, self.dec, self.events, self.meta = category, dec, events, meta
        self.brand_names = {}
        self.ents, self.index = [], {}
        self.quarantine = []
        self.deferred = []       # observations whose adapter reported a page/label identity conflict (review 3): resolved after all sources
        self.id_review = []      # (entity, scheme, value, reason) -> identity_conflicts rows once ids exist

    def anchors(self, keys):
        return sorted(I.anchor(self.category, k) for k in keys)

    def get(self, kind, brand, keys, obs):
        """Scoped-key match at this level. Two different hits = conflicting strong identifiers -> quarantine (None)."""
        ks = [k for k in keys if k is not None]
        hits = []
        for k in ks:
            e = self.index.get(k)
            if e is not None and e not in hits:
                hits.append(e)
        if len(hits) > 1:
            allk = set(ks) | {k for h in hits for k in h.keys}
            if self.dec.merge_allowed(self.anchors(allk)):
                for h in hits[1:]:
                    self.merge(hits[0], h, obs)
                hits = hits[:1]
            else:
                q = {"kind": kind, "keys": self.anchors(ks), "hits": [self.anchors(h.keys) for h in hits], "obs": obs}
                self.quarantine.append(q)
                self.events.append(("quarantine", self.category, None, self.anchors(ks), obs, {"hits": q["hits"]}))
                return None
        if hits:
            e = hits[0]
            new = [k for k in ks if k not in e.keys]
            if new:
                self.events.append(("attach_key", self.category, e, self.anchors(new), obs, {}))
        else:
            e = Ent(self.category, kind, brand)
            self.ents.append(e)
            self.events.append(("create", self.category, e, self.anchors(ks), obs, {"kind": kind}))
        for k in ks:
            self.index[k] = e; e.keys.add(k)
        if obs:
            e.obs.add(obs)
        return e

    def merge(self, a, b, obs):
        """Ledger-approved merge only: fold b into a, keep b's attachments (reversible via a split decision + replay)."""
        self.events.append(("merge", self.category, a, self.anchors(b.keys), obs, {}))
        a.keys |= b.keys; a.obs |= b.obs
        for k, v in b.idents.items():
            a.idents.setdefault(k, v)
        a.aliases.update(b.aliases); a.claims += b.claims; a.absences += b.absences
        a.srcs.update(b.srcs); a.documents += b.documents; a.rels += b.rels
        for k, v in b.extra.items():
            a.extra.setdefault(k, v)
        a.parent = a.parent or b.parent; a.family = a.family or b.family; a.name = a.name or b.name
        for k in b.keys:
            self.index[k] = a
        self.ents.remove(b)


def K(scheme, value, brand, level, market=None):
    return I.key(scheme, value, brand, market, level)


def add_ident(e, i, role=None, level=None):
    scheme = i["scheme"]
    nv = I.norm_value(scheme, i["value"], e.brand)
    valid = nv is not None
    d = {"scheme": scheme, "value": nv if valid else str(i["value"]), "value_raw": str(i.get("value_raw", i["value"])),
         "issuer": "GS1" if scheme == "gtin" else (i.get("issuer") or e.brand), "market": i.get("market"),
         "package_level": level or i.get("package_level") or "unverified", "role": (role or i.get("role") or "alias") if valid else "alias",
         "valid": valid}
    if scheme == "gtin":
        d["package_level"] = "package"; d["role"] = "alias"     # a GTIN names a trade item (package), never the model/config
    k = (scheme, d["value"])
    old = e.idents.get(k)
    if old is None or (old["role"] == "alias" and d["role"] == "key"):
        e.idents[k] = d
    return k


def add_src(e, pr, rec, sid="s1"):
    s = next((x for x in pr["sources"] if x["id"] == sid), None) or {"id": sid, "url": rec["url"], "tier": "manufacturer"}
    e.srcs.setdefault(rec["snapshot"], {"url": s["url"], "tier": s.get("tier", "manufacturer"), "label": s.get("label") or s.get("title"),
                                       "snapshot": rec["snapshot"], "retrieved_at": rec.get("fetched_at")})


def obs_of(sid, rec):
    return (sid, str(rec["ref"]), rec["snapshot"])


def attach_claims(pr, rec, sid, resolve, default=None):
    n = 0
    for c in pr["claims"]:
        e = resolve(c.get("locator") or {}) or default
        if e is None:
            continue
        add_src(e, pr, rec)
        e.claims.append((c, obs_of(sid, rec)))
        n += 1
    return n


PARSER = {"current": None}       # parser (id@version) of the observation being imported: relation policies are pinned to it


def link(child, typ, parent, method):
    if child is not None and parent is not None and child is not parent and not any(r[0] == typ and r[1] is parent for r in child.rels):
        child.rels.append((typ, parent, method, PARSER["current"] if not method.startswith(("suffix:", "stem:")) else None))


_ENT = re.compile(r"&(#\d+|#x[0-9a-fA-F]+|[A-Za-z][A-Za-z0-9]{1,31});")


def _un(v):
    return html.unescape(v) if isinstance(v, str) and _ENT.search(v) else v


def dehtml(pr):
    """Decode HTML entities (&trade; &reg; &amp; &#8482;) in names/aliases/claim values and literals, once, at import (coordinator
    finding 2026-11-23). Identifier VALUES are left alone (identity keys must not move); their value_raw is decoded. -> fields changed."""
    n = 0
    for a in pr.get("aliases") or []:
        t = _un(a.get("text")); n += t != a.get("text"); a["text"] = t
    for c in pr.get("claims") or []:
        for f in ("value", "raw", "quote"):
            if isinstance(c.get(f), str):
                t = _un(c[f]); n += t != c[f]; c[f] = t
            elif isinstance(c.get(f), list):
                t = [_un(x) for x in c[f]]; n += t != c[f]; c[f] = t
    for i in pr.get("identifiers") or []:
        if isinstance(i.get("value_raw"), str):
            t = _un(i["value_raw"]); n += t != i["value_raw"]; i["value_raw"] = t
    return n


# ----------------------------------------------------------------------------- per-source resolvers
def do_lenovo(world, meta, sid, rec, pr, extra, stats):
    brand = meta["brand"]
    ob = obs_of(sid, rec)
    pk = next(i for i in pr["identifiers"] if i["scheme"] == "mfr_model")
    title = next((a["text"] for a in pr["aliases"]), pk["value"])
    fam = world.get("family", brand, [K("x_lenovo_product", pk["value"], brand, "family")], ob)
    if fam is None:
        return
    fam.name = title; fam.idhint = f"{brand}-{slug(pk['value'])}"; fam.aliases[title] = "marketing_name"; add_src(fam, pr, rec)
    add_ident(fam, dict(pk, scheme="x_lenovo_product"), role="key", level="family")
    by_mtm, mts = {}, {}
    ids = pr["identifiers"]
    for n, i in enumerate(ids):
        if i["scheme"] == "x_lenovo_machine_type":
            mt = world.get("model", brand, [K("x_lenovo_machine_type", i["value"], brand, "model")], ob)
            if mt is None:
                continue
            mt.idhint = f"{brand}-{i['value'].lower()}"; mt.name = f"{title} ({i['value']})"
            link(mt, "member_of_family", fam, "adapter:lenovo-psref"); mt.family = fam
            add_ident(mt, i, role="key", level="model"); add_src(mt, pr, rec); mts[i["value"]] = mt
        elif i["scheme"] == "mtm":
            e = world.get("configuration", brand, [K("mtm", i["value"], brand, "configuration")], ob)
            if e is None:
                continue
            e.idhint = f"{brand}-{i['value'].lower()}"; e.name = title; e.family = fam
            mt = mts.get(i["value"][:4]) or world.get("model", brand, [K("x_lenovo_machine_type", i["value"][:4], brand, "model")], ob)
            if mt is not None and mt.idhint is None:
                mt.idhint = f"{brand}-{i['value'][:4].lower()}"; mt.name = f"{title} ({i['value'][:4]})"
                link(mt, "member_of_family", fam, "adapter:lenovo-psref"); mt.family = fam
                add_ident(mt, {"scheme": "x_lenovo_machine_type", "value": i["value"][:4]}, role="key", level="model")
            link(e, "configuration_of", mt, "adapter:lenovo-psref")
            add_ident(e, i, role="key", level="configuration")
            nxt = ids[n + 1] if n + 1 < len(ids) else None
            if nxt and nxt["scheme"] == "gtin":
                add_ident(e, nxt)
            e.lifecycle = "current"; e.aliases[title] = "marketing_name"; add_src(e, pr, rec)
            by_mtm[i["value"]] = e
    stats["claims_adapter"] += attach_claims(pr, rec, sid, lambda loc: by_mtm.get(loc.get("mtm")))
    groups = collections.Counter(m[:8] for m, _, _ in extra["nonus"])
    for us, e in by_mtm.items():
        e.extra["regional_mtms"] = groups.get(us[:8], 0)
    stats["nonus_mtms"] += len(extra["nonus"]); stats["us_mtms"] += len(by_mtm); stats["lenovo_all_mtms"] += extra["total"]
    stats["regional"] += [(m, m[:8], m[:4], fam, c, g, rec["snapshot"]) for m, g, c in extra["nonus"]]
    for m in by_mtm:
        stats["regional"].append((m, m[:8], m[:4], fam, "US", None, rec["snapshot"]))
    colmap, emitted = world.psref, world.psref_emitted
    for col, cnt in extra["columns"].items():
        if col not in emitted:
            stats["psref_cols"][col] += cnt
    for row in extra["us_rows"]:
        e = by_mtm.get(row.get("Model"))
        if e is None:
            continue
        for col, key in colmap.items():
            if col in emitted:
                continue
            v = (row.get(col) or "").strip() if isinstance(row.get(col), str) else ""
            if v:
                c = C.claim(row["Model"], key, v, None, v, "s1", "import.py+psref-mapping@1", "table", rec["fetched_at"],
                            locator={"mtm": row["Model"], "column": col})
                e.claims.append((c, ob)); stats["claims_psref_map"] += 1


def do_asus(world, meta, sid, rec, pr, extra, stats):
    brand = meta["brand"]
    ob = obs_of(sid, rec)
    title = next((a["text"] for a in pr["aliases"]), rec["ref"])
    fam = world.get("family", brand, [K("x_asus_series", rec["ref"], brand, "family")], ob)
    if fam is None:
        return
    fam.idhint = f"{brand}-{slug(rec['ref'])}"; fam.name = title; fam.aliases[title] = "marketing_name"; add_src(fam, pr, rec)
    add_ident(fam, {"scheme": "x_asus_series", "value": rec["ref"], "issuer": "asus"}, role="key", level="family")
    by = {}
    ids = pr["identifiers"]
    n = 0
    while n < len(ids):
        i = ids[n]
        if i["scheme"] == "mfr_model" and i.get("package_level") == "model":
            e = world.get("model", brand, [K("mfr_model", i["value"], brand, "model")], ob)
            if e is not None:
                e.idhint = f"{brand}-{slug(i['value'])}"; e.name = title; e.family = fam; e.lifecycle = "current"
                link(e, "member_of_family", fam, "adapter:asus-us")
                add_ident(e, i, role="key", level="model"); add_src(e, pr, rec); e.aliases[title] = "marketing_name"
                by[("model_code", i["value"])] = e
        elif i["scheme"] == "mfr_sku":
            keys = [K("mfr_sku", i["value"], brand, "configuration")]
            nxt = ids[n + 1] if n + 1 < len(ids) else None
            pair = nxt if nxt and nxt["scheme"] == "mfr_model" and nxt.get("package_level") == "configuration" else None
            if pair:
                keys.append(K("mfr_model", pair["value"], brand, "configuration"))
            e = world.get("configuration", brand, keys, ob)
            if e is not None:
                e.idhint = f"{brand}-{slug(i['value'])}"; e.name = title; e.family = fam; e.lifecycle = "current"
                link(e, "member_of_family", fam, "adapter:asus-us")
                add_ident(e, i, role="key", level="configuration"); add_src(e, pr, rec); e.aliases[title] = "marketing_name"
                if pair:
                    add_ident(e, pair, role="key", level="configuration"); stats["asus_sku_model_pairs"] += 1
                by[("sku", i["value"])] = e
            if pair:
                n += 1
        n += 1
    stats["claims_adapter"] += attach_claims(pr, rec, sid, lambda loc: by.get(("model_code", loc.get("model_code"))) if loc.get("model_code") else by.get(("sku", loc.get("sku"))))


def do_apple(world, meta, sid, rec, pr, extra, stats):
    brand = meta["brand"]
    ob = obs_of(sid, rec)
    title = next((a["text"] for a in pr["aliases"]), rec["ref"])
    models = [i for i in pr["identifiers"] if i["scheme"] == "mfr_model"]
    if not models:
        return
    e = world.get("model", brand, [K("mfr_model", i["value"], brand, "model") for i in models], ob)
    if e is None:
        return
    e.idhint = f"{brand}-{slug(models[0]['value'])}"; e.name = title; e.lifecycle = "current"; e.aliases[title] = "marketing_name"; add_src(e, pr, rec)
    e.extra["page_scope"] = [i["value"] for i in models]    # one support page covers these ids; not proof they are one platform
    for i in pr["identifiers"]:
        if i["scheme"] == "mfr_model":
            add_ident(e, i, role="key", level="model")
        elif i["scheme"] == "mfr_sku":
            add_ident(e, i, role="alias", level="configuration")   # part-number templates (xx/A): patterns, not orderable configs
    stats["claims_adapter"] += attach_claims(pr, rec, sid, lambda loc: e, e)


_CAPTOK = re.compile(r"(\d+(?:\.\d+)?)\s*(TB|GB)\b", re.I)


def _own_cap(pr, sku):
    return next((c.get("value") for c in pr["claims"] if c.get("key") == "gen.capacity" and (c.get("locator") or {}).get("sku") == sku
                 and isinstance(c.get("value"), (int, float)) and c["value"] > 0), None)


def _caps(text):
    return {float(v) * (1000 if u.upper() == "TB" else 1) for v, u in _CAPTOK.findall(text)}


def _skus_on_page(pr):
    return {(c.get("locator") or {}).get("sku") for c in pr["claims"] if c.get("key") == "gen.capacity"} - {None} | \
        {i["value"] for i in pr.get("identifiers") or [] if i.get("package_level") == "configuration" and i.get("scheme") == "mfr_sku"}


def _names_sku(text, sku):
    t, v = re.sub(r"[^A-Z0-9]", "", text.upper()), re.sub(r"[^A-Z0-9]", "", str(sku).upper())
    return len(v) >= 5 and v in t


def own_alias(pr, sku):
    """a2 r5: a configuration is named from its OWN marketing alias, never the model's first one (team-tm8fgq512g0c129 was '... 4TB').
    review-8: the alias must be identity-bound. (1) An alias naming this SKU (or carrying sku = it) binds; one naming another SKU of the page
    never does. (2) Otherwise bind by the configuration's own gen.capacity claim (the first marketing_name stating exactly one GB/TB capacity
    equal to it, +-3%) ONLY when no other configuration of the page has that capacity: equal-capacity siblings (heatsink / colour variants)
    are indistinguishable by capacity, so they get None. No capacity claim, or no alias stating it -> None (caller: neutral_name())."""
    others = _skus_on_page(pr) - {sku}
    mk = [a for a in pr["aliases"] if a["kind"] == "marketing_name"]
    for a in mk:
        if (a.get("sku") or (a.get("locator") or {}).get("sku")) == sku or _names_sku(a["text"], sku) and not any(_names_sku(a["text"], o) for o in others):
            return a["text"]
    cap = _own_cap(pr, sku)
    if cap is None:
        return None
    if any((oc := _own_cap(pr, o)) is not None and abs(oc - cap) / cap <= 0.03 for o in others):
        return None                                     # equal-capacity sibling on the page: capacity does not identify this configuration
    for a in mk:
        if a.get("sku") or (a.get("locator") or {}).get("sku") or any(_names_sku(a["text"], o) for o in others):
            continue                                    # bound to (or naming) another configuration
        toks = _caps(a["text"])
        if len(toks) == 1 and abs(next(iter(toks)) - cap) / cap <= 0.03:
            return a["text"]
    return None


def neutral_name(name, pr, sku):
    """review-8: the fallback name (the parent model's / page title) of a configuration on a page with capacity claims must not state another
    capacity: kept when every GB/TB figure in it equals the configuration's own gen.capacity (+-3%), else those figures are removed."""
    if not name or not any(c.get("key") == "gen.capacity" for c in pr["claims"]):
        return name
    toks, cap = _caps(name), _own_cap(pr, sku)
    if not toks or (cap is not None and all(abs(t - cap) / cap <= 0.03 for t in toks)):
        return name
    out = re.sub(r"\s*[-,/|(]?\s*\b\d+(?:\.\d+)?\s*(?:TB|GB)\b\s*\)?", " ", name, flags=re.I)
    out = re.sub(r"\s{2,}", " ", out).strip(" -,/|")
    return out or name


def do_generic(world, meta, sid, rec, pr, extra, stats):
    """dell-us, microsoft-surface, framework-us, samsung-us, razer-us: model-level key identifier (carries `series`) -> model under a
    family; configuration-level mfr_sku (carries `parent`) -> configuration. Claims resolve by locator.sku / locator.model_code."""
    brand = meta["brand"]
    ob = obs_of(sid, rec)
    title = next((a["text"] for a in pr["aliases"] if a["kind"] == "marketing_name"), None) or next((a["text"] for a in pr["aliases"]), rec["ref"])
    models, configs, last = {}, {}, None
    ids = pr["identifiers"]
    for i in ids:
        if i.get("package_level") == "model" and i.get("role", "key") == "key":
            series = i.get("series") or rec["ref"]
            fam = world.get("family", brand, [K("x_series", series, brand, "family")], ob)
            if fam is not None:
                fam.idhint = fam.idhint or f"{brand}-{slug(series)}"; fam.name = fam.name or title; add_src(fam, pr, rec)
                fam.aliases.setdefault(title, "marketing_name")
                add_ident(fam, {"scheme": "x_series", "value": series}, role="key", level="family")
            e = world.get("model", brand, [K(i["scheme"], i["value"], brand, "model")], ob)
            if e is None:
                continue
            e.idhint = e.idhint or f"{brand}-{slug(i['value'])}"; e.name = e.name or title; e.family = fam; e.lifecycle = "current"
            link(e, "member_of_family", fam, f"adapter:{sid}")
            add_ident(e, i, role="key", level="model"); add_src(e, pr, rec)
            for a in pr["aliases"]:
                if a["kind"] in ("marketing_name", "retail_slug"):
                    e.aliases.setdefault(a["text"], a["kind"])
            models[i["value"]] = e
    for i in ids:
        if i.get("package_level") == "configuration" and i.get("role", "key") == "key" and i["scheme"] == "mfr_sku":
            e = world.get("configuration", brand, [K("mfr_sku", i["value"], brand, "configuration")], ob)
            if e is None:
                last = None
                continue
            par = models.get(i.get("parent")) or (next(iter(models.values())) if len(models) == 1 else None)
            e.idhint = e.idhint or f"{brand}-{slug(i['value'])}"; e.name = e.name or own_alias(pr, i["value"]) or neutral_name(par.name if par else title, pr, i["value"]); e.lifecycle = "current"
            link(e, "configuration_of", par, f"adapter:{sid}"); e.family = e.family or (par.family if par else None)
            add_ident(e, i, role="key", level="configuration"); add_src(e, pr, rec)
            configs[i["value"]] = last = e
        elif i.get("package_level") == "configuration" and i.get("role") == "alias" and last is not None:
            add_ident(last, i, role="alias")
    stats["claims_adapter"] += attach_claims(pr, rec, sid, lambda loc: configs.get(loc.get("sku")) if loc.get("sku") else models.get(loc.get("model_code")))
    e0 = next(iter(models.values()), None)
    if e0 is not None:
        e0.absences += [(a, ob) for a in pr["absences"]]
    stats["configs"] += len(configs); stats["models"] += len(models)
    for lab in (pr["fingerprints"].get("unmapped_labels") or {}):
        stats["labels"][(world.category, brand, lab)] += 1
        stats["label_example"].setdefault((world.category, brand, lab), str(pr["fingerprints"]["unmapped_labels"][lab])[:80])


def stem_of(model, cfg):
    """research/monitors/identity.md: cut at the first '/' or '#', drop ONE trailing -X market/colour suffix, strip non-alphanumerics."""
    v = str(model).upper()
    for ch in cfg.get("cut_at") or []:
        v = v.split(ch)[0]
    if cfg.get("strip_market_suffix", True):
        v = re.sub(r"-[A-Z]{1,2}(\.[A-Z]{2,4})?$", "", v)
    if cfg.get("strip_regex"):            # category-declared market/channel tail (research/tvs/identity.md); proposals only
        v = re.sub(cfg["strip_regex"], "", v)
    return re.sub(r"[^A-Z0-9]", "", v)


def do_model(world, meta, sid, rec, pr, extra, stats):
    """importer 'model': one page/row = one model entity (key: mfr_model of the canonical brand, market NOT part of the key so an Energy
    Star `24MP750C` and a maker page `24MP750C` unify when they are exactly equal after normalisation). mtm identifiers -> package entities
    (only markets listed in category.yaml package_markets), hw_rev/edid_id identifiers -> revision entities, other identifiers -> aliases.
    Certifier/regulatory rows (tier != manufacturer) mint models too but never override a manufacturer's name. Stem proposals: stem_links."""
    cm = world.meta
    ob = obs_of(sid, rec)
    ids = pr["identifiers"]
    mi = next((i for i in ids if i["scheme"] == "mfr_model" and i.get("role", "key") == "key"), None)
    if mi is None:
        stats["no_model_identifier"] += 1
        return
    tier = next((x.get("tier") for x in pr["sources"]), "manufacturer")
    fp = pr.get("fingerprints") or {}
    if fp.get("wildcard_pattern"):
        if "es_cert_scopes" in (cm.get("features") or []) and sid == (cm.get("es_cert") or {}).get("source"):
            TC.collect_scope(world, meta, sid, rec, pr, PARSER["current"])      # r7: a certification scope, never a model (scripts/tvcert.py)
        stats["skipped_wildcard_pattern"] += 1
        return
    ic = fp.get("identity_conflict")
    if ic and not extra.get("_deferred"):       # review 3: corroborated pages claim the model key first, whatever the ingestion order
        world.deferred.append((ic.get("severity", 9), sid, str(rec["ref"]), meta, rec, pr, dict(extra, _deferred=True), stats))
        stats["identity_conflict_deferred"] += 1
        return
    listing = next((a["text"] for a in pr["aliases"] if a["kind"] in ("certifier_listing", "marketing_name")), "")
    if tier != "manufacturer" and cm["skip_rx"] is not None and cm["skip_rx"].search(listing):
        stats["skipped_other_category"] += 1
        return
    iss = (mi.get("issuer") or meta["brand"]).lower()
    brand = cm["brand_aliases"].get(iss, iss)
    world.brand_names.setdefault(brand, cm["brand_names"].get(brand) or (meta["brand_name"] if brand == meta["brand"] else brand.upper() if len(brand) <= 3 else brand.title()))
    title = next((a["text"] for a in pr["aliases"] if a["kind"] == "marketing_name"), None) or mi["value_raw"]
    sc = cm.get("identity_scope")
    if not sc:
        raise SystemExit(f"research/{world.category}/category.yaml: importer 'model' needs an explicit identity_scope (review 2 risk 4)")
    scoped = brand in (sc.get("market_scoped_brands") or []) or (sc.get("cross_market_brands", "*") != "*" and brand not in sc["cross_market_brands"])
    mkey = K("mfr_model", mi["value"], brand, "model", mi.get("market") if scoped else None)
    prev = world.index.get(mkey)
    if prev is not None and not scoped and mi.get("market"):
        stated = {v["market"] for (sch, _), v in prev.idents.items() if sch == "mfr_model" and v["role"] == "key" and v["market"]}
        if stated and mi["market"] not in stated:      # unstated matches any market; two different STATED markets never merge automatically
            world.quarantine.append({"kind": "model", "keys": world.anchors([mkey]), "hits": [world.anchors(prev.keys)], "obs": ob})
            world.events.append(("quarantine", world.category, None, world.anchors([mkey]), ob, {"reason": "cross_market_exact", "markets": sorted(stated | {mi["market"]})}))
            stats["quarantined_cross_market"] += 1
            return
    if ic and prev is not None:
        # a contradictory page whose model already exists from another page: quarantined (not attached, nothing minted), reviewable
        world.quarantine.append({"kind": "model", "keys": world.anchors([mkey]), "hits": [world.anchors(prev.keys)], "obs": ob})
        world.events.append(("quarantine", world.category, None, world.anchors([mkey]), ob, {"reason": "identity_conflict:" + ic.get("reason", "?"), "detail": ic}))
        world.id_review.append((prev, "mfr_model", mi["value"], f"{ic.get('reason')}: page {rec['ref']} quarantined, not attached ({json.dumps({k: v for k, v in ic.items() if k not in ('severity', 'model')}, sort_keys=True)[:200]})"))
        stats["quarantined_identity_conflict"] += 1
        return
    e = world.get("model", brand, [mkey], ob)
    if e is None:
        return
    if ic:           # the only page for this model contradicts itself: kept (existing id), listed for review
        world.id_review.append((e, "mfr_model", mi["value"], f"{ic.get('reason')}: sole page {rec['ref']} kept, identity uncorroborated ({json.dumps({k: v for k, v in ic.items() if k not in ('severity', 'model')}, sort_keys=True)[:200]})"))
        stats["identity_conflict_sole_page"] += 1
    for qm in fp.get("quarantined_members") or []:
        world.id_review.append((e, "member_handle", str(qm.get("handle")), f"bundle member quarantined: {qm.get('reason')} (name {qm.get('name')!r}, skus {qm.get('skus')})"))
    e.idhint = e.idhint or f"{brand}-{slug(mi['value'])}"
    nk = (0 if tier == "manufacturer" else 1, sid)      # deterministic whatever the ingestion order: manufacturer name, then source id
    if e.name is None or nk < getattr(e, "name_key", (9, "")):
        e.name = title; e.name_key = nk
    e.lifecycle = e.lifecycle or ("discontinued" if str(fp.get("status", "")).upper() == "DISCONTINUED" else "current")
    add_ident(e, mi, role="key", level="model"); add_src(e, pr, rec)
    e.__dict__.setdefault("msrc", set()).add(sid)
    for a in pr["aliases"]:
        e.aliases.setdefault(a["text"], a["kind"])
    if "es_cert_scopes" in (cm.get("features") or []) and sid == (cm.get("es_cert") or {}).get("source"):
        TC.collect_exact(world, e, sid, rec, pr)                                  # r7: declared-alias re-audit input
    if "same_hardware_relations" in (cm.get("features") or []) and sid == (cm.get("same_hardware") or {}).get("source"):
        XW.collect(world, e, sid, rec, pr, PARSER["current"])                   # r8: declared same-hardware aliases (scripts/xwalk.py)
    bsk = B.collect(world, e, brand, mi, pr, sid, rec, ob, PARSER["current"], cm.get("bundles"), world.brand_names.get(brand, "")) \
        if "bundle_packages" in (cm.get("features") or []) else set()       # r6: bundle SKUs -> package candidates (scripts/bundles.py), minted after all sources
    pkg = (cm.get("package_markets") or {}).get("mtm")
    last_pkg, owners = None, {mi["value"]: e}
    for i in ids:
        if i is mi or id(i) in bsk:
            continue
        sch = i["scheme"]
        if sch == "mtm":
            if pkg and not i["value"].upper().endswith(pkg["suffix"]):
                stats["regional_packages_not_published"] += 1
                last_pkg = None
                continue
            pk = world.get("package", brand, [K("mtm", i["value"], brand, "package")], ob)
            last_pkg = pk
            if pk is None:
                continue
            pk.idhint = pk.idhint or f"{brand}-{slug(i['value'])}"; pk.name = pk.name or f"{title} ({i['value']})"; pk.family = e.family
            add_ident(pk, i, role="key", level="package"); add_src(pk, pr, rec)
            link(pk, "package_of", e, f"adapter:{sid}")
            stats["packages"] += 1
        elif sch in ("hw_rev", "edid_id") or i.get("package_level") == "revision":
            rv = world.get("revision", brand, [K(sch, i["value"], brand, "revision")], ob)
            if rv is not None:
                # `revision_label` (adapter extra, e.g. "V4.60"): the identifier value is then model-scoped ("Archer AX55 V4.60") so versions of
                # different models never collide; the label names the entity and is what claim locators {"hw_rev": label} refer to.
                lab = i.get("revision_label") or i["value"]
                rv.idhint = rv.idhint or (f"{brand}-{slug(mi['value'])}-{slug(lab)}" if i.get("revision_label") else f"{brand}-{slug(mi['value'])}-{slug(i['value'])}")
                rv.name = rv.name or f"{title} (rev {lab})"; rv.extra["revision_label"] = lab
                add_ident(rv, dict(i, market=i.get("market") or mi.get("market")), role="key", level="revision"); add_src(rv, pr, rec)   # a revision is sold where its model is
                link(rv, "variant_of", e, f"adapter:{sid}"); owners[lab] = rv
        elif sch == "gtin" and last_pkg is not None:
            add_ident(last_pkg, i, role="alias")
        else:
            add_ident(e, i, role="alias")
    by_code = {mi["value"]: e}
    by_rev = {k: v for k, v in owners.items() if v is not e}
    stats["revisions"] += len(by_rev)
    stats["claims_adapter"] += attach_claims(pr, rec, sid, lambda loc: by_rev.get(loc.get("hw_rev")) or by_code.get(loc.get("model_code")) or e, e)
    e.absences += [(a, ob) for a in pr["absences"]]
    stats["models"] += 1
    um = fp.get("unmapped") or {}
    if um and all(isinstance(v, dict) for v in um.values()):     # per-model-code unmapped rows (asus_monitors): this entity's own code only
        um = um.get(mi["value"]) or {}
    for lab in um:
        stats["labels"][(world.category, brand, lab)] += 1
        stats["label_example"].setdefault((world.category, brand, lab), str(um[lab])[:80])
        raw = " | ".join(map(str, um[lab])) if isinstance(um[lab], list) else str(um[lab])     # label-mapping.yaml input (A2 2026-11-24)
        stats["label_values"].setdefault((world.category, brand, lab), []).append((e, raw, ob, rec["fetched_at"]))


def stem_links(world, stats):
    """Cross-source PROPOSALS (never merges): models of one brand whose stems agree but whose normalised keys differ, and whose source sets
    differ -> `possible_match`, status proposed (no policy approves it). Exact normalised matches are already one entity (same scoped key)."""
    cfg = world.meta.get("stem") or {}
    groups = collections.defaultdict(list)
    for e in world.ents:
        if e.kind == "model":
            mk = next((v["value"] for (sch, _), v in sorted(e.idents.items()) if sch == "mfr_model" and v["role"] == "key"), None)
            if mk:
                groups[(e.brand, stem_of(mk, cfg))].append((mk, e))
    for (brand, st), members in sorted(groups.items()):
        if len(members) < 2 or len(st) < 4:
            continue
        members.sort(key=lambda t: t[0])
        for n, (ka, a) in enumerate(members):
            for kb, b in members[n + 1:]:
                sa, sb = getattr(a, "msrc", set()), getattr(b, "msrc", set())
                if sa == sb and len(sa) == 1 and not cfg.get("same_source"):
                    continue      # same single source: colour/market siblings of one maker page set, not a cross-source match
                link(b, "possible_match", a, f"stem:{brand}")
                world.events.append(("propose_relation", world.category, b, [], None, {"type": "possible_match", "stem": st}))
                stats["stem_proposals"] += 1


def do_strip(world, meta, sid, rec, pr, extra, stats):
    brand = meta["brand"]
    ob = obs_of(sid, rec)
    m = next((i for i in pr["identifiers"] if i["scheme"] == "mfr_model"), None)
    if m is None:
        stats["no_model"] += 1
        return
    ids = pr["identifiers"]
    cfgs, model_gtins, last = [], [], None
    for i in ids:
        if i["scheme"] == "mfr_sku" and i.get("package_level") == "configuration":
            cfgs.append([i, []]); last = cfgs[-1]
        elif i["scheme"] == "gtin":
            (last[1] if last is not None else model_gtins).append(i)
    e = world.get("model", brand, [K("mfr_model", m["value"], brand, "model")], ob)     # GTINs are NOT merge keys (package level)
    if e is None:
        return
    e.idhint = e.idhint or f"{brand}-{slug(m['value'])}"
    for i in ids:
        if i["scheme"] == "mfr_sku" and i.get("package_level") == "configuration":
            continue
        if i["scheme"] == "gtin" and cfgs and i not in model_gtins:
            continue
        add_ident(e, i, role="key" if i["scheme"] == "mfr_model" else "alias", level="model" if i["scheme"] == "mfr_model" else None)
    for a in pr["aliases"]:
        e.aliases.setdefault(a["text"], a["kind"])
    e.name = e.name or next((a["text"] for a in pr["aliases"] if a["kind"] == "marketing_name"), None) or m["value"]
    add_src(e, pr, rec)
    page = e.srcs.get(rec["snapshot"], {}).get("url") or rec["url"]      # review 6 fix 3: an adapter's document links carry their own page edge
    e.documents += [dict(d, linked_from=d.get("linked_from") or page) for d in pr.get("documents", [])]
    e.absences += [(a, ob) for a in pr["absences"]]
    if (extra or {}).get("discontinued"):
        e.lifecycle = "discontinued"
    target = e
    for sku, gts in cfgs:
        ce = world.get("configuration", brand, [K("mfr_sku", sku["value"], brand, "configuration")], ob)
        if ce is None:
            continue
        ce.idhint = ce.idhint or f"{brand}-{slug(sku['value'])}"; ce.name = ce.name or e.name
        link(ce, "configuration_of", e, f"page-variants:{sid}")
        add_ident(ce, sku, role="key", level="configuration"); add_src(ce, pr, rec); ce.aliases.setdefault(e.name, "marketing_name")
        vi = (pr["fingerprints"].get("variants") or {}).get(sku["value"])
        if vi:
            ce.extra["variant"] = {"axis": vi["axis"], "value": vi["value"]}
        for g in gts:
            add_ident(ce, g)
        stats["configs"] += 1
        if (pr["fingerprints"] or {}).get("claims_on") == "configuration":
            target = ce; ce.extra["claims_own_page"] = True
    stats["claims_adapter"] += attach_claims(pr, rec, sid, lambda loc: target, target)
    for lab, raw in (pr["fingerprints"].get("unmapped") or {}).items():
        stats["labels"][(world.category, brand, lab)] += 1
        stats["label_example"].setdefault((world.category, brand, lab), str(raw)[:80])
        stats["label_values"].setdefault((world.category, brand, lab), []).append((e, str(raw), ob, rec["fetched_at"]))


# ----------------------------------------------------------------------------- label mapping (research/<cat>/label-mapping.yaml)
def _n(raw):
    m = re.search(r"-?\d[\d,]*\.?\d*", raw or "")
    if not m:
        return None
    v = float(m.group(0).replace(",", ""))
    return int(v) if v == int(v) else v


def _clean(raw):
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", (raw or "").replace("&nbsp;", " "))).strip()


def _dims(raw, order):
    m = re.match(r"\s*([\d.]+)\s*x\s*([\d.]+)\s*x\s*([\d.]+)", raw or "")
    if not m:
        return None
    return dict(zip(order, [float(x) for x in m.groups()]), unit="in")


def _usb_types(raw):
    a = re.search(r"(\d+)\s*(?:Type |USB-?)A", raw or "", re.I)
    c = re.search(r"(\d+)\s*(?:Type |USB-?)C", raw or "", re.I)
    d = {k: int(m.group(1)) for k, m in (("a", a), ("c", c)) if m}
    return d or None


TRANSFORMS = {
    "num": _n,
    "dollars": lambda r: (lambda m: int(m.group(1).replace(",", "")) if m else None)(re.search(r"\$\s?(\d[\d,]*)", _clean(r))),
    "yesno": lambda r: True if _clean(r).lower().startswith(("yes", "y")) else False if _clean(r).lower().startswith(("no", "none")) else None,
    "text": lambda r: _clean(r) or None,
    "dims_hwd_in": lambda r: _dims(r, "hwd"),
    "dims_whd_in": lambda r: _dims(r, "whd"),
    "plug_style": lambda r: ("right_angle" if re.search(r"right[- ]angle|angled|offset", r, re.I) else "flat" if re.search(r"flat", r, re.I) else
                             "pivot" if re.search(r"pivot|rotat|swivel", r, re.I) else "straight" if re.search(r"straight", r, re.I) else None),
    "listing_marks": lambda r: [m for m, rx in (("UL", r"(?<![A-Za-z])c?UL(?![A-Za-z])"), ("ETL", r"\bETL\b"), ("CSA", r"\bCSA\b")) if re.search(rx, r)] or None,
    "switch": lambda r: ("none" if re.search(r"^(no|none)\b|no power switch", _clean(r), re.I) else "per_outlet" if re.search(r"each outlet|per outlet|individual", r, re.I) else
                         "per_group" if re.search(r"group|bank", r, re.I) else "master" if re.search(r"switch|on/off|^yes", r, re.I) else None),
    "usb_types": _usb_types,
    "usb_c_count": lambda r: ({"c": _n(r)} if _n(r) else None),
    "emi": lambda r: (False if _clean(r).lower() in ("no", "none", "n/a") else True if _clean(r) else None),
    "material": lambda r: ("plastic" if "plastic" in r.lower() else "metal" if "metal" in r.lower() else None),
    "keyhole": lambda r: (["keyhole"] if _clean(r).lower().startswith("yes") else None),
    "pd_yesno": lambda r: (["PD"] if _clean(r).lower().startswith("yes") else None),
    # maker's explicit flicker-free statement ("Flicker-free: Yes", "TÜV Rheinland Flicker Free") -> flk.pwm 'none' AS a maker claim (A2 2026-11-24)
    "flicker_free": lambda r: ("none" if re.match(r"yes\b", _clean(r), re.I) or re.search(r"flicker[- ]?free", _clean(r), re.I) else None),
}


def load_label_rules(cat):
    p = ROOT / "research" / cat / "label-mapping.yaml"
    if not p.exists():
        return []
    out = []
    for r in yaml.safe_load(p.read_text())["rules"]:
        r = dict(r)
        r["_rx"] = re.compile(r["re"], re.I) if "re" in r else None
        out.append(r)
    return out


def rule_for(rules, brand, label):
    for r in rules:
        if r.get("brands") and brand not in r["brands"]:
            continue
        if (r["_rx"] is not None and r["_rx"].search(label)) or r.get("label") == label:
            return r


def apply_label_rules(cat, st, rules, keys, ignored_rows):
    for (c, brand, label), n in list(st["labels"].items()):
        r = rule_for(rules, brand, label)
        if r is None:
            continue
        if "ignore" in r:
            ignored_rows.append((c, brand, label, r["ignore"], n))
            del st["labels"][(c, brand, label)]
            continue
        if r["maps_to"] not in keys:
            continue
        fn, bad, skipped = TRANSFORMS[r["transform"]], 0, 0
        skip = re.compile(r["skip_values"], re.I) if r.get("skip_values") else None
        for e, raw, ob, observed in st["label_values"].get((c, brand, label), []):
            if skip and skip.search(_clean(raw)):
                skipped += 1
                continue
            v = fn(raw)
            if v is None:
                bad += 1
                continue
            ent = next((k[1] for k in e.idents if k[0] == "mfr_model"), e.idhint)
            cl = C.claim(ent, r["maps_to"], v, r.get("unit"), _clean(raw)[:300], "s1", "import.py+label-mapping@1", "table", observed,
                         locator={"label": label}, quote=f"{label}: {_clean(raw)}")
            e.claims.append((cl, ob)); st["claims_label_map"] += 1
        if skipped:
            ignored_rows.append((c, brand, label, "value is a placeholder/absence ('" + r["skip_values"] + "'): no claim written", skipped))
        if bad:
            st["labels"][(c, brand, label)] = bad
            st["label_example"][(c, brand, label)] = "value not parsed by transform " + r["transform"] + ": " + st["label_example"].get((c, brand, label), "")
        else:
            del st["labels"][(c, brand, label)]


def strip_variants(world, stats):
    """Documented cosmetic/pack/OEM suffixes -> PROPOSED relations only (review P0-3): kind/parent change only after a human
    approve_relation ledger line. Brand scoped; the base model must exist."""
    bybrand = collections.defaultdict(dict)
    for e in world.ents:
        k = next((k for k in e.idents if k[0] == "mfr_model" and e.idents[k]["role"] == "key"), None)
        if k and e.kind == "model":
            bybrand[e.brand][I.norm_value("mfr_model", k[1], e.brand)] = e
    for brand, models in bybrand.items():
        for nm, e in sorted(models.items(), key=lambda kv: (-len(kv[0]), kv[0])):
            for typ, axis, sfxs in (("same_configuration", "oem", ["OEM"]), ("package_of", "pack", PACKS),
                                    ("variant_of", "color", COLORS + (COLORS_TL if brand == "tripplite" else []))):
                hit = next((s for s in sfxs if nm.endswith(s) and nm[:-len(s)] in models and models[nm[:-len(s)]] is not e), None)
                if not hit:
                    continue
                link(e, typ, models[nm[:-len(hit)]], f"suffix:{brand}")
                e.extra["variant"] = {"suffix": hit, "axis": axis}
                stats[f"suffix_proposals_{axis}"] += 1
                world.events.append(("propose_relation", world.category, e, [], None, {"type": typ, "suffix": hit}))
                break


# ----------------------------------------------------------------------------- profile + mapping
_PROFILE_SCHEMA = json.loads((CODE / "schemas" / "category-profile.schema.json").read_text())
_RECORD_SCHEMA = json.loads((CODE / "schemas" / "record.schema.json").read_text())
CLAIM_VALIDATOR = jsonschema.Draft202012Validator({"$schema": _RECORD_SCHEMA.get("$schema"), "$defs": _RECORD_SCHEMA["$defs"], "$ref": "#/$defs/claim"})


def load_profile(cat):
    p = yaml.safe_load((ROOT / "research" / cat / "spec-profile.yaml").read_text())
    errs = sorted(jsonschema.Draft202012Validator(_PROFILE_SCHEMA).iter_errors(p), key=lambda e: list(e.path))
    if errs:
        raise SystemExit(f"research/{cat}/spec-profile.yaml violates category-profile.schema.json: " + "; ".join(e.message[:120] for e in errs[:5]))
    keys = {s["key"]: s for s in p["specs"]}
    al = {}
    for s in p["specs"]:
        for a in s.get("aliases", []) or []:
            al[a] = s["key"]
    return p, keys, al


def load_psref(cat, keys):
    p = ROOT / "research" / cat / "psref-mapping.yaml"
    if not p.exists():
        return {}, {}, set(), set()
    m = yaml.safe_load(p.read_text())["mapping"]
    single, multi, ignored, ident = {}, {}, set(), set()
    uses = collections.Counter(k for v in m.values() for k in (v.get("maps_to") or []))
    for col, v in m.items():
        if "ignored" in v:
            ignored.add(col)
        elif "maps_to" in v:
            ks = [k for k in v["maps_to"] if k in keys]
            if len(ks) == 1 and len(v["maps_to"]) == 1 and uses[ks[0]] == 1:
                single[col] = ks[0]
            else:
                multi[col] = v["maps_to"]
        else:
            ident.add(col)
    return single, multi, ignored, ident


def schema(con):
    con.executescript("""
    CREATE TABLE meta(k TEXT PRIMARY KEY, v TEXT);
    CREATE TABLE observations(snapshot TEXT, source_id TEXT, ref TEXT, adapter TEXT, fetched_at TEXT, url TEXT, n_claims INT, n_identifiers INT);
    CREATE TABLE entities(id TEXT PRIMARY KEY, category TEXT, kind TEXT, brand TEXT, brand_name TEXT, name TEXT, parent_id TEXT, family_id TEXT,
                          lifecycle TEXT, market TEXT, extra TEXT);
    CREATE TABLE identifiers(entity_id TEXT, scheme TEXT, value TEXT, value_raw TEXT, issuer TEXT, market TEXT, package_level TEXT, role TEXT,
                             valid INT, disputed INT DEFAULT 0);
    CREATE TABLE aliases(entity_id TEXT, text TEXT, kind TEXT);
    CREATE TABLE entity_sources(entity_id TEXT, sid TEXT, url TEXT, tier TEXT, label TEXT, snapshot TEXT, retrieved_at TEXT);
    CREATE TABLE source_links(entity_id TEXT, sid TEXT, linked_from TEXT);
    CREATE TABLE source_evidence(entity_id TEXT, sid TEXT, evidence TEXT);
    CREATE TABLE claims(id TEXT, entity_id TEXT, key TEXT, mapped_key TEXT, status TEXT, kind TEXT, cond TEXT, mmode TEXT, value TEXT,
                        norm_ok INT, norm_value TEXT, display TEXT, unit TEXT, raw TEXT, source TEXT, source_id TEXT, ref TEXT, snapshot TEXT,
                        locator TEXT, observed_at TEXT, extractor TEXT, review TEXT, decision TEXT, supersedes TEXT, doc TEXT,
                        PRIMARY KEY(entity_id, id));
    CREATE TABLE invalid_claims(category TEXT, source_id TEXT, key TEXT, error TEXT, n INT, example TEXT);
    CREATE TABLE absences(entity_id TEXT, key TEXT, status TEXT, reason TEXT, source TEXT);
    CREATE TABLE documents(entity_id TEXT, url TEXT, kind TEXT, label TEXT, linked_from TEXT);
    CREATE TABLE relations(entity_id TEXT, type TEXT, target_id TEXT, status TEXT, method TEXT, decision TEXT);
    CREATE TABLE identity_events(seq INT, event TEXT, category TEXT, entity_id TEXT, anchors TEXT, source_id TEXT, ref TEXT, snapshot TEXT, detail TEXT);
    CREATE TABLE quarantine(category TEXT, kind TEXT, keys TEXT, hits TEXT, source_id TEXT, ref TEXT, snapshot TEXT);
    CREATE TABLE identity_conflicts(category TEXT, scheme TEXT, value TEXT, entity_ids TEXT, reason TEXT);
    CREATE TABLE attachments(entity_id TEXT, source_id TEXT, ref TEXT, snapshot TEXT);
    CREATE TABLE regional_observations(mtm TEXT, config8 TEXT, machine_type TEXT, family_id TEXT, country TEXT, gtin_raw TEXT, gtin TEXT, snapshot TEXT);
    CREATE TABLE coverage(source_id TEXT, k TEXT, v TEXT);
    CREATE TABLE ignored_labels(category TEXT, source_id TEXT, label TEXT, reason TEXT, n INT);
    CREATE TABLE unmapped(category TEXT, source_id TEXT, key TEXT, what TEXT, n INT, example TEXT);
    CREATE INDEX i_claims ON claims(entity_id, mapped_key); CREATE INDEX i_ident ON identifiers(scheme, value); CREATE INDEX i_ent ON entities(category, kind);
    CREATE INDEX i_rel ON relations(entity_id);
    """)


def stable_cid(source_id, ref, c, key):
    body = {"src": source_id, "ref": ref, "key": key, "status": c["status"], "value": c.get("value"), "unit": c.get("unit"),
            "cond": canon_cond(c.get("conditions")), "kind": c.get("kind"), "meas": c.get("measurement"), "loc": c.get("locator") or {},
            "ex": ((c.get("method") or {}).get("extractor") or "").split("@")[0]}
    return "c_" + hashlib.sha256(canon(body).encode()).hexdigest()[:16]


CPU_KEYS = {"model": "cpu.model", "cores": "cpu.cores", "threads": "cpu.threads", "base_clock": "cpu.base_clock",
            "boost_clock": "cpu.boost_clock", "cache": "cpu.cache", "cores_threads": "cpu.cores_threads"}


def cpu_split(c, cid, keys):
    """Literal processor claim -> derived claims (same source/locator). The split cpu.model supersedes the literal one."""
    parts = _cpu.parse(c.get("value"))
    out = []
    for f, k in CPU_KEYS.items():
        if f not in parts or k not in keys:
            continue
        if f == "model" and parts[f] == c.get("value"):
            continue
        d = {"id": None, "key": k, "status": "known", "kind": c.get("kind", "official"), "value": parts[f], "unit": "GHz" if "clock" in f else None,
             "raw": c.get("raw"), "source": "s1", "method": {"stage": "derive", "extractor": "import.py+cpu-split@1"},
             "observed_at": c.get("observed_at"), "review": {"state": "candidate"}, "derived_from": [cid],
             "locator": dict(c.get("locator") or {}, split=f)}
        if f == "model":
            d["supersedes"] = cid
        out.append(d)
    return out


PSPLIT = "import.py+psref-split@1"
PSPLIT_COLS = {"Display": (_lcell.display, {"panel_type": "disp.panel_type", "nits_sdr": "disp.nits_sdr", "refresh": "disp.refresh",
                                            "resolution": "disp.resolution"}),
               "Memory Slots": (_lcell.slots, {"total": "mem.slots", "soldered": "mem.soldered"}),
               "Memory": (_lcell.memory, {"type": "mem.type"})}
PSPLIT_CLASH = {"soldered": {"socketed", "mixed"}, "socketed": {"soldered", "mixed"}}


def psref_split(c, cid, keys, cells):
    """Literal PSREF multi-target cell (research/laptops/psref-mapping.yaml maps_to list) -> derived claims (crawler/adapters/_lcell.py).
    A derived key equal to the literal's own key (mem.slots from Memory Slots) supersedes the literal. mem.soldered is dropped when the
    MTM's Memory cell contradicts the board statement (Memory Slots 'no slots' vs Memory '... SODIMM')."""
    fn, fmap = PSPLIT_COLS[(c.get("locator") or {}).get("column")]
    parts = fn(c.get("value"))
    if "soldered" in parts and _lcell.memory(cells.get("Memory")).get("soldered_hint") in PSPLIT_CLASH.get(parts["soldered"], ()):
        parts.pop("soldered")
    out = []
    for f, k in fmap.items():
        if f not in parts or k not in keys:
            continue
        d = {"id": None, "key": k, "status": "known", "kind": c.get("kind", "official"), "value": {"total": parts[f]} if f == "total" else parts[f],
             "unit": None, "raw": c.get("raw"), "source": "s1", "method": {"stage": "derive", "extractor": PSPLIT},
             "observed_at": c.get("observed_at"), "review": {"state": "candidate"}, "derived_from": [cid], "locator": dict(c.get("locator") or {}, split=f)}
        if k == c.get("key"):
            d["supersedes"] = cid
        out.append(d)
    return out


IMPORTERS = {"lenovo-psref": do_lenovo, "asus": do_asus, "apple": do_apple, "generic": do_generic, "strip": do_strip, "model": do_model}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--source", action="append")
    ap.add_argument("--reparse", action="store_true")
    ap.add_argument("--db", default=str(DB_DEFAULT))
    ap.add_argument("--data", default=str(ROOT / "data"), help="git-tracked decisions + id registry (tests point this at a copy)")
    ap.add_argument("--seed-ids", help="one-off: seed an empty registry from a pre-registry sqlite so published ids do not change")
    ap.add_argument("--reverse-sources", action="store_true", help="test: ingest sources in reverse order (ids must not change)")
    ap.add_argument("--no-mint", action="store_true", help="test: never append to the id registry (replay must not need new ids)")
    ap.add_argument("--strict-parsers", action="store_true", help="release: fail when a policy's audited parser fingerprint differs from the code")
    a = ap.parse_args()
    if a.source and Path(a.db).resolve() == DB_DEFAULT.resolve():
        raise SystemExit("--source builds a partial store; it may not replace state/specsheet.sqlite. Pass --db <scratch path>.")
    t0 = time.time()
    data = Path(a.data)
    dec = Decisions(data)
    locked_new, policy_lock_digest = dec.check_lock(write=not (bool(a.source) or a.no_mint))
    parsers = {sid: registry.parser_info(sid) for sid, m in registry.SOURCES.items()}
    current_fp = {v["parser"]: v["fingerprint"] for v in parsers.values() if v["parser"]}
    current_fp.update({B.TRANSFORM: B.fingerprint(), TC.TRANSFORM: TC.fingerprint(), XW.TRANSFORM: XW.fingerprint(), DA.TRANSFORM: DA.fingerprint(), DS.TRANSFORM: DS.fingerprint(), DS3.TRANSFORM: DS3.fingerprint(), DS7.TRANSFORM: DS7.fingerprint(), IA.TRANSFORM: IA.fingerprint(), HA.TRANSFORM: HA.fingerprint()})     # r7: shared transforms are pinned like parsers
    current_fp.update(registry.supplement_parsers())       # r7: legacy-store supplement extractors (crawlpy_strips_belkin) pinned like parsers
    current_fp[PSPLIT] = "sha256:" + hashlib.sha256(Path(_lcell.__file__).read_bytes()).hexdigest()[:20]       # psref-split cell parser, pinned like a parser
    drift = dec.parser_drift(current_fp)
    for pid, ex, old, new in drift:
        print(f"PARSER DRIFT: {pid} audited {ex} at {old}, code is now {new}: re-audit + new policy id", file=sys.stderr)
    if drift and a.strict_parsers:
        raise SystemExit(f"--strict-parsers: {len(drift)} audited parser(s) changed since their policy audit")
    reg = I.IdRegistry(data / "_ids" / "registry.jsonl", data / "_ids" / "tombstones.jsonl", readonly=bool(a.source) or a.no_mint)
    cats = sorted({m["category"] for m in registry.SOURCES.values() if (ROOT / "research" / m["category"] / "spec-profile.yaml").exists()})
    profiles = {c: load_profile(c) for c in cats}
    metas = {c: catmeta.load(c) for c in cats}
    unitsets = {c: N.units(profiles[c][0]) for c in cats}
    psref = {c: load_psref(c, profiles[c][1]) for c in cats}       # only categories with research/<cat>/psref-mapping.yaml have columns
    import lenovo_psref
    emitted = set(lenovo_psref.COLMAP)
    stats, worlds, obs_rows, events = {}, {}, [], []
    raw_digest_rows, parse_cache = [], collections.Counter()
    cat_stats = collections.defaultdict(lambda: collections.defaultdict(int))     # category-level (post-ingest) counters
    srcs = [(k, m) for k, m in registry.SOURCES.items() if m["category"] in cats]
    if a.reverse_sources:
        srcs.reverse()
    for sid, meta in srcs:
        if a.source and sid not in a.source:
            continue
        st = collections.defaultdict(int)
        st["regional"] = []; st["psref_cols"] = collections.Counter(); st["labels"] = collections.Counter(); st["label_example"] = {}; st["label_values"] = {}
        stats[sid] = st
        cat = meta["category"]
        w = worlds.setdefault(cat, World(cat, dec, events, metas[cat]))
        w.psref, w.psref_emitted = psref[cat][0], emitted
        disc = {}
        dp = ROOT / "raw" / sid / "discovery.json"
        if dp.exists():
            d = json.loads(dp.read_text())
            disc = {r["key"]: dict(r, **(r.get("hints") or {})) for r in d.get("refs", [])}
            st["discovery_complete"] = int(bool(d.get("complete")))
        n = 0
        cstats = {}
        PARSER["current"] = parsers[sid]["parser"]
        for rec, pr, extra in registry.iter_observations(sid, reparse=a.reparse, stats=cstats):
            n += 1
            st["html_entities_decoded"] += dehtml(pr)
            raw_digest_rows.append((sid, str(rec["ref"]), rec["snapshot"]))
            if sid == "cyberpower":
                extra = {"discontinued": bool((disc.get(rec["ref"]) or {}).get("discontinued"))}
            fn = IMPORTERS[meta.get("importer", "generic")]
            fn(w, meta, sid, rec, pr, extra, st)
            obs_rows.append((rec["snapshot"], sid, str(rec["ref"]), rec["adapter"], rec["fetched_at"], rec["url"], len(pr["claims"]), len(pr["identifiers"])))
        st["observations"] = n
        for k_, v_ in cstats.items():
            st[k_] = v_; parse_cache[k_] += v_
        print(f"{sid}: {n} observations {cstats or ''}", file=sys.stderr)
    for w in worlds.values():       # review 3: contradictory pages after every corroborated page of every source
        for sev, sid, ref, meta, rec, pr, extra, st in sorted(w.deferred, key=lambda t: t[:3]):
            IMPORTERS[meta.get("importer", "generic")](w, meta, sid, rec, pr, extra, st)
    for cat, w in worlds.items():   # r6: corroborated bundle SKUs -> package entities (contains -> member models); needs every model of the category
        if "bundle_packages" in metas[cat]["features"]:
            B.mint(w, cat_stats[cat], {"K": K, "add_ident": add_ident, "add_src": add_src, "link": link, "parser": PARSER, "slug": slug})
        if "es_cert_scopes" in metas[cat]["features"]:      # r7: certification scopes + declared-alias audit + reviewed crosswalks (scripts/tvcert.py)
            TC.apply(w, cat_stats[cat], {"link": link, "parser": PARSER, "crosswalks": data / "decisions" / "tv-crosswalks.yaml"})
        XW.apply(w, cat_stats[cat], {"link": link, "parser": PARSER, "decisions": data / "decisions"})     # r8: crosswalks + same_hardware_as
    doc_stats = DA.apply(worlds, events, {})        # document pipeline: linked manuals/datasheets -> claims on the linking page's entity (scripts/docattach.py)
    DS.apply(worlds, events, doc_stats)            # r2: SSD datasheet rows (scripts/docspec_attach.py, separate transform: docattach@1 stays pinned)
    DS3.apply(worlds, events, doc_stats)           # r3: TV / router / laptop spec-sheet rows (scripts/docspec_r3.py; docspec-attach@2 stays pinned)
    DS7.apply(worlds, events, doc_stats)           # r7: TV per-port HDMI rates from quick start guides (scripts/docspec_r7tv.py; r3@2 stays pinned)
    IA.apply(worlds, events, doc_stats)            # maker spec images (OCR) -> claims on the linking page's entity (scripts/imgattach.py)
    HA.apply(worlds, events, doc_stats)            # kind: hub pages (data/document-hubs.yaml) -> bound only by the document's own text (scripts/hubattach.py)
    ignored_rows = []
    rules = {c: load_label_rules(c) for c in worlds}
    for sid, st in stats.items():
        cat = registry.SOURCES[sid]["category"]
        if rules.get(cat):
            apply_label_rules(cat, st, rules[cat], profiles[cat][1], ignored_rows)
    for cat, w in worlds.items():
        if "strip_variants" in metas[cat]["features"]:
            strip_variants(w, stats.get("tripplite") or next(iter(stats.values())))
        if "stem_links" in metas[cat]["features"]:
            stem_links(w, cat_stats[cat])

    # ------------------------------------------------------------------ ids: registry first, then deterministic mint
    seed = {}
    if a.seed_ids and not reg.by_anchor:
        old = sqlite3.connect(a.seed_ids)
        for eid, cat, scheme, value, brand, kind in old.execute(
                "SELECT e.id, e.category, i.scheme, i.value, e.brand, e.kind FROM identifiers i JOIN entities e ON e.id=i.entity_id WHERE i.role='key'"):
            if cat == "laptops" and brand == "lenovo" and kind == "family" and scheme == "mfr_model":
                scheme = "x_lenovo_product"          # pre-registry importer keyed Lenovo families on the PSREF ProductKey as mfr_model
            k = I.key(scheme, value, brand, None, kind)
            if k:
                seed[I.anchor(cat, k)] = eid
    taken, minted, reused, id_conflicts, kind_changes = set(seed.values()), 0, 0, [], []
    pending = []
    for cat, w in worlds.items():
        for e in w.ents:
            anchors = w.anchors(e.keys)
            hit = reg.lookup(anchors)
            if len(hit) > 1:
                id_conflicts.append((cat, hit, anchors))
                events.append(("id_conflict", cat, e, anchors, None, {"ids": hit}))
            if hit and hit[0] not in taken:
                e.id = hit[0]; taken.add(e.id); reused += 1
                if reg.kind_of.get(e.id) and reg.kind_of[e.id] != e.kind:
                    kind_changes.append((cat, e.id, reg.kind_of[e.id], e.kind))
                    events.append(("id_kind_changed", cat, e, anchors, None, {"registered": reg.kind_of[e.id], "now": e.kind}))
                reg.add(e.id, anchors, cat, e.kind)
            else:
                pending.append((cat, I.LEVELS.get(e.kind, 9), anchors[0] if anchors else "", e, anchors))
    for cat, _lvl, _a0, e, anchors in sorted(pending, key=lambda t: (t[0], t[1], len(t[2]), t[2])):
        base = e.idhint or f"{e.brand}-{slug(next(iter(e.idents.values()))['value'] if e.idents else 'unnamed')}"
        sd = next((seed[x] for x in anchors if x in seed), None)
        if sd and sd not in reg.ids and re.match(r"^[a-z0-9][a-z0-9-]{1,95}$", sd):
            e.id = sd; reg.ids.add(sd); reg.add(sd, anchors, cat, e.kind)
        else:
            if a.no_mint:
                raise SystemExit(f"--no-mint: entity {anchors[:2]} has no registered id (replay would remint)")
            e.id = reg.mint(base, anchors, cat, e.kind, taken)
        taken.add(e.id); minted += 1
        events.append(("mint", cat, e, anchors, None, {"id": e.id}))

    # ------------------------------------------------------------------ relations: decide (ledger > policy > proposed); apply approved structure
    rel_rows = []
    for cat, w in worlds.items():
        for e in w.ents:
            e.parent = None
            for typ, tgt, method, parser in e.rels:
                st_, did = dec.relation_state(e.id, typ, tgt.id, method, parser)
                if any(dec.vetoed(x, y) for x in w.anchors(e.keys) for y in w.anchors(tgt.keys)):
                    st_, did = "rejected", "split-veto"
                rel_rows.append((e.id, typ, tgt.id, st_, method, did))
                if st_ != "approved":
                    continue
                if typ in ("configuration_of", "package_of", "variant_of") and e.parent is None:
                    e.parent = tgt
                    if method.startswith("suffix:"):
                        e.kind = {"package_of": "package", "variant_of": "configuration"}.get(typ, e.kind)
                elif typ == "member_of_family" and e.family is None:
                    e.family = tgt
    rel_ok = {(r[0], r[1], r[2]) for r in rel_rows if r[3] == "approved"}

    def famid(e):
        if e.family is not None and (e.id, "member_of_family", e.family.id) in rel_ok:
            return e.family.id
        seen = set(); p = e.parent
        while p is not None and p.id not in seen:
            seen.add(p.id)
            if p.family is not None and (p.id, "member_of_family", p.family.id) in rel_ok:
                return p.family.id
            p = p.parent
        return None

    # ------------------------------------------------------------------ gtin conflicts (one GTIN on unrelated entities)
    gt = collections.defaultdict(set)
    for cat, w in worlds.items():
        for e in w.ents:
            for (scheme, v), d in e.idents.items():
                if scheme == "gtin" and d["valid"]:
                    gt[(cat, v)].add(e)
    disputed, conflict_rows = set(), []
    for (cat, v), es in gt.items():
        if len(es) > 1:
            lineage = lambda e: {e.id} | ({e.parent.id} if e.parent else set())
            if any(not (lineage(x) & lineage(y)) for x in es for y in es if x is not y):
                disputed.add((cat, v))
                conflict_rows.append((cat, "gtin", v, json.dumps(sorted(x.id for x in es)), "one GTIN on unrelated entities: review"))
                events.append(("gtin_conflict", cat, None, [f"{cat}|gtin|GS1|{v}|"], None, {"ids": sorted(x.id for x in es)}))

    corr_stats = CR.apply(worlds, events, data)        # D9.2: data/corrections/*.yaml -> correction@1 claims (candidates until a ledger line decides)
    for w in worlds.values():
        B.finalize(w)               # package contents (entity ids now exist)
        TC.finalize(w, dec, {"add_src": add_src, "crosswalks": data / "decisions" / "tv-crosswalks.yaml"})   # r7: decided coverage edges -> allowlisted transfer
        XW.finalize(w, dec, {"add_src": add_src})       # r8: decided same_hardware_as edges -> certification-only transfer
    # ------------------------------------------------------------------ write
    dbp = Path(a.db); dbp.parent.mkdir(parents=True, exist_ok=True)
    tmp = dbp.with_suffix(".tmp")
    if tmp.exists():
        tmp.unlink()
    con = sqlite3.connect(tmp); schema(con)
    unmapped = collections.Counter(); unmapped_ex = {}
    invalid = collections.Counter(); invalid_ex = {}
    out_counts = collections.defaultdict(collections.Counter)
    review_counts = collections.defaultdict(collections.Counter)
    digest = hashlib.sha256()
    brand_names = {m["brand"]: m["brand_name"] for m in registry.SOURCES.values()}
    for w in worlds.values():
        for b, n in w.brand_names.items():
            brand_names.setdefault(b, n)
    for cat in sorted(worlds):
        w = worlds[cat]
        _, keys, al = profiles[cat]
        U = unitsets[cat]
        single = psref[cat][0]
        for e in sorted(w.ents, key=lambda x: x.id):
            market = "US" if any(v["market"] == "US" for v in e.idents.values()) else None
            con.execute("INSERT INTO entities VALUES (?,?,?,?,?,?,?,?,?,?,?)", (e.id, cat, e.kind, e.brand, brand_names.get(e.brand, e.brand), e.name,
                        e.parent.id if e.parent else None, famid(e), e.lifecycle, market, json.dumps(e.extra, sort_keys=True)))
            out_counts[cat][e.kind] += 1
            digest.update(canon(["e", e.id, e.kind, e.parent.id if e.parent else None]).encode())
            for v in e.idents.values():
                con.execute("INSERT INTO identifiers VALUES (?,?,?,?,?,?,?,?,?,?)", (e.id, v["scheme"], v["value"], v["value_raw"], v["issuer"], v["market"],
                            v["package_level"], v["role"], int(v["valid"]), int((cat, v["value"]) in disputed and v["scheme"] == "gtin")))
            for t, k in e.aliases.items():
                con.execute("INSERT INTO aliases VALUES (?,?,?)", (e.id, t, k))
            for ob in sorted(e.obs):
                con.execute("INSERT INTO attachments VALUES (?,?,?,?)", (e.id,) + ob)
            sids = {}
            for snap, s in sorted(e.srcs.items(), key=lambda kv: (kv[1]["url"], kv[0])):
                sids[snap] = f"s{len(sids) + 1}"
                con.execute("INSERT INTO entity_sources VALUES (?,?,?,?,?,?,?)", (e.id, sids[snap], s["url"], s["tier"], s["label"], snap, s["retrieved_at"]))
                if s.get("linked_from"):       # document sources: the page the document was linked from (source policy document_host inheritance)
                    con.execute("INSERT INTO source_links VALUES (?,?,?)", (e.id, sids[snap], s["linked_from"]))
                if s.get("evidence"):          # corrections: the issue that cites this page (E2/E3)
                    con.execute("INSERT INTO source_evidence VALUES (?,?,?)", (e.id, sids[snap], s["evidence"]))
            tier_of = {snap: s["tier"] for snap, s in e.srcs.items()}
            seen, rows = set(), []
            work = list(e.claims)
            states, pdid = {}, {}
            cells = {(c.get("locator") or {}).get("column"): c.get("value") for c, ob in e.claims if ob[0] == "lenovo-psref" and (c.get("locator") or {}).get("column")}
            i = 0
            while i < len(work):
                c, ob = work[i]; i += 1
                sid, ref, snap = ob
                loc = c.get("locator") or {}
                k = c["key"]; mk = k if k in keys else al.get(k)
                if loc.get("column") in single and single[loc["column"]] != mk:
                    if mk is not None:
                        unmapped[(cat, f"{k} -> {single[loc['column']]}")] += 1; unmapped_ex.setdefault((cat, f"{k} -> {single[loc['column']]}"), "adapter key overridden by psref-mapping.yaml: " + loc["column"])
                    mk = single[loc["column"]]
                if mk is None:
                    unmapped[(cat, k)] += 1; unmapped_ex.setdefault((cat, k), (c.get("raw") or "")[:80])
                cid = c.get("_cid") or stable_cid(sid, ref, c, mk or k)
                if cid in seen:
                    continue
                seen.add(cid)
                spec = keys.get(mk) if mk else None
                ok, nv, nx = N.normalise(spec, c, U) if spec else (False, None, {})
                doc = {"id": cid, "key": mk or k, "status": c["status"], "kind": c.get("kind") or "official", "source": sids.get(snap, "s1"),
                       "method": {"stage": STAGE_FIX.get((c.get("method") or {}).get("stage"), (c.get("method") or {}).get("stage") or "adapter"),
                                  "extractor": (c.get("method") or {}).get("extractor") or "unknown@0"},
                       "observed_at": c.get("observed_at") or "1970-01-01T00:00:00Z"}
                for f in ("unit", "raw", "quote", "locator", "measurement", "derived_from", "via_relation", "confidence", "supersedes", "extracted_at"):
                    if c.get(f) is not None:
                        doc[f] = c[f]
                if c.get("conditions"):
                    doc["conditions"] = canon_cond(c["conditions"])
                if c["status"] == "known":
                    doc["value"] = nv if ok else c.get("value")
                    if ok and spec.get("unit"):
                        doc["unit"] = spec["unit"]
                ctx = {"source_id": sid, "extractor": doc["method"]["extractor"], "key": mk or k, "spec_type": (spec or {}).get("type"), "kind": doc["kind"], "tier": tier_of.get(snap, "manufacturer"),
                       "status": c["status"], "normalized": ok}
                state, did = dec.claim_state(cid, ctx) if mk else ("candidate", None)
                if doc["method"]["extractor"].startswith("import.py+cpu-split") and state == "accepted" and did and did.startswith("claim/"):
                    parent_state = states.get((c.get("derived_from") or [None])[0])
                    if parent_state != "accepted":
                        state, did = "candidate", None
                if doc["method"]["extractor"] == PSPLIT and state == "accepted" and did and did.startswith("claim/"):
                    # parent accepted, or a parent that is a candidate only because the multi-target literal cannot normalise (no human decision on it)
                    ps, pd = pdid.get((c.get("derived_from") or [None])[0], ("rejected", None))
                    if not (ps == "accepted" or (ps == "candidate" and pd is None)):
                        state, did = "candidate", None
                doc["review"] = {"state": state, "by": did}
                errs = list(CLAIM_VALIDATOR.iter_errors(doc))
                if errs:
                    msg = errs[0].message[:120]
                    invalid[(cat, sid, mk or k, msg)] += 1; invalid_ex.setdefault((cat, sid, mk or k, msg), canon(doc)[:200])
                    continue
                states[cid] = state; pdid[cid] = (state, did)
                review_counts[cat][state] += 1
                rows.append((cid, e.id, k, mk, c["status"], doc["kind"], canon(doc.get("conditions") or {}), (c.get("measurement") or {}).get("mode"),
                             json.dumps(c.get("value")), int(ok), json.dumps(nv) if ok else None, canon(nx) if nx else None, doc.get("unit"), c.get("raw"), doc["source"],
                             sid, ref, snap, canon(loc), doc["observed_at"], doc["method"]["extractor"], state, did, c.get("supersedes"), canon(doc)))
                if state == "accepted":
                    digest.update(canon(["c", e.id, cid, mk, nv if ok else None]).encode())
                elif state == "rejected":
                    digest.update(canon(["r", e.id, cid]).encode())
                if "cpu_split" in metas[cat]["features"] and mk == "cpu.model" and not c.get("derived_from"):
                    for d in cpu_split(c, cid, keys):
                        d["_cid"] = stable_cid(sid, ref, d, d["key"])
                        work.append((d, ob))
                if "psref_split" in metas[cat]["features"] and sid == "lenovo-psref" and loc.get("column") in PSPLIT_COLS and not c.get("derived_from"):
                    for d in psref_split(c, cid, keys, cells):
                        d["_cid"] = stable_cid(sid, ref, d, d["key"])
                        work.append((d, ob))
            con.executemany("INSERT INTO claims VALUES (" + ",".join("?" * 25) + ")", rows)
            for ab, ob in e.absences:
                mk = ab["key"] if ab["key"] in keys else al.get(ab["key"])
                st_ = ab.get("status") or "not_published"
                if st_ not in ("unknown", "not_published", "not_applicable"):
                    st_ = "not_yet_extracted"     # blocked / ambiguous / not attempted: never 'not published'
                con.execute("INSERT INTO absences VALUES (?,?,?,?,?)", (e.id, mk or ab["key"], st_, ab.get("reason"), sids.get(ob[2], "s1")))
            seen_d = set()
            for d in e.documents:      # one row per linking edge (review 6 fix 3: the document_host policy reads each row's own linked_from)
                if (d["url"], d.get("linked_from")) not in seen_d:
                    seen_d.add((d["url"], d.get("linked_from")))
                    con.execute("INSERT INTO documents VALUES (?,?,?,?,?)", (e.id, d["url"], d.get("kind"), d.get("label"), d.get("linked_from")))
    for r in sorted(rel_rows):
        digest.update(canon(["l"] + list(r[:4])).encode())
    con.executemany("INSERT INTO relations VALUES (?,?,?,?,?,?)", sorted(rel_rows))
    ev_rows = []
    for n, (ev, cat, e, anchors, ob, detail) in enumerate(events):
        ob = ob or (None, None, None)
        ev_rows.append((n, ev, cat, e.id if e is not None else None, json.dumps(anchors), ob[0], ob[1], ob[2], json.dumps(detail, sort_keys=True)))
    con.executemany("INSERT INTO identity_events VALUES (?,?,?,?,?,?,?,?,?)", ev_rows)
    for cat, w in worlds.items():
        for q in w.quarantine:
            ob = q["obs"] or (None, None, None)
            con.execute("INSERT INTO quarantine VALUES (?,?,?,?,?,?,?)", (cat, q["kind"], json.dumps(q["keys"]), json.dumps(q["hits"]), ob[0], ob[1], ob[2]))
    review_rows = [(cat, scheme, value, json.dumps([e.id]), reason) for cat, w in sorted(worlds.items()) for e, scheme, value, reason in w.id_review]
    con.executemany("INSERT INTO identity_conflicts VALUES (?,?,?,?,?)", conflict_rows + review_rows + [(c, "id_registry", "", json.dumps(h), "anchors map to several registered ids: " + ",".join(an[:3])) for c, h, an in id_conflicts]
                    + [(c, "id_kind", i, json.dumps([i]), f"registered as {k0}, now {k1}: review (level is part of the anchor)") for c, i, k0, k1 in kind_changes]
                    + [(x["anchor"].split("|")[1] if x["anchor"].startswith("v2|") else x["anchor"].split("|")[0], "registry_ambiguous", x["anchor"], json.dumps(x["ids"]),
                        "one anchor registered under several ids" + (" (legacy v1 line, migrated by kind)" if x["legacy"] else "")) for x in reg.ambiguous]
                    + [(x["anchor"].split("|")[1], "registry_rebind", x["anchor"], json.dumps([x["bound"], x["attempted"]]), "anchor already bound to another id: not rebound")
                       for x in reg.rebinds])
    cov = []
    for sid, st in stats.items():
        for (mtm, c8, mt, fam, country, graw, snap) in st["regional"]:
            con.execute("INSERT INTO regional_observations VALUES (?,?,?,?,?,?,?,?)", (mtm, c8, mt, fam.id if fam else None, country, graw,
                        I.norm_gtin(graw) if graw else None, snap))
        if st["regional"]:
            regions = collections.Counter(r[4] or "?" for r in st["regional"])
            cov += [(sid, "mtms_observed", str(len(st["regional"]))), (sid, "mtms_published_scope", str(st["us_mtms"])),
                    (sid, "regions", json.dumps(dict(regions.most_common()))), (sid, "regional_claims_materialised", "no (US only; evidence by reference: snapshot + MTM)")]
        cov += [(sid, "observations", str(st["observations"])), (sid, "discovery_complete", str(st.get("discovery_complete", "unknown")))]
    con.executemany("INSERT INTO coverage VALUES (?,?,?)", cov)
    um_rows = []
    for (cat, k), n in sorted(unmapped.items(), key=lambda kv: -kv[1]):
        um_rows.append((cat, "adapters", k, "adapter_key_overridden_by_psref_mapping" if " -> " in k else "claim_key_not_in_profile", n, unmapped_ex[(cat, k)]))
    for sid, st in stats.items():
        for (cat, brand, lab), n in st["labels"].items():
            um_rows.append((cat, sid, lab, "source_label_not_mapped_by_adapter", n, st["label_example"].get((cat, brand, lab))))
        single, multi, ignored, ident = psref[registry.SOURCES[sid]["category"]]
        for col, n in st["psref_cols"].items():
            if col in ident:
                continue
            if col in ignored:
                um_rows.append(("laptops", sid, col, "psref_column_ignored_by_mapping", n, None))
            elif col in multi:
                um_rows.append(("laptops", sid, col, "psref_column_multi_target_needs_parser", n, ",".join(multi[col])))
            elif col not in single:
                um_rows.append(("laptops", sid, col, "psref_column_not_in_psref_mapping", n, None))
    con.executemany("INSERT INTO unmapped VALUES (?,?,?,?,?,?)", um_rows)
    con.executemany("INSERT INTO invalid_claims VALUES (?,?,?,?,?,?)", [k + (n, invalid_ex[k]) for k, n in invalid.items()])
    con.executemany("INSERT INTO ignored_labels VALUES (?,?,?,?,?)", ignored_rows)
    con.executemany("INSERT INTO observations VALUES (?,?,?,?,?,?,?,?)", obs_rows)
    def fdig(*paths):
        h = hashlib.sha256()
        for pth in paths:
            pth = Path(pth)
            h.update(str(pth.name).encode() + b"\0" + (pth.read_bytes() if pth.exists() else b"<absent>") + b"\0")
        return "sha256:" + h.hexdigest()
    raw_digest = "sha256:" + hashlib.sha256("\n".join("|".join(r) for r in sorted(raw_digest_rows)).encode()).hexdigest()
    used = {sid: parsers[sid] for sid in sorted(stats)}
    inputs = {"raw_snapshots": {"digest": raw_digest, "observations": len(raw_digest_rows)},
              "parsers": used,
              "profiles": {c: {"version": str(profiles[c][0]["version"]), "digest": fdig(ROOT / "research" / c / "spec-profile.yaml", ROOT / "research" / c / "category.yaml",
                                                                                      ROOT / "research" / c / "psref-mapping.yaml", ROOT / "research" / c / "label-mapping.yaml")} for c in cats},
              "normalizer": fdig(CODE / "scripts" / "normalize.py", CODE / "scripts" / "resolve.py"),
              "importer": fdig(CODE / "scripts" / "import.py", CODE / "scripts" / "identity.py", CODE / "scripts" / "decisions.py", CODE / "crawler" / "adapters" / "registry.py"),
              "policies": {"file": fdig(data / "decisions" / "policies.yaml"), "lock": policy_lock_digest, "active": [p["id"] for p in dec.active()],
                           "approval": dec.approvals(), "parser_drift": [list(x) for x in drift]},
              "ledger": {"digest": fdig(data / "decisions" / "ledger.jsonl"), "lines": dec.lines},
              "corrections": {"digest": corr_stats.get("digest"), "files": corr_stats.get("files", 0), "claims": corr_stats.get("claims", 0)},
              "registry": {"digest": fdig(data / "_ids" / "registry.jsonl", data / "_ids" / "tombstones.jsonl"), "migrated_legacy_anchors": reg.migrated,
                           "ambiguous": len(reg.ambiguous), "rebind_attempts": len(reg.rebinds), "kind_changes": len(kind_changes)}}
    meta_rows = {"built_at": time.strftime("%FT%TZ", time.gmtime()), "sources": json.dumps(sorted(stats)), "accepted_digest": digest.hexdigest(),
                 "policies": json.dumps([p["id"] for p in dec.claim_policies + dec.relation_policies]), "ledger_lines": str(dec.lines),
                 "profiles": json.dumps({c: str(profiles[c][0]["version"]) for c in cats}), "scope": "partial" if a.source else "full"}
    con.executemany("INSERT INTO meta VALUES (?,?)", list(meta_rows.items()))
    flushed = reg.flush()
    inputs["registry"]["digest_after"] = fdig(data / "_ids" / "registry.jsonl", data / "_ids" / "tombstones.jsonl")
    con.execute("INSERT INTO meta VALUES (?,?)", ("inputs", json.dumps(inputs, sort_keys=True)))
    con.commit(); con.close()
    os.replace(tmp, dbp)
    print(json.dumps({"db": str(dbp), "seconds": round(time.time() - t0, 1), "accepted_digest": digest.hexdigest(),
                      "entities": {c: dict(v) for c, v in out_counts.items()}, "claims_review": {c: dict(v) for c, v in review_counts.items()},
                      "ids": {"reused": reused, "new": minted, "registry_lines_appended": flushed, "id_conflicts": len(id_conflicts)},
                      "identity": {"quarantined_observations": sum(len(w.quarantine) for w in worlds.values()), "gtin_conflicts": len(conflict_rows), "page_identity_review": len(review_rows),
                                   "relations": dict(collections.Counter(f"{r[3]}:{r[4].split(':')[0]}" for r in rel_rows))},
                      "source_stats": {k: {a: b for a, b in v.items() if isinstance(b, int) and b and a in ("models", "packages", "skipped_wildcard_pattern", "skipped_other_category", "regional_packages_not_published", "no_model_identifier")} for k, v in stats.items() if metas[registry.SOURCES[k]["category"]]["features"] is not None and registry.SOURCES[k].get("importer") == "model"},
                      "stem_proposals": {c: dict(v) for c, v in cat_stats.items()},
                      "invalid_claims": sum(invalid.values()), "corrections": corr_stats, "documents": dict(sorted(doc_stats.items())), "unmapped_rows": len(um_rows), "ignored_label_rows": len(ignored_rows),
                      "governance": {"policies_locked_now": locked_new, "parser_drift": len(drift), "pending_approval": sorted(k for k, v in dec.approvals().items() if v != "approved"),
                                     "registry": inputs["registry"], "raw_snapshots": inputs["raw_snapshots"], "parse_cache": dict(parse_cache),
                                     "html_entities_decoded": sum(v.get("html_entities_decoded", 0) for v in stats.values()),
                                     "quarantined_cross_market": sum(v.get("quarantined_cross_market", 0) for v in stats.values())}}, indent=1))


if __name__ == "__main__":
    main()
