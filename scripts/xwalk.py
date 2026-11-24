"""Model-string crosswalks and declared same-hardware relations (A3-impl r8, transform xwalk@1). Brand- and category-generic; used by
import.py (importer 'model') when research/<cat>/category.yaml lists the features below. Nothing here merges entities or changes an id.

feature `model_crosswalks`, config `crosswalks: {file: <name in data/decisions/>, compare_keys: [spec keys]}`.
  A maker can print two namespaces for one product (Levoit marketing 'Core 400S' vs label code 'LAP-C401S-WUSR'; Coway / Blueair page names
  vs the ES / CARB model number). The decision file holds
    pairs:     reviewed pairs {brand, a, b, market, evidence: {url, quote}, by, at}. A pair yields a typed `same_model` link a -> b (method
               crosswalk:reviewed, parser xwalk@1, rel/<cat>-crosswalk@N) only if: a human `by` and a date; the evidence quote, from ONE source
               page, names BOTH exact strings; both exact model entities exist for the brand and differ; the pair's market is stated and both
               entities' model keys state that market; no other pair names either string with a different partner; no compare_key has known
               values that disagree. Otherwise the pair is recorded as rejected (extra.crosswalks[].reason), nothing linked.
    proposals: unreviewed candidates {brand, a, b, why}. Only a `possible_match` (method crosswalk:proposal, approvable by no policy).
  Nothing transfers over `same_model`: both ids, identifiers and claims stay as they are.

feature `same_hardware_relations`, config `same_hardware: {source: <ES source id>, transfer_keys: [...], compare_keys: [...]}`.
  An ENERGY STAR record's declared_same_hardware alias (the adapter's affirmative 'same as model X except model number' clause) that is ALSO the
  exact model key of another entity of the same brand (Blueair 4312112000: a CARB entity and a declared alias of ES 4312111000). Rule: the two
  stay separate entities with their own ids. The alias entity gets a directed `same_hardware_as` relation to the certified base, carrying the
  ES evidence (record, pd_ids, the declaration clause, date) in extra.same_hardware. Methods:
    es-declared:exact           approvable (rel/<cat>-es-same-hardware@N): clause re-checked as an exact affirmative declaration (no
                                'only difference' / 'identical in performance' / 'derivative' / negation), the record states United States,
                                the certification is dated, the alias is declared under ONE base, no compare_key disagrees;
    es-declared:not-exact | es-declared:market | es-declared:undated | es-declared:several-bases | es-declared:conflict   proposals only.
  Over an APPROVED edge ONLY the certification transfers (r7 rule): each transfer_key the base holds as a known, dated `true` from the ES
  record, emitted with extractor <source adapter>_same_hardware@1 (its own claim policy), raw + locator naming record, base and declaration.
  transfer_keys must be certification keys of the profile (index_rows.certification_keys): measured values (CADR, power, ozone ppb) never
  transfer. An alias entity that already holds its own record for a key gets nothing for it.
"""
import collections, hashlib, json, re, sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "crawler" / "adapters"))
import _contract as C  # noqa: E402
import identity as I  # noqa: E402

ID, VERSION = "xwalk", 1
TRANSFORM = f"{ID}@{VERSION}"
REL = "same_hardware_as"
APPROVABLE = "es-declared:exact"
AFFIRM = re.compile(r"same as|identical except|are identical except", re.I)
NEGATE = re.compile(r"only difference|identical in performance|derivative|\bnot\b|\bexcept for (?!colou?r|the model|model)", re.I)


def fingerprint():
    p = Path(__file__)
    return "sha256:" + hashlib.sha256(p.name.encode() + b"\0" + p.read_bytes() + b"\0").hexdigest()[:20]


def _sq(s):
    return re.sub(r"\s+", " ", str(s or "")).strip().upper()


def _models(world):
    out = {}
    for e in world.ents:
        if e.kind != "model":
            continue
        for (sch, _), v in sorted(e.idents.items()):
            if sch == "mfr_model" and v["role"] == "key":
                out.setdefault((e.brand, v["value"]), (e, v.get("market")))
    return out


def _find(models, brand, s):
    nv = I.norm_value("mfr_model", s, brand)
    return models.get((brand, nv)) if nv else None


def _known(e, key):
    return {json.dumps(c.get("value"), sort_keys=True) for c, _ in e.claims if c.get("key") == key and c.get("status") == "known"}


def disagree(a, b, keys):
    """-> the first compare key on which both entities state known values and no value is shared, else None."""
    for k in keys or []:
        va, vb = _known(a, k), _known(b, k)
        if va and vb and not (va & vb):
            return k
    return None


# ------------------------------------------------------------------ crosswalks (a) + (c)
def load(path):
    import yaml
    p = Path(path)
    doc = (yaml.safe_load(p.read_text()) if p.exists() else None) or {}
    return doc.get("pairs") or [], doc.get("proposals") or []


def check_pair(p, models, partner, compare_keys):
    """-> (why rejected | None, a entity, b entity)."""
    b_, a, b = p.get("brand"), str(p.get("a", "")), str(p.get("b", ""))
    ev = p.get("evidence") or {}
    q = _sq(ev.get("quote"))
    ae, be = _find(models, b_, a), _find(models, b_, b)
    if not p.get("by") or not p.get("at") or not ev.get("url") or not a or not b or _sq(a) not in q or _sq(b) not in q:
        return "pair needs a human reviewer, a date and one page's quote naming both exact strings", ae, be
    if ae is None or be is None:
        return "both exact model entities must exist for the brand", ae, be
    if ae[0] is be[0]:
        return "both strings already name one entity", ae, be
    if not p.get("market") or ae[1] != p["market"] or be[1] != p["market"]:
        return "market not stated identically by the pair and both entities", ae, be
    if len(partner[(b_, _sq(a))]) > 1 or len(partner[(b_, _sq(b))]) > 1:
        return "contradictory crosswalks name this string with different partners", ae, be
    k = disagree(ae[0], be[0], compare_keys)
    if k:
        return f"stated facts disagree ({k})", ae, be
    return None, ae, be


def crosswalks(world, stats, h, cfg):
    pairs, props = load(h["decisions"] / cfg["file"])
    models = _models(world)
    partner = collections.defaultdict(set)
    for p in pairs:
        partner[(p.get("brand"), _sq(p.get("a")))].add(_sq(p.get("b")))
        partner[(p.get("brand"), _sq(p.get("b")))].add(_sq(p.get("a")))
    for p in pairs:
        why, ae, be = check_pair(p, models, partner, cfg.get("compare_keys"))
        rec = {"a": p.get("a"), "b": p.get("b"), "market": p.get("market"), "evidence": p.get("evidence"), "by": p.get("by"), "at": p.get("at")}
        if why:
            stats["crosswalk_rejected"] += 1
            for x in (ae, be):
                if x is not None:
                    x[0].extra.setdefault("crosswalks", []).append(dict(rec, status="rejected", reason=why))
            continue
        h["parser"]["current"] = TRANSFORM
        h["link"](ae[0], "same_model", be[0], "crosswalk:reviewed")
        for x, other in ((ae[0], p["b"]), (be[0], p["a"])):
            x.extra.setdefault("crosswalks", []).append(dict(rec, partner=other, status="linked"))
        stats["crosswalk_linked"] += 1
    for p in props:
        ae, be = _find(models, p.get("brand"), p.get("a", "")), _find(models, p.get("brand"), p.get("b", ""))
        if ae is None or be is None or ae[0] is be[0]:
            stats["crosswalk_proposal_unmatched"] += 1
            continue
        h["parser"]["current"] = TRANSFORM
        h["link"](ae[0], "possible_match", be[0], "crosswalk:proposal")
        for x, other in ((ae[0], p["b"]), (be[0], p["a"])):
            x.extra.setdefault("crosswalks", []).append({"a": p.get("a"), "b": p.get("b"), "partner": other, "status": "proposal", "why": p.get("why")})
        stats["crosswalk_proposals"] += 1


# ------------------------------------------------------------------ declared same hardware (b)
def collect(world, e, sid, rec, pr, parser):
    """An exact ES row (do_model): remember it with its parser for the same-hardware pass."""
    world.__dict__.setdefault("shw_rows", []).append((e, sid, rec, pr, parser))


def _raw_rows(sid, rec, pr):
    pds = {str(i["value"]) for i in pr["identifiers"] if i["scheme"] == "x_energystar_pd_id"}
    try:
        rows = json.loads((C.BlobStore(sid).dir / rec["blob"]).read_bytes())
    except (OSError, KeyError, ValueError):
        return []
    return [r for r in rows if str(r.get("pd_id")) in pds]


def clause_for(rows, token):
    """-> (clause text, record states United States) of the first raw clause naming the token as a whole word."""
    rx = re.compile(r"(?<![A-Za-z0-9])" + re.escape(token) + r"(?![A-Za-z0-9])", re.I)
    for r in rows:
        for cl in str(r.get("additional_model_information") or "").split(";"):
            if rx.search(cl):
                return cl.strip(), "united states" in str(r.get("markets") or "").lower()
    return None, False


def _cert(e, sid, key):
    """The base's own known, dated `true` for a transfer key from the ES source -> (claim, obs) or None."""
    for c, ob in e.claims:
        if ob[0] == sid and c.get("key") == key and c.get("status") == "known" and c.get("value") is True \
                and (c.get("locator") or {}).get("date_certified") and "same_hardware_of" not in (c.get("locator") or {}):
            return c, ob
    return None


def same_hardware(world, stats, h, cfg):
    rows = world.__dict__.get("shw_rows") or []
    models = _models(world)
    sid = cfg["source"]
    keys = cfg.get("transfer_keys") or []
    bases = collections.defaultdict(set)
    for e, _, _, pr, _ in rows:
        for a in pr["aliases"]:
            if a["kind"] == "declared_same_hardware":
                bases[(e.brand, I.norm_value("mfr_model", a["text"], e.brand))].add(id(e))
    for e, sid_, rec, pr, parser in rows:
        raw = None
        for a in pr["aliases"]:
            if a["kind"] != "declared_same_hardware":
                continue
            hit = _find(models, e.brand, a["text"])
            if hit is None or hit[0] is e:
                continue                      # an alias only: nothing to relate
            f = hit[0]
            raw = raw if raw is not None else _raw_rows(sid_, rec, pr)
            clause, us = clause_for(raw, a["text"])
            dated = any(_cert(e, sid_, k) for k in keys) if keys else False
            method = APPROVABLE
            if not clause or not AFFIRM.search(clause) or NEGATE.search(clause):
                method = "es-declared:not-exact"
            elif not us:
                method = "es-declared:market"
            elif not dated:
                method = "es-declared:undated"
            elif len(bases[(e.brand, I.norm_value("mfr_model", a["text"], e.brand))]) > 1:
                method = "es-declared:several-bases"
            else:
                k = disagree(f, e, cfg.get("compare_keys"))
                if k:
                    method = "es-declared:conflict"
                    world.id_review.append((f, "mfr_model", a["text"], f"declared same hardware as {e.idhint} but {k} disagrees: kept as a proposal"))
            h["parser"]["current"] = f"{parser}+{TRANSFORM}"
            h["link"](f, REL, e, method)
            loc = (_cert(e, sid_, keys[0]) or ({}, None))[0].get("locator") if keys else {}
            ev = {"relation": REL, "role": "declared_alias", "alias": a["text"], "record": f"{sid_}:{(loc or {}).get('energystar_pd_id')}",
                  "declaration": (clause or "")[:300], "date_certified": (loc or {}).get("date_certified"), "method": method,
                  "snapshot": rec.get("snapshot"), "parser": f"{parser}+{TRANSFORM}", "_base": e, "_rec": rec, "_pr": pr, "_sid": sid_}
            f.__dict__.setdefault("shw_edges", []).append(ev)
            e.__dict__.setdefault("shw_back", []).append({"relation": REL, "role": "certified_base", "alias": a["text"], "_alias": f,
                                                          "record": ev["record"], "declaration": ev["declaration"],
                                                          "date_certified": ev["date_certified"], "method": method})
            stats["same_hardware_" + method.split(":")[1]] += 1


def apply(world, stats, h):
    cm = world.meta
    feats = cm.get("features") or []
    if "model_crosswalks" in feats:
        crosswalks(world, stats, h, cm["crosswalks"])
    if "same_hardware_relations" in feats:
        cfg = cm["same_hardware"]
        cert = set(((cm["profile"].get("index_rows") or {}).get("certification_keys")) or [])
        bad = [k for k in cfg.get("transfer_keys") or [] if k not in cert]
        if bad:
            raise SystemExit(f"research/{world.category}/category.yaml same_hardware.transfer_keys {bad} are not profile certification_keys: "
                             "only certification may transfer over same_hardware_as")
        same_hardware(world, stats, h, cfg)


def finalize(world, dec, h):
    """Once ids exist: decide each same_hardware_as edge (ledger > policy > proposed); over an approved one transfer ONLY the certification."""
    cfg = world.meta.get("same_hardware") or {}
    keys = cfg.get("transfer_keys") or []
    for e in world.ents:
        for b in e.__dict__.get("shw_back") or []:
            al = b.pop("_alias")
            b["alias_id"] = al.id
            e.extra.setdefault("same_hardware", []).append(b)
        edges = e.__dict__.get("shw_edges")
        if not edges:
            continue
        for x in edges:
            base, rec, pr, sid = x.pop("_base"), x.pop("_rec"), x.pop("_pr"), x.pop("_sid")
            st, did = dec.relation_state(e.id, REL, base.id, x["method"], x["parser"])
            if any(dec.vetoed(p, q) for p in world.anchors(e.keys) for q in world.anchors(base.keys)):
                st, did = "rejected", "split-veto"
            x.update(target=base.id, status=st, decision=did, transferred=[])
            if st == "approved":
                for k in keys:
                    got = _cert(base, sid, k)
                    if got is None or _cert(e, sid, k) is not None or any(c.get("key") == k and c.get("status") == "known" and ob[0] == sid
                                                                         for c, ob in e.claims):
                        continue
                    c, ob = got
                    h["add_src"](e, pr, rec)
                    bk = next((v["value"] for (sch, _), v in sorted(base.idents.items()) if sch == "mfr_model" and v["role"] == "key"), base.id)
                    loc = dict(c.get("locator") or {}, same_hardware_of=bk, declared_alias=x["alias"])
                    e.claims.append(({"key": k, "status": "known", "kind": c.get("kind") or "official", "value": True, "unit": None,
                                      "raw": f"{c.get('raw') or ''} (record {x['record']} of {bk}, certified {loc.get('date_certified')}; "
                                             f"declared same hardware: {x['declaration'][:160]})",
                                      "source": "s1", "method": {"stage": "feed", "extractor": cfg["extractor"]},
                                      "observed_at": c.get("observed_at"), "locator": loc}, ob))
                    x["transferred"].append(k)
            e.extra.setdefault("same_hardware", []).append({k: v for k, v in x.items() if k not in ("snapshot", "parser")})
    world.__dict__.pop("shw_rows", None)
    for e in world.ents:
        for b in e.extra.get("same_hardware") or []:
            if b.get("role") == "certified_base":
                al = next((x for x in world.ents if x.id == b["alias_id"]), None)
                edge = next((x for x in (al.extra.get("same_hardware") or []) if x.get("role") == "declared_alias" and x.get("target") == e.id
                             and x.get("alias") == b["alias"]), None) if al else None
                if edge:
                    b.update(status=edge["status"], decision=edge["decision"])
