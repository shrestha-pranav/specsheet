#!/usr/bin/env python3
"""Killer-query presets with a build-time fill gate.

Reads docs/presets.json (the preset definitions) and the published docs/api/v1 index, measures how much of each preset's slice has its
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


def _verdict(row, field, suffix, value):
    """'match' | 'unknown' | 'no' for one active filter, same rules as matchFacet (unknown is never no)."""
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


def measure(preset, category, schema, rows, default_min):
    fields = {f["key"]: f for f in schema["fields"]}
    active = _parse_filters(preset.get("filters") or {}, fields)
    gate_keys = list(dict.fromkeys([f["key"] for f, _, _ in active] + list(preset.get("require") or [])))
    for key in gate_keys:
        if key not in fields:
            raise SystemExit(f"preset {preset['id']}: gate key {key!r} not in {category['id']} schema")
    total = len(rows)
    per_key = []
    for key in gate_keys:
        known = sum(1 for r in rows if _known(r, key))
        per_key.append({"key": key, "label": fields[key]["label"], "known": known, "total": total, "fill": round(known / total, 4) if total else 0.0})
    weakest = min(per_key, key=lambda k: k["fill"]) if per_key else None
    min_fill = float(preset.get("min_fill", default_min))
    fill = weakest["fill"] if weakest else 1.0
    brands_total = Counter(r.get("brand") or "" for r in rows)
    def lacking(key, floor=1):
        have = Counter(r.get("brand") or "" for r in rows if _known(r, key))
        return [{"brand": b, "rows": n} for b, n in brands_total.most_common() if have[b] == 0 and n >= floor and b]
    gate = {"passes": fill >= min_fill, "min_fill": min_fill, "fill": fill, "keys": per_key}
    if weakest:
        miss = lacking(weakest["key"])
        gate.update(key=weakest["key"], label=weakest["label"], known=weakest["known"], total=total,
                    missing_brands=miss[:8], missing_brand_count=len(miss))
        if gate["passes"]:       # a passing preset can still have brands we do not cover: say so (any gate key, brands with 10+ rows)
            seen = {}
            for key in gate_keys:
                for b in lacking(key, 10):
                    seen.setdefault(b["brand"], {"brand": b["brand"], "rows": b["rows"], "label": fields[key]["label"]})
            gate["uncovered_brands"] = sorted(seen.values(), key=lambda b: -b["rows"])[:5]
    matches = maybe = 0
    for r in rows:
        v = [_verdict(r, f, s, val) for f, s, val in active]
        if "no" in v:
            continue
        if "unknown" in v:
            maybe += 1
        else:
            matches += 1
    return gate, {"matches": matches, "maybe": maybe, "total": total}


def build(api, categories, source=None):
    src = source or json.loads((DOCS / "presets.json").read_text())
    by_id = {c["id"]: c for c in categories}
    default_min = float(src.get("default_min_fill", 0.8))
    cache, out = {}, []
    ids = set()
    for p in src["presets"]:
        if p["id"] in ids:
            raise SystemExit(f"duplicate preset id {p['id']}")
        ids.add(p["id"])
        cat = by_id.get(p["category"])
        if not cat or not cat.get("index") or not cat.get("schema"):
            raise SystemExit(f"preset {p['id']}: category {p['category']!r} is not a published indexed category")
        if p["category"] not in cache:
            cache[p["category"]] = (json.loads((api / cat["schema"]).read_text()), _rows(api, cat))
        schema, rows = cache[p["category"]]
        have = {f["key"] for f in schema["fields"]}
        for key in p.get("columns") or []:
            if key not in have:
                raise SystemExit(f"preset {p['id']}: column {key!r} not in {p['category']} schema")
        gate, count = measure(p, cat, schema, rows, default_min)
        out.append({**p, "category_name": cat["name"], "min_fill": gate["min_fill"], "gate": gate, "count": count})
    return {"version": 1, "default_min_fill": default_min, "renderers": src.get("renderers", {}), "presets": out}


def write(api):
    api = Path(api)
    categories = json.loads((api / "categories.json").read_text())
    data = build(api, categories)
    (api / "presets.json").write_text(json.dumps(data, indent=1, ensure_ascii=False) + "\n")
    return {"presets": len(data["presets"]), "pass": [p["id"] for p in data["presets"] if p["gate"]["passes"]]}


if __name__ == "__main__":
    print(json.dumps(write(DOCS / "api" / "v1"), indent=1))
