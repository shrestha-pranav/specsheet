#!/usr/bin/env python3
"""Killer-query presets with a build-time fill gate.

Reads docs/presets.json (the preset definitions) and the published docs/api/v1 index, measures how much of each preset's in-scope population (D8) has its
keys known, and writes docs/api/v1/presets.json: the definitions plus `gate` (pass/fail against min_fill, the weakest key, brands with no
value for it) and `count` (matches vs unknown-might-match). Nothing about fill is hand-written: change the data and the gate moves.
build.py calls write(api) after categories.json exists. Filter semantics mirror docs/app.js matchFacet exactly (tests/frontend smoke
cross-checks the counts in a real browser).
"""
import json
import re
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DOCS = ROOT / "docs"
NUMERIC = ("number", "integer", "range")
KEY = re.compile(r"^f_(.+)_(min|max|value)$")


def _rows(api, category):
    rows = []
    for shard in category.get("index") or []:
        rows += json.loads((api / shard).read_text())
    return [r for r in rows if r.get("kind") != "revision"]       # the app drops revision rows from every listing


def _known(row, key):
    return key in (row.get("v") or {})


def _prov(row, key):
    """D10 provenance of a known value from the index row: x[key].k (absent = official from the maker or a certifier; `label` = the
    maker's own label read from a contributor photo, still official)."""
    return ((row.get("x") or {}).get(key) or {}).get("k") or "official"


NON_MAKER = ("derived", "measured", "reported")


def _parse_filters(filters, fields):
    """{app url key: value} -> [(field, 'min'|'max'|'value', value)] for facet fields only (the app ignores the rest)."""
    out = []
    for k, v in filters.items():
        m = KEY.match(k)
        if not m or v in ("", None) or m.group(1) not in fields:
            raise SystemExit(f"preset filter {k!r} does not name a schema field")
        field = fields[m.group(1)]
        if not field.get("facet"):
            raise SystemExit(f"preset filter {k!r}: field is not a facet in the app")
        out.append((field, m.group(2), str(v)))
    return out


def _same(a, b):
    return json.dumps(a, sort_keys=True) == json.dumps(b, sort_keys=True)


def _verdict(row, field, suffix, value):
    """'match' | 'unknown' | 'no' | 'disagree' for one active filter, same rules as matchFacet (unknown is never no). D10 (product/decisions.md):
    a filtered key with a disagreeing alternative of another kind (index x[key].alt) is never matched silently:
      - headline matches and any alternative has a different value (either side of the filter) -> 'disagree';
      - headline fails and an alternative would match -> 'disagree' (never ruled out); all values fail -> 'no';
      - no headline but alternatives (or index status s[key] == 'conflicted') -> explicit 'disagree', not a generic 'unknown'
        (review-7: a conflict without a headline value kept its conflict state). All alternatives failing -> 'no'."""
    key = field["key"]
    v = _verdict1(row, field, suffix, value)
    alts = ((row.get("x") or {}).get(key) or {}).get("alt") or []
    if v == "unknown":
        if alts:
            return "no" if all(_verdict1({"v": {key: a["v"]}}, field, suffix, value) == "no" for a in alts) else "disagree"
        return "disagree" if (row.get("s") or {}).get(key) == "conflicted" else "unknown"
    if alts:
        av = [_verdict1({"v": {key: a["v"]}}, field, suffix, value) for a in alts]
        if v == "match" and (any(x != "match" for x in av) or any(not _same(a["v"], row["v"][key]) for a in alts)):
            return "disagree"
        if v == "no" and any(x == "match" for x in av):
            return "disagree"
    return v


def _verdict1(row, field, suffix, value):
    key = field["key"]
    kind = field["type"]
    facet = field.get("facet")
    enum_facet = isinstance(facet, dict) and facet.get("kind") == "enum"
    if not _known(row, key):
        return "unknown"
    val = row["v"][key]
    if kind in NUMERIC and not enum_facet:
        if kind == "range":
            lo, hi = (val or {}).get("min"), (val or {}).get("max")
        else:
            lo = hi = val
        try:
            lo, hi = float(lo), float(hi)
        except (TypeError, ValueError):
            return "no"
        if suffix == "min":
            return "match" if lo >= float(value) else "no"
        return "match" if hi <= float(value) else "no"
    if kind == "bool":
        return "match" if val is (value == "yes") else "no"
    if kind == "enum":
        return "match" if val == value else "no"
    return "match" if value.lower() in str(val).lower() else "no"


def _scope(preset, default_scope):
    sc = {**default_scope, **(preset.get("scope") or {})}
    return sc.get("sources"), bool(sc.get("include_discontinued")), list(sc.get("by") or []), sc.get("basis") or ""


def measure(preset, category, schema, rows, default_min, default_min_brands=2, default_scope=None):
    """D8 (product/decisions.md): fill per gate key = known / in-scope rows. Unknown always stays in; a key is never scoped by itself."""
    fields = {f["key"]: f for f in schema["fields"]}
    active = _parse_filters(preset.get("filters") or {}, fields)
    gate_keys = list(dict.fromkeys([f["key"] for f, _, _ in active] + list(preset.get("require") or [])))
    for key in gate_keys:
        if key not in fields:
            raise SystemExit(f"preset {preset['id']}: gate key {key!r} not in {category['id']} schema")
        if not (fields[key].get("facet") or fields[key].get("column")):
            raise SystemExit(f"preset {preset['id']}: gate key {key!r} is neither a facet nor a column, so the index does not carry it and it would measure 0 (set facet or column in the {category['id']} profile)")
    sources, incl_disc, by, basis = _scope(preset, default_scope or {})
    active_keys = {f["key"] for f, _, _ in active}
    for key in by:
        if key not in active_keys:
            raise SystemExit(f"preset {preset['id']}: scope.by key {key!r} is not a filter key of the preset")
    if sources is not None and any("t" not in r for r in rows):
        raise SystemExit(f"preset {preset['id']}: index rows of {category['id']} carry no source tiers (`t`); rebuild the index")
    category_total = len(rows)
    wanted = set(sources) if sources is not None else None
    def has_tier(r):
        return wanted is None or bool(wanted & set(r.get("t") or []))
    # Coordinator ruling r12 (A2-safe): recall-only records (gen.record_kind recall_only: identity + CPSC recall facts, no maker or certifier
    # record) are never in a preset's population, whatever its source scope.
    recall_only = [r for r in rows if (r.get("v") or {}).get("gen.record_kind") == "recall_only"]
    rows_in = [r for r in rows if (r.get("v") or {}).get("gen.record_kind") != "recall_only"]
    no_tier = [r for r in rows_in if not has_tier(r)]
    rest = [r for r in rows_in if has_tier(r)]
    discont = [r for r in rest if not incl_disc and r.get("lifecycle") == "discontinued"]
    pool = [r for r in rest if incl_disc or r.get("lifecycle") != "discontinued"]
    by_filters = {k: [t for t in active if t[0]["key"] == k] for k in by}
    def ruled_out(r, skip=None):
        return [k for k in by if k != skip and any(_verdict(r, f, s, v) == "no" for f, s, v in by_filters[k])]
    by_count = {k: 0 for k in by}
    for r in pool:
        out = ruled_out(r)
        if out:
            by_count[out[0]] += 1
    min_fill = float(preset.get("min_fill", default_min))
    min_brands = int(preset.get("min_brands", default_min_brands))
    per_key, pops = [], {}
    for key in gate_keys:
        pop = [r for r in pool if not ruled_out(r, key) and (r.get("s") or {}).get(key) != "not_applicable"]
        pops[key] = pop
        known = sum(1 for r in pop if _known(r, key))
        by_kind = Counter(_prov(r, key) for r in pop if _known(r, key))       # D10: fill counts every kind, broken down on the card
        assert sum(by_kind.values()) == known, "one headline kind per known row: alternatives never add to fill"
        per_key.append({"key": key, "label": fields[key]["label"], "known": known, "total": len(pop), "fill": round(known / len(pop), 4) if pop else 0.0,
                        "by_kind": dict(sorted(by_kind.items()))})
    weakest = min(per_key, key=lambda k: k["fill"]) if per_key else None
    fill = weakest["fill"] if weakest else 1.0
    def brand_of(r):
        return r.get("brand") or ""
    covered = None
    for key in gate_keys:
        have = {brand_of(r) for r in pops[key] if _known(r, key) and brand_of(r)}
        covered = have if covered is None else covered & have
    covered = sorted(covered or [])
    non_maker = []      # D10: brands whose known values on some gate key are all non-maker kinds (derived / measured / reported)
    for b in covered:
        for key in gate_keys:
            ks = {_prov(r, key) for r in pops[key] if brand_of(r) == b and _known(r, key)}
            if ks and ks <= set(NON_MAKER):
                non_maker.append({"brand": b, "key": key, "kinds": sorted(ks)})
                break
    brands_all = Counter(brand_of(r) for r in rows_in)
    in_scope_brands = {brand_of(r) for r in pool}
    tier_brands = {brand_of(r) for r in rest}
    not_covered = [{"brand": b, "rows": n, "reason": "no maker source" if b not in tier_brands else "discontinued only" if b not in in_scope_brands else "no value"}
                   for b, n in brands_all.most_common() if b and b not in covered]
    passes = fill >= min_fill and (not gate_keys or len(covered) >= min_brands)
    gate = {"passes": passes, "min_fill": min_fill, "min_brands": min_brands, "fill": fill, "keys": per_key,
            "scope": {"basis": basis, "sources": sources, "include_discontinued": incl_disc, "in_scope": len(pool), "category_total": category_total, "covered_brands": covered,
                      "excluded": {"source_tier": len(no_tier), "discontinued": len(discont), "by": by_count, "recall_only": len(recall_only)}, "not_covered": not_covered[:8]},
            "non_maker_brands": non_maker}
    if weakest:
        pop = pops[weakest["key"]]
        have = Counter(brand_of(r) for r in pop if _known(r, weakest["key"]))
        miss = [{"brand": b, "rows": n} for b, n in Counter(brand_of(r) for r in pop).most_common() if have[b] == 0 and b]
        gate.update(key=weakest["key"], label=weakest["label"], known=weakest["known"], total=weakest["total"],
                    missing_brands=miss[:8], missing_brand_count=len(miss))
        if passes:       # a passing preset can still have brands we do not cover: say so (any gate key, in-scope brands with 10+ rows)
            seen = {}
            for key in gate_keys:
                have_k = Counter(brand_of(r) for r in pops[key] if _known(r, key))
                for b, n in Counter(brand_of(r) for r in pops[key]).most_common():
                    if b and n >= 10 and have_k[b] == 0:
                        seen.setdefault(b, {"brand": b, "rows": n, "label": fields[key]["label"]})
            gate["uncovered_brands"] = sorted(seen.values(), key=lambda b: -b["rows"])[:5]
    # Disjoint buckets (review-7): every in-scope row is exactly one of match | unknown | disagree | no (a row with both an unknown and a
    # disagreeing filter is 'disagree'). `maybe` = unknown + disagree is kept for the app's card; consumers never add maybe and disagree.
    buckets = Counter()
    for r in pool:
        v = [_verdict(r, f, s, val) for f, s, val in active]
        buckets["no" if "no" in v else "disagree" if "disagree" in v else "unknown" if "unknown" in v else "match"] += 1
    assert sum(buckets.values()) == len(pool)
    return gate, {"matches": buckets["match"], "maybe": buckets["unknown"] + buckets["disagree"], "unknown": buckets["unknown"], "disagree": buckets["disagree"],
                  "ruled_out": buckets["no"], "total": len(pool), "out_of_scope": category_total - len(pool)}


def build(api, categories, source=None, skip_unpublished=False):
    """skip_unpublished (build.py --no-state only): presets of categories this build does not publish are left out instead of failing."""
    src = source or json.loads((DOCS / "presets.json").read_text())
    by_id = {c["id"]: c for c in categories}
    default_min = float(src.get("default_min_fill", 0.8))
    default_min_brands = int(src.get("default_min_brands", 2))
    default_scope = src.get("default_scope") or {}
    cache, out = {}, []
    ids = set()
    for p in src["presets"]:
        if p["id"] in ids:
            raise SystemExit(f"duplicate preset id {p['id']}")
        ids.add(p["id"])
        cat = by_id.get(p["category"])
        if skip_unpublished and not cat:
            continue
        if not cat or not cat.get("index") or not cat.get("schema"):
            raise SystemExit(f"preset {p['id']}: category {p['category']!r} is not a published indexed category")
        if p["category"] not in cache:
            cache[p["category"]] = (json.loads((api / cat["schema"]).read_text()), _rows(api, cat))
        schema, rows = cache[p["category"]]
        have = {f["key"] for f in schema["fields"]}
        for key in p.get("columns") or []:
            if key not in have:
                raise SystemExit(f"preset {p['id']}: column {key!r} not in {p['category']} schema")
            f = next(f for f in schema["fields"] if f["key"] == key)
            if not (f.get("facet") or f.get("column")):
                raise SystemExit(f"preset {p['id']}: column {key!r} is neither a facet nor a column field, so the index does not carry it")
        gate, count = measure(p, cat, schema, rows, default_min, default_min_brands, default_scope)
        out.append({**p, "category_name": cat["name"], "min_fill": gate["min_fill"], "gate": gate, "count": count})
    return {"version": 1, "default_min_fill": default_min, "default_min_brands": default_min_brands, "renderers": src.get("renderers", {}), "presets": out}


def write(api, skip_unpublished=False):
    api = Path(api)
    categories = json.loads((api / "categories.json").read_text())
    data = build(api, categories, skip_unpublished=skip_unpublished)
    (api / "presets.json").write_text(json.dumps(data, indent=1, ensure_ascii=False) + "\n")
    return {"presets": len(data["presets"]), "pass": [p["id"] for p in data["presets"] if p["gate"]["passes"]]}


if __name__ == "__main__":
    print(json.dumps(write(DOCS / "api" / "v1"), indent=1))
