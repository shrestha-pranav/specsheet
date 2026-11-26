#!/usr/bin/env python3
"""A3-fix (2026-11-26): Codex review-9 counterexamples (reviews/2026-11-26-astra-review-9.md), one class per finding.
P1-1 TV per-port counts need a complete independent inventory, never transfer across a shared guide; P1-2 SFC 2.0 -> PPS only from an
affirmative own-product output sentence; P1-3 UPS trailing bounds / between-ranges / lower bounds / unsupported qualifiers;
P2 Dell connector-unknown USB entry; P2 naming binding veto + '1,024GB'; P2 AOC absence-based native refresh withheld."""
import gzip, importlib, importlib.util, json, sys, tempfile, unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "scripts"), str(ROOT / "crawler"), str(ROOT / "crawler" / "adapters")]
import documents as D  # noqa: E402
import _contract as C  # noqa: E402
import _docspec_tvports as TP  # noqa: E402
import docspec_r7tv as R7TV  # noqa: E402
import pb_pps_r7 as PPS  # noqa: E402
import _powerstation as PS  # noqa: E402
import dell as DL  # noqa: E402
import aoc_monitors as AOC  # noqa: E402

SNAP = C.Snapshot("sha256:x", C.Ref("x", "r", "https://x", {}), 200, "2026-11-26T00:00:00Z", "https://x", {})
FOUR = "HDMI ports 1 & 2: Supports up to 4K/144Hz\nHDMI ports 3 & 4: Supports up to 4K/60Hz"


TRUST_ALL = lambda cat, e, c, ob: True       # review-10: the inventory must be trusted; these fixtures exercise the @2 rules with every count trusted


def tdoc(text):
    return {"pages": [{"n": 3, "text": text, "blocks": [], "method": "text_layer"}]}


class TvPortsParser(unittest.TestCase):
    def test_unparsed_statement_voids_list(self):
        # review repro: ports 1-2 explicitly 60 Hz, port 3 stated in a form the rate pattern does not read -> nothing (not 0)
        t = "HDMI ports 1 & 2: Supports up to 4K/60Hz\nHDMI port 3: Supports 4K@120Hz with VRR"
        self.assertEqual(TP.tv(tdoc(t)), [])
        self.assertEqual(TP.tv(tdoc(FOUR + "\nHDMI port 4: eARC")), [])

    def test_facts_carry_stated_port_count(self):
        f = TP.tv(tdoc(FOUR))
        self.assertEqual({(x["key"], x["value"], x["n_ports"]) for x in f}, {("hdmi.ports_4k120", 2, 4), ("hdmi.has_4k120", True, 4)})


class TvPortsTransform(unittest.TestCase):
    def setUp(self):
        self.imp = importlib.import_module("import")

    def world(self, models, counts):
        class Dec:
            def merge_allowed(self, a):
                return False
        w = self.imp.World("tvs", Dec(), [], {})
        ents = {}
        for m in models:
            ref = m.lower()
            ob = ("maker-tvs", ref, "sha256:p" + ref)
            e = w.get("model", "acme", [self.imp.K("mfr_model", m, "acme", "model")], ob)
            e.obs.add(ob)
            e.srcs.setdefault(ob[2], {"url": f"https://acme.example/{ref}", "tier": "manufacturer", "label": "page", "snapshot": ob[2], "retrieved_at": None})
            for n in counts.get(m, []):
                e.claims.append(({"key": "hdmi.count", "status": "known", "kind": "official", "value": n}, ob))
            self.imp.add_ident(e, {"scheme": "mfr_model", "value": m}, role="key", level="model")
            ents[m] = e
        return w, ents

    def store(self, d, refs):
        tmp = Path(tempfile.mkdtemp())
        (tmp / "text").mkdir()
        url = "https://acme.example/docs/qsg.pdf"
        (tmp / "text" / f"{7:064x}.json").write_text(json.dumps(d))
        found = [{"source_id": "maker-tvs", "ref": r, "page_url": f"https://acme.example/{r}", "category": "tvs"} for r in refs]
        (tmp / "discovery.json").write_text(json.dumps({"docs": [{"url": url, "norm_url": D.norm_url(url), "kind": "quick_start", "categories": ["tvs"],
                                                                  "link_text": "quick start guide", "decision": "fetch", "found_on": found}]}))
        (tmp / "snapshots.jsonl").write_text(json.dumps({"snapshot": f"sha256:{7:064x}", "ref": D.norm_url(url), "url": url, "status": 200,
                                                         "blob": "blobs/7.pdf", "fetched_at": "2026-11-26T00:00:00Z"}) + "\n")
        return tmp

    def got(self, e):
        return {c["key"]: c["value"] for c, ob in e.claims if ob[0] == R7TV.SOURCE_ID}

    def test_complete_inventory_emits(self):
        w, ents = self.world(["85QM7K"], {"85QM7K": [4]})
        R7TV.apply({"tvs": w}, [], {}, trusted=TRUST_ALL, root=self.store(tdoc("85QM7K\n" + FOUR), ["85qm7k"]))
        self.assertEqual(self.got(ents["85QM7K"]), {"hdmi.ports_4k120": 2, "hdmi.has_4k120": True})

    def test_partial_prefix_emits_nothing_not_even_zero(self):
        prefix = "85QM7K\nHDMI ports 1 & 2: Supports up to 4K/60Hz"           # 2 of the model's 4 ports
        for counts in ({"85QM7K": [4]}, {}, {"85QM7K": [4, 3]}):              # inventory 4, none, conflicting
            w, ents = self.world(["85QM7K"], counts)
            st = R7TV.apply({"tvs": w}, [], {}, trusted=TRUST_ALL, root=self.store(tdoc(prefix + "\nHDMI port 3: Supports up to 4K/60Hz"), ["85qm7k"]))
            self.assertEqual(self.got(ents["85QM7K"]), {}, counts)
            self.assertEqual(st["r7ports_no_complete_inventory"], 1)
        w, ents = self.world(["85QM7K"], {})                                   # complete-looking list, no independent inventory
        R7TV.apply({"tvs": w}, [], {}, trusted=TRUST_ALL, root=self.store(tdoc("85QM7K\n" + FOUR), ["85qm7k"]))
        self.assertEqual(self.got(ents["85QM7K"]), {})

    def test_shared_guide_never_transfers(self):
        # one guide linked from both sizes' pages and naming both: @1 exempted linked models; @2 gives nothing to either
        w, ents = self.world(["85QM7K", "98QM7K"], {"85QM7K": [4], "98QM7K": [4]})
        ev = []
        st = R7TV.apply({"tvs": w}, ev, {}, trusted=TRUST_ALL, root=self.store(tdoc("85QM7K 98QM7K\n" + FOUR), ["85qm7k", "98qm7k"]))
        self.assertEqual((self.got(ents["85QM7K"]), self.got(ents["98QM7K"])), ({}, {}))
        self.assertEqual(st["r7ports_proposal_multi_model"], 2)

    def test_series_token_does_not_bind_a_size(self):
        w, ents = self.world(["85QM7K"], {"85QM7K": [4]})
        R7TV.apply({"tvs": w}, [], {}, trusted=TRUST_ALL, root=self.store(tdoc("QM7K Series\n" + FOUR), ["85qm7k"]))
        self.assertEqual(self.got(ents["85QM7K"]), {})


class Sfc2Pps(unittest.TestCase):
    def test_review_counterexamples_emit_nothing(self):
        for s in ("Samsung Super Fast Charging 2.0 is not supported.",
                  "Does this power bank support Samsung Super Fast Charging 2.0?",
                  "Recharge using a Samsung Super Fast Charging 2.0 adapter.",
                  "Our other model P99 supports Samsung Super Fast Charging 2.0.",
                  "The P88 supports Samsung Super Fast Charging 2.0.",
                  "Q: Samsung Super Fast Charging 2.0 compatible",
                  "Charge the power bank with a 45W max for Samsung wall charger."):
            self.assertIsNone(PPS.sfc2(s, "P73"), s)

    def test_own_output_statement_kept_derived(self):
        self.assertTrue(PPS.sfc2("It also supports Samsung Super Fast Charging 2.0.", "P73"))
        self.assertTrue(PPS.sfc2("The P73 supports Samsung Super Fast Charging 2.0 for Galaxy S25.", "P73"))
        self.assertTrue(PPS.sfc2("Only the USB-C port / cable supports 40W max output for iPhone 17 Series and 45W max for Samsung", "A1638"))
        pr = C.ParseResult()
        PPS.add_derived(pr, "iniu_powerbanks@7", SNAP, "P73", "It also supports Samsung Super Fast Charging 2.0")
        c = [x for x in pr.claims if x["key"] == "pd.pps"]
        self.assertEqual((len(c), c[0]["kind"], c[0]["value"], c[0]["conditions"]), (1, "derived", True, {"basis": "derived"}))
        self.assertFalse([x for x in pr.claims if x["key"] != "pd.pps"])                        # no invented PPS range


def ups_row(v, label="UPS Switchover Time"):
    pr = C.ParseResult()
    PS.emit_rows(pr, "x@1", SNAP, "Explorer 1000", {label: v}, "spec")
    return [(c.get("value"), c["status"]) for c in pr.claims if c["key"] == "ups.switchover_ms"]


def ups_prose(sent):
    return PS.ups_prose(f"<p>{sent}</p>", ("Explorer 1000",))[0]


class UpsQualifiers(unittest.TestCase):
    def test_trailing_upper_bounds_keep_up_to(self):
        for v in ("20 ms maximum", "20ms max", "20 ms or less", "20 ms or below", "20 ms at most"):
            self.assertEqual(ups_row(v), [("up to 20", "known")], v)
            self.assertEqual(ups_prose(f"UPS switchover {v}."), "up to 20", v)

    def test_ranges_never_endpoints(self):
        for v in ("between 10 and 20 ms", "from 10 to 20 ms", "10/20 ms", "10 or 20 ms"):
            got = ups_row(v)
            self.assertTrue(got and all(st != "known" for _, st in got), (v, got))
            self.assertIsNone(ups_prose(f"UPS switchover {v}."), v)

    def test_lower_bounds_never_exact(self):
        for v in ("≥20 ms", ">=20ms", ">20 ms", "at least 20 ms", "20 ms or more", "20ms+", "20 ms minimum", "min. 20 ms"):
            got = ups_row(v)
            self.assertTrue(got and all(st != "known" for _, st in got), (v, got))
            self.assertIsNone(ups_prose(f"UPS switchover {v}."), v)

    def test_unsupported_qualifiers_write_no_value(self):
        for v in ("~20ms", "approx. 20 ms", "about 20 ms", "20 ms (typical)", "±20ms"):
            got = ups_row(v)
            self.assertTrue(all(st != "known" for _, st in got), (v, got))
            self.assertIsNone(ups_prose(f"UPS switchover {v}."), v)

    def test_exact_and_leading_bounds_unchanged(self):
        self.assertEqual(ups_row("20ms"), [(20, "known")])
        self.assertEqual(ups_row("＜20ms, Online UPS: 0ms"), [("up to 20", "known")])
        self.assertEqual(ups_prose("Explorer 1000 UPS switchover 20ms."), 20)


class DellConnector(unittest.TestCase):
    def test_connector_unknown_usb_keeps_literal(self):
        lines = ["1 Thunderbolt 4 port with Power Delivery and DisplayPort", "1 USB 3.2 Gen 1 (5 Gbps) port", "1 HDMI 2.1 port"]
        self.assertFalse(DL.connectors_stated(lines))
        self.assertTrue(DL.connectors_stated(["1 Thunderbolt 4 port with Power Delivery and DisplayPort", "1 USB 3.2 Gen 1 Type-A port"]))
        self.assertTrue(DL.connectors_stated(["2 USB 3.2 Gen 2 Type-C ports with DisplayPort", "1 headset jack"]))


_spec = importlib.util.spec_from_file_location("specsheet_import_r9", ROOT / "scripts" / "import.py")
IMP = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(IMP)


class Naming(unittest.TestCase):
    def test_foreign_binding_vetoes_textual_match(self):
        pr = {"aliases": [{"kind": "marketing_name", "text": "WD_BLACK SN850X WDS100T2X0E 1TB", "sku": "WDS200T2X0E"}],
              "claims": [], "identifiers": []}
        self.assertIsNone(IMP.own_alias(pr, "WDS100T2X0E"))

    def test_grouped_capacity(self):
        self.assertEqual(IMP._strip_caps("SSD 1,024GB"), "SSD")
        self.assertEqual(IMP._caps("SSD 1,024GB"), {1024.0})
        self.assertEqual(IMP._caps("500GB / 2TB"), {500.0, 2000.0})


class AocNative(unittest.TestCase):
    def page(self, row):
        ld = json.dumps({"@type": "Product", "model": "Q27G40", "name": "AOC Q27G40"})
        return (f'<title>Q27G40</title><script type="application/ld+json">{ld}</script>'
                '<div class="accordion__section-button-title"><h3>Display</h3></div>'
                f'<div class="product-specification__label"><span class="subtitle">Max Refresh rate</span></div>'
                f'<div class="product-specification__value"><span>{row}</span></div></div>')

    def claims(self, row):
        snap = C.Snapshot("sha256:x", C.Ref(AOC.SOURCE, "q27g40", "https://www.aoc.com/us/monitors/q27g40", {}), 200, "t", "https://x", {})
        return {c["key"]: c["value"] for c in AOC.parse_html(snap, self.page(row)).claims}

    def test_plain_row_no_absence_native(self):
        got = self.claims("180 Hz")
        self.assertEqual(got.get("res.refresh_max"), 180)
        self.assertNotIn("res.refresh_native", got)

    def test_explicit_native_kept(self):
        self.assertEqual(self.claims("260Hz (OC, 240Hz Native)").get("res.refresh_native"), 240)


if __name__ == "__main__":
    unittest.main()
