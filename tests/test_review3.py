"""Adversarial fixtures for reviews/2026-11-23-astra-review-3.md (robot vacuums + power banks), one test per exit criterion of the three
ranked fixes. Fast, pure parsers; the last class reads the release store (state/specsheet.sqlite) that release.sh builds before the tests.

  python3 -m unittest tests.test_review3

1 trusted semantics   enum negation / generic words / single vs dual rotating mop; negated certification; Matter only via a CSA exact match;
                      all-port totals need explicit port membership (two-port '&', subset totals, additive wattage)
2 identity            corroborated grouping (no SKU bridge across incompatible names, Plus/RDS distinct, Complete packs fold); INIU/UGREEN
                      page-vs-label conflicts go to identity review with existing ids
3 conditions          capacity bases apart (class never fills cell mAh), all-port vs single-port naming, 5 V ratings keep their load,
                      unlabelled dual figures unresolved, plausibility rejections and mixed robot+dock cells kept with literal + reason
4 policies            one consolidated pending policy per category (+ Matter); superseded active policies match no current extractor
"""
import json, sqlite3, sys, unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts")); sys.path.insert(0, str(ROOT / "crawler" / "adapters"))
import yaml  # noqa: E402
import decisions as D  # noqa: E402
import registry  # noqa: E402
import _contract as C  # noqa: E402
import _robovac as RV  # noqa: E402
import _powerbank as P  # noqa: E402
import shopify_powerbanks as S  # noqa: E402
import csa_dcl_robovac as CSA  # noqa: E402
import dreame_robovac as DR  # noqa: E402
import roborock_robovac as RR  # noqa: E402

SNAP = C.Snapshot("sha256:x", C.Ref("fx", "k", "https://example.test/p", {}), 200, "2026-11-23T00:00:00Z", "https://example.test/p", {})


def unresolved(v):
    return isinstance(v, (RV.Unresolved, P.Unresolved))


class Fix1Enums(unittest.TestCase):
    def test_negation_never_emits_a_mechanism(self):
        for cell in ("no camera", "No camera, 3D structured light", "without LiDAR", "not equipped with RGB camera"):
            self.assertTrue(unresolved(RV.obstacle_sensors(cell)), cell)
        self.assertTrue(unresolved(RV.navigation("no LiDAR, camera vSLAM")))
        self.assertTrue(unresolved(RV.mop_type("no mop")))

    def test_generic_laser_visual_camera_are_not_mechanisms(self):
        self.assertTrue(unresolved(RV.obstacle_sensors("Laser Obstacle Avoidance")), "laser != structured light")
        self.assertTrue(unresolved(RV.obstacle_sensors("AI Camera x2 + LED")), "camera != RGB")
        self.assertTrue(unresolved(RV.obstacle_sensors("3D ToF + AI Camera + LED")), "a partial list would deny the camera")
        self.assertTrue(unresolved(RV.obstacle_sensors("AI vision")))
        self.assertTrue(unresolved(RV.navigation("visual")), "visual != vSLAM")
        self.assertTrue(unresolved(RV.navigation("laser navigation")))
        self.assertTrue(unresolved(RV.navigation("LDS + vSLAM")), "two mechanisms in one cell")

    def test_explicit_mechanisms_are_kept(self):
        self.assertEqual(RV.obstacle_sensors("AI RGB + 3D Structured Light + LED"), ["structured_light", "rgb_camera"])
        self.assertEqual(RV.obstacle_sensors("Dual-line laser+RGB AI+LED"), ["structured_light", "rgb_camera"])
        self.assertEqual(RV.obstacle_sensors("RGBD+camera light"), ["rgb_camera"], "an illuminator is not a second camera")
        self.assertEqual(RV.navigation("Fully-Embedded dToF LiDAR"), "dtof")
        self.assertEqual(RV.navigation("LDS"), "lidar")
        self.assertEqual(RV.navigation("vSLAM camera"), "vslam_camera")

    def test_single_vs_dual_rotating_mop(self):
        self.assertTrue(unresolved(RV.mop_type("single rotating mop")), "no single_spinning enum: never dual_spinning")
        self.assertTrue(unresolved(RV.mop_type("rotating mop")), "uncounted")
        self.assertTrue(unresolved(RV.mop_type("dual mops")), "count without rotation")
        self.assertTrue(unresolved(RV.mop_type("Dual Omni-Scrub Mops")), "trademark")
        self.assertTrue(unresolved(RV.mop_type("Detachable Mop Pad")), "a pad is not 'static'")
        self.assertEqual(RV.mop_type("Dual-Rotary Mop (3 Pair)"), "dual_spinning")
        self.assertEqual(RV.mop_type("Rotating Dual-Mop (OZMO Turbo 2.0)"), "dual_spinning")
        self.assertEqual(RV.mop_type("OZMO ROLLER 3.0, Microfiber Mop Roller"), "roller")

    def test_unresolved_cell_keeps_literal_and_reason(self):
        pr = C.ParseResult()
        RV.add(pr, "fx@1", SNAP, "X1", "nav.obstacle_sensors", RV.obstacle_sensors("no camera"), "no camera", "Obstacle Avoidance")
        RV.add(pr, "fx@1", SNAP, "X1", "nav.obstacle_sensors", RV.obstacle_sensors("AI RGB + 3D Structured Light"), "AI RGB + 3D Structured Light", "OA")
        bad, good = pr.claims
        self.assertEqual((bad["status"], bad["raw"], "value" in bad), ("unknown", "no camera", False))
        self.assertIn("negated", bad["quote"])
        self.assertEqual((good["status"], good["value"], good["raw"]), ("known", ["structured_light", "rgb_camera"], "AI RGB + 3D Structured Light"))


class Fix1Certification(unittest.TestCase):
    D = ["*25,000Pa suction: not certified by SGS; tested in laboratory", "*19,000Pa: Based on our in-house lab data",
         "*7000Pa: Certified by TÜV SÜD", "*5000Pa measured in a laboratory", "*0 tangles: Certified by TÜV SÜD"]

    def test_negated_or_bare_lab_is_unstated(self):
        self.assertEqual(RV.basis_for("25,000", self.D)[0], "mfr_unstated")
        self.assertEqual(RV.basis_for("5000", self.D)[0], "mfr_unstated", "'laboratory' alone is not in-house")
        self.assertEqual(RV.basis_for("190", self.D), ("mfr_unstated", None), "number must be in the disclaimer (190 is not 19000)")

    def test_affirmative_attribution_is_manufacturer_reported(self):
        self.assertEqual(RV.basis_for("7000", self.D)[0], "mfr_reported_certified", "page statement, certificate not checked")
        self.assertEqual(RV.basis_for("19,000", self.D)[0], "mfr_in_house_lab")
        prof = yaml.safe_load((ROOT / "research/robot-vacuums/spec-profile.yaml").read_text())
        self.assertIn("mfr_reported_certified", next(c for c in prof["conditions"] if c["id"] == "claim_basis")["enum"])

    def _dcl(self, product_name):
        b = {"model": {"vid": 1, "pid": 2, "deviceTypeId": CSA.ROBOVAC, "productName": product_name}, "brand": "dreame",
             "matched_store_model": "L40s Ultra", "compliance": [{"softwareVersionCertificationStatus": 2, "cDCertificateId": "CSA1", "softwareVersion": 1}]}
        return CSA.parse_bundle(SNAP, b)

    def test_matter_only_through_csa_exact_match(self):
        self.assertEqual([c["key"] for c in self._dcl("Dreame L40s Ultra").claims], ["smart.matter"])
        self.assertEqual(self._dcl("Dreame L40s Ultra CE").claims, [], "regional ledger name is not the US model")
        self.assertEqual(self._dcl("L40s Ultra Kit").claims, [])
        dec = D.Decisions(ROOT / "data")
        ctx = {"source_id": "dreame-us-robovac", "extractor": registry.parser_info("dreame-us-robovac")["parser"], "key": "smart.matter",
               "kind": "official", "tier": "manufacturer", "status": "known", "normalized": True}
        self.assertEqual(dec.claim_state("c_0000000000000000", ctx)[0], "candidate", "a maker-page Matter tick is never trusted")


class Fix1Totals(unittest.TestCase):
    def test_two_port_ampersand_is_ambiguous(self):
        ports, _, total, _ = P.ports_from("USB-C1 & USB-C2: 5V3A 9V3A 20V3A 60W(Max)")
        self.assertEqual(ports, [], "neither each-port nor all-ports is proven")
        self.assertTrue(unresolved(total))
        ports, _, total, _ = P.ports_from("OUT1&OUT2: 5V3A 9V3A 45W(Max); OUT3: 5V3A 22.5W(Max); OUT1+OUT2: 15W(Max); Total(OUT1+OUT2+OUT3): 15W(Max)")
        self.assertEqual([(p["name"], p["max_w"]) for p in ports], [("OUT1&OUT2", 45), ("OUT3", 22.5)], "'&' = each port when '+' marks combos")
        self.assertEqual(total, 15)

    def test_subset_total_is_not_all_ports(self):
        _, _, total, _ = P.ports_from("OUT1: 5V3A 45W(Max); OUT2: 5V3A 20W(Max); OUT3: 5V2.4A 12W(Max); Total(OUT1+OUT2): 50W(Max)")
        self.assertTrue(unresolved(total)); self.assertIn("omits OUT3", total.reason)
        t = ("Wireless OUT (Phone) : 25W / 15W; Wireless OUT (Watch) : 5W; USB-C OUT1 / OUT2: 5V⎓3A, 15V⎓3A, 45W (Max); USB-C OUT1 + OUT2: 24W (Max); "
             "Total [OUT1+OUT2+Wireless Out(Phone)+Wireless Out (Watch)] : 15W (Max)")
        _, _, total, toks = P.ports_from(t)
        self.assertEqual((total, toks), (15, ["OUT1", "OUT2", "W(PHONE)", "W(WATCH)"]), "INIU P841: the 24 W two-port figure is not the total")

    def test_additive_wattage_is_not_summed(self):
        _, _, total, _ = P.ports_from("USB-C1: 5V3A 20V3.25A 65W(Max); USB-A: 5V3A 15W(Max); USB-C1+USB-A: 65W+15W (Total)")
        self.assertTrue(unresolved(total), "65W+15W (Total) is not 'as printed' 80 W")
        _, _, total, _ = P.ports_from("Wireless OUT: 15W / 10W; OUT : 5V⎓3A, 9V⎓2.22A, 20W(MAX); Total (OUT+Wireless OUT) : 10W + 5W = 15W(MAX)")
        self.assertEqual(total, 15, "a printed sum is a printed total")

    def test_mode_dependent_or_uninventoried_totals(self):
        t = "Wall Charger Mode : OUT1: 30W(MAX); OUT2: 22.5W(MAX); Total(OUT1+OUT2): 18W(MAX); Power Bank Mode: OUT1: 30W(MAX); OUT2: 22.5W(MAX); Total(OUT1+OUT2): 15W(MAX)"
        self.assertTrue(unresolved(P.ports_from(t)[2]))
        self.assertTrue(unresolved(P.ports_from("USB-C1 + USB-C2: 165W Max (5V/3A, 9V/3A, etc.) Total")[2]), "no port inventory to check")
        self.assertIsNone(P.ports_from("USB-C: 5V3A 9V2.22A 20W(max)")[2], "one listed port is not an all-ports figure")


class Fix2Identity(unittest.TestCase):
    @staticmethod
    def prod(handle, title, skus):
        return {"handle": handle, "title": title, "product_type": "Robot Vacuums", "variants": [{"sku": s} for s in skus]}

    def model_of(self, p):
        return p["title"]

    def test_sku_bridge_cannot_merge_incompatible_endpoints(self):
        ps = [self.prod("a", "L10s Ultra", ["S1"]), self.prod("b", "L10s Ultra Heat", ["S1", "S2"]), self.prod("c", "L10s Ultra Heat", ["S2"])]
        conf = []
        groups = RV.group(ps, self.model_of, lambda p: 0, conf)
        self.assertEqual(sorted(len(m) for _, _, m in groups), [1, 2], "A~B (SKU) and B~C never collapse A~C")
        self.assertEqual(conf[0]["sku"], "S1")

    def test_plus_and_rds_stay_distinct_complete_folds(self):
        ps = [self.prod("q", "Q7 Max", ["Q1"]), self.prod("qp", "Q7 Max+", ["Q1", "Q2"]), self.prod("s", "S8 MaxV Ultra", ["R1"]),
              self.prod("srds", "S8 MaxV Ultra RDS", ["R1", "R2"]), self.prod("x", "X50 Ultra", ["X1", "X2"]), self.prod("xc", "X50 Ultra Complete", ["X2"]),
              self.prod("xw", "X50 Ultra", ["X3"])]
        groups = {n: sorted(p["handle"] for p in m) for n, _, m in RV.group(ps, self.model_of, lambda p: len(p["title"]))}
        self.assertEqual(groups, {"Q7 Max": ["q"], "Q7 Max+": ["qp"], "S8 MaxV Ultra": ["s"], "S8 MaxV Ultra RDS": ["srds"],
                                  "X50 Ultra": ["x", "xc", "xw"]})

    def test_stored_bundle_members_are_corroborated(self):
        canon = self.prod("x", "X50 Ultra", ["X1"])
        prods = [canon, self.prod("xc", "X50 Ultra Complete", ["X1"]), self.prod("xh", "X50 Ultra Heat", ["X1"]), self.prod("xk", "X50 Ultra Complete", ["K9"])]
        kept, q = RV.corroborate(prods, canon, self.model_of)
        self.assertEqual([p["handle"] for p in kept], ["x", "xc"])
        self.assertEqual({x["handle"]: x["reason"][:20] for x in q}, {"xh": "model name disagrees", "xk": "pack listing without"})

    def test_iniu_p41_e1_and_ugreen_label_disagreements(self):
        iniu, ug = S.IniuPowerbanks.__new__(S.IniuPowerbanks), S.UgreenPowerbanks.__new__(S.UgreenPowerbanks)
        c, _ = S.identity_check(iniu, "P41", "P41", "iniu-p41-e1-power-bank-fast-charge-22-5w", {"variants": [{"sku": ""}]})
        self.assertEqual(c["reason"], "handle_disagrees")
        c, _ = S.identity_check(iniu, "P41", "P41", "iniu-p41-power-bank-45w", {"variants": [{"sku": "D01-P41-E2-BK-US"}]})
        self.assertEqual(c["reason"], "sku_disagrees")
        c, foreign = S.identity_check(iniu, "P55-E2", "P55-E2", "iniu-carry-p55-e2-power-bank", {"variants": [{"sku": "D01-P55-E2-BK-US"}, {"sku": "D01-P55L-E2-BK-US"}]})
        self.assertEqual((c, foreign), (None, ["D01-P55L-E2-BK-US"]), "another model's SKU is not an alias")
        c, _ = S.identity_check(ug, "75982", "75982SR", "ugreen-honkai-star-rail-10000mah", {"variants": [{"sku": "75982SR"}]})
        self.assertEqual(c["reason"], "edition_suffix", "an edition is not merged automatically")
        c, _ = S.identity_check(ug, "35524", "35524", "130w-usb-c-power-bank-cable", {"variants": [{"sku": "35524+70427P"}]})
        self.assertEqual(c["reason"], "bundle_skus")
        c, foreign = S.identity_check(ug, "75982", "75982", "magflow-air", {"variants": [{"sku": "75982"}, {"sku": "65839"}]})
        self.assertEqual((c, foreign), (None, []), "UGREEN colour item numbers stay typed aliases")
        c, _ = S.identity_check(ug, "PB571", "PB571", "ugreen-uno", {"variants": [{"sku": "35605"}]})
        self.assertIsNone(c, "PB label model + item numbers is the wanted mapping")


class Fix3Conditions(unittest.TestCase):
    def test_capacity_bases_stay_apart(self):
        self.assertEqual(P.rated("13500mAh(5V/6A)"), (13500, {"rated_voltage_v": 5, "rated_current_a": 6}), "5 V rating keeps its load")
        self.assertTrue(unresolved(P.rated("3000mAh (5V)")[0]), "no load printed")
        self.assertTrue(unresolved(P.rated("11600mAh(5V/9V/7A typical output)")[0]))
        self.assertTrue(unresolved(P.rated("20000mAh")[0]), "a rated row without basis never becomes cell mAh")
        self.assertTrue(unresolved(P.energy("74Wh/75.5Wh 7.4V")), "unlabelled dual Wh: no silent pick")
        # r7 (A2 coverage r2): a labelled pair keeps BOTH figures, each with its energy_basis condition
        self.assertEqual([x[:2] for x in P.energy("Rated energy: 74Wh / 75.5Wh typical")], [(74, {"energy_basis": "rated"}), (75.5, {"energy_basis": "typical"})])
        self.assertTrue(unresolved(P.energy("72Wh/73.44wh 14.4V")), "lowercase wh is still a second figure")
        self.assertEqual(P.energy("20000mAh/3.6V/72Wh"), 72)
        src = (ROOT / "crawler/adapters/anker_powerbanks.py").read_text()
        self.assertIn('add("cap.class_mah", P.mah(title)', src, "Anker title capacity is a class")
        self.assertNotIn('add("cap.cell_mah", P.mah(title)', src)
        prof = {s["key"]: s for s in yaml.safe_load((ROOT / "research/power-banks/spec-profile.yaml").read_text())["specs"]}
        self.assertEqual(prof["cap.rated_mah"]["basis_conditions"], ["rated_voltage_v", "rated_current_a"])
        self.assertNotIn("Belkin title", " ".join(prof["cap.cell_mah"]["sources"]))

    def test_all_port_vs_single_port_naming(self):
        prof = {s["key"]: s for s in yaml.safe_load((ROOT / "research/power-banks/spec-profile.yaml").read_text())["specs"]}
        self.assertEqual(prof["out.max_total_w"]["label"], "All-ports simultaneous output")
        self.assertEqual(prof["out.max_single_port_w"]["label"], "Best single-port output")
        self.assertNotIn("Belkin", " ".join(prof["out.max_total_w"]["sources"]))
        _, _, total, toks = P.ports_from("OUT1&OUT2: 5V3A 15V3A 45W(Max); OUT3: 5V3A 22.5W(Max); OUT1+OUT2: 15W(Max); Total(OUT1+OUT2+OUT3): 15W(Max)")
        self.assertEqual((total, toks), (15, ["OUT1", "OUT2", "OUT3"]), "15 W all-port and 45 W single-port stay distinct")

    def test_plausibility_rejection_and_mixed_cells_are_preview_evidence(self):
        self.assertTrue(unresolved(RV.robot_weight(14601)))
        self.assertEqual(RV.robot_weight(4200), 4200)
        d = RV.robot_dims({"length": 350, "width": 3400.8, "height": 79.8})
        self.assertTrue(unresolved(d)); self.assertIn("3400.8", d.reason)
        pr = C.ParseResult()
        RV.add(pr, "fx@1", SNAP, "S8", "phys.robot_weight_g", RV.robot_weight(14601), "Robot Weight 32.19 lbs", "Robot Weight")
        RV.add(pr, "fx@1", SNAP, "S8", "phys.robot_dimensions", RV.MIXED, "Robot&Dock Size 15.2 x 16.3 x 17.1 in", "Dimensions")
        self.assertEqual([(c["status"], c["raw"][:12], bool(c["quote"])) for c in pr.claims],
                         [("unknown", "Robot Weight", True), ("unknown", "Robot&Dock S", True)])

    def test_roborock_mixed_dimension_cell_is_kept(self):
        h = ('Specifications:<h3><span class="font-semibold">Dimensions: </span>Robot &amp; Dock: 15.2 x 16.3 x 17.1 inches</h3>'
             '<h3><span class="font-semibold">Robot Weight: </span>Robot &amp; Dock 32.19 lbs</h3>')
        b = {"html": h, "products": [{"handle": "s8", "title": "Roborock S8 MaxV Ultra", "product_type": "Robot Vacuums", "variants": [{"sku": "RR-S8MU0-M1"}]}]}
        snap = C.Snapshot("sha256:x", C.Ref("roborock-us-robovac", "s8", "https://us.roborock.com/products/s8", {}), 200, "t", "u", {})
        pr = RR.parse_bundle(snap, b)
        got = {c["key"]: c["status"] for c in pr.claims if c["key"].startswith("phys.robot")}
        self.assertEqual(got, {"phys.robot_dimensions": "unknown", "phys.robot_weight_g": "unknown"})


class Policies(unittest.TestCase):
    # r6: power banks re-issued as @5 (parser bump for the repeated-port-row fix); @4 joins the inert superseded set
    NEW = {"claim/mfr-robovac-structured@5", "claim/mfr-power-banks-structured@8", "claim/dcl-matter-certified@2",
           "claim/belkin-support-articles@1"}   # r7: power banks @5 -> @6; A2 preset fill: @6 -> @7; 2026-11-25: + Belkin support articles; 2026-11-26 r7 PPS: @7 -> @8
    OLD = {"claim/mfr-robovac-structured@2", "claim/mfr-robovac-structured@3", "claim/mfr-robovac-structured@4",
           "claim/mfr-power-banks-structured@2", "claim/mfr-power-banks-structured@3", "claim/mfr-power-banks-structured@4", "claim/mfr-power-banks-structured@5", "claim/mfr-power-banks-structured@6", "claim/mfr-power-banks-structured@7", "claim/dcl-matter-certified@1"}

    def test_consolidated_pending_policies_cover_every_current_extractor(self):
        dec = D.Decisions(ROOT / "data")
        pol = {p["id"]: p for p in dec.claim_policies}
        self.assertTrue(self.NEW <= set(pol))
        for i in self.NEW:
            a = pol[i]["approval"]; self.assertIn(a["state"], ("pending", "approved"), i); self.assertTrue(a["state"] == "pending" or (a.get("by") and a.get("at")), i)  # human-approved 2026-11-23
        cur = {registry.parser_info(s)["parser"] for s, m in registry.SOURCES.items() if m["category"] in ("robot-vacuums", "power-banks")}
        covered = {x for i in self.NEW for x in pol[i]["match"]["extractors"]}
        self.assertEqual(cur, covered, "every current robovac/power-bank extractor is under exactly the new policies")
        self.assertNotIn("smart.matter", pol["claim/mfr-robovac-structured@5"]["match"]["keys"]["dreame-us-robovac"])

    def test_superseded_active_policies_accept_nothing_now(self):
        dec = D.Decisions(ROOT / "data")
        cur = {registry.parser_info(s)["parser"] for s in registry.SOURCES}
        for p in dec.claim_policies:
            if p["id"] in self.OLD:
                self.assertFalse(set(p["match"]["extractors"]) & cur, f"{p['id']} still matches a live extractor")


class ReleaseStore(unittest.TestCase):
    """Reads the store import.py just wrote (release.sh runs import before the tests). Skipped when absent."""
    db = ROOT / "state" / "specsheet.sqlite"

    def setUp(self):
        if not self.db.exists():
            self.skipTest("no release store")
        self.con = sqlite3.connect(self.db)

    def test_page_conflicts_reviewable_and_ids_kept(self):
        rows = self.con.execute("SELECT value, entity_ids, reason FROM identity_conflicts WHERE category='power-banks' AND scheme='mfr_model'").fetchall()
        if not rows:
            self.skipTest("store predates review-3 import")
        by = {(v, json.loads(e)[0]): r for v, e, r in rows}
        self.assertTrue(any(k == ("P41", "iniu-p41") and "handle_disagrees" in r for k, r in by.items()), "P41-E1 page is reviewable")
        self.assertTrue(any(k == ("75982", "ugreen-75982") and "edition_suffix" in r for k, r in by.items()))
        ids = {json.loads(l)["id"] for l in (ROOT / "data/_ids/registry.jsonl").read_text().splitlines() if l.strip()}
        ents = {r[0] for r in self.con.execute("SELECT id FROM entities WHERE category IN ('power-banks','robot-vacuums')")}
        self.assertTrue({"iniu-p41", "ugreen-75982", "ugreen-75701", "ugreen-35524", "iniu-p73-e1"} <= ents & ids, "existing public ids survive")
        self.assertFalse({"iniu-p41-e1", "ugreen-75982sr"} & ids, "no id minted for a quarantined page")


if __name__ == "__main__":
    unittest.main()
