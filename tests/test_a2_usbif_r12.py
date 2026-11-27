"""A2-usbif r12: USB-IF certified-product overlay (scripts/usbif.py, crawler/adapters/usbif_products.py). Pure fixtures, no network.

  python3 -I tests/test_a2_usbif_r12.py
"""
import collections, sys, unittest
from pathlib import Path

CODE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(CODE / "crawler" / "adapters"))
sys.path.insert(0, str(CODE / "scripts"))
import identity as I  # noqa: E402
import usbif as U  # noqa: E402
import yaml  # noqa: E402

REC = {"snapshot": "sha256:" + "0" * 64, "fetched_at": "2026-11-26T00:00:00Z"}


def row(**kw):
    r = {"id": "1", "name": "", "field_usb_model_part_number": "", "field_device_status": "Pass", "device_tid": "1000081",
         "device_company_view_field": "Nekteck, Inc.", "field_device_category": "", "field_cable_marketing_category": "",
         "field_usb_cable_max_speed": "", "field_pd_silicon_and_brick_marke_1": "Power Brick", "global_pass_date": "2017-09-06T00:00:00"}
    r.update(kw)
    return r


class Ent:
    def __init__(self, category, brand, model, scheme="mfr_model"):
        self.category, self.brand, self.kind = category, brand, "model"
        v = I.norm_value(scheme, model, brand)
        self.idents = {(scheme, v): {"scheme": scheme, "value": v, "valid": True, "role": "key"}}
        self.keys = {(scheme, v)}
        self.claims, self.srcs, self.obs = [], {}, set()


class World:
    def __init__(self, category, ents):
        self.category, self.ents = category, ents

    def anchors(self, keys):
        return sorted(map(str, keys))


def run(rows, ents):
    worlds = collections.defaultdict(list)
    for e in ents:
        worlds[e.category].append(e)
    worlds = {c: World(c, es) for c, es in worlds.items()}
    events = []
    st = U.apply(worlds, events, collections.Counter(), rows=rows, rec=REC)
    return st, events


def keys(e):
    return {c["key"]: c for c, _ in e.claims}


class Overlay(unittest.TestCase):
    def test_exact_maker_model_binds_all_four_keys(self):
        e = Ent("chargers", "nekteck", "NK-CC-PD45W")
        st, ev = run([row(field_usb_model_part_number="NK-CC-PD45W", name="USB-C PD 45W &amp; USB-A 12W Car Charger")], [e])
        k = keys(e)
        self.assertEqual(set(k), set(U.KEYS))
        self.assertIs(k["cert.usb_if"]["value"], True)
        self.assertEqual((k["cert.usb_if_tid"]["value"], k["cert.usb_if_date"]["value"], k["cert.usb_if_product_type"]["value"]),
                         ("1000081", "2017-09-06", "power_brick"))
        self.assertEqual({c["method"]["extractor"] for c, _ in e.claims}, {U.EXTRACTOR})
        (snap, src), = e.srcs.items()
        self.assertEqual(src["tier"], "certifier")
        self.assertTrue(src["url"].startswith("https://www.usb.org/") and snap.endswith("#tid=1000081"))
        self.assertEqual({ob for _, ob in e.claims}, {(U.SOURCE_ID, "tid:1000081", snap)})
        self.assertEqual([x[0] for x in ev], ["usbif_attach"])

    def test_no_prefix_or_stem_match(self):
        e = Ent("chargers", "nekteck", "NK-CC-PD45W")
        for pn in ("NK-CC-PD45", "NK-CC-PD45W-B", "NKCCPD45W2"):
            run([row(field_usb_model_part_number=pn)], [e])
        self.assertEqual(e.claims, [])

    def test_oem_listing_is_proposal_only(self):
        e = Ent("chargers", "belkin", "WCA008")
        st, ev = run([row(device_company_view_field="Channel Well Technology Co., Ltd", field_usb_model_part_number="WCA008",
                          name="30W USB-C PD Cube Wall Charger with PPS")], [e])
        self.assertEqual(e.claims, [])
        self.assertEqual([(x[0], x[5]["reason"]) for x in ev], [("usbif_proposal", "oem_listing")])

    def test_product_type_must_match_category(self):
        e = Ent("chargers", "ugreen", "CD241")
        st, ev = run([row(device_company_view_field="Ugreen Group Limited", field_usb_model_part_number="CD241",
                          field_pd_silicon_and_brick_marke_1="", field_cable_marketing_category="Cable Assembly &gt;USB-C to USB-C")], [e])
        self.assertEqual(e.claims, [])
        self.assertEqual(ev[0][5]["reason"], "type_mismatch")

    def test_obsolete_or_no_tid_attaches_nothing_and_never_false(self):
        e = Ent("chargers", "nekteck", "NK-CC-PD45W")
        run([row(field_usb_model_part_number="NK-CC-PD45W", field_device_status="Obsolete"),
             row(field_usb_model_part_number="NK-CC-PD45W", device_tid="")], [e])
        self.assertEqual(e.claims, [])
        f = Ent("power-banks", "nekteck", "NK-PB1")
        run([], [f])
        self.assertFalse(any(c.get("value") is False for c, _ in f.claims))

    def test_name_cell_only_when_part_number_empty_and_a_model_list(self):
        self.assertEqual([t for t, _ in U.tokens(row(name="RJ-4250WB, RJ-4230B"))], ["RJ-4250WB", "RJ-4230B"])
        self.assertEqual(U.tokens(row(name="USB-C PD 45W Car Charger")), [])
        self.assertEqual([t for t, _ in U.tokens(row(field_usb_model_part_number="USB 2.0 TYPE C-C 5A 4M with E-mark, PN:TC-C2C-20-4M"))],
                         ["TC-C2C-20-4M"])

    def test_two_tids_keep_only_cert_flag(self):
        e = Ent("chargers", "nekteck", "NK-CC-PD45W")
        run([row(field_usb_model_part_number="NK-CC-PD45W"), row(id="2", device_tid="1000099", field_usb_model_part_number="NK-CC-PD45W")], [e])
        self.assertEqual({c["key"] for c, _ in e.claims}, {"cert.usb_if"})
        self.assertEqual(len(e.srcs), 2)

    def test_profiles_carry_the_keys(self):
        for cat in U.CATEGORY_TYPES:
            prof = yaml.safe_load((CODE / "research" / cat / "spec-profile.yaml").read_text())
            have = {s["key"]: s for s in prof["specs"]}
            self.assertTrue(set(U.KEYS) <= set(have), cat)
            self.assertEqual(set(have["cert.usb_if_product_type"]["enum"]) >= set(U.CATEGORY_TYPES.values()), True)

    def test_policy_invariant(self):
        pol = yaml.safe_load((CODE / "data" / "decisions" / "policies.yaml").read_text())
        ps = [p for p in pol.get("claim_policies", []) if U.EXTRACTOR in ((p.get("match") or {}).get("extractors") or [])]
        for p in ps:
            self.assertEqual(p["match"]["source_ids"], [U.SOURCE_ID])
            self.assertTrue(set(p["match"]["keys"]) <= set(U.KEYS))
            a = p.get("approval") or {}
            self.assertTrue(a.get("state") == "pending" or (a.get("state") == "approved" and a.get("by") and a.get("at")), p["id"])

    def test_source_policy_lists_usb_org(self):
        import source_policy
        self.assertEqual(source_policy.load().crawl("https://www.usb.org/vtm-products/v1/all"), "agent")


if __name__ == "__main__":
    unittest.main()
