#!/usr/bin/env python3
"""ENERGY STAR Certified Room Air Cleaners V3.0 adapter v1 (contract ARCHITECTURE 15.5), category air-purifiers. Cross-brand seed.

Source   : data.energystar.gov Socrata dataset gaa3-swy6 (US EPA open data; robots Crawl-delay 1; no key). Only CURRENTLY certified models.
discover : ONE SoQL GET of the whole dataset (248 rows on 2026-11-23), stored as ref '_all'. Rows are grouped per (canonical brand,
           normalised model): 'Coway' / 'Coway Airmega' / 'AIRMEGA' rows for one string are one ref (_airpurifier.brand_id). A model_number
           cell that lists several exact strings ('Airmega 350(W);Airmega 350(BG)') gives one ref per listed string: each is named
           by the filing. Cells with '*' or '#' (documented wildcards: * = letter, # = digit) are WILDCARD FAMILIES -> one ref flagged
           wildcard; the importer skips them (never a product). Cells naming no plausible model ('W', 'B', 'Kilo') -> no ref, counted.
fetch    : no network; a snapshot record per ref pointing at the '_all' blob (_airpurifier.shared_list_snapshot).
parse    : pure. Canada-only rows are dropped (market US only). When the ref's rows (several pd_ids) disagree on a field, that field is
           unresolved (status unknown, every value kept in raw), never one picked. Bases in conditions:
           - CADR (smoke/dust/pollen/PM2.5): cadr_basis=energy_star_certified (reported to EPA through a recognised certification body,
             AHAM AC-1 method; NOT the AHAM Verifide programme).
           - room.size_sqft: room_basis=energy_star_formula (smoke CADR x 1.55, per the dataset's own definition).
           - filter.true_hepa=True only from a filter type exactly 'HEPA' (the dataset defines HEPA = True HEPA, >= 99.97% at 0.3 um);
             'HEPA-Type' means "not demonstrated" and gives filter.hepa_class=hepa_type, never true_hepa (affirmative-only, never false).
           - eff.energy_star=True dated by date_certified; eff.most_efficient from its own Yes/No field.
           - Power: the dataset has no watts column. CADR/W, IEF and annual kWh are stored as printed; watts are NOT derived.
           additional_model_information: tokens in a clause the partner declares identical ('same as model X except model number',
           'identical except model number/name', 'same as X, except for color') -> aliases kind=declared_same_hardware; other tokens ->
           model_variant (unverified). "identical in performance ... only difference is" is NOT a same-hardware declaration.
Usage    : python3 -I crawler/adapters/energystar_airpurifiers.py discover|fetch|parse|run
"""
import json, re, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
import _contract as C
from _contract import Ref, Discovery, ParseResult, claim  # noqa
import _airpurifier as A
import _run

ID, VERSION, SOURCE = "energystar_airpurifiers", 1, "energystar-airpurifiers"
CATEGORIES = {"air-purifiers"}
API = "https://data.energystar.gov/resource/gaa3-swy6.json"
ADAPTER = f"{ID}@{VERSION}"
DELAY = 1.0
LIST = "_all"
SAME = re.compile(r"(is )?(the )?same as (the )?(basic )?model.{0,40}?except (for )?(the )?model (number|name|designation)|identical except (for )?"
                  r"(the )?model (number|name|designation)|are identical except for the model (number|name)|same as \S{3,40},? except for colou?r",
                  re.I)
NOT_SAME = re.compile(r"only difference|identical in performance|derivative", re.I)
TOKEN = re.compile(r"[A-Za-z0-9][A-Za-z0-9._/+()-]{2,40}")
FIELDS_CADR = (("smoke_free_clean_air_delivery", "cadr.smoke_cfm"), ("dust_free_clean_air_delivery", "cadr.dust_cfm"),
               ("pollen_free_clean_air_delivery", "cadr.pollen_cfm"), ("pm25_cadr", "cadr.pm25_cfm"))
FIELDS_EFF = (("smoke_free_clean_air_delivery_rate_cfm_w", "eff.smoke_cadr_per_w"), ("dust_free_clean_air_delivery_rate_cfm_w", "eff.dust_cadr_per_w"),
              ("pollen_free_clean_air_delivery_rate_cfm_w", "eff.pollen_cadr_per_w"), ("integrated_energy_factor_cfm_w", "eff.ief"))
TECH = {"fan and filter": "fan_filter", "ion generator": "ionizer", "uv light": "uv", "plasmawave": "plasmawave", "fan with electrostatic plates": "electrostatic"}
FILTER = {"hepa": "hepa", "hepa-type": "hepa_type", "activated carbon": "activated_carbon", "composite filter": "composite",
          "permanent washable filter": "washable", "non-woven": "non_woven"}


def model_cells(raw):
    """model_number cell -> [(model, is_wildcard)]; ';'-separated lists are several exact strings."""
    out = []
    for t in [x.strip() for x in str(raw or "").split(";")]:
        if not t:
            continue
        wild = bool(re.search(r"[*#]", t))
        if wild or A.model_ok(t):
            out.append((t[:40], wild))
    return out


def split_additional(txt, own):
    """-> ([(token, kind)], [declaration phrases]). A token is declared only inside a clause (up to ';') that carries a same-hardware
    statement and no difference statement."""
    out, phrases, seen = [], [], set()
    for clause in re.split(r";", txt or ""):
        m = SAME.search(clause)
        declared = bool(m) and not NOT_SAME.search(clause)
        if declared:
            phrases.append(m.group(0))
        body = re.sub(r"\(\s*\d{8,14}\s*\)|UPC:?\s*\d+", " ", clause)
        body = re.sub(r"(,| is | are |\.)\s*(same|identical|model is|model with|usa market|canada market|\* can|where|may be|followed).*$", " ", body,
                      flags=re.I)
        body = re.sub(r"\(\s*where.*$|\(\s*[\"\u201c]?x[\"\u201d]?\s*can.*$", " ", body, flags=re.I)
        for t in re.split(r"[,\s]+", body):
            t = re.sub(r"^Model(?=[A-Z0-9])", "", t.strip().rstrip(".:"))
            if t.endswith("-") or re.search(r"-[a-z]{2,}$", t):
                continue                                   # 'LAP-C161-followed', 'LAP-C401S-may', 'LAP-C511S-': prose, not a model
            if (t and TOKEN.fullmatch(t) and re.search(r"\d", t) and re.search(r"[A-Za-z]", t) or (t.isdigit() and 6 <= len(t) <= 11)) \
                    and A.norm(t) != A.norm(own) and A.norm(t) not in seen:
                seen.add(A.norm(t))
                out.append((t, "model_pattern" if re.search(r"[*#]|X{3,}", t) else "declared_same_hardware" if declared else "model_variant"))
    return out, phrases


class EnergyStarAirPurifiers:
    id, version, source_id, categories = ID, VERSION, SOURCE, CATEGORIES

    def __init__(self):
        self.store = C.BlobStore(SOURCE)

    def discover(self, checkpoint, net):
        url = API + "?$limit=50000&$order=pd_id"
        snap, body = C.http_snapshot(self.store, Ref(SOURCE, LIST, url, {}), url, DELAY, ".json", ADAPTER)
        if body is None:
            return Discovery([], False, f"soql {snap.status}", checkpoint or {})
        rows = json.loads(body)
        groups, rejected = {}, 0
        for r in rows:
            cells = model_cells(r.get("model_number"))
            if not cells:
                rejected += 1
            for m, wild in cells:
                k = f"{A.brand_id(r.get('brand_name'))}|{A.norm(m)}"
                g = groups.setdefault(k, {"brand": A.brand_id(r.get("brand_name")), "model": m, "wildcard": wild, "pd_ids": []})
                g["pd_ids"].append(r["pd_id"])
        refs = [Ref(SOURCE, k, url, g) for k, g in sorted(groups.items())]
        return Discovery(refs, True, None, {"rows": len(rows), "refs": len(refs), "rejected_model_cells": rejected})

    def fetch(self, ref, prior, net):
        return A.shared_list_snapshot(self.store, ref, LIST, ADAPTER, ".json")

    def parse(self, snap, blobs, profile):
        pr = ParseResult()
        h = snap.ref.hints or {}
        if snap.ref.key == LIST or not h.get("pd_ids"):
            pr.absences.append({"key": "*", "reason": "dataset list snapshot (per-model refs carry the claims)", "source": "s1"})
            return pr
        allrows = json.loads(blobs.read(snap.snapshot, ".json"))
        rows = [r for r in allrows if r.get("pd_id") in set(h["pd_ids"])]
        us = [r for r in rows if "united states" in (r.get("markets") or "").lower()]
        return parse_rows(snap, h, us, len(rows))


def parse_rows(snap, h, rows, n_all=None):
    pr, obs = ParseResult(), snap.fetched_at
    model = h["model"]
    if not rows:
        pr.absences.append({"key": "*", "reason": "no United States row for this model (Canada-only certification)", "source": "s1"})
        pr.fingerprints = {"model": model, "rows": n_all}
        return pr
    rows = sorted(rows, key=lambda r: (r.get("date_certified") or "", r["pd_id"]), reverse=True)
    r0 = rows[0]
    pr.sources = [{"id": "s1", "url": snap.ref.url, "label": "ENERGY STAR Certified Room Air Cleaners V3.0 (data.energystar.gov gaa3-swy6)",
                   "source_id": SOURCE, "tier": "regulatory", "retrieved_at": obs, "snapshot": snap.snapshot}]
    pr.identifiers.append({"scheme": "mfr_model", "value": model, "value_raw": r0.get("model_number"), "issuer": h["brand"], "market": "US",
                           "package_level": "model", "role": "key", "sources": ["s1"]})
    for r in rows:
        pr.identifiers.append({"scheme": "x_energystar_pd_id", "value": r["pd_id"], "value_raw": r["pd_id"], "issuer": "energystar", "sources": ["s1"]})
        if len(model_cells(r.get("model_number"))) > 1:
            continue                       # a UPC on a record naming several models cannot be attributed to one of them
        for u in re.split(r"[;,\s]+", r.get("upc") or ""):
            d = re.sub(r"\D", "", u)
            if len(d) >= 11:
                pr.identifiers.append({"scheme": "gtin", "value": d.zfill(14), "value_raw": u, "issuer": "GS1", "package_level": "package",
                                       "role": "alias", "sources": ["s1"]})
    if h.get("wildcard"):
        pr.aliases.append({"text": model, "kind": "model_pattern", "source": "s1", "observed_at": obs})
    nm = A.clean(r0.get("model_name"))
    if nm and A.norm(nm) != A.norm(model):
        pr.aliases.append({"text": nm[:80], "kind": "certifier_listing", "source": "s1", "observed_at": obs})
    phrases = []
    for r in rows:
        toks, ph = split_additional(r.get("additional_model_information"), model)
        phrases += ph
        for t, kind in toks:
            if not any(a["text"] == t for a in pr.aliases):
                pr.aliases.append({"text": t[:60], "kind": kind, "source": "s1", "observed_at": obs})
    loc = {"energystar_pd_id": ",".join(r["pd_id"] for r in rows), "date_certified": (r0.get("date_certified") or "")[:10]}

    def field(f, conv=A.num):
        vals = {r.get(f) for r in rows if r.get(f) not in (None, "")}
        if not vals:
            return None, None, False
        raw = f"{f}: {' | '.join(sorted(map(str, vals)))}"
        conv_vals = {conv(v) for v in vals}
        if len(conv_vals) != 1 or None in conv_vals:
            return None, raw, True
        return conv_vals.pop(), raw, False

    def add(key, f, unit=None, cond=None, conv=A.num, value=None):
        v, raw, conflict = field(f, conv)
        if raw is None:
            return
        if conflict:
            pr.claims.append(claim(model, key, None, unit, raw, "s1", ADAPTER, "socrata_json", obs, dict(loc), raw, conditions=cond, status="unknown"))
            return
        if value is not None:
            v = value(v)
            if v is None:
                return
        pr.claims.append(claim(model, key, A.intish(v) if isinstance(v, float) else v, unit, raw, "s1", ADAPTER, "socrata_json", obs, dict(loc),
                               raw, conditions=cond))

    for f, key in FIELDS_CADR:
        add(key, f, "cfm", {"cadr_basis": "energy_star_certified"})
    add("room.size_sqft", "room_size_sq_ft", "ft2", {"room_basis": "energy_star_formula"})
    for f, key in FIELDS_EFF:
        add(key, f, "cfm/W")
    add("pwr.annual_kwh", "annual_energy_use_kwh_yr", "kWh", {"power_basis": "energy_star_16h_active"})
    add("ozone.es_emissions_ppb", "ozone_emissions_ppb", "ppb")
    add("tech.technologies", "technology_types", None, None, conv=lambda s: tuple(sorted({TECH.get(x.strip().lower(), x.strip().lower().replace(" ", "_"))
                                                                                        for x in s.split(",") if x.strip()})),
        value=lambda t: list(t))
    # filters: per slot; never false
    hepa_true = hepa_type = False
    for i in (1, 2, 3, 4):
        v, raw, conflict = field(f"filter_{i}_type", conv=lambda s: s.strip().lower())
        if v is None or conflict:
            continue
        cls = FILTER.get(v)
        stage = {"hepa": "hepa", "hepa_type": "hepa", "activated_carbon": "carbon"}.get(cls, cls or "other")
        if cls:
            pr.claims.append(claim(model, "filter.types", cls, None, raw, "s1", ADAPTER, "socrata_json", obs, dict(loc, slot=i), raw,
                                   conditions={"filter_stage": stage}))
        hepa_true |= cls == "hepa"
        hepa_type |= cls == "hepa_type"
        pn, praw, pconf = field(f"replacement_model_number_{i}", conv=lambda s: A.clean(s))
        if pn and not pconf and re.search(r"\d", pn):
            pr.claims.append(claim(model, "filter.part_number", pn[:60], None, praw, "s1", ADAPTER, "socrata_json", obs, dict(loc, slot=i), praw,
                                   conditions={"filter_stage": stage}))
    if hepa_true:
        q = "filter type: HEPA (dataset definition: True HEPA, >= 99.97% at 0.3 um)"
        pr.claims.append(claim(model, "filter.true_hepa", True, None, q, "s1", ADAPTER, "socrata_json", obs, dict(loc), q))
    if hepa_type or hepa_true:
        pr.claims.append(claim(model, "filter.hepa_class", "hepa" if hepa_true else "hepa_type", None,
                               "filter type: " + ("HEPA" if hepa_true else "HEPA-Type"), "s1", ADAPTER, "socrata_json", obs, dict(loc)))
    add("smart.wifi", "connected_capable", None, None, conv=lambda s: {"yes": True, "no": False}.get(s.strip().lower()),
        value=lambda b: b if isinstance(b, bool) else None)
    v, raw, conflict = field("automatic_mode", conv=lambda s: s.strip())
    if v and not conflict:
        parts = {x.strip().lower() for x in v.split(",")}
        if "air quality sensor" in parts:
            pr.claims.append(claim(model, "feat.auto_mode", True, None, raw, "s1", ADAPTER, "socrata_json", obs, dict(loc), raw))
            pr.claims.append(claim(model, "sensor.air_quality", True, None, raw, "s1", ADAPTER, "socrata_json", obs, dict(loc), raw))
    add("eff.most_efficient", "meets_most_efficient_criteria", None, None, conv=lambda s: {"yes": True, "no": False}.get(s.strip().lower()),
        value=lambda b: b if isinstance(b, bool) else None)
    q = f"ENERGY STAR certified {loc['date_certified']} (Room Air Cleaners V3.0)"
    pr.claims.append(claim(model, "eff.energy_star", True, None, q, "s1", ADAPTER, "socrata_json", obs, dict(loc), q))
    pr.fingerprints = {"raw": snap.snapshot, "model": model, "wildcard_pattern": bool(h.get("wildcard")), "rows": len(rows), "declarations": phrases,
                       "unmapped": {k: r0[k] for k in ("energy_star_partner", "date_available_on_market", "connects_using", "connected_features",
                                                        "energy_star_model_identifier") if r0.get(k) not in (None, "")}}
    return pr


if __name__ == "__main__":
    _run.main(EnergyStarAirPurifiers())
