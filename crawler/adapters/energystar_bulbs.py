#!/usr/bin/env python3
"""ENERGY STAR Connected Light Bulbs (A2-bulb r12, owner request): data.energystar.gov msj5-kqfv -> category light-bulbs.

Dataset state (checked 2026-11-26 through the Socrata catalog + view metadata, crawler UA): the ENERGY STAR Lamps (light bulbs) programme has
SUNSET; the catalog no longer carries a "Certified Light Bulbs" dataset, only this frozen "Connected Light Bulbs" one (rowsUpdatedAt
2025-01-15, V2.0/V2.1 lamps spec, 465 rows, every row connected_lamp = Yes). So every row is a SMART bulb, certification dates are 2016-2023,
and cert.energy_star here means "was certified under the (now ended) lamps programme", never a current listing. Licence: EPA open data,
public domain (data/source-policy.yaml data.energystar.gov).

Shared code: discover / fetch come from crawler/adapters/energystar_appliances.py unchanged (paged SoQL through crawl.Net, own UA, robots +
Crawl-delay per hop, DELAY 1.5 s, one stored snapshot per page, one ref per (brand, model_number)), rebound to this module's parser id the way
energystar_siblings.py does. parse_rows is this module's own (bulb rules below).

Rules (research/light-bulbs/spec-profile.yaml traps):
  - US rows only (markets contains "United States"); Canada-only filings dropped.
  - Pattern rows (model_number with * or #: Globe 34208*, Nanoleaf NL67E1##) are NOT entities this round: fingerprint wildcard_pattern, the
    importer counts them as skipped_wildcard_pattern (no lamp pattern-coverage ruling exists yet; 14 of 373 US rows).
  - light.lumens = the certified light output (LM-79) of the filing, tested at the filing's CCT: condition cct_k (a BASIS condition: two
    figures at different CCTs are never compared or merged). ENERGY STAR tests a colour bulb in WHITE: nothing here ever writes
    light.lumens_color_max.
  - power.equiv_watts is the marketing "replaces a 60 W bulb" class, its own key, never a brightness value.
  - light.efficacy_lm_w is ENERGY STAR's own column (same filing's lumens / watts), not derived here.
  - smart.color only POSITIVE from special_features: Full-Color-Tunable -> full_color, else White-Tunable -> tunable_white. A row without
    either flag says nothing (WiZ 9290024493A is a colour bulb whose row omits the flag), so no claim, never "none".
  - ctl.dimmable true from 'Dimmable', false only from an explicit 'Non-Dimmable'; blank = unknown.
  - smart.protocols from the connected-protocol column (Wi-Fi / Bluetooth / Zigbee / Other); ENERGY STAR has no Matter or Thread value.
  - Several US filings of one model string: a field on which they disagree is unresolved (status unknown, all values in raw).
  - A model cell the shared splitter cut inside parentheses (CL-SMRT-A19-10W-2757(WIFI,T20)) mints nothing.
  - Pack SKUs (GE CLEDA199CD1-2P / -4P, Philips 12NC sub-codes) in additional_model_information are model_variant aliases, never entities.
Usage    : python3 -I crawler/adapters/energystar_bulbs.py discover|fetch|parse|run
"""
import re, sys, types
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
import energystar_appliances as E
from _contract import ParseResult, claim
import _run

ID, VERSION = "energystar_bulbs", 1
ADAPTER = f"{ID}@{VERSION}"
STAGE = E.STAGE
clean, num, yesno, intish, norm = E.clean, E.num, E.yesno, E.intish, E.norm


def _rebind(fn):
    g = dict(E.__dict__, ADAPTER=ADAPTER, PATTERN_EXTRACTOR=f"{ID}_pattern@{VERSION}")
    return types.FunctionType(fn.__code__, g, fn.__name__, fn.__defaults__, fn.__closure__)


# Spelling variants of one filing brand (ENERGY STAR brand_name typed by hand). Sub-brand folding is category.yaml's decision.
BRANDS = {"feit electroc": "feit_electric", "phillips": "philips", "megalight inc": "megalight", "ge lighting": "ge", "euri lighting": "euri",
          "ledvance llc": "ledvance", "connected max": "connected_max"}


def brand_id(raw):
    b = clean(raw).lower()
    return BRANDS.get(b) or E.brand_id(raw)


def shape(s):
    t = clean(s).upper().replace(" ", "")
    return t.lower() if re.fullmatch(r"[A-Z]{1,4}\d{1,3}[SL]?", t) else None      # A19 BR30 PAR30S PAR30L MR16 G25 B11 ST19 C9; 'ST' alone = unknown


def base(s):
    m = re.match(r"\s*(E\d{2}|GU\d{1,2}|G\d{1,2}|B\d{2}|GX\d{2})\b", clean(s), re.I)
    return m.group(1).lower() if m else None


LAMP_CAT = {"omnidirectional": "omnidirectional", "directional": "directional", "decorative": "decorative"}
PROTO = {"wi-fi": "wifi", "wifi": "wifi", "bluetooth": "bluetooth", "zigbee": "zigbee", "other": "other"}


def protocols(s):
    parts = [clean(x).lower() for x in re.split(r"[,;/]", str(s or "")) if clean(x)]
    return tuple(sorted({PROTO.get(p, "other") for p in parts})) if parts else None


def dimmable(s):
    t = clean(s).lower()
    return True if t == "dimmable" else False if t in ("non-dimmable", "not dimmable", "no") else None


def feats(s):
    return [clean(x).lower() for x in str(s or "").split(",") if clean(x)]


def color(s):
    f = feats(s)
    return "full_color" if "full-color-tunable" in f else "tunable_white" if "white-tunable" in f else None


SPECIAL = {"damp location rated": "damp_rated", "wet location rated": "wet_rated", "recessed fixtures": "recessed_ok",
           "not for use in recessed fixtures": "not_recessed", "not rated for recessed fixtures": "not_recessed", "wireless control": "wireless_control",
           "use with timers": "timers_ok", "use with photo and/or motion sensors": "sensors_ok", "dim to warm": "dim_to_warm",
           "full-color-tunable": "full_color_tunable", "white-tunable": "white_tunable", "three-way": "three_way", "outdoor": "outdoor"}


def special(s):
    f = feats(s)
    return tuple(sorted({SPECIAL.get(x, "other") for x in f})) if f else None


def pos(conv):
    """Only a positive value is a claim (absence of a flag is not 'false')."""
    return lambda s: True if conv(s) is True else None


# (column, key, unit, conv)
FIELDS = [
    ("bulb_type", "form.shape", None, shape),
    ("base_type", "form.base", None, base),
    ("lamp_category", "gen.lamp_category", None, E.enum_of(LAMP_CAT)),
    ("technology", "gen.technology", None, lambda s: clean(s).lower() or None),
    ("brightness_lumens", "light.lumens", "lm", num),
    ("energy_used_watts", "power.watts", "W", num),
    ("wattage_equivalency_watts", "power.equiv_watts", "W", num),
    ("efficacy_lumens_watt", "light.efficacy_lm_w", "lm/W", num),
    ("light_appearance_kelvin", "light.cct_k", "K", num),
    ("color_quality_cri", "light.cri", None, num),
    ("r9", "light.r9", None, num),
    ("beam_angle", "light.beam_angle_deg", "deg", num),
    ("cbcp", "light.cbcp_cd", "cd", num),
    ("dimmable", "ctl.dimmable", None, dimmable),
    ("dims_down_to", "ctl.dims_down_to_pct", "%", num),
    ("three_way", "ctl.three_way", None, yesno),
    ("special_features", "smart.color", None, color),
    ("special_features", "features.es_special", None, special),
    ("connected_lamp", "smart.connected", None, pos(yesno)),
    ("communication_method_connected_protocol", "smart.protocols", None, protocols),
    ("standby_power_consumption_w", "power.standby_w", "W", num),
    ("power_factor", "power.power_factor", None, num),
    ("life_hrs", "life.rated_h", "h", num),
    ("warranty_years", "life.warranty_years", "yr", num),
    ("maximum_overall_length_mm", "form.length_mm", "mm", num),
    ("maximum_overall_diameter_mm", "form.diameter_mm", "mm", num),
    ("lamp_rated_for_enclosed_fixtures", "form.enclosed_rated", None, yesno),
]
CCT_BASIS = ("light.lumens", "light.efficacy_lm_w", "power.watts")     # values the filing's test CCT qualifies


class EnergyStarBulbs(E._EnergyStarAppliance):
    id, version = ID, VERSION
    snapshot_formats = [f"{ID}@*"]
    source_id, categories = "energystar-light-bulbs", {"light-bulbs"}
    dataset, label, date_field = "msj5-kqfv", "ENERGY STAR Connected Light Bulbs (lamps programme sunset; dataset frozen 2025-01-15)", "date_qualified"
    discover = _rebind(E._EnergyStarAppliance.discover)
    fetch = _rebind(E._EnergyStarAppliance.fetch)

    def parse_rows(self, snap, h, rows):
        pr, obs = ParseResult(), snap.fetched_at
        model = h["model"]
        if h.get("pattern"):
            pr.absences.append({"key": "*", "reason": "ENERGY STAR wildcard pattern row (no lamp pattern-coverage ruling): not an entity", "source": "s1"})
            pr.fingerprints = {"model": model, "wildcard_pattern": True}
            return pr
        if model.count("(") != model.count(")"):      # shared model_cells split a parenthesised cell on its comma ('...-2757(WIFI,T20)')
            pr.absences.append({"key": "*", "reason": "model cell split inside parentheses: not a model string", "source": "s1"})
            pr.fingerprints = {"model": model, "split_model_cell": True}
            return pr
        us = [r for r in rows if "united states" in (r.get("markets") or "").lower()]
        if not us:
            pr.absences.append({"key": "*", "reason": "no United States row (Canada-only certification)", "source": "s1"})
            pr.fingerprints = {"model": model, "rows": len(rows)}
            return pr
        us.sort(key=lambda r: (r.get(self.date_field) or "", r["pd_id"]), reverse=True)
        r0 = us[0]
        brand = brand_id(r0.get("brand_name"))
        pr.sources = [{"id": "s1", "url": snap.ref.url, "label": f"{self.label} (data.energystar.gov {self.dataset})", "source_id": self.source_id,
                       "tier": "regulatory", "retrieved_at": obs, "snapshot": snap.snapshot}]
        pr.identifiers.append({"scheme": "mfr_model", "value": model, "value_raw": model, "issuer": brand, "market": "US",
                               "package_level": "model", "role": "key", "sources": ["s1"]})
        for r in us:
            pr.identifiers.append({"scheme": "x_energystar_pd_id", "value": r["pd_id"], "value_raw": r["pd_id"], "issuer": "energystar", "sources": ["s1"]})
        nm = clean(r0.get("model_name"))
        if nm and norm(nm) != norm(model):
            pr.aliases.append({"text": nm[:80], "kind": "certifier_listing", "source": "s1", "observed_at": obs})
        seen = set()
        for r in us:
            for t in re.split(r"[,;\s]+", clean(r.get("additional_model_information"))):
                t = t.strip(".:()")
                if 4 <= len(t) <= 40 and re.search(r"\d", t) and re.fullmatch(r"[A-Za-z0-9/._+-]+", t) and norm(t) != norm(model) and norm(t) not in seen:
                    seen.add(norm(t))
                    pr.aliases.append({"text": t, "kind": "model_variant", "source": "s1", "observed_at": obs})
        loc = {"energystar_pd_id": ",".join(r["pd_id"] for r in us), "date_certified": E.date10(r0.get(self.date_field))}
        ccts = {num(r.get("light_appearance_kelvin")) for r in us} - {None}
        cct_cond = {"cct_k": intish(ccts.pop())} if len(ccts) == 1 else ({"cct_k": sorted(intish(c) for c in ccts)} if ccts else None)

        def emit(key, value, unit, raw, cond=None, status="known"):
            pr.claims.append(claim(model, key, value, unit, raw, "s1", ADAPTER, STAGE, obs, dict(loc), raw, conditions=cond, status=status))

        for col, key, unit, conv in FIELDS:
            vals = {clean(r.get(col)) for r in us if clean(r.get(col))}
            if not vals:
                continue
            raw = f"{col}: {' | '.join(sorted(vals))}"
            cond = cct_cond if key in CCT_BASIS else None
            cv = {conv(v) for v in vals}
            if None in cv and len(cv) == 1:
                continue                                 # nothing positive / parseable stated: no claim (absent = unknown)
            if len(cv) != 1:
                emit(key, None, unit, raw, cond, status="unknown")
                continue
            v = cv.pop()
            emit(key, list(v) if isinstance(v, tuple) else intish(v) if isinstance(v, float) else v, unit, raw, cond)
        d = loc["date_certified"]
        if d:
            emit("cert.es_date", d, None, f"{self.date_field}: {d}")
        emit("cert.energy_star", True, None, f"ENERGY STAR certified {d or '(undated)'} under Lamps V2.0/V2.1 (programme since sunset), pd_id {loc['energystar_pd_id']}")
        pr.fingerprints = {"raw": snap.snapshot, "model": model, "rows": len(us), "brand": brand,
                           "unmapped": {k: r0[k] for k in ("energy_star_partner", "product_finder_bulb_type", "date_available_on_market",
                                                            "energy_star_model_identifier") if r0.get(k) not in (None, "")}}
        return pr


if __name__ == "__main__":
    _run.main(EnergyStarBulbs())
