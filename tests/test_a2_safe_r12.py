"""A2-safe r12: CPSC recalls overlay (crawler/adapters/cpsc_recalls.py). Pure fixtures, no network.

  python3 -I tests/test_a2_safe_r12.py
"""
import json, sys, unittest
from pathlib import Path

CODE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(CODE / "crawler" / "adapters"))
sys.path.insert(0, str(CODE / "scripts"))
import _contract as C  # noqa: E402
import cpsc_recalls as R  # noqa: E402
import presets as P  # noqa: E402
import registry  # noqa: E402
import yaml  # noqa: E402

ANKER = {"RecallNumber": "25011", "RecallDate": "2024-10-17T00:00:00", "Title": "Anker Power Banks Recalled Due to Fire and Burn Hazards; Manufactured by Anker Innovations",
         "URL": "https://www.cpsc.gov/Recalls/2025/Anker-Power-Banks-Recalled", "Products": [{"Name": "Anker Power Banks", "Model": "", "Description": ""}],
         "Description": "This recall involves Anker Power Banks with model numbers A1642, A1647 and A1652. The power bank can be used ... with a 12W (A1642) output.",
         "Hazards": [{"Name": "The power bank's lithium-ion battery can overheat, posing fire and burn hazards."}], "RemedyOptions": [{"Option": "Replace"}],
         "Manufacturers": [{"Name": "Anker Innovations Limited, of China"}]}
BELKIN = {"RecallNumber": "26090", "RecallDate": "2025-11-13T00:00:00", "Title": "Belkin Recalls Portable Power Banks and Wireless Charging Stands Due to Fire and Burn Hazards",
          "Products": [{"Name": "Portable Power Banks and Wireless Charging Stands"}],
          "Description": "This recall involves charging stands with model number MMA008 and power banks with model numbers BPB002 and PB0003. Model number \"MMA008\" is printed on the bottom."}


def snap(body, src="cpsc-recalls-power-banks"):
    return C.Snapshot("sha256:" + "0" * 64, C.Ref(src, f"{body['brand']}|{body['model']}", "https://www.saferproducts.gov/RestWebServices/Recall?format=json", {}),
                      200, "2026-11-26T00:00:00Z", "https://www.saferproducts.gov/RestWebServices/Recall?format=json&RecallDateStart=2024-01-01&RecallDateEnd=2024-12-31", {})


def claims(pr):
    return {c["key"]: c for c in pr.claims}


class Extraction(unittest.TestCase):
    def test_models_after_a_lead_only(self):
        self.assertEqual([m for m, _ in R.models_printed(R.text_of(ANKER))], ["A1642", "A1647", "A1652"])
        t = "Galanz: one of the following model numbers are included in this recall: BCD-215V-62H, GLR76TRDER or GLR76TWEER. \"Galanz,\" ..."
        self.assertEqual([m for m, _ in R.models_printed(t)], ["BCD-215V-62H", "GLR76TRDER", "GLR76TWEER"])

    def test_prefix_series_negation_and_split_tokens_yield_nothing(self):
        for t in ("Model Numbers Starting With Date Codes VCSB481, VCSB482", "Brand Model # beginning with Serial # range Bosch SGE63E",
                  "the ASKO model series DW95 with model numbers 1355, 1385", "No other Insignia model televisions, model IS-LCDTV27, are involved.",
                  "Model numbers ending with an E are not included on the recall.", "marketed as model numbers SBS24 I0 and more"):
            self.assertEqual([m for m, _ in R.models_printed(t) if m in ("VCSB481", "SGE63E", "DW95", "IS-LCDTV27", "SBS24")], [], t)

    def test_local_product_type_assigns_each_lead(self):
        got = dict(R.models_printed(R.text_of(BELKIN)))
        self.assertEqual(got, {"MMA008": "chargers", "BPB002": "power-banks", "PB0003": "power-banks"})

    def test_category_priority(self):
        self.assertEqual(R.category_of({"Title": "Lenovo Recalls USB-C Laptop Power Banks Due to Fire Hazard"}), "power-banks")
        self.assertEqual(R.category_of({"Title": "Dynabook Recalls Toshiba Laptop AC Adapters"}), "chargers")
        self.assertEqual(R.category_of({"Title": "Viking Recalls Built-In Side-by-Side Refrigerator Freezers"}), "refrigerators")
        self.assertIsNone(R.category_of({"Title": "Porter-Cable Fixed-Base Production Routers Recalled"}))     # woodworking routers

    def test_brand_gate_prefers_product_names(self):
        brx = {"ge": R.brand_rx("ge", "GE"), "haier": R.brand_rx("haier", "Haier")}
        r = {"Title": "GE Appliances, a Haier Company, Recalls Refrigerators", "Products": [{"Name": "GE-brand French Door Refrigerators"}]}
        self.assertEqual(R.brands_named(r, brx), ["ge"])


class Parse(unittest.TestCase):
    def body(self, match, model="A1642"):
        return {"brand": "anker", "model": model, "match": match, "category": "power-banks", "recalls": [ANKER]}

    def test_recall_only_record_carries_identity_and_recall_facts_only(self):
        pr = R.parse_bundle(snap(self.body("recall_only")), self.body("recall_only"))
        key = [i for i in pr.identifiers if i["role"] == "key"]
        self.assertEqual([(i["scheme"], i["value"], i["issuer"]) for i in key], [("mfr_model", "A1642", "anker")])
        c = claims(pr)
        self.assertEqual(set(c), set(R.KEYS))
        self.assertEqual(c["gen.record_kind"]["value"], "recall_only")
        self.assertEqual(c["safety.recall_id"]["value"], ["25011"])
        self.assertEqual(c["safety.recall_date"]["value"], "2024-10-17")
        self.assertEqual(c["safety.recall_remedy"]["value"], ["replace"])
        self.assertTrue(c["safety.recall"]["value"].startswith("CPSC 25011 (2024-10-17): "))
        self.assertEqual({x["method"]["extractor"] for x in pr.claims}, {R.ADAPTER})
        self.assertEqual(pr.sources[0]["tier"], "regulatory")

    def test_enrichment_never_sets_record_kind(self):
        pr = R.parse_bundle(snap(self.body("existing")), self.body("existing"))
        self.assertNotIn("gen.record_kind", claims(pr))
        self.assertIn("safety.recall", claims(pr))

    def test_model_must_be_printed_in_stored_notice(self):
        pr = R.parse_bundle(snap(self.body("recall_only", "A1653")), self.body("recall_only", "A1653"))
        self.assertEqual(pr.claims, []); self.assertEqual(pr.identifiers, [])

    def test_never_writes_a_negative(self):
        pr = R.parse_bundle(snap(self.body("recall_only")), dict(self.body("recall_only"), recalls=[]))
        self.assertEqual(pr.claims, [])


class Wiring(unittest.TestCase):
    def test_one_source_per_category_and_profiles_carry_keys(self):
        for c in R.CATEGORIES:
            sid = f"cpsc-recalls-{c}"
            self.assertEqual(registry.SOURCES[sid]["category"], c)
            self.assertEqual(registry.SOURCES[sid]["importer"], "model")
            keys = {s["key"] for s in yaml.safe_load((CODE / "research" / c / "spec-profile.yaml").read_text())["specs"]}
            self.assertTrue(set(R.KEYS) <= keys, c)

    def test_policy_is_explicit_and_not_self_approved(self):
        pol = yaml.safe_load((CODE / "data" / "decisions" / "policies.yaml").read_text())
        p = next(x for x in pol["claim_policies"] if x["id"] == "claim/cpsc-recalls@1")
        self.assertEqual(p["match"]["extractors"], [R.ADAPTER])
        self.assertEqual(sorted(p["match"]["source_ids"]), sorted(f"cpsc-recalls-{c}" for c in R.CATEGORIES))
        for sid in p["match"]["source_ids"]:
            self.assertEqual(sorted(p["match"]["keys"][sid]), sorted(R.KEYS))
        a = p.get("approval") or {}
        self.assertTrue(a.get("state") == "pending" or (a.get("state") == "approved" and a.get("by") and a.get("at")))

    def test_source_hosts_listed_before_use(self):
        sp = yaml.safe_load((CODE / "data" / "source-policy.yaml").read_text())
        d = {s["domain"]: s for s in sp["sources"]}
        for host in ("www.saferproducts.gov", "www.cpsc.gov"):
            self.assertEqual(d[host]["kind"], "government"); self.assertEqual(d[host].get("crawl", "agent"), "agent")
            self.assertEqual(d[host]["evidence"]["level"], "fetched")
        self.assertTrue(R.API.startswith("https://www.saferproducts.gov/"))


class Presets(unittest.TestCase):
    def test_recall_only_rows_are_out_of_every_preset_population(self):
        schema = {"fields": [{"key": "x.n", "label": "N", "type": "number", "facet": {"kind": "range"}},
                             {"key": "gen.record_kind", "label": "Kind", "type": "enum", "facet": {"kind": "enum"}}]}
        rows = [{"id": "a", "brand": "A", "t": ["manufacturer"], "v": {"x.n": 5}},
                {"id": "b", "brand": "B", "t": ["manufacturer"], "v": {"x.n": 6}},
                {"id": "c", "brand": "C", "t": ["regulatory"], "v": {"gen.record_kind": "recall_only"}}]
        preset = {"id": "p", "filters": {"f_x.n_min": "1"}, "scope": {"sources": ["regulatory", "manufacturer"]}}
        gate, count = P.measure(preset, {"id": "cat"}, schema, rows, 0.8)
        self.assertEqual(gate["scope"]["in_scope"], 2)
        self.assertEqual(gate["scope"]["excluded"]["recall_only"], 1)
        self.assertEqual(gate["fill"], 1.0)
        self.assertEqual(count["total"], 2)


if __name__ == "__main__":
    unittest.main()
