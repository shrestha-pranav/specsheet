"""TV certification coverage and ES/site reconciliation (A3-impl r7, transform tvcert@1, review 4 fixes 2 + 3). Used by import.py (importer
'model') when research/<cat>/category.yaml lists `es_cert_scopes` in `features`; config `es_cert: {source: <ES source id>}`.

Fix 2, certification scopes. An ENERGY STAR record whose model number is a wildcard family ('OLED65C5***') never names a product and never
merges anything. It becomes a SCOPE: raw pattern, record id (pd_id), brand, stated market, declaration text, snapshot, date and parser.
Existing exact model entities are connected by a directed `covered_by_certification` edge (model -> 'energystar-tvs:<pd_id>'), never
parent / alias / inheritance / sibling traversal:
  - the whole model key must match the pattern using ONLY the filing's documented wildcard alphabet and width: '*' = one [A-Z0-9] when the
    record says '* may be any alphanumeric'; every other character is a literal (escaped). Any other wildcard ('#', '?') or an undocumented
    '*' = unknown semantics -> proposal only (method es-scope:undocumented-wildcard);
  - covered patterns: the basic model plus additional patterns whose own clause is an exact affirmative 'X is the same as <basic> except for
    model designation' / 'Same as basic model except model designation'. A listed pattern without a declaration (es-scope:listed-undeclared)
    or with any other wording (negation, extra exceptions: es-scope:declaration-not-exact) is a proposal only;
  - guards (fail closed, no edge): same brand; the record states United States AND the model's key states market US (unknown != US); the
    pattern's size digits agree with the certified diagonal (<= 1.6 in) and every size the model's own pages state (<= 1.05 in: makers
    measure ~0.5-1.0 in more than ES; the literal size digits already pin the class); a dated record; a stated model year
    (gen.model_year, if any) within one year of the record's availability year;
  - several records matching one model keep separate edges; if they disagree (diagonal, display type) every such edge is quarantined
    (es-scope:conflict, proposal) and an identity_conflicts row is written.
Only an APPROVED edge (rel/tvs-es-certification-scope@1 or a ledger line) transfers anything, and only:
  - pwr.energy_star = true, dated (raw + locator carry the record id, pattern and date_qualified), extractor energystar_tvs_coverage@1
    (claim/tvs-es-certification-coverage@1). A missing/removed record is unknown, never false;
  - power (pwr.on_mode_w, pwr.on_mode_doe_w, pwr.standby_w, pwr.annual_kwh with their original basis conditions) ONLY with applicability
    evidence: the record states the measurement applies to every covered designation, or a reviewed data/decisions/tv-crosswalks.yaml
    `power_applicability` entry names this exact record + model; extractor energystar_tvs_power_applicability@1 (separate allowlist,
    claim/tvs-es-power-applicability@1). Otherwise the figures are shown only on the certification record (extra.certifications[].power).
  - never physical, stand/VESA, panel, refresh, HDMI, warranty or package facts (TRANSFER_KEYS / POWER_KEYS are the only keys emitted).

Fix 3, ES vs site reconciliation. data/decisions/tv-crosswalks.yaml `pairs` are reviewed exact pairs (site string, certified string, market,
evidence url + quote naming both strings, human `by`). A pair yields a typed `same_model` link (method crosswalk:reviewed, rel/tvs-crosswalk@1)
only if: both exact model entities exist for the brand; a `suffix_rules` entry for that brand makes site == certified + suffix EXACTLY (so size,
generation, production/revision letter and LG channel/stand letters are identical by construction); the pair's market equals the rule's market
and both entities state it; no other pair names either string with a different partner; stated sizes agree. Nothing merges: both ids, both
printed identifiers and the evidence are kept (extra.crosswalks). Without a pair the stem `possible_match` proposal stays as it is.
Declared aliases (ES 'Same as basic model except model designation') are re-audited against the same guards: exact affirmative clause, US
record, equal size digits, and (brand-scoped structure, Samsung only today) equal series prefix, year letter and production letter; one base per
alias. An alias that fails becomes kind proposed_same_hardware (extra.alias_audit has the reason); no id changes.
"""
import collections, hashlib, json, re, sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "crawler" / "adapters"))
import _contract as C  # noqa: E402

ID, VERSION = "tvcert", 1
TRANSFORM = f"{ID}@{VERSION}"
COVERAGE_EXTRACTOR = "energystar_tvs_coverage@1"
POWER_EXTRACTOR = "energystar_tvs_power_applicability@1"
REL = "covered_by_certification"
TRANSFER_KEYS = ("pwr.energy_star",)
POWER_KEYS = ("pwr.on_mode_w", "pwr.on_mode_doe_w", "pwr.standby_w", "pwr.annual_kwh")
DOC_WILDCARD = re.compile(r"\*\s*(?:may be|=)\s*any\s+alphanumeric", re.I)
DOC_SENTENCE = re.compile(r"\(?\s*\*\s*(?:may be|=)\s*any\s+alphanumeric[^;]*$", re.I)
DECL = re.compile(r"^\s*([A-Z0-9*#?-]{3,40})\s+is the same as\s+([A-Z0-9*#?-]{3,40})\s+except for model designation\s*\.?\s*$", re.I)
SAME_BASIC = re.compile(r"^\s*same as (?:the )?basic model except (?:for )?model designation\s*\.?\s*$", re.I)
POWER_APPLIES = re.compile(r"(?:measure\w*|test(?:ed|ing)?\s+data|power\s+(?:data|values|figures))[^;]{0,60}\bappl(?:y|ies)\s+to\s+(?:all|every|each)\b", re.I)
TOKEN = re.compile(r"[A-Za-z0-9*#?-]{3,40}")
SAMSUNG = re.compile(r"^(QN|UN|KQ)(\d{2,3})([A-Z]{1,3}\d{2,3})([A-Z])([A-Z]?)([A-Z])$")      # QN 65 S90 D A F: prefix size series year channel production
STRUCT = {"samsung": SAMSUNG}
METHODS_APPROVABLE = ("es-scope:documented",)


def fingerprint():
    p = Path(__file__)
    return "sha256:" + hashlib.sha256(p.name.encode() + b"\0" + p.read_bytes() + b"\0").hexdigest()[:20]


def _flt(v):
    try:
        return float(str(v).replace(",", ""))
    except (TypeError, ValueError):
        return None


def raw_row(sid, rec):
    """The latest certification row of an ES snapshot (same choice as the adapter: latest date_qualified)."""
    try:
        rows = json.loads((C.BlobStore(sid).dir / rec["blob"]).read_bytes())
    except (OSError, KeyError, ValueError):
        return None
    if not rows:
        return None
    return sorted(rows, key=lambda r: r.get("date_qualified", ""), reverse=True)[0]


def size_digits(s):
    m = re.match(r"^[A-Z]*?(\d{2,3})", str(s).upper())
    return int(m[1]) if m else None


def clauses(ami, basic):
    """-> [(token, role, declaration text)] for the additional patterns of one record. role: declared | listed | declaration_not_exact."""
    out, seen = [], set()
    for clause in (ami or "").split(";"):
        parts = [p.strip() for p in clause.split(",") if p.strip()]
        toks = [p for p in parts if TOKEN.fullmatch(p) and re.search(r"\d", p)]
        text = [p for p in parts if p not in toks]
        decl = next((d for d in text if re.search(r"same as", d, re.I)), None)
        for t in toks:
            u = t.upper()
            if u == basic.upper() or u in seen:
                continue
            seen.add(u)
            if decl is None:
                out.append((u, "listed", None)); continue
            d = DOC_SENTENCE.sub("", decl).strip()
            m = DECL.match(d)
            exact = bool(m and m[1].upper() == u and m[2].upper() == basic.upper()) or bool(SAME_BASIC.match(d))
            out.append((u, "declared" if exact and not re.search(r"\bnot\b", d, re.I) else "declaration_not_exact", decl))
    return out


def pattern_rx(pat, documented):
    """-> (compiled full-string regex, semantics) ; semantics 'documented' | 'undocumented' | 'literal'."""
    if not re.search(r"[*#?]", pat):
        return re.compile(re.escape(pat) + r"\Z"), "literal"
    sem = "documented" if documented and not re.search(r"[#?]", pat) else "undocumented"
    return re.compile("".join("[A-Z0-9]" if ch in "*#?" else re.escape(ch) for ch in pat) + r"\Z"), sem


def scope_of(row, brand, sid, rec, pr, parser):
    raw = row["model_number"].strip().upper()
    ami = row.get("additional_model_information") or ""
    documented = bool(DOC_WILDCARD.search(ami))
    pats = [(raw, "basic", None)] + clauses(ami, raw)
    power = [{"key": c["key"], "value": c.get("value"), "unit": c.get("unit"), "conditions": c.get("conditions") or {}, "raw": c.get("raw")}
             for c in pr.get("claims") or [] if c.get("key") in POWER_KEYS and c.get("status") == "known"]
    return {"record": f"{sid}:{row.get('pd_id')}", "pd_id": str(row.get("pd_id")), "raw_pattern": raw, "brand": brand,
            "markets": row.get("markets"), "us": "united states" in str(row.get("markets") or "").lower(), "documented": documented,
            "diag": _flt(row.get("diagonal_viewable_screen_size_inches")), "display": row.get("display_type"),
            "date_qualified": (row.get("date_qualified") or "")[:10] or None, "date_available": (row.get("date_available_on_market") or "")[:10] or None,
            "patterns": pats, "power_applicability": bool(POWER_APPLIES.search(ami)), "power": power, "declaration_text": ami[:300],
            "sid": sid, "rec": rec, "pr": pr, "parser": f"{parser}+{TRANSFORM}", "observed_at": rec.get("fetched_at"), "snapshot": rec.get("snapshot")}


def _brand(world, mi, meta):
    iss = (mi.get("issuer") or meta["brand"]).lower()
    return world.meta["brand_aliases"].get(iss, iss)


def collect_scope(world, meta, sid, rec, pr, parser):
    """A wildcard ES row (do_model skips it as a model): record its certification scope."""
    mi = next((i for i in pr["identifiers"] if i["scheme"] == "mfr_model" and i.get("role", "key") == "key"), None)
    row = raw_row(sid, rec)
    if mi is None or row is None:
        return
    world.__dict__.setdefault("cert_scopes", []).append(scope_of(row, _brand(world, mi, meta), sid, rec, pr, parser))


def collect_exact(world, e, sid, rec, pr):
    """An exact ES row: keep its clauses for the declared-alias re-audit."""
    row = raw_row(sid, rec)
    if row is not None:
        world.__dict__.setdefault("cert_exact", []).append((e, row))


def _key(e):
    return next(((v["value"], v["market"]) for (sch, _), v in sorted(e.idents.items()) if sch == "mfr_model" and v["role"] == "key"), (None, None))


def _claims(e, key):
    return [c["value"] for c, _ in e.claims if c.get("key") == key and c.get("status") == "known" and _flt(c.get("value")) is not None]


def _guards(sc, pat, e):
    """-> None (passes) or the failing guard."""
    key, market = _key(e)
    if e.brand != sc["brand"]:
        return "brand"
    if not sc["us"] or market != "US":
        return "market (record must state United States and the model key must state US)"
    if not sc["date_qualified"]:
        return "undated record"
    sd = size_digits(pat)
    if sc["diag"] is None or sd is None or abs(sd - sc["diag"]) > 1.6:
        return "size (pattern size digits vs certified diagonal)"
    for v in _claims(e, "gen.viewable_diag"):         # makers measure ~0.5-1.0 in more than the ES viewable diagonal; a size step is >= 1 in
        if abs(float(v) - sc["diag"]) > 1.05:
            return f"size (model states {v} in, record {sc['diag']})"
    for v in _claims(e, "gen.size_class"):
        if abs(float(v) - sc["diag"]) > 1.6:
            return f"size class (model states {v}, record {sc['diag']})"
    ya = int(sc["date_available"][:4]) if sc["date_available"] else None
    for v in _claims(e, "gen.model_year"):
        if ya is None or abs(int(float(v)) - ya) > 1:
            return f"year (model states {v}, record available {sc['date_available']})"
    return None


def apply(world, stats, h):
    """After every source: match scopes to existing models, re-audit declared aliases, apply reviewed crosswalks. h: link, parser, decisions
    file path (crosswalks)."""
    scopes = world.__dict__.get("cert_scopes") or []
    models = [e for e in world.ents if e.kind == "model"]
    by_brand = collections.defaultdict(list)
    for e in models:
        by_brand[e.brand].append(e)
    per_model = collections.defaultdict(list)
    for sc in scopes:
        stats["cert_scopes"] += 1
        hits = 0
        for pat, role, decl in sc["patterns"]:
            rx, sem = pattern_rx(pat, sc["documented"])
            for e in by_brand.get(sc["brand"], []):
                k, _ = _key(e)
                if not k or not rx.match(k):
                    continue
                g = _guards(sc, pat, e)
                if g:
                    stats["cert_guard_failed"] += 1
                    if g.startswith("size") or g.startswith("year"):
                        world.id_review.append((e, "x_energystar_pattern", pat, f"certification scope {sc['record']} not applied: {g}"))
                    continue
                method = ("es-scope:undocumented-wildcard" if sem == "undocumented" else
                          {"basic": "es-scope:documented", "declared": "es-scope:documented", "listed": "es-scope:listed-undeclared"}.get(role, "es-scope:declaration-not-exact"))
                per_model[e].append({"sc": sc, "pattern": pat, "role": role, "declaration": decl, "method": method})
                hits += 1
        stats["cert_scopes_matched" if hits else "cert_scopes_unmatched"] += 1
    for e, edges in per_model.items():
        ok = [x for x in edges if x["method"] in METHODS_APPROVABLE]
        recs = {x["sc"]["record"] for x in ok}
        if len(recs) > 1 and (len({x["sc"]["diag"] for x in ok}) > 1 or len({x["sc"]["display"] for x in ok}) > 1):
            for x in ok:
                x["method"] = "es-scope:conflict"
            world.id_review.append((e, "x_energystar_pattern", ",".join(sorted(recs)), "certification scopes disagree (diagonal/display type): quarantined"))
            stats["cert_conflicts"] += 1
        out = []
        for x in edges:
            sc = x["sc"]
            out.append({"relation": REL, "record": sc["record"], "pattern": sc["raw_pattern"], "matched_pattern": x["pattern"], "role": x["role"],
                        "brand": sc["brand"], "market": sc["markets"], "declaration": x["declaration"], "date_qualified": sc["date_qualified"],
                        "snapshot": sc["snapshot"], "parser": sc["parser"], "method": x["method"],
                        "power": sc["power"], "_sc": sc})
        e.__dict__["cert_edges"] = out
        stats["cert_edges"] += len(out)
    audit_aliases(world, stats)
    crosswalks(world, stats, h)


def audit_aliases(world, stats):
    """Re-audit ES declared_same_hardware aliases (exact rows) against the review-4 guards; demote failures to proposed_same_hardware."""
    rows = world.__dict__.get("cert_exact") or []
    bases = collections.defaultdict(set)
    decl = {}
    for e, row in rows:
        basic = row["model_number"].strip().upper()
        for tok, role, text in clauses(row.get("additional_model_information"), basic):
            bases[tok].add(basic)
            decl[(id(e), tok)] = (basic, role, text, "united states" in str(row.get("markets") or "").lower())
    for e, row in rows:
        for text, kind in list(e.aliases.items()):
            if kind != "declared_same_hardware":
                continue
            tok = text.upper()
            basic, role, dtext, us = decl.get((id(e), tok), (None, None, None, False))
            why = None
            if basic is None or role != "declared":
                why = "declaration is not an exact affirmative same-as-basic-model statement"
            elif not us:
                why = "record does not state United States"
            elif size_digits(tok) is None or size_digits(tok) != size_digits(basic):
                why = "size digits differ"
            elif len(bases[tok]) > 1:
                why = "declared under several base models: " + ", ".join(sorted(bases[tok]))
            else:
                rx = STRUCT.get(e.brand)
                a, b = (rx.match(tok), rx.match(basic)) if rx else (None, None)
                if rx is None or not (a and b):
                    why = "no brand-scoped model-number structure to check generation / revision"
                elif (a[1], a[2], a[4], a[6]) != (b[1], b[2], b[4], b[6]):
                    why = "series prefix / size / year letter / production letter differ"
            stats["declared_aliases_audited"] += 1
            if why:
                e.aliases[text] = "proposed_same_hardware"
                e.extra.setdefault("alias_audit", []).append({"alias": text, "was": "declared_same_hardware", "now": "proposed_same_hardware", "reason": why})
                stats["declared_aliases_demoted"] += 1


def load_crosswalks(path):
    import yaml
    p = Path(path)
    doc = (yaml.safe_load(p.read_text()) if p.exists() else None) or {}
    return doc.get("suffix_rules") or [], doc.get("pairs") or [], doc.get("power_applicability") or []


def crosswalks(world, stats, h):
    rules, pairs, _ = load_crosswalks(h["crosswalks"])
    models = {}
    for e in world.ents:
        if e.kind == "model":
            k, m = _key(e)
            if k:
                models[(e.brand, k)] = (e, m)
    partner = collections.defaultdict(set)
    for p in pairs:
        partner[("s", p.get("brand"), str(p.get("site", "")).upper())].add(str(p.get("certified", "")).upper())
        partner[("c", p.get("brand"), str(p.get("certified", "")).upper())].add(str(p.get("site", "")).upper())
    for p in pairs:
        b, s, c = p.get("brand"), str(p.get("site", "")).upper(), str(p.get("certified", "")).upper()
        ev = p.get("evidence") or {}
        se, ce = models.get((b, s)), models.get((b, c))
        rule = next((r for r in rules if r.get("brand") == b and s == c + str(r.get("suffix", "")).upper() and r.get("suffix")), None)
        why = None
        if not p.get("by") or not ev.get("url") or not (s in str(ev.get("quote", "")).upper() and c in str(ev.get("quote", "")).upper()):
            why = "pair needs a human reviewer and evidence whose quote names both exact strings"
        elif se is None or ce is None:
            why = "both exact model entities must exist"
        elif rule is None:
            why = "not an exact brand-scoped market-suffix pair (production letter / channel / stand differences stay separate)"
        elif not p.get("market") or p.get("market") != rule.get("market") or se[1] != rule["market"] or ce[1] != rule["market"]:
            why = "market not stated identically by the pair, the rule and both entities"
        elif len(partner[("s", b, s)]) > 1 or len(partner[("c", b, c)]) > 1:
            why = "contradictory crosswalks name this string with different partners"
        else:
            sa, sb = set(map(float, _claims(se[0], "gen.viewable_diag"))), set(map(float, _claims(ce[0], "gen.viewable_diag")))
            if sa and sb and max(abs(x - y) for x in sa for y in sb) > 1.05:
                why = "stated sizes disagree"
        rec = {"site": s, "certified": c, "market": p.get("market"), "evidence": ev, "by": p.get("by"), "at": p.get("at")}
        if why:
            stats["crosswalk_rejected"] += 1
            if se is not None:
                se[0].extra.setdefault("crosswalks", []).append(dict(rec, status="rejected", reason=why))
            continue
        h["parser"]["current"] = TRANSFORM
        h["link"](se[0], "same_model", ce[0], "crosswalk:reviewed")
        for x, other in ((se[0], c), (ce[0], s)):
            x.extra.setdefault("crosswalks", []).append(dict(rec, partner=other, status="linked"))
        stats["crosswalk_linked"] += 1


def finalize(world, dec, h):
    """Once ids exist: decide each coverage edge (ledger > policy > proposed), then transfer ONLY the allowlisted, dated facts."""
    _, _, appl = load_crosswalks(h["crosswalks"])
    applies = {(str(a.get("record")), str(a.get("model", "")).upper()) for a in appl if a.get("by") and (a.get("evidence") or {}).get("url")}
    for e in world.ents:
        edges = e.__dict__.get("cert_edges")
        if not edges:
            continue
        k, _ = _key(e)
        out = []
        for x in edges:
            sc = x.pop("_sc")
            st, did = dec.relation_state(e.id, REL, x["record"], x["method"], x["parser"])
            x["status"], x["decision"] = ("approved" if st == "approved" else "proposed" if st == "proposed" else "rejected"), did
            power_ok = sc["power_applicability"] or (sc["record"], k) in applies or (sc["pd_id"], k) in applies
            x["power_transferred"] = bool(power_ok and st == "approved")
            out.append(x)
            if st != "approved":
                continue
            h["add_src"](e, sc["pr"], sc["rec"])
            ob = (sc["sid"], str(sc["rec"]["ref"]), sc["rec"]["snapshot"])
            loc = {"energystar_pd_id": sc["pd_id"], "date_qualified": sc["date_qualified"], "certification_pattern": sc["raw_pattern"],
                   "matched_pattern": x["matched_pattern"], "coverage": REL}
            lit = f"ENERGY STAR certified {sc['date_qualified']} (record {sc['pd_id']}, {sc['raw_pattern']}" + \
                  (f", declared {x['matched_pattern']}" if x["matched_pattern"] != sc["raw_pattern"] else "") + f", covers {k})"
            e.claims.append(({"key": "pwr.energy_star", "status": "known", "kind": "official", "value": True, "unit": None, "raw": lit,
                              "source": "s1", "method": {"stage": "feed", "extractor": COVERAGE_EXTRACTOR}, "observed_at": sc["observed_at"],
                              "locator": loc}, ob))
            if x["power_transferred"]:
                for p in sc["power"]:
                    e.claims.append(({"key": p["key"], "status": "known", "kind": "official", "value": p["value"], "unit": p["unit"],
                                      "conditions": p["conditions"], "raw": (p["raw"] or "")[:200] + f" (applies to {k})", "source": "s1",
                                      "method": {"stage": "feed", "extractor": POWER_EXTRACTOR}, "observed_at": sc["observed_at"], "locator": loc}, ob))
        e.extra["certifications"] = sorted(out, key=lambda x: (x["record"], x["matched_pattern"]))
