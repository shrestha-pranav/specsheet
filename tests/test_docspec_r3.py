#!/usr/bin/env python3
"""docspec r3 (2026-11-25): docspec-tv@1 / docspec-router@1 / docspec-laptop@1 cell rules and docspec-attach-r3@1 identity binding.
Per category: one corroborating claim, one new fill, one wrong-model document that must not attach."""
import importlib, json, sys, tempfile, unittest
from pathlib import Path

CODE = Path(__file__).resolve().parent.parent
sys.path[:0] = [str(CODE / "scripts"), str(CODE / "crawler"), str(CODE / "crawler" / "adapters")]
import documents as D  # noqa: E402
import _docspec_tv as TV  # noqa: E402
import _docspec_router as RT  # noqa: E402
import _docspec_laptop as LP  # noqa: E402
import docspec_r3 as R3  # noqa: E402


def doc(*lines):
    return {"pages": [{"n": 1, "text": "\n".join(lines), "blocks": [], "method": "text_layer"}]}


def kv(facts):
    return {f["key"]: f["value"] for f in facts}


class Cells(unittest.TestCase):
    def test_tv(self):
        x11l = kv(TV.tv(doc("                     HDMI                                   4x HDMI 2.1 (4K@144HZ), HDMI4 with EARC",
                             "Backlight Type                      SQD-Mini LED with Halo Control System",
                             "Native Panel Refresh Rate                              144Hz",
                             "Panel Type                                     WHVA 2.0 Ultra Panel")))
        self.assertEqual(x11l, {"hdmi.count": 4, "hdmi.earc": True, "hdmi.has_4k120": True, "hdmi.ports_4k120": 4, "panel.backlight": "mini_led",
                                "refresh.native_hz": 144})                  # WHVA is a brand name: no lcd_type
        # LG three-column line: the pair is found mid-line
        self.assertEqual(kv(TV.tv(doc("  Simplink (HDMI CEC)        •          HDMI                 3 (HDCP 2.2)"))), {"hdmi.count": 3})
        self.assertEqual(kv(TV.tv(doc("  TruMotion 120 (Refresh Rate 60Hz)        Yes          USB      2"))), {"refresh.native_hz": 60})
        self.assertEqual(kv(TV.tv(doc("   IPS Panel                       •"))), {"panel.lcd_type": "ips"})
        # nothing: HDMI 2.1 without a 4K120 figure, per-size columns, a size qualifier, marketing-only refresh, prose, mixed versions
        self.assertEqual(kv(TV.tv(doc("HDMI        4 (HDMI 2.1)"))), {"hdmi.count": 4})
        self.assertEqual(TV.tv(doc("HDMI      3      3      4")), [])
        self.assertEqual(TV.tv(doc('HDMI      98": TBD')), [])
        self.assertEqual(TV.tv(doc("   TruMotion 240Hz                 •")), [])
        self.assertEqual(TV.tv(doc("The HDMI 2.1 port supports 4K@120Hz gaming on select models.")), [])
        self.assertNotIn("hdmi.ports_4k120", kv(TV.tv(doc("HDMI     2x HDMI 2.1 (4K@120Hz), 2x HDMI 2.0"))))
        self.assertEqual(TV.tv(doc("Panel Refresh      60Hz", "Panel Refresh      120Hz")), [])        # two values in one document
        self.assertEqual(TV.tv(doc("VRR      No")), [])

    def test_router(self):
        self.assertEqual(kv(RT.router(doc("WiFi Standard        WiFi 7 (802.11be)", "Bands        Tri-band 2.4GHz / 5GHz / 6GHz",
                                          "WAN Port        1x 10 Gigabit Ethernet", "LAN Ports        4 x 2.5G Ethernet"))),
                         {"wifi.generation": "wifi7", "wifi.band_count": 3, "wifi.has_6ghz": True, "port.wan_speed_mbps": 10000, "port.lan_count": 4})
        self.assertEqual(RT.router(doc("WiFi Standard      802.11ax 2.4/5/6 GHz")), [{"key": "wifi.has_6ghz", "value": True, "raw": "802.11ax 2.4/5/6 GHz",
                                                                                 "quote": "WiFi Standard 802.11ax 2.4/5/6 GHz", "page": 1, "ocr": False, "ocr_conf": None}])
        self.assertEqual(RT.router(doc("WAN Port      2.5G and 10G")), [])
        self.assertEqual(RT.router(doc("Experience blazing WiFi 7 speeds across your whole home.")), [])

    def test_laptop(self):
        self.assertEqual(kv(LP.laptop(doc("Memory Slots        Two DDR5 SO-DIMM slots", "Max Memory        Up to 64GB DDR5-5600"))),
                         {"mem.slots": {"total": 2}, "mem.max": 64.0})
        self.assertEqual(kv(LP.laptop(doc("Memory        16GB LPDDR5x soldered, no slots"))), {"mem.soldered": "soldered"})
        self.assertEqual(kv(LP.laptop(doc("Memory        8GB soldered + one DDR5 SO-DIMM slot"))), {"mem.soldered": "mixed"})
        self.assertEqual(LP.laptop(doc("Memory        16GB DDR5 on board, Max Capacity: 32GB")), [])     # ASUS trap: a free slot is possible
        self.assertEqual(LP.laptop(doc("Max Memory    Arrow Lake: up to 64GB; Meteor Lake: up to 32GB")), [])
        self.assertEqual(kv(LP.laptop(doc("Power Delivery     USB-C PD charging up to 100W"))), {"pwr.max_pd_in": 100.0})
        self.assertEqual(LP.laptop(doc("Power Delivery     USB-C PD output up to 15W")), [])


SHEETS = {
    "tvs": (doc("75X11L   85X11L   98X11L", "      HDMI           4x HDMI 2.1 (4K@144HZ), HDMI4 with EARC"), "hdmi.count", 4, "hdmi.has_4k120"),
    "routers": (doc("Model: RS700", "WiFi Standard        WiFi 7 (802.11be)", "Bands        Tri-band"), "wifi.band_count", 3, "wifi.generation"),
    "laptops": (doc("Model 82XV0001US", "Memory Slots        Two DDR5 SO-DIMM slots", "Max Memory        Up to 64GB"), "mem.max", 64.0, "mem.slots"),
}
MODELS = {"tvs": ("75X11L", "85X11L", "65QM7K"), "routers": ("RS700", None, "RS300"), "laptops": ("82XV0001US", None, "82XW0002US")}


class Attach(unittest.TestCase):
    def setUp(self):
        self.imp = importlib.import_module("import")

    def world(self, cat, models, corroborate):
        class Dec:
            def merge_allowed(self, a):
                return False
        w = self.imp.World(cat, Dec(), [], {})
        ents = {}
        for m in models:
            ref = m.lower()
            ob = ("maker-" + cat, ref, "sha256:p" + ref)
            e = w.get("model", "acme", [self.imp.K("mfr_model", m, "acme", "model")], ob)
            e.obs.add(ob)
            e.srcs.setdefault(ob[2], {"url": f"https://acme.example/{ref}", "tier": "manufacturer", "label": "page", "snapshot": ob[2], "retrieved_at": None})
            key, val = corroborate
            e.claims.append(({"key": key, "status": "known", "kind": "official", "value": val}, ob))
            self.imp.add_ident(e, {"scheme": "mfr_model", "value": m}, role="key", level="model")
            ents[m] = e
        return w, ents

    def store(self, cat, d, refs):
        tmp = Path(tempfile.mkdtemp())
        (tmp / "text").mkdir()
        url = f"https://acme.example/docs/{cat}.pdf"
        (tmp / "text" / f"{1:064x}.json").write_text(json.dumps(d))
        found = [{"source_id": "maker-" + cat, "ref": r, "page_url": f"https://acme.example/{r}", "category": cat} for r in refs]
        (tmp / "discovery.json").write_text(json.dumps({"docs": [{"url": url, "norm_url": D.norm_url(url), "kind": "spec_sheet", "categories": [cat],
                                                                  "link_text": "spec sheet", "decision": "fetch", "found_on": found}]}))
        (tmp / "snapshots.jsonl").write_text(json.dumps({"snapshot": f"sha256:{1:064x}", "ref": D.norm_url(url), "url": url, "status": 200,
                                                         "blob": "blobs/1.pdf", "fetched_at": "2026-11-25T00:00:00Z"}) + "\n")
        return tmp

    def test_corroborate_fill_and_wrong_model(self):
        for cat, (d, ckey, cval, fillkey) in SHEETS.items():
            with self.subTest(cat=cat):
                own, sib, wrong = MODELS[cat]
                models = [m for m in (own, sib, wrong) if m]
                w, ents = self.world(cat, models, (ckey, cval))
                tmp = self.store(cat, d, [m.lower() for m in models])          # the sheet is linked from every page, incl. the wrong model's
                ev, st = [], R3.apply({cat: w}, [], {}, root=tmp)
                got = {c["key"]: c for c, ob in ents[own].claims if ob[0] == R3.SOURCE_ID}
                self.assertEqual(got[ckey]["value"], cval)                     # corroborates the page value
                self.assertIn(fillkey, got)                                    # new fill (no page value for this key)
                self.assertEqual(got[ckey]["locator"]["identifiers"], [own])
                self.assertEqual(got[ckey]["method"]["extractor"], R3.extractor(cat))
                self.assertEqual(got[ckey]["conditions"]["identity_scope"], "document")
                self.assertFalse([c for c, ob in ents[wrong].claims if ob[0] == R3.SOURCE_ID])      # not named: never attaches
                self.assertGreaterEqual(st["r3_proposal_model_not_named"], 1)

    def test_unlinked_same_brand_model_blocks(self):
        d = doc("75X11L   65QM7K", "      HDMI           4x HDMI 2.1 (4K@144HZ)")
        w, ents = self.world("tvs", ["75X11L", "65QM7K"], ("hdmi.count", 4))
        tmp = self.store("tvs", d, ["75x11l"])                                 # 65QM7K is named but its page does not link the sheet
        ev = []
        st = R3.apply({"tvs": w}, ev, {}, root=tmp)
        self.assertEqual(st["r3_proposal_multi_model"], 1)
        self.assertFalse([c for c, ob in ents["75X11L"].claims if ob[0] == R3.SOURCE_ID])


if __name__ == "__main__":
    unittest.main()
