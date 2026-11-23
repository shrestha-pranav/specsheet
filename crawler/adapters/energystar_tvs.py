#!/usr/bin/env python3
"""ENERGY STAR Certified Televisions adapter v1 (contract ARCHITECTURE 15.5), category tvs. Cross-brand model-number seed.

Source   : data.energystar.gov Socrata dataset pd96-rr3d (official US EPA open data; robots Crawl-delay 1; no key). Same pattern as
           energystar_monitors.py (qbg3-d468). The dataset holds only CURRENTLY certified TVs (175 rows on 2026-11-23).
discover : one SoQL group-by -> one Ref per (brand_name, model_number).
fetch    : one SoQL GET per model (all certification rows for it) -> JSON blob.
parse    : pure. Latest row wins. Identifiers: mfr_model (certified string; '(01)'-style trailing version tag kept in value_raw), gtin per `upc`
           (several, ';'-separated), x_energystar_pd_id. A model_number with '*'/'#' is a WILDCARD FAMILY (LG certifies 'OLED65C5***' =
           "may be any alphanumeric according to color of stand or enclosure"): fingerprints.wildcard_pattern -> the importer skips it, it never
           names a product (identity.md).
           additional_model_information is split into tokens. Tokens the partner declares identical ('Same as basic model except model
           designation', 'X is the same as Y except for model designation') become aliases kind=declared_same_hardware - this is the
           maker's own statement in a regulatory filing and the ONLY corroboration identity.md accepts for grouping a retailer designation
           (QN65S92FAF, OLED65C4AU*) with a base model. Undeclared tokens are kind=model_variant (unverified sibling).
claims   : power figures carry their basis in conditions (power_basis = energy_star_on_mode | doe_federal_test; standby_network). The
           certification limit (maximum_on_mode_power_for_certification_watts) is a programme threshold, not a product fact: never a claim.
           Native resolution is accepted only when horizontal > vertical (one RCA row is swapped: 2160 x 3840 -> absence, never re-ordered).
Usage    : python3 -I crawler/adapters/energystar_tvs.py discover|fetch|parse|run [--limit N] [--match REGEX]
"""
import json, re, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
import _contract as C
from _contract import Ref, Discovery, ParseResult, claim  # noqa
import _run

ID, VERSION, SOURCE = "energystar_tvs", 1, "energystar-tvs"
CATEGORIES = {"tvs"}
API = "https://data.energystar.gov/resource/pd96-rr3d.json"
ADAPTER = f"{ID}@{VERSION}"
DELAY = 1.0
DISPLAY = {"LCD": "lcd", "QD-LED (QLED)": "lcd", "OLED": "oled"}
BACKLIGHT = {"Direct-lit LED": "direct_led", "Edge-lit LED": "edge_led", "OLED": "self_emissive"}
TOKEN = re.compile(r"[A-Za-z0-9][A-Za-z0-9._/+*#-]{2,40}")
SAME = re.compile(r"same as (the )?basic model except|is the same as .{2,40} except for model", re.I)


def _q(**kw):
    from urllib.parse import urlencode
    return API + "?" + urlencode(kw)


def _flt(s):
    try:
        return float(str(s).replace(",", ""))
    except (TypeError, ValueError):
        return None


def issuer_of(brand):
    return re.sub(r"[.\s]+$", "", (brand or "").strip()).lower()


def split_additional(txt, model):
    """-> [(token, kind)] in order, plus the declaration phrases found. A token is 'declared' when the clause it sits in (text up to the next
    ';') carries a same-hardware statement. Clauses without one give plain model_variant tokens."""
    out, phrases = [], []
    for clause in re.split(r";", txt or ""):
        declared = bool(SAME.search(clause))
        if declared:
            phrases.append(SAME.search(clause).group(0))
        body = re.sub(r"\(\*=[^)]*\)|\*\s*may be any.*$|same as.*$|is the same as.*$", " ", clause, flags=re.I)
        for t in re.split(r"[,\s]+", body):
            t = t.strip().rstrip(".")
            if t and TOKEN.fullmatch(t) and re.search(r"\d", t) and re.search(r"[A-Za-z]", t) and t.upper() != model.upper():
                if (t, "x") not in [(a, "x") for a, _ in out]:
                    out.append((t, "declared_same_hardware" if declared else "model_variant"))
    return out, phrases


class EnergyStarTvs:
    id, version, source_id, categories = ID, VERSION, SOURCE, CATEGORIES

    def __init__(self):
        self.store = C.BlobStore(SOURCE)

    def discover(self, checkpoint, net):
        url = _q(**{"$select": "brand_name,model_number,count(*) as n,max(date_qualified) as last", "$group": "brand_name,model_number",
                    "$order": "brand_name,model_number", "$limit": 20000})
        r = net.get(url, DELAY)
        if not hasattr(r, "status_code") or r.status_code != 200:
            return Discovery([], False, f"soql {getattr(r, 'status_code', r)}", checkpoint or {})
        rows = r.json()
        refs = [Ref(SOURCE, f"{x['brand_name']}|{x['model_number']}", API, {"brand": x["brand_name"], "model": x["model_number"],
                    "cert_rows": int(x["n"]), "last_certified": (x.get("last") or "")[:10]}) for x in rows if x.get("model_number")]
        return Discovery(refs, True, None, {"models": len(refs)})

    def fetch(self, ref, prior, net):
        h = ref.hints
        esc = lambda s: s.replace("'", "''")
        url = _q(**{"$where": f"brand_name='{esc(h['brand'])}' AND model_number='{esc(h['model'])}'", "$order": "date_qualified DESC"})
        snap, _ = C.http_snapshot(self.store, ref, url, DELAY, ".json", ADAPTER)
        return snap

    def parse(self, snap, blobs, profile):
        rows = json.loads(blobs.read(snap.snapshot, ".json"))
        pr = ParseResult()
        if not rows:
            pr.absences.append({"key": "*", "reason": "no rows returned", "source": "s1"})
            return pr
        rows.sort(key=lambda r: r.get("date_qualified", ""), reverse=True)
        r0, obs = rows[0], snap.fetched_at
        raw_model = r0["model_number"].strip()
        pattern = bool(re.search(r"[*#]", raw_model))
        model = re.sub(r"\s*\(\d{1,3}\)\s*$", "", raw_model).strip()[:40]        # Hisense '100U77SUA(01)': version tag kept in value_raw
        iss = issuer_of(r0.get("brand_name"))
        pr.sources = [{"id": "s1", "url": snap.ref.url, "label": "ENERGY STAR Certified Televisions (data.energystar.gov pd96-rr3d)",
                       "source_id": "energystar-televisions", "tier": "regulatory", "retrieved_at": obs, "snapshot": snap.snapshot}]
        pr.identifiers.append({"scheme": "mfr_model", "value": model, "value_raw": raw_model, "issuer": iss, "market": "US",
                               "package_level": "model", "role": "key", "sources": ["s1"]})
        seen = set()
        for r in rows:
            for u in re.split(r"[;,\s]+", r.get("upc") or ""):
                d = re.sub(r"\D", "", u)
                if d and d.zfill(14) not in seen:
                    seen.add(d.zfill(14))
                    pr.identifiers.append({"scheme": "gtin", "value": d.zfill(14), "value_raw": u, "issuer": "GS1", "package_level": "package",
                                           "role": "alias", "sources": ["s1"]})
        pr.identifiers.append({"scheme": "x_energystar_pd_id", "value": r0["pd_id"], "value_raw": r0["pd_id"], "issuer": "energystar", "sources": ["s1"]})
        if pattern:
            pr.aliases.append({"text": raw_model, "kind": "model_pattern", "source": "s1", "observed_at": obs})
        if r0.get("model_name") and r0["model_name"].strip().upper() not in (model.upper(), raw_model.upper()):
            pr.aliases.append({"text": r0["model_name"].strip(), "kind": "marketing_name", "source": "s1", "observed_at": obs})
        toks, phrases = split_additional(r0.get("additional_model_information"), model)
        for t, kind in toks:
            pr.aliases.append({"text": t[:60], "kind": "model_pattern" if re.search(r"[*#]", t) else kind, "source": "s1", "observed_at": obs})
        loc = {"energystar_pd_id": r0["pd_id"], "date_qualified": (r0.get("date_qualified") or "")[:10]}
        mapped = set()

        def add(key, value, unit, field, cond=None):
            raw = f"{field}: {r0.get(field)}"
            pr.claims.append(claim(model, key, value, unit, raw, "s1", ADAPTER, "socrata_json", obs, dict(loc), raw, conditions=cond))
            mapped.add(field)

        f = "diagonal_viewable_screen_size_inches"
        if _flt(r0.get(f)):
            add("gen.viewable_diag", _flt(r0[f]), "in", f)
        h, v = _flt(r0.get("native_horizontal_resolution_pixels")), _flt(r0.get("native_vertical_resolution_pixels"))
        if h and v and h > v and h == int(h) and v == int(v):
            add("res.native", f"{int(h)}x{int(v)}", None, "native_horizontal_resolution_pixels")
            add("res.width_px", int(h), "px", "native_horizontal_resolution_pixels"); add("res.height_px", int(v), "px", "native_vertical_resolution_pixels")
        elif h and v:
            pr.absences.append({"key": "res.native", "reason": f"ES row lists horizontal {h:g} < vertical {v:g} (swapped?); not re-ordered", "source": "s1"})
        if (dt := DISPLAY.get(r0.get("display_type"))):
            add("panel.display_tech", dt, None, "display_type")
            if r0["display_type"] == "QD-LED (QLED)":
                add("panel.quantum_dot", True, None, "display_type")
        if (bl := BACKLIGHT.get(r0.get("backlight_technology_type"))) and (bl == "self_emissive") == (r0.get("display_type") == "OLED"):
            add("panel.backlight", bl, None, "backlight_technology_type")
        f = "power_consumption_in_on_mode_watts"
        if _flt(r0.get(f)) is not None:
            add("pwr.on_mode_w", _flt(r0[f]), "W", f, {"power_basis": "energy_star_on_mode"})
        f = "reported_on_mode_power_per_the_federal_test_procedure_watts"
        if _flt(r0.get(f)) is not None:
            add("pwr.on_mode_doe_w", _flt(r0[f]), "W", f, {"power_basis": "doe_federal_test"})
        f = "reported_annual_energy_consumption_kwh"
        if _flt(r0.get(f)) is not None:
            add("pwr.annual_kwh", _flt(r0[f]), "kWh", f, {"power_basis": "doe_federal_test"})
        for f, net in (("power_consumption_in_standby_mode_when_network_not_connected_watts", "not_connected"),
                       ("power_consumption_in_standby_mode_when_network_connected_watts", "connected")):
            if _flt(r0.get(f)) is not None:
                add("pwr.standby_w", _flt(r0[f]), "W", f, {"power_basis": "energy_star_standby", "standby_network": net})
        if r0.get("automatic_brightness_control") in ("Yes", "No"):
            add("pic.auto_brightness", r0["automatic_brightness_control"] == "Yes", None, "automatic_brightness_control")
        pr.claims.append(claim(model, "pwr.energy_star", True, None, f"ENERGY STAR certified {loc['date_qualified']}", "s1", ADAPTER, "socrata_json",
                               obs, dict(loc), f"ENERGY STAR certified {loc['date_qualified']}"))
        unmapped = {k: r0[k] for k in ("product_type", "application", "resolution_format", "high_contrast_ratio_hcr_display", "physical_data_ports_available",
                                       "ethernet_supported", "features", "maximum_on_mode_power_for_certification_watts", "date_available_on_market",
                                       "markets", "energy_star_partner", "screen_area_square_inches", "reported_standby_active_low_mode_power_watts",
                                       "low_power_wireless_technologies_supported") if r0.get(k) not in (None, "")}
        pr.fingerprints = {"raw": snap.snapshot, "cert_rows": len(rows), "model": model, "wildcard_pattern": pattern, "unmapped": unmapped,
                           "declarations": phrases, "note": "maximum_on_mode_power_for_certification_watts is the programme limit, not a product value"}
        return pr


if __name__ == "__main__":
    _run.main(EnergyStarTvs())
