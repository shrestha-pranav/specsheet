#!/usr/bin/env python3
"""ENERGY STAR major-appliance adapter v1 (contract ARCHITECTURE 15.5), parameterised per Socrata dataset. A2-appl r11.

One class per dataset (one registry SOURCES entry per dataset id), shared code below:
  energystar-refrigerators  p5st-her9  ENERGY STAR Certified Residential Refrigerators   -> category refrigerators
  energystar-dishwashers    q8py-6w3f  ENERGY STAR Certified Residential Dishwashers     -> category dishwashers
Source   : data.energystar.gov (US EPA open data, public domain; data/source-policy.yaml free/paid/licence_grant true). robots.txt allows
           /resource/ with Crawl-delay 1: the shared crawl.Net client honours it (own UA, robots checked per host); DELAY 1.5 s on top.
discover : paged SoQL GETs ($limit PAGE, $offset, $order=pd_id), one stored snapshot per page (ref '_page_NNN', raw JSON as served). Rows
           are grouped per (canonical brand, normalised model_number cell); one ref per group, hints = pd_ids + the page snapshots.
fetch    : no network; a snapshot record per ref pointing at the page blob of its first row (rows of other pages read by hint).
parse    : pure. A1 rulings (research/refrigerators/spec-profile.yaml cert.energy_star traps; team/reports/2026-11-26-a1-r11-appliances.md):
  - PATTERN rows (model_number with '*' or '#', or a trailing 'R/L' hinge alternation) are their OWN entities: key scheme
    x_energystar_model_pattern (never mfr_model, so a pattern never merges with or expands into a concrete SKU), gen.is_pattern = true.
    Their claims carry extractor energystar_appliances_pattern@1 so the claim policy can allow exactly A1's energy-defining key list
    (PATTERN_KEYS) for them; every other value of the row (dims, depth flag, features, connectivity) is still emitted (preview) but no
    policy accepts it. UPCs on a pattern row are covered-UPC lookup aliases (kind covered_upc), never gtin identifiers.
  - Concrete rows: key mfr_model, gen.is_pattern = false. additional_model_information tokens = model_variant aliases (preview evidence
    for the covered_by_certification matcher, scripts/escover.py), never identifiers.
  - DOE test procedure is a condition on kWh / volume / water values (refrigerators appendix_a; dishwashers appendix_c1: ES active rows are
    the procedure of the active specification; C2 not tagged until its mandatory date is confirmed, A1 open item).
  - capacity.adjusted_ft3 is its own key, never capacity.total_ft3. better_than_* / percent_less_* are percents (unit %).
  - refrigerant.type = the R-number only, when the free-text cell names exactly one; charge / GWP digits stay in raw. refrigerant.gwp only
    from an explicit 'GWP' token (refrigerant_with_gwp).
  - Dishwasher width > 30 in (Beko 59.8: centimetres in the inches column) is QUARANTINED: status unknown, raw kept, never converted.
  - Rows without "United States" in markets are dropped; refrigerator rows typed Upright/Chest Freezer belong to `freezers` and are dropped.
  - Several pd_ids for one model string (re-filings): a field on which they disagree is unresolved (status unknown, all values in raw).
  - Absent from ES = unknown: nothing here ever writes cert.energy_star = false.
Usage    : python3 -I crawler/adapters/energystar_appliances.py <refrigerators|dishwashers> discover|fetch|parse|run
"""
import html, json, re, sys, unicodedata
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
import _contract as C
from _contract import Ref, Discovery, ParseResult, claim  # noqa
import _run

ID, VERSION = "energystar_appliances", 1
ADAPTER = f"{ID}@{VERSION}"
PATTERN_EXTRACTOR = f"{ID}_pattern@{VERSION}"
BASE = "https://data.energystar.gov/resource/{}.json"
DELAY = 1.5
PAGE = 1000
STAGE = "socrata_json"
PATTERN_RX = re.compile(r"[*#]|[RL]/[LR]$|x{3,}$")      # '*' / '#' wildcards, trailing R/L hinge alternation, trailing 'xxx' placeholder
DOC_NOTE = re.compile(r"\s*\(\s*[x*]\s*=[^)]*\)\s*$", re.I)    # 'NS-OCF55xxxxxx (x = a-z, A-Z, 0-9, -, blank)': the filing's own note
# Spelling variants only. Sub-brand folding (Cafe / Profile / Monogram -> ge, ...) is a category.yaml brand_aliases decision, not the adapter's.
BRAND_ALIASES = {"fisher&paykel": "fisher_paykel", "fisher & paykel": "fisher_paykel", "fisher and paykel": "fisher_paykel",
                 "black+decker": "black_decker", "black & decker": "black_decker", "jenn-air": "jennair"}
YESNO = {"yes": True, "no": False}


def clean(s):
    return re.sub(r"\s+", " ", html.unescape(str(s or ""))).strip()


def brand_id(raw):
    b = unicodedata.normalize("NFKD", re.sub(r"[™®©]", "", clean(raw))).encode("ascii", "ignore").decode().lower().strip(" .,")   # Café -> cafe
    return BRAND_ALIASES.get(b, re.sub(r"[^a-z0-9]+", "_", b).strip("_"))


def norm(m):
    return re.sub(r"\s+", "", str(m or "")).upper()


def is_pattern(m):
    m = re.sub(r"\s+", "", str(m or ""))
    return bool(PATTERN_RX.search(m.upper()) or re.search(r"x{3,}$", m))


def model_cells(raw):
    """model_number cell -> [model strings]. A cell listing several strings (',' or ';') names each; a trailing '(x = ...)' note is the
    filing's wildcard documentation and is dropped from the string (the string is then a pattern)."""
    t = clean(raw)
    doc = bool(DOC_NOTE.search(t))
    t = DOC_NOTE.sub("", t)
    parts = [clean(x) for x in re.split(r"[;,]", t) if clean(x)] if re.search(r"[;,]", t) else [t]
    out = []
    for m in parts:
        if re.search(r"\d", m) and len(norm(m)) >= 3 and len(m) <= 60:
            out.append((m, doc or is_pattern(m)))
    return out


def num(s):
    m = re.fullmatch(r"\s*(-?\d[\d,]*(?:\.\d+)?)\s*", str(s or ""))
    return float(m.group(1).replace(",", "")) if m else None


def intish(x):
    return int(x) if isinstance(x, float) and x.is_integer() else x


def yesno(s):
    return YESNO.get(clean(s).lower())


def enum_of(table):
    return lambda s: table.get(clean(s).lower())


def date10(s):
    m = re.match(r"(\d{4}-\d{2}-\d{2})", str(s or ""))
    return m.group(1) if m else None


REFRIGERANT = re.compile(r"\bR\s*-?\s*(600a|134a|1234yf|290|513a|744|32|410a|450a|152a)\b", re.I)


def refrigerant_type(s):
    found = {m.group(1).lower() for m in REFRIGERANT.finditer(str(s or ""))}
    return ("r" + found.pop()) if len(found) == 1 else None


def refrigerant_gwp(s):
    vals = {float(m.group(1)) for m in re.finditer(r"GWP\s*[:=]?\s*(\d+(?:\.\d+)?)", str(s or ""), re.I)}
    return intish(vals.pop()) if len(vals) == 1 else None


def dryer_list(s):
    t = {"automatic door release": "auto_door_open", "auto door open": "auto_door_open", "condensation dry": "condensation",
         "condensation": "condensation", "fan-assisted dry": "fan_assisted", "fan assisted dry": "fan_assisted", "heated dry": "heated",
         "mineral dry": "mineral_zeolite", "zeolite": "mineral_zeolite", "air dry": "air", "turbo dry": "turbo"}
    parts = [clean(x).lower() for x in str(s or "").split(",") if clean(x)]
    if not parts:
        return None
    return tuple(sorted({t.get(p, "other") for p in parts}))


# ---------------------------------------------------------------- per-dataset field maps
# (column, key, unit, conv, conditions, quarantine) ; quarantine(v) -> reason or None
TP_FRIDGE = {"test_procedure": "appendix_a"}
TP_DW = {"test_procedure": "appendix_c1"}
FRIDGE_TYPE = {"bottom freezer": "bottom_freezer", "top freezer": "top_freezer", "side-by-side": "side_by_side", "side by side": "side_by_side",
               "all refrigerator": "freezerless_single_door", "freezerless and single door": "freezerless_single_door",
               "compact refrigerator": "compact_refrigerator", "compact cooler": "compact_cooler", "cooler": "cooler"}
FRIDGE_DROP_TYPES = ("upright freezer", "chest freezer")
DEFROST = {"automatic": "automatic", "partial automatic": "partial_automatic", "partial-automatic": "partial_automatic", "manual": "manual"}
COUNTER = {"counter depth": True, "counter-depth": True, "standard depth": False, "standard": False, "yes": True, "no": False}
TUB = {"stainless steel": "stainless", "stainless": "stainless", "plastic": "plastic", "hybrid (plastic & steel)": "hybrid", "hybrid": "hybrid"}
DW_TYPE = {"standard": "standard", "compact": "compact"}
PROTO = {"wi-fi": "wifi", "wifi": "wifi", "bluetooth": "bluetooth", "zigbee": "zigbee", "thread": "thread", "matter": "matter"}


def protocols(s):
    parts = [clean(x).lower() for x in re.split(r"[,;/]", str(s or "")) if clean(x)]
    return tuple(sorted({PROTO.get(p, "other") for p in parts})) if parts else None


FRIDGE_FIELDS = [
    ("type", "config.es_type", None, enum_of(FRIDGE_TYPE), None),
    ("product_class", "config.es_product_class", None, lambda s: clean(s) or None, None),
    ("standard_or_counter_depth", "config.counter_depth", None, enum_of(COUNTER), None),
    ("compact", "config.compact", None, yesno, None),
    ("built_in", "config.built_in", None, yesno, None),
    ("defrost_type", "config.defrost", None, enum_of(DEFROST), None),
    ("width_in", "dims.width_in", "in", num, None),
    ("height_in", "dims.height_in", "in", num, None),
    ("capacity_total_volume_ft3", "capacity.total_ft3", "ft3", num, TP_FRIDGE),
    ("adjusted_volume_ft3", "capacity.adjusted_ft3", "ft3", num, TP_FRIDGE),
    ("annual_energy_use_kwh_yr", "energy.annual_kwh", "kWh/yr", num, TP_FRIDGE),
    ("us_federal_standard_kwh_yr", "energy.federal_standard_kwh", "kWh/yr", num, None),
    ("percent_less_energy_use_than_us_federal_standard", "energy.pct_below_federal", "%", num, None),
    ("meets_most_efficient_criteria", "cert.es_most_efficient", None, yesno, None),
    ("refrigerant_type", "refrigerant.type", None, refrigerant_type, None),
    ("refrigerant_with_gwp", "refrigerant.gwp", None, refrigerant_gwp, None),
    ("ice_maker", "features.ice_maker", None, yesno, None),
    ("thru_the_door_dispenser", "features.dispenser", None, lambda s: "none" if yesno(s) is False else None, None),   # Yes: water vs ice+water not stated
    ("connected_functionality", "conn.connected", None, yesno, None),
    ("connects_using", "conn.protocols", None, protocols, None),
]
DW_FIELDS = [
    ("type", "config.es_type", None, enum_of(DW_TYPE), None),
    ("width_inches", "dims.width_in", "in", num, None),
    ("depth_inches", "dims.depth_in", "in", num, None),
    ("capacity_maximum_number_of_place_settings", "capacity.place_settings", None, num, None),
    ("annual_energy_use_kwh_year", "energy.annual_kwh", "kWh/yr", num, TP_DW),
    ("better_than_us_federal_standard_kwh_year", "energy.pct_below_federal", "%", num, None),
    ("water_use_gallons_cycle", "water.gal_per_cycle", "gal", num, TP_DW),
    ("meets_most_efficient_criteria", "cert.es_most_efficient", None, yesno, None),
    ("tub_material", "features.tub_material", None, enum_of(TUB), None),
    ("drying_method", "features.drying_method", None, dryer_list, None),
    ("soil_sensing_capability", "features.soil_sensor", None, yesno, None),
    ("connected_capable", "conn.connected", None, yesno, None),
]
# A1 transfer lists: the ONLY keys a pattern row may assert (policy allowlist for PATTERN_EXTRACTOR). gen.is_pattern is the row's own flag.
FRIDGE_PATTERN_KEYS = ("cert.energy_star", "cert.es_most_efficient", "cert.es_date", "energy.annual_kwh", "energy.federal_standard_kwh",
                       "energy.pct_below_federal", "capacity.total_ft3", "capacity.adjusted_ft3", "config.es_type", "config.es_product_class",
                       "config.compact", "config.built_in", "refrigerant.type", "gen.is_pattern")
DW_PATTERN_KEYS = ("cert.energy_star", "cert.es_most_efficient", "cert.es_date", "energy.annual_kwh", "energy.pct_below_federal",
                   "water.gal_per_cycle", "capacity.place_settings", "config.es_type", "features.soil_sensor", "features.drying_method",
                   "gen.is_pattern")


def dw_width_quarantine(v):
    return "implausible width for inches (> 30 in): centimetres typed into the inches column (Beko 59.8 cm); quarantined, not converted" \
        if v is not None and v > 30 else None


class _EnergyStarAppliance:
    id, version = ID, VERSION
    dataset = label = date_field = None
    fields, pattern_keys, quarantine, drop_types = (), (), {}, ()

    def __init__(self):
        self.store = C.BlobStore(self.source_id)

    @property
    def api(self):
        return BASE.format(self.dataset)

    def discover(self, checkpoint, net):
        rows, pages, off, n = [], [], 0, 0
        while True:
            url = f"{self.api}?$limit={PAGE}&$offset={off}&$order=pd_id"
            key = f"_page_{n:03d}"
            snap, body = C.http_snapshot(self.store, Ref(self.source_id, key, url, {}), url, DELAY, ".json", ADAPTER)
            if body is None:
                return Discovery([], False, f"soql page {n}: {snap.status}", checkpoint or {})
            batch = json.loads(body)
            pages.append({"key": key, "snapshot": snap.snapshot, "rows": len(batch)})
            for r in batch:
                rows.append((r, snap.snapshot))
            if len(batch) < PAGE:
                break
            off += PAGE; n += 1
        groups, rejected = {}, 0
        for r, sha in rows:
            cells = model_cells(r.get("model_number"))
            if not cells:
                rejected += 1
            for m, pat in cells:
                b = brand_id(r.get("brand_name"))
                k = f"{b}|{norm(m)}"
                g = groups.setdefault(k, {"brand": b, "model": m, "pattern": pat, "pd_ids": [], "pages": []})
                g["pattern"] = g["pattern"] or pat
                if len(cells) > 1:
                    g["multi_model_cell"] = True
                g["pd_ids"].append(r["pd_id"])
                if sha not in g["pages"]:
                    g["pages"].append(sha)
        refs = [Ref(self.source_id, k, self.api, g) for k, g in sorted(groups.items())]
        return Discovery(refs, True, None, {"rows": len(rows), "pages": pages, "refs": len(refs), "rejected_model_cells": rejected,
                                             "patterns": sum(1 for g in groups.values() if g["pattern"])})

    def fetch(self, ref, prior, net):
        import time
        now = time.strftime("%FT%TZ", time.gmtime())
        pages = (ref.hints or {}).get("pages") or []
        recs = {r["snapshot"]: r for r in self.store.snapshots() if r.get("status") == 200 and str(r.get("ref", "")).startswith("_page_")}
        rec = recs.get(pages[0]) if pages else None
        if rec is None:
            s = C.Snapshot("sha256:", ref, "no_page_snapshot", now, ref.url, {})
        else:
            s = C.Snapshot(rec["snapshot"], ref, 200, rec["fetched_at"], rec["final_url"], {"etag": rec.get("etag"), "last_modified": rec.get("last_modified")})
        self.store.append(s, ADAPTER, ".json")
        return s

    def parse(self, snap, blobs, profile):
        pr = ParseResult()
        h = snap.ref.hints or {}
        if snap.ref.key.startswith("_page_") or not h.get("pd_ids"):
            pr.absences.append({"key": "*", "reason": "dataset page snapshot (per-model refs carry the claims)", "source": "s1"})
            return pr
        want, rows = set(h["pd_ids"]), []
        for sha in h.get("pages") or [snap.snapshot]:
            rows += [r for r in json.loads(blobs.read(sha, ".json")) if r.get("pd_id") in want]
        return self.parse_rows(snap, h, rows)

    def parse_rows(self, snap, h, rows):
        pr, obs = ParseResult(), snap.fetched_at
        model, pattern = h["model"], bool(h.get("pattern"))
        us = [r for r in rows if "united states" in (r.get("markets") or "").lower()]
        dropped = [r for r in us if clean(r.get("type")).lower() in self.drop_types]
        us = [r for r in us if r not in dropped]
        if not us:
            reason = "row types belong to another category (freezers)" if dropped else "no United States row (Canada-only certification)"
            pr.absences.append({"key": "*", "reason": reason, "source": "s1"})
            pr.fingerprints = {"model": model, "rows": len(rows), "dropped_other_category": len(dropped)}
            return pr
        us.sort(key=lambda r: (r.get(self.date_field) or "", r["pd_id"]), reverse=True)
        r0 = us[0]
        pr.sources = [{"id": "s1", "url": snap.ref.url, "label": f"{self.label} (data.energystar.gov {self.dataset})", "source_id": self.source_id,
                       "tier": "regulatory", "retrieved_at": obs, "snapshot": snap.snapshot}]
        pr.identifiers.append({"scheme": "x_energystar_model_pattern" if pattern else "mfr_model", "value": model, "value_raw": model,
                               "issuer": h["brand"], "market": "US", "package_level": "model", "role": "key", "sources": ["s1"]})
        for r in us:
            pr.identifiers.append({"scheme": "x_energystar_pd_id", "value": r["pd_id"], "value_raw": r["pd_id"], "issuer": "energystar", "sources": ["s1"]})
            if len(model_cells(r.get("model_number"))) > 1:
                continue                   # a UPC on a row naming several models cannot be attributed to one of them
            for u in re.split(r"[;,\s]+", r.get("upc") or ""):
                d = re.sub(r"\D", "", u)
                if len(d) < 11:
                    continue
                if pattern:      # one UPC = one concrete unit: on a pattern row it is a scan -> row lookup alias only
                    pr.aliases.append({"text": d, "kind": "covered_upc", "source": "s1", "observed_at": obs})
                else:
                    pr.identifiers.append({"scheme": "gtin", "value": d.zfill(14), "value_raw": u, "issuer": "GS1", "package_level": "package",
                                           "role": "alias", "sources": ["s1"]})
        if pattern:
            pr.aliases.append({"text": model, "kind": "model_pattern", "source": "s1", "observed_at": obs})
        nm = clean(r0.get("model_name"))
        if nm and norm(nm) != norm(model):
            pr.aliases.append({"text": nm[:80], "kind": "certifier_listing", "source": "s1", "observed_at": obs})
        covered = []
        for r in us:
            for t in re.split(r"[,;\s]+", clean(r.get("additional_model_information"))):
                t = t.strip(".:()")
                if 4 <= len(t) <= 40 and re.search(r"\d", t) and re.search(r"[A-Za-z]", t) and re.fullmatch(r"[A-Za-z0-9*#/._+-]+", t) \
                        and norm(t) != norm(model) and norm(t) not in covered:
                    covered.append(norm(t))
                    pr.aliases.append({"text": t, "kind": "model_pattern" if is_pattern(t) else "model_variant", "source": "s1", "observed_at": obs})
        loc = {"energystar_pd_id": ",".join(r["pd_id"] for r in us), "date_certified": date10(r0.get(self.date_field))}
        ext = PATTERN_EXTRACTOR if pattern else ADAPTER

        def emit(key, value, unit, raw, cond=None, status="known"):
            pr.claims.append(claim(model, key, value, unit, raw, "s1", ext, STAGE, obs, dict(loc), raw, conditions=cond, status=status))

        for col, key, unit, conv, cond in self.fields:
            vals = {clean(r.get(col)) for r in us if clean(r.get(col))}
            if not vals:
                continue                                    # blank = unknown: no claim
            raw = f"{col}: {' | '.join(sorted(vals))}"
            conv_vals = {conv(v) for v in vals}
            if len(conv_vals) != 1 or None in conv_vals:
                emit(key, None, unit, raw, cond, status="unknown")
                continue
            v = conv_vals.pop()
            q = self.quarantine.get(key)
            if q and q(v):
                emit(key, None, unit, f"{raw} [{q(v)}]", cond, status="unknown")
                continue
            if isinstance(v, tuple):
                v = list(v)
            emit(key, intish(v) if isinstance(v, float) else v, unit, raw, cond)
        emit("gen.is_pattern", pattern, None, f"model_number: {r0.get('model_number')}" + (" (certified pattern: * # or R/L)" if pattern else ""))
        d = loc["date_certified"]
        emit("cert.es_date", d, None, f"{self.date_field}: {d}") if d else None
        q = f"ENERGY STAR certified {d or '(undated)'} ({self.label}, pd_id {loc['energystar_pd_id']})"
        emit("cert.energy_star", True, None, q)
        pr.fingerprints = {"raw": snap.snapshot, "model": model, "model_cell": r0.get("model_number"), "es_pattern": pattern, "rows": len(us), "covered_tokens": covered,
                           "unmapped": {k: r0[k] for k in ("energy_star_partner", "date_available_on_market", "additional_model_information",
                                                            "energy_star_model_identifier") if r0.get(k) not in (None, "")}}
        if pattern:
            pr.fingerprints["non_transfer_keys"] = sorted({c["key"] for c in pr.claims} - set(self.pattern_keys))
        return pr


class EnergyStarRefrigerators(_EnergyStarAppliance):
    source_id, categories = "energystar-refrigerators", {"refrigerators"}
    dataset, label, date_field = "p5st-her9", "ENERGY STAR Certified Residential Refrigerators", "date_qualified"
    fields, pattern_keys, drop_types = FRIDGE_FIELDS, FRIDGE_PATTERN_KEYS, FRIDGE_DROP_TYPES


class EnergyStarDishwashers(_EnergyStarAppliance):
    source_id, categories = "energystar-dishwashers", {"dishwashers"}
    dataset, label, date_field = "q8py-6w3f", "ENERGY STAR Certified Residential Dishwashers", "date_certified"
    fields, pattern_keys = DW_FIELDS, DW_PATTERN_KEYS
    quarantine = {"dims.width_in": dw_width_quarantine}


CLASSES = {"refrigerators": EnergyStarRefrigerators, "dishwashers": EnergyStarDishwashers}

if __name__ == "__main__":
    cat = sys.argv.pop(1) if len(sys.argv) > 1 and sys.argv[1] in CLASSES else None
    if cat is None:
        raise SystemExit("usage: energystar_appliances.py <refrigerators|dishwashers> discover|fetch|parse|run")
    _run.main(CLASSES[cat]())
