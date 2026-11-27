#!/usr/bin/env python3
"""ENERGY STAR appliance siblings (A2-appl2 r12): freezers, clothes washers, clothes dryers, built ON crawler/adapters/energystar_appliances.py.

Why a second module instead of more classes in energystar_appliances.py: registry.parser_fingerprint hashes a source's module plus every local
module it imports, and the refrigerators / dishwashers policies (claim/appliances-energystar@2, claim/appliances-es-pattern@2) are approved
against the current energystar_appliances@1 fingerprint. Editing that file would drift both approved policies for no change in their output.
This module imports it unchanged, so any later edit of the shared code still drifts BOTH parsers (it is a dependency of this fingerprint).

Shared code reused verbatim: discover (paged SoQL, own UA via crawl.Net, robots + Crawl-delay per hop, DELAY 1.5 s), fetch (no network), the
whole parse_rows rule set (A1 rulings, team/reports/2026-11-26-a1-r11-appliances.md): pattern rows are their own entities (key scheme
x_energystar_model_pattern, gen.is_pattern, a separate pattern extractor whose policy allows only the energy-defining keys); concrete rows key
mfr_model; US-market rows only; re-filings that disagree on a field leave it unknown; absent from ES = unknown (cert.energy_star only true).
The methods are rebound to this module's parser ids (types.FunctionType over the same code object with ADAPTER / PATTERN_EXTRACTOR replaced),
so claims carry energystar_siblings@1 / energystar_siblings_pattern@1 and the policies pin THIS fingerprint. Snapshots carry the same tag.

  energystar-freezers        8t9c-g3tn  ENERGY STAR Certified Residential Freezers        -> freezers         (DOE 10 CFR 430 App. B)
  energystar-clothes-washers bghd-e2wd  ENERGY STAR Certified Residential Clothes Washers -> clothes-washers  (App. J2; v8.1 spec)
  energystar-clothes-dryers  t9u7-4d2j  ENERGY STAR Certified Residential Clothes Dryers  -> clothes-dryers   (App. D2; v1.1 spec)

Category rules (research/<cat>/spec-profile.yaml traps):
  - washers: volume_cubic_feet is the DOE (Appendix J2) tub volume -> capacity.doe_ft3; maker "IEC" capacity is a different, larger figure
    (capacity.iec_ft3, maker-only). IMEF / IWF / annual kWh / annual gal are J2 metrics (test_procedure appendix_j2). The 2023 DOE rule's new
    Appendix J reports EER / WER instead: different keys, never mixed with J2 values. Rows not "Residential" (intended_market Commercial only)
    are kept and flagged by config.intended_market.
  - dryers: CEF, drum capacity and annual kWh are Appendix D2 figures (test_procedure appendix_d2). D1 CEF (no auto-termination credit) reads
    higher for the same dryer and is never compared. The Most-Efficient "CEF max dry" is its own key (a calculated, not a measured, figure).
  - freezers: like refrigerators (A1 transfer list), procedure appendix_b; adjusted volume = 1.73 x freezer volume (its own key, never capacity).
Usage    : python3 -I crawler/adapters/energystar_siblings.py <freezers|clothes-washers|clothes-dryers> discover|fetch|parse|run
"""
import re, sys, types
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
import energystar_appliances as E
import _run

ID, VERSION = "energystar_siblings", 1
ADAPTER = f"{ID}@{VERSION}"
PATTERN_EXTRACTOR = f"{ID}_pattern@{VERSION}"
clean, num, yesno, enum_of = E.clean, E.num, E.yesno, E.enum_of


def _rebind(fn):
    """Same code object, this module's parser ids: the claims and snapshots name energystar_siblings, not energystar_appliances."""
    g = dict(E.__dict__, ADAPTER=ADAPTER, PATTERN_EXTRACTOR=PATTERN_EXTRACTOR)
    return types.FunctionType(fn.__code__, g, fn.__name__, fn.__defaults__, fn.__closure__)


def flist(table, other="other"):
    """'Steam Cycle,Sanitize Option' -> sorted tuple of enum ids; 'None' -> () (an explicit empty list)."""
    def conv(s):
        parts = [clean(x).lower() for x in str(s or "").split(",") if clean(x)]
        if not parts:
            return None
        if parts == ["none"]:
            return ()
        return tuple(sorted({table.get(p, other) for p in parts}))
    return conv


def protocols(s):
    return E.protocols(s)


# ---------------------------------------------------------------- freezers (8t9c-g3tn)
TP_B = {"test_procedure": "appendix_b"}
FREEZER_TYPE = {"upright freezer": "upright", "chest freezer": "chest", "compact": "compact"}   # ES files compacts as type "Compact"; upright vs chest is in the product class (16/17 upright, 18 chest)
FREEZER_FIELDS = [
    ("type", "config.es_type", None, enum_of(FREEZER_TYPE), None),
    ("product_class", "config.es_product_class", None, lambda s: clean(s) or None, None),
    ("compact", "config.compact", None, yesno, None),
    ("built_in", "config.built_in", None, yesno, None),
    ("defrost_type", "config.defrost", None, enum_of(E.DEFROST), None),
    ("capacity_total_volume_ft3", "capacity.total_ft3", "ft3", num, TP_B),
    ("adjusted_volume_ft3", "capacity.adjusted_ft3", "ft3", num, TP_B),
    ("annual_energy_use_kwh_yr", "energy.annual_kwh", "kWh/yr", num, TP_B),
    ("us_federal_standard_kwh_yr", "energy.federal_standard_kwh", "kWh/yr", num, None),
    ("percent_less_energy_use_than_us_federal_standard", "energy.pct_below_federal", "%", num, None),
    ("meets_most_efficient_criteria", "cert.es_most_efficient", None, yesno, None),
    ("refrigerant_type", "refrigerant.type", None, E.refrigerant_type, None),
    ("refrigerant_with_gwp", "refrigerant.gwp", None, E.refrigerant_gwp, None),
    ("ice_maker", "features.ice_maker", None, yesno, None),
    ("connected_functionality", "conn.connected", None, yesno, None),
]
FREEZER_PATTERN_KEYS = ("cert.energy_star", "cert.es_most_efficient", "cert.es_date", "energy.annual_kwh", "energy.federal_standard_kwh",
                        "energy.pct_below_federal", "capacity.total_ft3", "capacity.adjusted_ft3", "config.es_type", "config.es_product_class",
                        "config.compact", "config.built_in", "config.defrost", "refrigerant.type", "gen.is_pattern")

# ---------------------------------------------------------------- clothes washers (bghd-e2wd)
TP_J2 = {"test_procedure": "appendix_j2"}
LOAD = {"front load": "front", "top load": "top"}
WASHER_SPECIAL = {"combination all-in-one washer/dryer": "all_in_one_washer_dryer", "combination all-in-one washer-dryer": "all_in_one_washer_dryer",
                  "laundry center": "laundry_center"}
MARKET = {"residential": "residential", "commercial": "commercial", "residential, commercial": "both", "commercial, residential": "both",
          "both": "both"}
WASHER_FEATURES = {"steam cycle": "steam", "anti-wrinkle": "anti_wrinkle", "gentle cycle": "gentle", "delayed start": "delay_start",
                   "delay start": "delay_start", "sanitize option": "sanitize", "hand wash cycle": "hand_wash", "drum clean": "drum_clean",
                   "supplementary wash system": "supplementary_wash", "delicates": "delicates", "pre soak": "pre_soak",
                   "impeller": "impeller", "agitator": "agitator"}      # top-load wash action is filed here (Impeller / Agitator), not in a column of its own
WASHER_FIELDS = [
    ("load_configuration", "config.load", None, enum_of(LOAD), None),
    ("special_type", "config.special_type", None, enum_of(WASHER_SPECIAL), None),
    ("intended_market", "config.intended_market", None, enum_of(MARKET), None),
    ("volume_cubic_feet", "capacity.doe_ft3", "ft3", num, TP_J2),
    ("height_inches", "dims.height_in", "in", num, None),
    ("width_inches", "dims.width_in", "in", num, None),
    ("depth_inches", "dims.depth_in", "in", num, None),
    ("integrated_modified_energy_factor_imef", "energy.imef", "ft3/kWh/cycle", num, TP_J2),
    ("us_federal_standard_imef", "energy.federal_standard_imef", "ft3/kWh/cycle", num, TP_J2),
    ("annual_energy_use_kwh_year", "energy.annual_kwh", "kWh/yr", num, TP_J2),
    ("integrated_water_factor_iwf", "water.iwf", "gal/cycle/ft3", num, TP_J2),
    ("us_federal_standard_iwf", "water.federal_standard_iwf", "gal/cycle/ft3", num, TP_J2),
    ("annual_water_use_gallons_year", "water.annual_gal", "gal/yr", num, TP_J2),
    ("additional_washer_features", "features.washer", None, flist(WASHER_FEATURES), None),
    ("meets_most_efficient_criteria", "cert.es_most_efficient", None, yesno, None),
    ("connected", "conn.connected", None, yesno, None),
    ("connects_using", "conn.protocols", None, protocols, None),
]
WASHER_PATTERN_KEYS = ("cert.energy_star", "cert.es_most_efficient", "cert.es_date", "energy.imef", "energy.federal_standard_imef",
                       "energy.annual_kwh", "water.iwf", "water.federal_standard_iwf", "water.annual_gal", "capacity.doe_ft3", "config.load",
                       "config.special_type", "gen.is_pattern")

# ---------------------------------------------------------------- clothes dryers (t9u7-4d2j)
TP_D2 = {"test_procedure": "appendix_d2"}
FUEL = {"electric": "electric", "gas": "gas"}
VENT = {"vented": False, "ventless": True}
HEAT_PUMP = {"heat pump": "heat_pump", "hybrid heat pump": "hybrid_heat_pump", "no": "none", "none": "none", "n/a": "none"}
DRYER_SPECIAL = WASHER_SPECIAL
DRYER_FEATURES = {"drum light": "drum_light", "wrinkle prevention option": "wrinkle_prevention", "steam cycle": "steam",
                  "sanitization cycle": "sanitize", "filter cleaning indicator": "filter_indicator", "energy monitor/indicator": "energy_monitor",
                  "time remaining display": "time_remaining", "supplementary drying system": "supplementary_drying"}


def voltage(s):
    m = re.fullmatch(r"\s*(120|208|240|208/240|208-240|220-240)\s*V?\s*", clean(s), re.I)
    return int(m.group(1)[-3:]) if m else None


DRYER_FIELDS = [
    ("product_type", "config.es_product_type", None, lambda s: clean(s) or None, None),
    ("type", "config.fuel", None, enum_of(FUEL), None),
    ("vented_or_ventless", "config.ventless", None, enum_of(VENT), None),
    ("heat_pump_technology", "config.heat_pump", None, enum_of(HEAT_PUMP), None),
    ("special_type", "config.special_type", None, enum_of(DRYER_SPECIAL), None),
    ("voltage", "elec.voltage", "V", voltage, None),
    ("drum_capacity_cu_ft", "capacity.drum_ft3", "ft3", num, TP_D2),
    ("height_inches", "dims.height_in", "in", num, None),
    ("width_inches", "dims.width_in", "in", num, None),
    ("depth_inches", "dims.depth_in", "in", num, None),
    ("combined_energy_factor_cef", "energy.cef", "lb/kWh", num, TP_D2),
    ("estimated_annual_energy_use_kwh_yr", "energy.annual_kwh", "kWh/yr", num, TP_D2),
    ("estimated_energy_test_cycle_time_min", "energy.test_cycle_min", "min", num, TP_D2),
    ("calculated_combined_energy_factor_max_dryness_setting_lbs_kwh", "energy.cef_max_dry", "lb/kWh", num, None),
    ("additional_dryer_features", "features.dryer", None, flist(DRYER_FEATURES), None),
    ("refrigerant_type", "refrigerant.type", None, E.refrigerant_type, None),
    ("refrigerant_with_gwp", "refrigerant.gwp", None, E.refrigerant_gwp, None),
    ("meets_most_efficient_criteria", "cert.es_most_efficient", None, yesno, None),
    ("connected", "conn.connected", None, yesno, None),
    ("connected_demand_response_functionality_tested", "conn.protocols", None, protocols, None),   # holds 'Wi-Fi': the connects-using column, mislabelled
]
DRYER_PATTERN_KEYS = ("cert.energy_star", "cert.es_most_efficient", "cert.es_date", "energy.cef", "energy.annual_kwh", "energy.test_cycle_min",
                      "energy.cef_max_dry", "capacity.drum_ft3", "config.es_product_type", "config.fuel", "config.ventless", "config.heat_pump",
                      "refrigerant.type", "gen.is_pattern")


class _Sibling(E._EnergyStarAppliance):
    id, version = ID, VERSION
    snapshot_formats = [f"{ID}@*"]
    discover = _rebind(E._EnergyStarAppliance.discover)
    fetch = _rebind(E._EnergyStarAppliance.fetch)
    parse_rows = _rebind(E._EnergyStarAppliance.parse_rows)


class EnergyStarFreezers(_Sibling):
    source_id, categories = "energystar-freezers", {"freezers"}
    dataset, label, date_field = "8t9c-g3tn", "ENERGY STAR Certified Residential Freezers", "date_qualified"
    fields, pattern_keys = FREEZER_FIELDS, FREEZER_PATTERN_KEYS


class EnergyStarClothesWashers(_Sibling):
    source_id, categories = "energystar-clothes-washers", {"clothes-washers"}
    dataset, label, date_field = "bghd-e2wd", "ENERGY STAR Certified Residential Clothes Washers", "date_qualified"
    fields, pattern_keys = WASHER_FIELDS, WASHER_PATTERN_KEYS


class EnergyStarClothesDryers(_Sibling):
    source_id, categories = "energystar-clothes-dryers", {"clothes-dryers"}
    dataset, label, date_field = "t9u7-4d2j", "ENERGY STAR Certified Residential Clothes Dryers", "date_qualified"
    fields, pattern_keys = DRYER_FIELDS, DRYER_PATTERN_KEYS


CLASSES = {"freezers": EnergyStarFreezers, "clothes-washers": EnergyStarClothesWashers, "clothes-dryers": EnergyStarClothesDryers}

if __name__ == "__main__":
    cat = sys.argv.pop(1) if len(sys.argv) > 1 and sys.argv[1] in CLASSES else None
    if cat is None:
        raise SystemExit("usage: energystar_siblings.py <freezers|clothes-washers|clothes-dryers> discover|fetch|parse|run")
    _run.main(CLASSES[cat]())
