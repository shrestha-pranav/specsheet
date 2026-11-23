#!/usr/bin/env python3
"""ENERGY STAR Certified Displays adapter v1 (contract ARCHITECTURE 15.5), category monitors. Cross-brand model-number seed.

Source   : data.energystar.gov Socrata dataset qbg3-d468 (official US EPA/DOE open data; robots Crawl-delay 1; no key needed).
discover : one SoQL group-by -> one Ref per (brand_name, model_number) with display_type='Monitor' (signage excluded).
fetch    : one SoQL GET per model (all certification rows for it; a model is re-certified several times) -> JSON blob.
parse    : pure. Latest certification row wins per field; identifiers mfr_model (+gtin when `upc` present, + x_energystar_pd_id);
           claims keyed to research/monitors/spec-profile.yaml; ES-only fields (HDR flag, color spaces, USB-C PD yes/no,
           interfaces) are kept raw in fingerprints.unmapped, never coerced.
Caveat   : model_number is the maker's *certified* model string (Dell 'E2026Hf' = factory suffix variant); region/colour
           suffixes are often stripped or merged in additional_model_information (alias list). Not an orderable SKU.
Usage    : python3 -I crawler/adapters/energystar_monitors.py discover|fetch|parse|run [--limit N] [--match REGEX]
"""
import json, re, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
import _contract as C
from _contract import Ref, Discovery, ParseResult, claim  # noqa
import _run

ID, VERSION, SOURCE = "energystar_monitors", 1, "energystar-monitors"
CATEGORIES = {"monitors"}
API = "https://data.energystar.gov/resource/qbg3-d468.json"
ADAPTER = f"{ID}@{VERSION}"
DELAY = 1.0
PANEL = {"TN LCD": "TN", "IPS LCD": "IPS", "VA LCD": "VA", "TN": "TN", "IPS": "IPS", "VA": "VA"}


def _q(**kw):
    from urllib.parse import urlencode
    return API + "?" + urlencode(kw)


def _flt(s):
    try:
        return float(str(s).replace(",", ""))
    except (TypeError, ValueError):
        return None


class EnergyStarMonitors:
    id, version, source_id, categories = ID, VERSION, SOURCE, CATEGORIES

    def __init__(self):
        self.store = C.BlobStore(SOURCE)

    def discover(self, checkpoint, net):
        url = _q(**{"$select": "brand_name,model_number,count(*) as n,max(date_certified) as last",
                    "$where": "display_type='Monitor'", "$group": "brand_name,model_number", "$order": "brand_name,model_number", "$limit": 20000})
        r = net.get(url, DELAY)
        if not hasattr(r, "status_code") or r.status_code != 200:
            return Discovery([], False, f"soql {getattr(r, 'status_code', r)}", checkpoint or {})
        rows = r.json()
        refs = [Ref(SOURCE, f"{x['brand_name']}|{x['model_number']}",
                    _q(**{"$where": f"display_type='Monitor' AND brand_name='{x['brand_name']}' AND model_number='{x['model_number']}'"}),
                    {"brand": x["brand_name"], "model": x["model_number"], "cert_rows": int(x["n"]), "last_certified": x["last"][:10]})
                for x in rows if x.get("model_number")]
        return Discovery(refs, True, None, {"models": len(refs)})

    def fetch(self, ref, prior, net):
        h = ref.hints
        esc = lambda s: s.replace("'", "''")
        url = _q(**{"$where": f"display_type='Monitor' AND brand_name='{esc(h['brand'])}' AND model_number='{esc(h['model'])}'",
                    "$order": "date_certified DESC"})
        snap, _ = C.http_snapshot(self.store, ref, url, DELAY, ".json", ADAPTER)
        return snap

    def parse(self, snap, blobs, profile):
        rows = json.loads(blobs.read(snap.snapshot, ".json"))
        pr = ParseResult()
        if not rows:
            pr.absences.append({"key": "*", "reason": "no rows returned", "source": "s1"})
            return pr
        rows.sort(key=lambda r: r.get("date_certified", ""), reverse=True)
        r0, obs = rows[0], snap.fetched_at
        raw_model = r0["model_number"].strip()
        pattern = bool(re.search(r"[*#]|\(", raw_model))          # partner listed a wildcard family ('S24A40*###  (*=0-9, #=A-Z, blank)')
        parts = [x.strip() for x in re.sub(r"\s*\(.*$", "", raw_model).split(",") if x.strip()]   # some partners list 'A, B, C' in one cell
        model = (parts[0].split()[0] if pattern and parts else parts[0] if parts else raw_model)[:40]
        extra = [x for x in parts[1:] if x.upper() != model.upper() and re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._/+*#-]{2,40}", x)]
        pr.sources = [{"id": "s1", "url": snap.ref.url, "label": "ENERGY STAR Certified Displays (data.energystar.gov qbg3-d468)",
                       "source_id": "energystar-displays", "tier": "regulatory", "retrieved_at": obs, "snapshot": snap.snapshot}]
        pr.identifiers.append({"scheme": "mfr_model", "value": model, "value_raw": raw_model, "issuer": r0.get("brand_name", "").lower(), "market": "US",
                               "package_level": "model", "role": "key", "sources": ["s1"]})
        for r in rows:
            u = re.sub(r"\D", "", r.get("upc") or "")
            if u and not any(i["scheme"] == "gtin" and i["value"] == u.zfill(14) for i in pr.identifiers):
                pr.identifiers.append({"scheme": "gtin", "value": u.zfill(14), "value_raw": r["upc"], "issuer": "GS1", "package_level": "package", "role": "alias", "sources": ["s1"]})
        if pattern:
            pr.aliases.append({"text": raw_model, "kind": "model_pattern", "source": "s1", "observed_at": obs})
        pr.identifiers.append({"scheme": "x_energystar_pd_id", "value": r0["pd_id"], "value_raw": r0["pd_id"], "issuer": "energystar", "sources": ["s1"]})
        if r0.get("model_name") and r0["model_name"].strip().upper() != model.upper():
            pr.aliases.append({"text": r0["model_name"].strip(), "kind": "marketing_name", "source": "s1", "observed_at": obs})
        for a in extra:
            pr.aliases.append({"text": a[:60], "kind": "model_variant", "source": "s1", "observed_at": obs})
        for a in (r0.get("additional_model_information") or "").split(","):
            a = a.strip()
            if a and a.upper() != model.upper() and re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._/+*#-]{2,40}", a):
                pr.aliases.append({"text": a, "kind": "model_variant", "source": "s1", "observed_at": obs})
        loc = {"energystar_pd_id": r0["pd_id"], "date_certified": r0.get("date_certified", "")[:10]}

        def add(key, value, unit, raw):
            pr.claims.append(claim(model, key, value, unit, str(raw), "s1", ADAPTER, "socrata_json", obs, dict(loc), f"{key} <- {raw}"))

        mapped = set()
        def has(f):
            v = r0.get(f)
            if v not in (None, "", "N/A", "None"):
                mapped.add(f)
                return v
        if (v := has("panel_type")):
            if v in PANEL:
                add("panel.technology", PANEL[v], None, v)
            else:
                mapped.discard("panel_type")
        if (v := has("native_resolution_pixels")):
            add("res.native", v.replace(" ", ""), None, v)
            m = re.fullmatch(r"(\d+)\s*x\s*(\d+)", v)
            if m:
                add("res.width_px", int(m[1]), "px", v); add("res.height_px", int(m[2]), "px", v)
        if (v := has("screen_size_inches")) and _flt(v):
            add("gen.viewable_diag", _flt(v), "in", v)
        if (v := has("maximum_luminance_candelas")) and _flt(v):
            add("hdr.sdr_typ", _flt(v), "nit", v)       # ES 'maximum luminance' as reported by the maker (SDR); basis typ/min unstated
        if (v := has("display_contrast_ratio_at")) and _flt(v) and _flt(v) >= 100:   # values 1-8 are not contrast ratios (field reused by some partners)
            add("hdr.contrast_static", f"{int(_flt(v))}:1", None, v)
        if (v := has("on_mode_power_watts")) and _flt(v) is not None:
            add("pwr.typical", _flt(v), "W", v)          # measured on-mode power per ES test, not nameplate
        if (v := has("sleep_mode_power_watts")) and _flt(v) is not None:
            add("pwr.standby", _flt(v), "W", v)
        if (v := has("power_source")):
            add("pwr.external_adapter", "external" in v.lower(), None, v) if re.search(r"internal|external", v, re.I) else None
        add("pwr.energy_star", True, None, f"ENERGY STAR certified {loc['date_certified']}")
        if (v := r0.get("date_available_on_market")):
            add("gen.release_year", int(v[:4]), None, v)
        unmapped = {k: r0[k] for k in ("high_dynamic_range_hdr", "color_spaces_supported", "usb_c_with_power_delivery", "signal_or_data_interfaces",
                                       "model_features", "enhanced_performance_display", "monitor_total_energy", "off_mode_power_watts",
                                       "screen_area_square_inches", "markets", "energy_star_partner") if r0.get(k) not in (None, "")}
        pr.fingerprints = {"raw": snap.snapshot, "cert_rows": len(rows), "model": model, "wildcard_pattern": pattern, "unmapped": unmapped,
                           "note": "ES HDR/color/USB-C fields are yes/no or generic; not VESA tiers or PD wattage"}
        return pr


if __name__ == "__main__":
    _run.main(EnergyStarMonitors())
