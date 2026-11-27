"""ENERGY STAR appliance pattern coverage (A2-appl r11, transform escover@1). Used by import.py for categories whose category.yaml lists
`es_pattern_entities` in `features` (refrigerators, dishwashers); config `es_patterns: {source: <ES source id>}`.

A1 ruling (team/reports/2026-11-26-a1-r11-appliances.md; research/refrigerators/spec-profile.yaml cert.energy_star traps):
  - an ENERGY STAR pattern row ('BRB106003**', 'ARD484F*10R/L') is its OWN entity, keyed x_energystar_model_pattern (do_model mints it; it
    never shares a key with a concrete mfr_model, so it is never merged with or expanded into a SKU);
  - a concrete model entity of the same brand is connected to it by a directed covered_by_certification edge (model -> pattern entity),
    published like the TV edges (extra.certifications, v1_publish.cert_out), only when
      (a) the pattern row lists the concrete string verbatim in additional_model_information   -> method es-pattern:listed  (role listed), or
      (b) the WHOLE concrete string matches the pattern with '*' = exactly one [A-Z0-9], '#' = one digit, a trailing 'R/L' = R or L, every
          other character literal, and exactly ONE pattern entity of the brand matches                -> method es-pattern:unique-match (role basic);
    two or more matching patterns -> es-pattern:ambiguous; a pattern using any other placeholder (trailing 'xxx', '(x = ...)') ->
    es-pattern:undocumented-token. Those two are proposals only (no policy names them).
  - nothing merges, nothing is inherited, no SKU is synthesised. Transfer of the energy-defining keys over an APPROVED edge is not
    implemented in escover@1: the edge is evidence only (the concrete rows already carry their own ES values; maker pages are a later round).
"""
import collections, hashlib, re
from pathlib import Path

ID, VERSION = "escover", 1
TRANSFORM = f"{ID}@{VERSION}"
REL = "covered_by_certification"
PATTERN_SCHEME = "x_energystar_model_pattern"
METHODS_APPROVABLE = ("es-pattern:listed", "es-pattern:unique-match")


def fingerprint():
    p = Path(__file__)
    return "sha256:" + hashlib.sha256(p.name.encode() + b"\0" + p.read_bytes() + b"\0").hexdigest()[:20]


def pattern_rx(pat):
    """-> compiled full-string regex, or None when the pattern uses a placeholder A1 did not define."""
    p = re.sub(r"\s+", "", pat).upper()
    tail = ""
    if re.search(r"[RL]/[LR]$", p):
        p, tail = p[:-3], "[RL]"
    if "/" in p and re.search(r"/\*|\*/", p):
        return None                                   # 'DEU2450B*/*': '/' next to a wildcard = undocumented alternation
    if re.search(r"x{3,}$", re.sub(r"\s+", "", pat)):
        return None                                   # lowercase 'xxx' placeholder: undocumented
    body = "".join("[A-Z0-9]" if ch == "*" else r"\d" if ch == "#" else re.escape(ch) for ch in p)
    return re.compile(body + tail + r"\Z")


def loose_stem(pat):
    """Undocumented-placeholder patterns: the literal prefix before the first placeholder (proposals only)."""
    return re.split(r"[*#/]|x{3,}$", re.sub(r"\s+", "", pat))[0].upper()


def _key(e, scheme, raw=False):
    return next((v["value_raw" if raw else "value"] for (sch, _), v in sorted(e.idents.items()) if sch == scheme and v["role"] == "key"), None)


def apply(world, stats, parser):
    """After every source: build the coverage edges of one category world."""
    pats = [e for e in world.ents if e.kind == "model" and _key(e, PATTERN_SCHEME)]
    concrete = [e for e in world.ents if e.kind == "model" and _key(e, "mfr_model") and not _key(e, PATTERN_SCHEME)]
    by_brand = collections.defaultdict(list)
    for p in pats:
        raw = _key(p, PATTERN_SCHEME, raw=True)       # as filed: the lowercase 'xxx' placeholder only survives in value_raw
        by_brand[p.brand].append((p, raw, pattern_rx(raw)))
    listed = collections.defaultdict(set)              # (brand, concrete string) -> pattern entities that list it verbatim
    for p in pats:
        for text, kind in p.aliases.items():
            if kind == "model_variant":
                listed[(p.brand, re.sub(r"\s+", "", text).upper())].add(p)
    stats["es_pattern_entities"] += len(pats)
    for e in concrete:
        k = _key(e, "mfr_model")
        kn = re.sub(r"\s+", "", k).upper()
        edges = []
        for p in sorted(listed.get((e.brand, kn), ()), key=lambda x: _key(x, PATTERN_SCHEME)):
            edges.append((p, "listed", "es-pattern:listed"))
        hits = [(p, pk) for p, pk, rx in by_brand.get(e.brand, []) if rx is not None and rx.match(kn)]
        undocumented = [(p, pk) for p, pk, rx in by_brand.get(e.brand, []) if rx is None
                        and len(loose_stem(pk)) >= 4 and kn.startswith(loose_stem(pk))]
        method = "es-pattern:unique-match" if len(hits) == 1 else "es-pattern:ambiguous"
        for p, pk in hits:
            if not any(x[0] is p for x in edges):
                edges.append((p, "basic", method))
        for p, pk in undocumented:
            if not any(x[0] is p for x in edges):
                edges.append((p, "basic", "es-pattern:undocumented-token"))
        if edges:
            e.__dict__["es_pattern_edges"] = [{"target": p, "role": role, "method": m, "parser": f"{parser}+{TRANSFORM}"} for p, role, m in edges]
            for _, _, m in edges:
                stats["es_pattern_edges:" + m] += 1


def finalize(world, dec):
    """Once ids exist: decide each edge (ledger > policy > proposed); publish via extra.certifications. No claim moves."""
    for e in world.ents:
        edges = e.__dict__.get("es_pattern_edges")
        if not edges:
            continue
        out = []
        for x in edges:
            p = x["target"]
            st, did = dec.relation_state(e.id, REL, p.id, x["method"], x["parser"])
            if st == "rejected":
                continue
            date = next((c.get("value") for c, _ in p.claims if c.get("key") == "cert.es_date" and c.get("status") == "known"), None)
            out.append({"record": p.id, "pattern": _key(p, PATTERN_SCHEME), "matched_pattern": _key(p, PATTERN_SCHEME), "role": x["role"],
                        "market": "US", "declaration": None, "date_qualified": date, "method": x["method"],
                        "status": "approved" if st == "approved" else "proposed", "decision": did, "power_transferred": False, "power": []})
        if out:
            e.extra["certifications"] = sorted(out, key=lambda x: (x["record"], x["method"]))
