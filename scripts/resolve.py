"""Pure, condition-aware spec resolution + approved-graph inheritance (review P0-2, P1-4). Used by v1_publish.py; unit-tested in
tests/test_resolve.py.

resolve_spec(spec, claims, absences) -> published `specs[key]` (record.schema.json $defs.resolved) or None.
  claims: [{id, status, kind, cond: dict, mmode, ok, value (normalised), raw, nx: {display, qualifier}, source, supersedes}]
  1. supersession first: a claim named in another claim's `supersedes` is dropped.
  2. group by canonical condition tuple. The headline group is the profile's `headline_condition` (exact match) or, when the
     spec has none, the unconditional group {}. Non-headline groups publish as `conditional[]`. No headline group -> the
     headline is `unknown` (never "the first condition"), conditional rows still publish.
  3. inside a group, the primary kind is official > derived > reported > measured. Distinct primary values -> `conflicted`
     with alternatives. Other kinds (measured beside official, per measurement mode) publish as `alternatives` with their kind:
     a measurement never overwrites or conflicts with the official value, and equal values are NOT collapsed across kinds.
"""
import json

KIND_ORDER = ["official", "derived", "reported", "measured"]
ABSENCE_OK = {"unknown", "not_published", "not_applicable", "not_yet_extracted"}


def ckey(cond):
    return json.dumps({k: (sorted(v, key=str) if isinstance(v, list) else v) for k, v in sorted((cond or {}).items())}, sort_keys=True)


def _group(spec, cs):
    """One condition group -> partial result (value/status/kind/sources/claims/alternatives)."""
    by_kind = {}
    for c in cs:
        by_kind.setdefault(c.get("kind") or "official", []).append(c)
    primary_kind = next((k for k in KIND_ORDER if k in by_kind), next(iter(by_kind)))
    prim = by_kind[primary_kind]
    vals, order = {}, []
    for c in prim:
        if not c["ok"]:
            continue
        k = json.dumps(c["value"], sort_keys=True)
        if k not in vals:
            vals[k] = {"value": c["value"], "sources": set(), "claims": [], "nx": c.get("nx") or {}}
            order.append(k)
        vals[k]["sources"].add(c["source"]); vals[k]["claims"].append(c["id"])
    out = {"kind": primary_kind}
    if not order:   # nothing normalised: keep the literal, never coerce
        out.update(value=None, status="not_yet_extracted", sources=sorted({c["source"] for c in prim}), claims=[c["id"] for c in prim],
                   raw=(prim[0].get("raw") or "")[:300])
    elif len(order) == 1:
        v = vals[order[0]]
        out.update(value=v["value"], status="known", sources=sorted(v["sources"]), claims=v["claims"])
        for f in ("display", "qualifier"):
            if v["nx"].get(f):
                out[f] = v["nx"][f]
    else:
        out.update(value=None, status="conflicted", sources=sorted({s for k in order for s in vals[k]["sources"]}),
                   claims=[i for k in order for i in vals[k]["claims"]],
                   alternatives=[{"value": vals[k]["value"], "kind": primary_kind, "sources": sorted(vals[k]["sources"])} for k in order])
    alts = out.setdefault("alternatives", [])
    for kind in KIND_ORDER:
        if kind == primary_kind or kind not in by_kind:
            continue
        seen = {}
        for c in by_kind[kind]:
            if not c["ok"]:
                continue
            k = json.dumps([c["value"], c.get("mmode")], sort_keys=True)
            a = seen.get(k)
            if a is None:
                a = seen[k] = {"value": c["value"], "kind": kind, "sources": []}
                if c.get("mmode"):
                    a["measurement_mode"] = c["mmode"]
                alts.append(a)
            if c["source"] not in a["sources"]:
                a["sources"].append(c["source"])
            out["claims"].append(c["id"])
    if not alts:
        del out["alternatives"]
    return out


def resolve_spec(spec, claims, absences):
    sup = {c["supersedes"] for c in claims if c.get("supersedes")}
    claims = [c for c in claims if c["id"] not in sup]
    unit = spec.get("unit")
    known = [c for c in claims if c["status"] == "known"]
    if known:
        groups = {}
        for c in known:
            groups.setdefault(ckey(c.get("cond")), []).append(c)
        head = ckey(spec.get("headline_condition") or {})
        conditional = []
        for g in sorted(groups):
            if g == head:
                continue
            r = _group(spec, groups[g])
            row = {"conditions": json.loads(g), "value": r["value"], "status": r["status"], "kind": r["kind"], "sources": r["sources"]}
            if r.get("alternatives"):
                row["alternatives"] = r["alternatives"]
            conditional.append(row)
        if head in groups:
            r = _group(spec, groups[head])
        else:
            r = {"value": None, "status": "unknown", "kind": None, "sources": sorted({s for row in conditional for s in row["sources"]}),
                 "claims": [], "note": "only condition-specific values are published; no value for the headline condition"}
        out = {"value": r["value"], "unit": unit, "status": r["status"], "sources": r["sources"], "claims": r["claims"] + [c["id"] for g in groups if g != head for c in groups[g]],
               "kind": r["kind"], "confidence": None, "source_scope": "field"}
        for f in ("raw", "note", "display", "qualifier", "alternatives"):
            if r.get(f):
                out[f] = r[f]
        if conditional:
            out["conditional"] = conditional
        if out["status"] == "conflicted" and len(out.get("alternatives") or []) < 2:
            out["status"] = "known"
        return out
    other = [c for c in claims if c["status"] in ABSENCE_OK]
    if other:
        c = other[0]
        return {"value": None, "unit": unit, "status": c["status"], "sources": [c["source"]], "claims": [c["id"]], "kind": None, "confidence": None, "source_scope": "field"}
    if absences:
        a = absences[0]
        st = a["status"] if a["status"] in ABSENCE_OK else "not_yet_extracted"
        return {"value": None, "unit": unit, "status": st, "sources": [a["source"]], "claims": [], "kind": None, "confidence": None, "source_scope": "field",
                "note": (a.get("reason") or "")[:200]}
    return None


LEVEL = {"family": 0, "model": 1, "configuration": 2, "package": 3}
PACKAGE_LOCAL = ("phys.", "ship.", "pack.", "contents")


def inheritable(spec, parent_kind, child_kind):
    """Profile-driven: a spec inherits from parent P iff it does not vary below P's level (spec.level <= P's level); packages never
    inherit physical/shipping/pack facts (dimensions, weight, pack count are package facts, not component facts)."""
    if parent_kind == "family":
        return False
    if child_kind == "package" and spec["key"].startswith(PACKAGE_LOCAL):
        return False
    return LEVEL.get(spec.get("level") or "model", 1) <= LEVEL.get(parent_kind, 1)


def topo(ents, parent_of):
    """Entity ids ordered parents-first over the approved parent graph; cycles are broken (and reported) rather than looped."""
    out, state, cycles = [], {}, []
    for eid in sorted(ents):
        stack = []
        cur = eid
        while cur is not None and state.get(cur) is None:
            state[cur] = "open"; stack.append(cur)
            nxt = parent_of.get(cur)
            if nxt is not None and state.get(nxt) == "open":
                cycles.append(nxt); nxt = None
            cur = nxt
        for x in reversed(stack):
            state[x] = "done"; out.append(x)
    return out, cycles
