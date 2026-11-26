"""A3-impl r7: review 4's three ranked fixes, every exit criterion as an adversarial fixture.

1. Bundles (scripts/bundles.py, transform bundles@2): rigid vs flexible 200W panels, SKU-digit collisions, slash / pipe content, both free
   syntaxes, zero counts, conflicting and unparseable observations, regional SKU reuse and punctuation variants never mint `contains`; exact
   multi-model / quantity bundles still do; disputes land in identity_conflicts, promotions are separate; rel/bundle-contents@1 is inert.
2. TV certification scopes (scripts/tvcert.py): documented wildcard matches get only dated pwr.energy_star; power needs applicability
   evidence; wrong size / year / market, unknown wildcard semantics, undeclared listings and conflicting records fail closed; physical / panel
   facts never transfer; no ids merge.
3. ES vs site reconciliation: a reviewed exact pair links (same_model, no merge); production-letter, LG channel, unknown market, unevidenced and
   contradictory pairs stay separate; the stem possible_match proposal is untouched; declared aliases are re-audited and demoted on failure.

Pure fixtures plus one throwaway data root (SPECSHEET_ROOT, as tests/test_r6.py) holding two categories, imported and published once.
  python3 -I tests/test_r7.py
"""
import copy, hashlib, json, os, shutil, sqlite3, subprocess, sys, tempfile, unittest
from pathlib import Path

import yaml

CODE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(CODE / "scripts"))
sys.path.insert(0, str(CODE / "crawler" / "adapters"))
import bundles as B  # noqa: E402
import tvcert as TC  # noqa: E402
import decisions as D  # noqa: E402
import registry  # noqa: E402


def mem(title, names, pw=(), caps=None, brand=""):
    return B.members(title, {B.norm(n) for n in names}, pw, brand, caps)


class BundleParser(unittest.TestCase):
    def test_rigid_and_flexible_panels_are_different_parts(self):
        self.assertNotEqual(B.canon_desc("200W Rigid Solar Panel"), B.canon_desc("200W Flexible Solar Panel"))
        self.assertNotEqual(B.canon_desc("220W Solar Panel"), B.canon_desc("220W Portable Solar Panel"), "no lossy number-only signature")
        self.assertEqual(B.canon_desc("2 X 200W  Solar Panels"), B.canon_desc("2 x 200w solar panel"), "only case, spacing, plural fold")

    def test_no_sku_digit_inference(self):
        self.assertIsNone(mem("100W Bifacial Solar Panel", ["C1000 Gen 2", "A1763"])[0], "SKU B17631A9 contains 1763: no longer a member")
        self.assertIsNone(mem("2× 100W Bifacial Solar Panel", ["A1763"])[0])

    def test_slash_only_splits_known_colours(self):
        self.assertIsNone(mem("K-1 + Panel / Battery", ["K-1"])[0], "a slash that is no colour may hide contents")
        self.assertIsNone(mem("Solar / K-1 + Panel", ["K-1"])[0])
        m, _ = mem("Black / K-1 + 100W Panel", ["K-1"])
        self.assertEqual(m["parts"], [("100W Panel", 1)])

    def test_pipe_tail_kept_and_list_like_tail_rejected(self):
        m, _ = mem("K-1 + 100W Panel | 1800W, 1440Wh, 100W Solar Kit", ["K-1"])
        self.assertEqual((m["complete"], m["unparsed"]), (False, ["1800W, 1440Wh, 100W Solar Kit"]), "unknown text preserved, not explicit")
        self.assertIsNone(mem("K-1 | + 100W Panel", ["K-1"])[0])
        self.assertIsNone(mem("K-1 + Switch | 2 x 100W Panel", ["K-1"])[0])

    def test_both_free_syntaxes_are_promotions(self):
        for t in ("K-1 + Free 100W Panel", "K-1 + 100W Panel (Free)", "K-1 + 100W Panel（Free）"):
            m, why = mem(t, ["K-1"])
            self.assertIsNone(m, t); self.assertIn("single item", why)
        m, _ = mem("AC200P+B230 ( Free XT90-P090D ) | 2000W, 4048Wh Power Kit", ["AC200P"])
        self.assertEqual((m["parts"], m["promotions"]), ([("B230", 1)], ["XT90-P090D"]))
        m, _ = mem("K-1 + 2 x 100W Panel + Bag (Free)", ["K-1"])
        self.assertEqual((m["parts"], m["promotions"]), ([("100W Panel", 2)], ["Bag"]))
        self.assertIsNone(mem("K-1 + Panel free-standing", ["K-1"])[0], "other free wording is unparseable")

    def test_zero_and_repeated_quantities(self):
        self.assertIsNone(mem("0 x K-1 + 100W Panel", ["K-1"])[0])
        self.assertIsNone(mem("K-1 + 100W Panel x 0", ["K-1"])[0])
        m, _ = mem("K-1 + 200W Panel + 200W panels", ["K-1"])
        self.assertEqual(m["parts"], [("200W Panel", 2)], "equivalent parts form one multiset entry")

    def test_pack_word_fabricates_nothing(self):
        m, why = mem("X50 Ultra Complete / White", ["X50 Ultra"], pw=["Complete"])
        self.assertIsNone(m); self.assertIn("not itemised", why)
        m, _ = mem("X50 Ultra Complete + Spare Mop", ["X50 Ultra"], pw=["Complete"])
        self.assertEqual((m["parts"], m["complete"]), ([("Spare Mop", 1)], False))

    def test_capacity_note_must_match_the_page(self):
        self.assertIsNone(mem("Explorer 5000 Plus (10kWh) + Smart Transfer Switch", ["Explorer 5000 Plus"], caps={5040.0})[0])
        self.assertIsNotNone(mem("DELTA 3 Max (2048Wh) + 400W Solar Panel", ["DELTA 3 Max"], caps={2048.0})[0])
        self.assertIsNone(mem("DELTA 3 Max (2048Wh) + 400W Solar Panel", ["DELTA 3 Max"], caps=set())[0], "unverifiable note: not the model")

    def test_exact_multi_model_quantity_bundles_pass(self):
        m, _ = mem("(Members-only) 2 x K-1 + K-2 + 200W Panel x 2", ["K-1"])
        self.assertEqual((m["model"], m["parts"], m["complete"]), (2, [("K-2", 1), ("200W Panel", 2)], True))


class Policies(unittest.TestCase):
    """Same pattern as test_r6: new ids pending, old versions inert (match nothing live), allowlists separate."""

    @classmethod
    def setUpClass(cls):
        cls.dec = D.Decisions(CODE / "data")
        cls.pol = {p["id"]: p for p in cls.dec.claim_policies + cls.dec.relation_policies + cls.dec.retired_policies}

    def test_new_policies_pending(self):
        for i in ("rel/bundle-contents@2", "claim/tvs-es-certification-coverage@1", "claim/tvs-es-power-applicability@1",
                  "rel/tvs-es-certification-scope@1", "rel/tvs-crosswalk@1"):
            a = self.pol[i]["approval"]; self.assertIn(a["state"], ("pending", "approved"), i); self.assertTrue(a["state"] == "pending" or (a.get("by") and a.get("at")), i)  # human-approved 2026-11-23

    def test_bundle_contents_1_inert_and_2_pins_the_transform(self):
        live = {f"{registry.parser_info(s)['parser']}+{B.TRANSFORM}" for s, m in registry.SOURCES.items()
                if m["category"] in ("power-stations", "robot-vacuums")}
        old = {p for r in self.pol["rel/bundle-contents@1"]["rules"] for p in r["parsers"]}
        new = {p for r in self.pol["rel/bundle-contents@8"]["rules"] for p in r["parsers"]}   # r7 (A2 coverage r2): @2 -> @3, station parsers bumped; A2-mon r5: @5 (stations @4); A2-dell r6: @7 (stations @6); A3-fix review-8: @8 (stations @7)
        self.assertFalse(old & live, "@1 rules match no link the bundles@2 transform emits")
        self.assertNotIn("rel/bundle-contents@1", [p["id"] for p in self.dec.relation_policies], "@1 is retired (verbatim, still locked)")
        self.assertEqual(self.pol["rel/bundle-contents@1"]["retired"]["superseded_by"], "rel/bundle-contents@2")
        self.assertTrue(new <= live)
        self.assertEqual(self.pol["rel/bundle-contents@8"]["audit"]["parsers"][B.TRANSFORM], B.fingerprint(), "audited transform == code")
        self.assertEqual({t for r in self.pol["rel/bundle-contents@8"]["rules"] for t in r["types"]}, {"contains"})

    def test_tv_allowlists_separate_and_pinned(self):
        cov = self.pol["claim/tvs-es-certification-coverage@1"]["match"]
        pw = self.pol["claim/tvs-es-power-applicability@1"]["match"]
        self.assertEqual(cov["keys"], {"energystar-tvs": ["pwr.energy_star"]})
        self.assertEqual(set(pw["keys"]["energystar-tvs"]), set(TC.POWER_KEYS))
        self.assertEqual((cov["extractors"], pw["extractors"]), ([TC.COVERAGE_EXTRACTOR], [TC.POWER_EXTRACTOR]))
        for i in ("claim/tvs-structured@1", "claim/tvs-structured@2"):
            self.assertFalse({TC.COVERAGE_EXTRACTOR, TC.POWER_EXTRACTOR} & set(self.pol[i]["match"]["extractors"]), "direct ES list never transfers")
        for i in ("claim/tvs-es-certification-coverage@1", "claim/tvs-es-power-applicability@1", "rel/tvs-es-certification-scope@1", "rel/tvs-crosswalk@1"):
            self.assertEqual(self.pol[i]["audit"]["parsers"][TC.TRANSFORM], TC.fingerprint(), i)
        rules = self.pol["rel/tvs-es-certification-scope@1"]["rules"]
        self.assertEqual([r["method"] for r in rules], ["es-scope:documented"], "undocumented / undeclared / conflict stay proposals")

    def test_production_crosswalks_hold_no_pair(self):
        rules, pairs, appl = TC.load_crosswalks(CODE / "data" / "decisions" / "tv-crosswalks.yaml")
        self.assertEqual((pairs, appl), ([], []), "without reviewed evidence QN65S90FAF ~ QN65S90FAFXZA stays a proposal")
        self.assertEqual([(r["brand"], r["suffix"], r["market"]) for r in rules], [("samsung", "XZA", "US")])


class TvClauses(unittest.TestCase):
    def test_declarations(self):
        c = TC.clauses("OLED77B4AU*,OLED77B4AU*,OLED77B4AU* is the same as OLED77B4PU* except for model designation.* may be any alphanumeric "
                       "according to color of stand or enclosure; OLED77B4EU*,OLED77B4EU*,* may be any alphanumeric", "OLED77B4PU*")
        self.assertEqual([(t, r) for t, r, _ in c], [("OLED77B4AU*", "declared"), ("OLED77B4EU*", "listed")])
        c = TC.clauses("XA10,XA10,XA10 is not the same as BB10 except for model designation; XA20,XA20,Same as basic model except model designation "
                       "and stand", "BB10")
        self.assertEqual([r for _, r, _ in c], ["declaration_not_exact", "declaration_not_exact"], "negation / extra exception")

    def test_wildcard_semantics(self):
        rx, sem = TC.pattern_rx("OLED65C5***", True)
        self.assertEqual(sem, "documented")
        self.assertTrue(rx.match("OLED65C5PUA")); self.assertFalse(rx.match("OLED65C5PUAX")); self.assertFalse(rx.match("OLED65C5PU"))
        self.assertFalse(rx.match("OLED65C5P-A"), "documented alphabet only")
        self.assertEqual(TC.pattern_rx("OLED65C5***", False)[1], "undocumented")
        self.assertEqual(TC.pattern_rx("OLED65C5###", True)[1], "undocumented")
        self.assertFalse(TC.pattern_rx("OLED.5C5***", True)[0].match("OLED65C5PUA"), "literals escaped")


# ----------------------------------------------------------------------------- fixture data root
KIT_PROFILE = """
profile_format: specsheet.category-profile/1
category: kitx
version: 0.1.0
label: Kits
identity: {levels: [family, model, configuration, package], primary_key: manufacturer model number}
groups: [{id: general, label: General}]
specs:
  - {key: gen.power, label: Power, group: general, type: number, unit: W, tier: core, level: model, facet: {kind: range, bins: [100]}, sources: [spec page]}
"""
TV_PROFILE = """
profile_format: specsheet.category-profile/1
category: tvx
version: 0.1.0
label: TVs
identity: {levels: [family, model], primary_key: manufacturer model number}
conditions:
  - {id: power_basis, label: Power basis, type: enum, enum: [energy_star_on_mode, doe_federal_test, energy_star_standby]}
groups: [{id: general, label: General}]
specs:
  - {key: gen.viewable_diag, label: Diagonal, group: general, type: number, unit: in, tier: core, level: model, facet: false, sources: [x]}
  - {key: phys.weight, label: Weight, group: general, type: number, unit: kg, tier: core, level: model, facet: false, sources: [x]}
  - {key: panel.display_tech, label: Display, group: general, type: enum, enum: [lcd, oled], tier: core, level: model, facet: false, sources: [x]}
  - {key: pwr.energy_star, label: ENERGY STAR, group: general, type: bool, tier: core, level: model, facet: false, sources: [x]}
  - {key: pwr.on_mode_doe_w, label: DOE on-mode, group: general, type: number, unit: W, tier: core, level: model, facet: false,
     conditions: [power_basis], basis_conditions: [power_basis], sources: [x]}
"""
KIT_CAT = """
name: Kits
description: Fixture.
columns: [gen.power]
features: [bundle_packages]
bundles: {pack_words: [Complete]}
identity_scope: {cross_market_brands: "*", market_scoped_brands: []}
"""
TV_CAT = """
name: TVs
description: Fixture.
columns: [gen.viewable_diag]
features: [stem_links, es_cert_scopes]
es_cert: {source: es-tvx}
stem: {cut_at: [], strip_market_suffix: false, strip_regex: 'XZA$', same_source: true}
identity_scope: {cross_market_brands: "*", market_scoped_brands: []}
"""
CROSSWALKS = """
format: specsheet.tv-crosswalks/1
suffix_rules:
  - {brand: samsung, suffix: XZA, market: US}
pairs:
  - {brand: samsung, site: QN65S90FAFXZA, certified: QN65S90FAF, market: US, by: fixture-human, at: '2026-11-23',
     evidence: {url: 'https://example.invalid/crosswalk', quote: 'QN65S90FAFXZA is the US retail code of certified model QN65S90FAF'}}
  - {brand: samsung, site: QN55S90FAEXZA, certified: QN55S90FAF, market: US, by: fixture-human,
     evidence: {url: 'https://example.invalid/x', quote: 'QN55S90FAEXZA QN55S90FAF'}}
  - {brand: lg, site: OLED65C5PUA, certified: OLED65C5AUA, market: US, by: fixture-human,
     evidence: {url: 'https://example.invalid/x', quote: 'OLED65C5PUA OLED65C5AUA'}}
  - {brand: samsung, site: QN43S90FAFXZA, certified: QN43S90FAF, market: US, by: fixture-human,
     evidence: {url: 'https://example.invalid/x', quote: 'QN43S90FAFXZA QN43S90FAF'}}
  - {brand: samsung, site: QN85S90FAFXZA, certified: QN85S90FAF, market: US, by: fixture-human,
     evidence: {url: 'https://example.invalid/x', quote: 'QN85S90FAFXZA QN85S90FAF'}}
  - {brand: samsung, site: QN85S90FAFXZA, certified: QN85S92FAF, market: US, by: fixture-human,
     evidence: {url: 'https://example.invalid/x', quote: 'QN85S90FAFXZA QN85S92FAF'}}
  - {brand: samsung, site: QN77S90FAFXZA, certified: QN77S90FAF, market: US, by: fixture-human, evidence: {url: 'https://example.invalid/x', quote: 'same TV'}}
power_applicability: []
"""
DOC = "* may be any alphanumeric according to color of stand or enclosure"


def claim(key, value, unit, ex, cond=None):
    c = {"id": f"c_{key}_{value}", "key": key, "status": "known", "kind": "official", "unit": unit, "raw": f"{key}={value}", "source": "s1",
         "method": {"stage": "table", "extractor": ex}, "observed_at": "2026-11-23T00:00:00Z", "value": value, "locator": {}}
    if cond:
        c["conditions"] = cond
    return c


def page(model, issuer, market, claims, aliases=(), packages=(), skus=(), tier="manufacturer", fp=None):
    ids = [{"scheme": "mfr_model", "value": model, "value_raw": model, "issuer": issuer, "market": market, "package_level": "model", "role": "key",
            "sources": ["s1"]}]
    ids += [{"scheme": "mfr_sku", "value": s, "value_raw": s, "issuer": issuer, "market": market, "package_level": "configuration", "role": "alias",
             "sources": ["s1"], "option": o} for s, o in skus]
    return {"identifiers": ids, "aliases": [{"text": t, "kind": k} for t, k in aliases], "claims": claims, "media": [], "documents": [],
            "absences": [], "links": [], "fingerprints": dict(fp or {}, packages=[{"sku": s, "title": t} for s, t in packages]),
            "sources": [{"id": "s1", "url": f"https://example.invalid/{issuer}/{model}", "label": "page", "tier": tier}]}


K = lambda *a: claim(*a, ex="kitco@1")
KIT = [
    page("K-1", "kitco", "US", [K("gen.power", 500, "W"), K("cap.energy_wh", 5040, "Wh")],
         packages=[("KP-RIGID", "K-1 + 200W Rigid Solar Panel"), ("KP-MULTI", "(Members-only) 2 x K-1 + K-2 + 200W Panel x 2"),
                   ("KP-REP", "K-1 + 200W Panel + 200W panels"), ("KP-SLASH", "K-1 + Panel / Battery"), ("KP-COLOUR", "Black / K-1 + 100W Panel"),
                   ("KP-PIPE", "K-1 + 100W Panel | 1800W, 1440Wh"), ("KP-PIPE2", "K-1 | + 100W Panel"), ("KP-FREE1", "K-1 + Free 100W Panel"),
                   ("KP-FREE2", "K-1 + 100W Panel (Free)"), ("KP-FREE3", "K-1 + B230 ( Free XT90 )"), ("KP-ZERO", "0 x K-1 + 100W Panel"),
                   ("KP-UNP", "K-1 + 100W Panel"), ("KP-REG", "K-1 + 100W Panel"), ("KP-PUNCT", "K-1 + 50W Panel"), ("KPPUNCT", "K-1 + 50W Panel"),
                   ("KP-PLAIN", "K-1 + 100W Panel"), ("KP-10K", "K-1 (10kWh) + Switch"), ("KP-CAP", "K-1 (5040Wh) + Switch")],
         skus=[("KP-PLAIN", "White"), ("KP-CPL", "K-1 Complete")]),
    page("K-1", "kitco", "US", [], packages=[("KP-RIGID", "K-1 + 200W Flexible Solar Panel"), ("KP-UNP", "K-1 Special Edition Kit")]),
    page("K-1", "kitco", None, [], packages=[("KP-REG", "K-1 + 100W Panel")]),           # same SKU, unstated market: regional reuse not conflated
    page("K-2", "kitco", "US", [K("gen.power", 300, "W")]),
    page("A1763", "kitco", "US", [K("gen.power", 1000, "W")], packages=[("B17631A9", "100W Bifacial Solar Panel")]),
]
ESX = lambda *a, **k: claim(*a, ex="esx@1", **k)
L = lambda *a: claim(*a, ex="lgx@1")


def es_row(model, ami, diag, markets="United States", date="2024-11-18", avail="2025-04-04", display="OLED", pd=None):
    return {"brand_name": "LG" if model.startswith(("OLED", "5", "6")) else "Samsung", "model_number": model, "additional_model_information": ami,
            "markets": markets, "diagonal_viewable_screen_size_inches": str(diag), "date_qualified": date + "T00:00:00.000",
            "date_available_on_market": avail + "T00:00:00.000", "display_type": display, "pd_id": pd or str(int(hashlib.sha256(model.encode()).hexdigest(), 16) % 10 ** 7)}


ES_POWER = [ESX("pwr.on_mode_doe_w", 149.0, "W", cond={"power_basis": "doe_federal_test"}), ESX("pwr.energy_star", True, None),
            ESX("panel.display_tech", "oled", None), ESX("gen.viewable_diag", 64.5, "in")]
ES = [   # (parsed page, raw row)
    ("R1", "OLED65C5***", "lg", DOC, 64.5, {}),
    ("R2", "OLED77B4PU*", "lg", "OLED77B4AU*,OLED77B4AU*,OLED77B4AU* is the same as OLED77B4PU* except for model designation." + DOC +
     "; OLED77B4EU*,OLED77B4EU*," + DOC, 76.7, {}),
    ("R3", "OLED55C5###", "lg", "# is a version letter", 54.6, {}),
    ("R4", "OLED48C5***", "lg", DOC, 47.5, {"markets": "Canada"}),
    ("R5", "OLED42C5***", "lg", DOC, 41.5, {}),
    ("R6", "OLED83C5***", "lg", DOC, 82.5, {}),
    ("R7", "OLED83C5P**", "lg", DOC, 82.5, {"display": "LCD"}),
    ("R8", "OLED65C4***", "lg", DOC, 64.5, {}),
    ("R9", "OLED50X5***", "lg", DOC + "; measurements apply to all covered designations", 49.5, {}),
    ("E1", "QN65S90FAF", "samsung", "QN65S90FDF,QN65S90FDF,Same as basic model except model designation; QN65S92FAF,QN65S92FAF,Same as basic model "
     "except model designation", 64.5, {}),
    ("E2", "QN55S90FAF", "samsung", "QN55S90FAE,QN55S90FAE,Same as basic model except model designation; QN55S92FAF,QN55S92FAF,Same as basic "
     "model except model designation and stand", 54.6, {}),
    ("E3", "QN65S90FBF", "samsung", "QN65S90FDF,QN65S90FDF,Same as basic model except model designation", 64.5, {}),
    ("E4", "QN85S90FAF", "samsung", "", 84.5, {}), ("E5", "QN85S92FAF", "samsung", "", 84.5, {}), ("E6", "QN43S90FAF", "samsung", "", 42.5, {}),
    ("E7", "QN77S90FAF", "samsung", "", 76.7, {}),
]
LG = [("OLED65C5PUA", "US", 65.1), ("OLED65C5AUA", None, 65.1), ("OLED77B4AUA", "US", 77.4), ("OLED77B4EUA", "US", 77.4), ("OLED55C5PUA", "US", 55.2),
      ("OLED48C5PUA", "US", 48.2), ("OLED42C5PUA", "US", 54.6), ("OLED83C5PUA", "US", 83.5), ("OLED65C4PUA", "US", 65.1), ("OLED50X5PUA", "US", 50.0)]
SAM = [("QN65S90FAFXZA", "US", 64.5), ("QN55S90FAEXZA", "US", 54.6), ("QN85S90FAFXZA", "US", 84.5), ("QN43S90FAFXZA", None, 42.5),
       ("QN77S90FAFXZA", "US", 76.7)]


def policies():
    real = {p["id"]: p for p in (yaml.safe_load((CODE / "data" / "decisions" / "policies.yaml").read_text()) or {}).get("claim_policies", []) +
            yaml.safe_load((CODE / "data" / "decisions" / "policies.yaml").read_text()).get("relation_policies", [])}
    cov, pw = copy.deepcopy(real["claim/tvs-es-certification-coverage@1"]), copy.deepcopy(real["claim/tvs-es-power-applicability@1"])
    for p in (cov, pw):                     # the REAL allowlists, re-pointed at the fixture ES source id
        p["match"]["source_ids"] = ["es-tvx"]; p["match"]["keys"] = {"es-tvx": p["match"]["keys"]["energystar-tvs"]}
    scope = copy.deepcopy(real["rel/tvs-es-certification-scope@1"]); scope["rules"][0]["parsers"] = ["esx@1+tvcert@1"]
    return {"format": "specsheet.policies/1", "claim_policies": [
        {"id": "claim/fx-site@1", "since": "2026-11-23", "rationale": "fixture", "match": {
            "extractors": ["kitco@1", "lgx@1", "samx@1"], "source_ids": ["kitco-us", "lgx-us", "samx-us"], "kinds": ["official"],
            "tiers": ["manufacturer"], "statuses": ["known"], "require_normalized": False, "keys": ["gen.power", "gen.viewable_diag", "phys.weight", "panel.display_tech"]}},
        {"id": "claim/fx-es-direct@1", "since": "2026-11-23", "rationale": "fixture: the direct ES list includes panel facts", "match": {
            "extractors": ["esx@1"], "source_ids": ["es-tvx"], "kinds": ["official"], "tiers": ["regulatory"], "statuses": ["known"],
            "require_normalized": False, "keys": ["pwr.energy_star", "panel.display_tech", "gen.viewable_diag", "pwr.on_mode_doe_w"]}},
        cov, pw],
        "relation_policies": [
            {"id": "rel/fx-bundle@1", "since": "2026-11-23", "rationale": "fixture: the r6-shaped rule", "rules": [{"method": "bundle:kitco-us", "types": ["contains"], "parsers": ["kitco@1"]}]},
            {"id": "rel/fx-bundle@2", "since": "2026-11-23", "rationale": "fixture", "rules": [{"method": "bundle:kitco-us", "types": ["contains"], "parsers": ["kitco@1+bundles@2"]}]},
            scope, copy.deepcopy(real["rel/tvs-crosswalk@1"])]}


def write_source(t, sid, rows, raw=None):
    d = t / "raw" / sid
    (d / "parsed").mkdir(parents=True)
    (d / "blobs").mkdir()
    log = []
    for n, pr in enumerate(rows):
        (d / "parsed" / f"r{n}.json").write_text(json.dumps(pr))
        h = hashlib.sha256(f"{sid}|{n}".encode()).hexdigest()
        if raw:
            (d / "blobs" / f"{h}.json").write_text(json.dumps([raw[n]]))
        log.append({"snapshot": f"sha256:{h}", "ref": f"r{n}", "url": pr["sources"][0]["url"], "final_url": pr["sources"][0]["url"], "status": 200,
                    "fetched_at": "2026-11-23T00:00:00Z", "etag": None, "last_modified": None, "adapter": "fixture@1", "blob": f"blobs/{h}.json"})
    (d / "snapshots.jsonl").write_text("".join(json.dumps(x) + "\n" for x in log))


class Fixture(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = t = Path(tempfile.mkdtemp(prefix="specsheet-r7-"))
        os.symlink(CODE / "schemas", t / "schemas")
        for cat, prof, cm in (("kitx", KIT_PROFILE, KIT_CAT), ("tvx", TV_PROFILE, TV_CAT)):
            (t / "research" / cat).mkdir(parents=True)
            (t / "research" / cat / "spec-profile.yaml").write_text(prof)
            (t / "research" / cat / "category.yaml").write_text(cm)
        dd = t / "data" / "decisions"
        dd.mkdir(parents=True)
        (dd / "policies.yaml").write_text(yaml.safe_dump(policies(), sort_keys=False))
        (dd / "ledger.jsonl").write_text("")
        (dd / "tv-crosswalks.yaml").write_text(CROSSWALKS)
        src = lambda b, cat, p: {"brand": b, "brand_name": b.upper(), "category": cat, "module": "none", "importer": "model", "parser": p}
        (t / "sources.extra.json").write_text(json.dumps({"kitco-us": src("kitco", "kitx", "kitco@1"), "es-tvx": src("energystar", "tvx", "esx@1"),
                                                          "lgx-us": src("lg", "tvx", "lgx@1"), "samx-us": src("samsung", "tvx", "samx@1")}))
        write_source(t, "kitco-us", KIT)
        es_pages, es_raw = [], []
        for _, model, issuer, ami, diag, kw in ES:
            wild = any(ch in model for ch in "*#")
            al = [(tok, "declared_same_hardware" if "same as" in (txt or "").lower() else "model_variant") for tok, _, txt in TC.clauses(ami, model)
                  if not any(ch in tok for ch in "*#")]
            cl = [c for c in ES_POWER if c["key"] != "gen.viewable_diag"] + [ESX("gen.viewable_diag", diag, "in")]
            es_pages.append(page(model, issuer, "US", cl, aliases=al, tier="regulatory", fp={"wildcard_pattern": wild}))
            es_raw.append(es_row(model, ami, diag, **kw))
        write_source(t, "es-tvx", es_pages, es_raw)
        write_source(t, "lgx-us", [page(m, "lg", mk, [L("gen.viewable_diag", d, "in"), L("phys.weight", 20, "kg"), L("panel.display_tech", "oled", None)] +
                                        ([L("gen.model_year", 2021, None)] if m == "OLED65C4PUA" else [])) for m, mk, d in LG])
        write_source(t, "samx-us", [page(m, "samsung", mk, [claim("gen.viewable_diag", d, "in", ex="samx@1")]) for m, mk, d in SAM])
        env = dict(os.environ, SPECSHEET_ROOT=str(t))
        imp = lambda *a: subprocess.run([sys.executable, "-I", str(CODE / "scripts" / "import.py"), "--data", str(t / "data"), *a],
                                        env=env, capture_output=True, text=True)
        r = imp(); assert r.returncode == 0, r.stderr[-3000:]
        cls.imp = json.loads(r.stdout[r.stdout.index("{"):])
        cls.reg1 = (t / "data" / "_ids" / "registry.jsonl").read_text()
        r = imp("--no-mint"); assert r.returncode == 0, r.stderr[-3000:]
        cls.imp2 = json.loads(r.stdout[r.stdout.index("{"):])
        cls.con = sqlite3.connect(t / "state" / "specsheet.sqlite"); cls.con.row_factory = sqlite3.Row
        code = ("import sys, json; sys.path.insert(0, %r); import v1_publish as P; from pathlib import Path; st = {}; P.publish(Path(%r), st); print(json.dumps(st))"
                % (str(CODE / "scripts"), str(t / "api")))
        r = subprocess.run([sys.executable, "-I", "-c", code], env=env, capture_output=True, text=True)
        assert r.returncode == 0, r.stderr[-3000:]
        cls.api = t / "api"

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.tmp, ignore_errors=True)

    def ent(self, eid):
        return self.con.execute("SELECT * FROM entities WHERE id=?", (eid,)).fetchone()

    def ex(self, eid):
        return json.loads(self.ent(eid)["extra"] or "{}")

    def claims(self, eid, key=None):
        return [dict(r) for r in self.con.execute("SELECT * FROM claims WHERE entity_id=?" + (" AND key=?" if key else ""), (eid, key) if key else (eid,))]

    def conflicts(self, value):
        return [r["reason"] for r in self.con.execute("SELECT * FROM identity_conflicts WHERE value=?", (value,))]

    # --------------------------------------------------------------- 1 bundles
    def test_bundles_minted_only_when_exact(self):
        pk = {r["id"] for r in self.con.execute("SELECT id FROM entities WHERE category='kitx' AND kind='package'")}
        self.assertEqual(pk, {"kitco-kp-multi", "kitco-kp-rep", "kitco-kp-colour", "kitco-kp-pipe", "kitco-kp-free3", "kitco-kp-cap"})

    def test_contains_decided_by_2_never_by_1(self):
        rows = self.con.execute("SELECT * FROM relations WHERE type='contains'").fetchall()
        self.assertTrue(rows)
        self.assertEqual({(r["status"], r["decision"]) for r in rows}, {("approved", "rel/fx-bundle@2")})
        m = {r["target_id"] for r in rows if r["entity_id"] == "kitco-kp-multi"}
        self.assertEqual(m, {"kitco-k-1", "kitco-k-2"})
        self.assertEqual(self.ex("kitco-kp-multi")["contents"], [{"entity": "kitco-k-1", "qty": 2}, {"entity": "kitco-k-2", "qty": 1},
                                                                 {"description": "200W Panel", "qty": 2}])
        self.assertEqual(self.ex("kitco-kp-rep")["contents"][1], {"description": "200W Panel", "qty": 2})

    def test_disputes_quarantined_not_reattached(self):
        for sku in ("KP-RIGID", "KP-UNP", "KP-REG", "KP-PUNCT", "KPPUNCT", "KP-PLAIN"):
            self.assertEqual(len(self.conflicts(sku)), 1, sku)
        self.assertIn("different contents", self.conflicts("KP-RIGID")[0])
        self.assertIn("do not itemise", self.conflicts("KP-UNP")[0])
        self.assertIn("different markets", self.conflicts("KP-REG")[0])
        self.assertIn("punctuation", self.conflicts("KP-PUNCT")[0])
        idents = {r["value"] for r in self.con.execute("SELECT value FROM identifiers WHERE entity_id='kitco-k-1'")}
        self.assertFalse({"KP-RIGID", "KP-UNP", "KP-REG"} & idents, "a disputed bundle SKU is not restored as a configuration alias")
        self.assertIn("KP-CPL", idents, "a pack-word-only option stays a plain alias")
        self.assertNotIn("kitco-b17631a9", {r["id"] for r in self.con.execute("SELECT id FROM entities")})

    def test_promotions_and_incomplete_contents_published(self):
        d = json.loads((self.api / "kitx" / "products" / "kitco-kp-free3.json").read_text())
        self.assertEqual(d["contents"], [{"entity": "kitco-k-1", "qty": 1}, {"description": "B230", "qty": 1}])
        self.assertEqual([p["text"] for p in d["bundle_evidence"]["promotions"]], ["XT90"])
        self.assertTrue(d["bundle_evidence"]["promotions"][0]["observed_at"])
        self.assertEqual(d["bundle_evidence"]["evidence"], "manufacturer_store_listing")
        p = json.loads((self.api / "kitx" / "products" / "kitco-kp-pipe.json").read_text())
        self.assertEqual((p["bundle_evidence"]["complete"], p["bundle_evidence"]["unparsed"]), (False, ["1800W, 1440Wh"]))
        self.assertIn("incomplete", p["notes"])

    def test_ids_stable_on_replay(self):
        self.assertEqual(self.imp2["ids"]["new"], 0)
        self.assertEqual(self.imp2["ids"]["reused"], self.imp["ids"]["reused"] + self.imp["ids"]["new"])

    # --------------------------------------------------------------- 2 certification scopes
    def certs(self, eid):
        return {(c["matched_pattern"], c["method"], c["status"]) for c in self.ex(eid).get("certifications", [])}

    def es_claims(self, eid):
        return [c for c in self.claims(eid) if c["extractor"].startswith("energystar_tvs_")]

    def test_documented_match_transfers_only_dated_certification(self):
        self.assertEqual(self.certs("lg-oled65c5pua"), {("OLED65C5***", "es-scope:documented", "approved")})
        cs = self.es_claims("lg-oled65c5pua")
        self.assertEqual([(c["key"], c["value"], c["review"]) for c in cs], [("pwr.energy_star", "true", "accepted")])
        self.assertEqual(cs[0]["decision"], "claim/tvs-es-certification-coverage@1")
        self.assertIn("2024-11-18", cs[0]["raw"]); self.assertEqual(json.loads(cs[0]["locator"])["date_qualified"], "2024-11-18")
        keys = {c["key"] for c in self.claims("lg-oled65c5pua") if c["source_id"] == "es-tvx"}
        self.assertEqual(keys, {"pwr.energy_star"}, "panel / size / power facts of the record never transfer")
        self.assertEqual(self.certs("lg-oled77b4aua"), {("OLED77B4AU*", "es-scope:documented", "approved")}, "exactly declared pattern")

    def test_power_needs_applicability_evidence(self):
        self.assertFalse([c for c in self.claims("lg-oled65c5pua") if c["extractor"] == TC.POWER_EXTRACTOR])
        c = next(x for x in self.ex("lg-oled65c5pua")["certifications"])
        self.assertEqual((c["power_transferred"], [p["key"] for p in c["power"]]), (False, ["pwr.on_mode_doe_w"]), "shown on the record only")
        pw = [x for x in self.claims("lg-oled50x5pua") if x["extractor"] == TC.POWER_EXTRACTOR]
        self.assertEqual([(x["key"], x["review"], x["decision"]) for x in pw], [("pwr.on_mode_doe_w", "accepted", "claim/tvs-es-power-applicability@1")])
        self.assertEqual(json.loads(pw[0]["cond"]), {"power_basis": "doe_federal_test"}, "original basis kept")

    def test_fail_closed(self):
        self.assertEqual(self.certs("lg-oled65c5aua"), set(), "unknown market is not US")
        self.assertEqual(self.certs("lg-oled48c5pua"), set(), "Canada record")
        self.assertEqual(self.certs("lg-oled42c5pua"), set(), "page states 54.6 in under a 41.5 in record")
        self.assertTrue(any("size" in r for r in self.conflicts("OLED42C5***")))
        self.assertEqual(self.certs("lg-oled65c4pua"), set(), "stated 2021 model vs a 2025 record")
        self.assertTrue(any("year" in r for r in self.conflicts("OLED65C4***")))
        self.assertEqual(self.certs("lg-oled55c5pua"), {("OLED55C5###", "es-scope:undocumented-wildcard", "proposed")})
        self.assertEqual(self.certs("lg-oled77b4eua"), {("OLED77B4EU*", "es-scope:listed-undeclared", "proposed")})
        self.assertEqual({m for _, m, _ in self.certs("lg-oled83c5pua")}, {"es-scope:conflict"})
        for eid in ("lg-oled65c5aua", "lg-oled48c5pua", "lg-oled42c5pua", "lg-oled65c4pua", "lg-oled55c5pua", "lg-oled77b4eua", "lg-oled83c5pua"):
            self.assertFalse(self.es_claims(eid), eid)

    def test_no_identity_change(self):
        kinds = {r["kind"] for r in self.con.execute("SELECT kind FROM entities WHERE category='tvx'")}
        self.assertEqual(kinds, {"model"}, "a pattern never becomes an entity")
        for r in self.con.execute("SELECT entity_id, count(*) n FROM identifiers WHERE scheme='mfr_model' AND role='key' GROUP BY entity_id"):
            self.assertEqual(r["n"], 1)
        pats = self.con.execute("SELECT count(*) FROM identifiers WHERE value LIKE '%*%' OR value LIKE '%#%'").fetchone()[0]
        self.assertEqual(pats, 0)
        self.assertEqual(self.ent("lg-oled65c5pua")["parent_id"], None)
        d = json.loads((self.api / "tvx" / "products" / "lg-oled65c5pua.json").read_text())
        self.assertEqual([c["record"] for c in d["certifications"]], ["es-tvx:" + es_row("OLED65C5***", "", 0)["pd_id"]])

    # --------------------------------------------------------------- 3 reconciliation
    def rels(self, eid, typ):
        return {(r["target_id"], r["status"], r["decision"]) for r in self.con.execute("SELECT * FROM relations WHERE entity_id=? AND type=?", (eid, typ))}

    def test_reviewed_exact_pair_links_without_merge(self):
        self.assertEqual(self.rels("samsung-qn65s90fafxza", "same_model"), {("samsung-qn65s90faf", "approved", "rel/tvs-crosswalk@1")})
        self.assertIn(("samsung-qn65s90faf", "proposed", None), self.rels("samsung-qn65s90fafxza", "possible_match"), "stem proposal unchanged")
        self.assertIsNotNone(self.ent("samsung-qn65s90faf")); self.assertIsNotNone(self.ent("samsung-qn65s90fafxza"))
        x = self.ex("samsung-qn65s90fafxza")["crosswalks"][0]
        self.assertEqual((x["status"], x["evidence"]["url"], x["by"]), ("linked", "https://example.invalid/crosswalk", "fixture-human"))

    def test_other_pairs_stay_separate(self):
        for site, why in (("samsung-qn55s90faexza", "production letter"), ("lg-oled65c5pua", "channel"), ("samsung-qn43s90fafxza", "market"),
                          ("samsung-qn85s90fafxza", "contradictory"), ("samsung-qn77s90fafxza", "evidence")):
            self.assertEqual(self.rels(site, "same_model"), set(), site)
            self.assertTrue(any(why in c["reason"] for c in self.ex(site)["crosswalks"]), (site, self.ex(site)["crosswalks"]))

    def test_declared_alias_audit(self):
        al = lambda eid: {r["text"]: r["kind"] for r in self.con.execute("SELECT * FROM aliases WHERE entity_id=?", (eid,))}
        self.assertEqual(al("samsung-qn65s90faf")["QN65S92FAF"], "declared_same_hardware")
        self.assertEqual(al("samsung-qn65s90faf")["QN65S90FDF"], "proposed_same_hardware", "declared under two base models")
        self.assertEqual(al("samsung-qn55s90faf")["QN55S90FAE"], "proposed_same_hardware", "production letter differs")
        self.assertEqual(al("samsung-qn55s90faf")["QN55S92FAF"], "proposed_same_hardware", "extra exception 'and stand'")
        reasons = {a["alias"]: a["reason"] for a in self.ex("samsung-qn55s90faf")["alias_audit"]}
        self.assertIn("production letter", reasons["QN55S90FAE"])
        self.assertEqual(self.imp["stem_proposals"]["tvx"]["declared_aliases_demoted"], 4)


if __name__ == "__main__":
    unittest.main()
