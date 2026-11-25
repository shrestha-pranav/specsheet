"""Pure, condition-aware spec resolution + approved-graph inheritance (review P0-2, P1-4, review 2 risks 2-3). Used by v1_publish.py;
unit-tested in tests/test_resolve.py and tests/test_adversarial.py.

resolve_spec(spec, claims, absences) -> published `specs[key]` (record.schema.json $defs.resolved) or None.
  claims: [{id, status, kind, cond: dict, mmode, ok, value (normalised), raw, nx: {display, qualifier}, source, supersedes}]
  1. supersession first: a claim named in another claim's `supersedes` is dropped.
  2. group by canonical condition tuple MINUS the spec's basis_conditions. The headline group is the profile's `headline_condition`
     (exact match) or, when the spec has none, the unconditional group {}. Non-headline groups publish as `conditional[]`. No headline
     group -> the headline is `unknown` (never "the first condition"), conditional rows still publish.
  3. inside a group, the primary kind is official > derived > reported > measured. Claims of that kind are folded into SEMANTIC
     ASSERTIONS = (value, qualifier, basis conditions, measurement mode); equal numbers with different qualifiers/bases/modes are distinct
     assertions. Assertions are ordered by their canonical form, so the result never depends on claim order.
       one assertion                                   -> known, carrying its qualifier/display/basis/measurement_mode
       two assertions with the same basis+mode          -> conflicted (a real disagreement; exact 100 vs "up to" 100 included)
       assertions differ ONLY in basis/mode, same value -> known; `alternatives` list each basis with its provenance
       assertions differ ONLY in basis/mode, values differ -> unknown + note: incomparable test bases, never a conflict and never a pick
     Other kinds (measured beside official, per measurement mode) publish as `alternatives` with their kind: a measurement never
     overwrites or conflicts with the official value. Every branch (headline, alternative, conditional row) keeps qualifier, display,
     basis, measurement_mode and its claim ids + sources.
"""
import json

# Document pipeline (scripts/docattach.py): provenance conditions say WHICH evidence a claim came from (a manual, an OCR'd page), not under
# which operating condition the value holds. They are neither grouping nor basis conditions: a manual and the product page stating the
# same value are one assertion; stating different values is a conflict, never two incomparable "bases".
PROVENANCE = ("document_kind", "ocr", "ocr_conf", "identity", "identity_scope", "identity_variant")      # identity*: docattach@2 identity-evidence trust
MERGE_NOTE = "merged: page rows completed from linked documents (only fields the page left empty; nothing overridden)"
KIND_ORDER = ["official", "derived", "reported", "measured"]
ABSENCE_OK = {"unknown", "not_published", "not_applicable", "not_yet_extracted"}


def ckey(cond):
    return json.dumps({k: (sorted(v, key=str) if isinstance(v, list) else v) for k, v in sorted((cond or {}).items())}, sort_keys=True)


def split_cond(spec, cond):
    """-> (grouping conditions, basis conditions)."""
    basis = set(spec.get("basis_conditions") or [])
    cond = {k: v for k, v in (cond or {}).items() if k not in PROVENANCE}
    return {k: v for k, v in cond.items() if k not in basis}, {k: v for k, v in cond.items() if k in basis}


def _assertions(spec, cs):
    """Fold claims into semantic assertions keyed by (value, qualifier, basis, mode); sorted canonically (order independent)."""
    out = {}
    for c in cs:
        if not c["ok"]:
            continue
        nx = c.get("nx") or {}
        basis = split_cond(spec, c.get("cond"))[1]
        k = json.dumps([c["value"], nx.get("qualifier"), basis, c.get("mmode")], sort_keys=True)
        a = out.get(k)
        if a is None:
            a = out[k] = {"value": c["value"], "qualifier": nx.get("qualifier"), "basis": basis, "mmode": c.get("mmode"), "displays": set(),
                          "sources": set(), "claims": set(), "doc_only": True}
        a["doc_only"] = a["doc_only"] and "document_kind" in (c.get("cond") or {})
        if nx.get("display"):
            a["displays"].add(nx["display"])
        a["sources"].add(c["source"]); a["claims"].add(c["id"])
    return [out[k] for k in sorted(out)]


def _alt(a, kind):
    d = {"value": a["value"], "kind": kind, "sources": sorted(a["sources"]), "claims": sorted(a["claims"])}
    if a["qualifier"]:
        d["qualifier"] = a["qualifier"]
    if a["displays"]:
        d["display"] = sorted(a["displays"])[0]
    if a["basis"]:
        d["basis"] = a["basis"]
    if a["mmode"]:
        d["measurement_mode"] = a["mmode"]
    return d


def _group(spec, cs):
    """One condition group -> partial result (value/status/kind/sources/claims/alternatives + qualifier/display/basis/mode)."""
    by_kind = {}
    for c in cs:
        by_kind.setdefault(c.get("kind") or "official", []).append(c)
    primary_kind = next((k for k in KIND_ORDER if k in by_kind), sorted(by_kind)[0])
    prim = by_kind[primary_kind]
    asr = _assertions(spec, prim)
    out = {"kind": primary_kind}
    if not asr:   # nothing normalised: keep the literal, never coerce
        first = sorted(prim, key=lambda c: c["id"])[0]
        out.update(value=None, status="not_yet_extracted", sources=sorted({c["source"] for c in prim}), claims=sorted(c["id"] for c in prim),
                   raw=(first.get("raw") or "")[:300])
        alts = []
    elif len(asr) == 1:
        a = _alt(asr[0], primary_kind)
        out.update(value=a["value"], status="known", sources=a["sources"], claims=a["claims"])
        for f in ("qualifier", "display", "basis", "measurement_mode"):
            if a.get(f):
                out[f] = a[f]
        alts = []
    elif (m := _item_merge(spec, asr)) is not None:
        out.update(value=m, status="known", sources=sorted({s for a in asr for s in a["sources"]}), claims=sorted({i for a in asr for i in a["claims"]}),
                   note=MERGE_NOTE)
        alts = []
    else:
        alts = [_alt(a, primary_kind) for a in asr]
        out.update(sources=sorted({s for a in asr for s in a["sources"]}), claims=sorted({i for a in asr for i in a["claims"]}))
        frames = {}
        for a in asr:
            frames.setdefault(json.dumps([a["basis"], a["mmode"]], sort_keys=True), []).append(a)
        if any(len(v) > 1 for v in frames.values()):
            out.update(value=None, status="conflicted")
        elif len({json.dumps([a["value"], a["qualifier"]], sort_keys=True) for a in asr}) == 1:
            out.update(value=asr[0]["value"], status="known")
            if asr[0]["qualifier"]:
                out["qualifier"] = asr[0]["qualifier"]
            d = sorted({x for a in asr for x in a["displays"]})
            if d:
                out["display"] = d[0]
        else:
            out.update(value=None, status="unknown",
                       note="no single headline: the values were stated under different test bases / measurement modes (see alternatives); they are not comparable")
    for kind in KIND_ORDER:
        if kind == primary_kind or kind not in by_kind:
            continue
        for a in _assertions(spec, by_kind[kind]):
            alts.append(_alt(a, kind))
            out["claims"] = sorted(set(out["claims"]) | a["claims"])
    if alts:
        out["alternatives"] = alts
    return out


def _same(a, b):
    if isinstance(a, (int, float)) and isinstance(b, (int, float)) and not isinstance(a, bool) and not isinstance(b, bool):
        return abs(float(a) - float(b)) < 1e-9
    return a == b


def rows_compatible(base, rows, idf):
    """Every row of `rows` names a row of `base` (by id field) and agrees with it on every field both state."""
    if not (isinstance(base, list) and isinstance(rows, list)):
        return False
    by = {r.get(idf): r for r in base if isinstance(r, dict)}
    for r in rows:
        if not isinstance(r, dict) or r.get(idf) not in by:
            return False
        b = by[r.get(idf)]
        if any(v is not None and b.get(f) is not None and not _same(v, b.get(f)) for f, v in r.items()):
            return False
    return True


def _item_merge(spec, asr):
    """List-of-items spec (items.id_field), exactly one page assertion + document-only assertions that are row-compatible with it (and
    with each other): the page's rows, with empty fields filled from the documents. Anything else -> None (normal path: conflict)."""
    idf = (spec.get("items") or {}).get("id_field")
    if spec.get("type") != "list" or not idf or len(asr) < 2:
        return None
    base = [a for a in asr if not a["doc_only"]]
    docs = [a for a in asr if a["doc_only"]]
    if len(base) != 1 or not docs or any(a["basis"] or a["mmode"] or a["qualifier"] for a in asr):
        return None
    merged = [dict(r) for r in base[0]["value"]] if isinstance(base[0]["value"], list) else None
    if merged is None:
        return None
    for d in docs:
        if not rows_compatible(merged, d["value"], idf):
            return None
        by = {r.get(idf): r for r in merged}
        for r in d["value"]:
            for f, v in r.items():
                if v is not None and by[r[idf]].get(f) is None:
                    by[r[idf]][f] = v
    return merged


def supports(claim_value, published):
    """Gate support: a claim supports a published value when equal, or (merged item lists) when its rows are a compatible subset."""
    if json.dumps(claim_value, sort_keys=True) == json.dumps(published, sort_keys=True):
        return True
    if isinstance(published, list) and published and all(isinstance(r, dict) and "name" in r for r in published):
        return rows_compatible(published, claim_value, "name")
    return False


ROW_FIELDS = ("kind", "claims", "qualifier", "display", "basis", "measurement_mode", "alternatives", "note", "raw")


def resolve_spec(spec, claims, absences):
    sup = {c["supersedes"] for c in claims if c.get("supersedes")}
    claims = [c for c in claims if c["id"] not in sup]
    unit = spec.get("unit")
    known = [c for c in claims if c["status"] == "known"]
    if known:
        groups = {}
        for c in known:
            groups.setdefault(ckey(split_cond(spec, c.get("cond"))[0]), []).append(c)
        head = ckey(spec.get("headline_condition") or {})
        conditional = []
        for g in sorted(groups):
            if g == head:
                continue
            r = _group(spec, groups[g])
            row = {"conditions": json.loads(g), "value": r["value"], "status": r["status"], "sources": r["sources"]}
            for f in ROW_FIELDS:
                if r.get(f):
                    row[f] = r[f]
            conditional.append(row)
        if head in groups:
            r = _group(spec, groups[head])
        else:
            r = {"value": None, "status": "unknown", "kind": None, "sources": sorted({s for row in conditional for s in row["sources"]}),
                 "claims": [], "note": "only condition-specific values are published; no value for the headline condition"}
        out = {"value": r["value"], "unit": unit, "status": r["status"], "sources": r["sources"],
               "claims": sorted(set(r["claims"]) | {c["id"] for g in groups if g != head for c in groups[g]}),
               "kind": r["kind"], "confidence": None, "source_scope": "field"}
        for f in ("raw", "note", "display", "qualifier", "basis", "measurement_mode", "alternatives"):
            if r.get(f):
                out[f] = r[f]
        if conditional:
            out["conditional"] = conditional
        return out
    other = sorted((c for c in claims if c["status"] in ABSENCE_OK), key=lambda c: c["id"])
    if other:
        c = other[0]
        return {"value": None, "unit": unit, "status": c["status"], "sources": [c["source"]], "claims": [c["id"]], "kind": None, "confidence": None, "source_scope": "field"}
    if absences:
        a = absences[0]
        st = a["status"] if a["status"] in ABSENCE_OK else "not_yet_extracted"
        return {"value": None, "unit": unit, "status": st, "sources": [a["source"]], "claims": [], "kind": None, "confidence": None, "source_scope": "field",
                "note": (a.get("reason") or "")[:200]}
    return None


LEVEL = {"family": 0, "model": 1, "revision": 2, "configuration": 2, "package": 3}
PACKAGE_LOCAL = ("phys.", "ship.", "pack.", "contents")


def revision_scope(spec, identity=None):
    """'all' only with established applicability: the profile says so (revision_scope: all), the spec is family-level, or the profile
    lists it as model_defining (a different value would be a different model). Everything else is 'unspecified': a model page that
    does not name its hardware version describes the default/unstated revision, not all of them (review 2 risk 3)."""
    if spec.get("revision_scope") == "all" or spec.get("level") == "family" or spec["key"] in ((identity or {}).get("model_defining") or []):
        return "all"
    return "unspecified"


def inheritable(spec, parent_kind, child_kind, identity=None):
    """Profile-driven: a spec inherits from parent P iff it does not vary below P's level (spec.level <= P's level); packages never
    inherit physical/shipping/pack facts (dimensions, weight, pack count are package facts, not component facts); a revision inherits
    only facts whose revision_scope is 'all' (established applicability), never the unspecified/default-revision ones."""
    if parent_kind == "family":
        return False
    if child_kind == "revision":
        return revision_scope(spec, identity) == "all"
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
