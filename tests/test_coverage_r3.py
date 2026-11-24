"""A2 coverage r3 (2026-11-24): bare DRAM-less, Kingston legacy datasheets, Ubiquiti spec tree, GL.iNet spec table, BenQ PWM/PD. Pure fixtures."""
import json, sys, unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "crawler" / "adapters"))
import _contract as C  # noqa: E402
import _ssdprose as SP  # noqa: E402
import kingston_ssd as K  # noqa: E402
import ubiquiti_routers as U  # noqa: E402
import glinet_routers as G  # noqa: E402
import benq_monitors as B  # noqa: E402


def snap(src, key, hints=None):
    return C.Snapshot("sha256:x", C.Ref(src, key, "https://example.invalid/" + key, hints or {}), 200, "t", "u", {})


def claims(pr):
    return {c["key"]: c["value"] for c in pr.claims}


class Dramless(unittest.TestCase):
    def test_bare_and_self_description(self):
        self.assertEqual(SP.extract("<p>It features advanced security, DRAM-less design, and efficient performance.</p>")["claims"]["hw.dram_type"][0], "dramless")
        r = SP.extract("<p>Built for handhelds, this DRAM-less drive provides up to 100% more power efficiency over the previous generation.</p>")
        self.assertEqual(r["claims"]["hw.dram_type"][0], "dramless")
        self.assertEqual(SP.extract("<p>This DRAM-less SSD supports Host Memory Buffer (HMB) for speed.</p>")["claims"]["hw.dram_type"][0], "dramless_hmb")
        self.assertEqual(SP.extract("<p>Compared to DRAM-less drives, the SN850X is equipped with DRAM cache.</p>")["claims"], {})


KLEG = """SPECIFICATIONS
Form Factor
M.2 2280
Interface
PCIe 4.0 x4 NVMe
Capacities2
250GB, 500GB
                                                                                                                    KINGSTON PART NUMBERS
Sequential Read/Write1
250GB – 3,000/1,300MB/s                 500GB – 3,500/2,100MB/s                                          SNV2S/250G
Endurance (Total Bytes Written)3                                                                                    SNV2S/500G
250GB – 80TB      500GB – 160TB
Warranty/Support4
Limited 3-year warranty with free technical support
1. Based on out-of-box performance.
"""


class KingstonLegacy(unittest.TestCase):
    def test_two_column_layout(self):
        pr = K.parse_text(snap("kingston-us-ssd", "SNV2S"), KLEG)
        got = {(c["locator"]["sku"], c["key"]): c["value"] for c in pr.claims}
        self.assertEqual((got[("SNV2S/250G", "perf.seq_write")], got[("SNV2S/500G", "perf.seq_read")]), (1300, 3500))
        self.assertEqual((got[("SNV2S/250G", "end.tbw")], got[("SNV2S/500G", "end.tbw")]), (80, 160))
        self.assertNotIn(("SNV2S/250G", "hw.dram_type"), got)


def ui_page(rows, name="UDR7"):
    labels, feats = {}, []
    for i, (par, lab, val) in enumerate(rows):
        pid = labels.setdefault(par, f"p-{par}") if par else None
        if par and not any(f["feature"]["id"] == pid for f in feats):
            feats.append({"feature": {"id": pid, "label": par, "parentId": None}})
        f = {"feature": {"id": f"f{i}", "label": lab, "parentId": pid}}
        f["value" if val not in ("True",) else "flag"] = val
        feats.append(f)
    pp = {"props": {"pageProps": {"product": {"name": name, "title": "Dream Router 7", "variants": [{"sku": name + "-US"}],
                                              "technicalSpecification": {"sections": [{"section": {"label": "S"}, "features": feats}]}}}}}
    return '<script id="__NEXT_DATA__" type="application/json">' + json.dumps(pp) + "</script>"


class Ubiquiti(unittest.TestCase):
    def test_band_rows_ports_poe(self):
        h = ui_page([("MIMO", "6 GHz", "2 x 2 (DL/UL MU-MIMO)"), ("MIMO", "5 GHz", "4 x 4 (DL/UL MU-MIMO)"), ("Max. Data Rate", "5 GHz", "4.3 Gbps (BW240)"),
                     ("Max. Data Rate", "6 GHz", "5.8 Gbps (BW320)"), (None, "Processor", "Quad-core ARM® Cortex®-A53 at 1.5 GHz"),
                     (None, "System Memory", "3 GB"), (None, "Default WAN Ports", "(1) 10G SFP+\n(1) 2.5 GbE RJ45"), (None, "Max. WAN Port Count", "4"),
                     ("Port Layout", "2.5 GbE RJ45", "4 (1 PoE)\n(2.5G/1G)"), ("Port Layout", "10G SFP+", "1\n(10G/1G)"), ("Port Layout", "Console", "1"),
                     (None, "PoE Budget", "15.4W")])
        c = claims(U.parse_html(snap("ubiquiti-us-routers", "udr7", {"device_type": "router", "category": "cloud-gateways"}), h))
        self.assertEqual((c["wifi.streams_5"], c["wifi.streams_6"], c["wifi.max_width_5_mhz"], c["wifi.max_width_6_mhz"]), (4, 2, "240", "320"))
        self.assertEqual((c["hw.cpu_cores"], c["hw.ram_mb"], c["port.lan_count"], c["port.wan_speed_mbps"]), (4, 3072, 3, 10000))
        self.assertNotIn("hw.soc_model", c, "Cortex-A53 is a CPU core, not a SoC")
        self.assertTrue(c["port.poe"].startswith("PoE out, 15.4W budget"))


class Glinet(unittest.TestCase):
    def test_spec_table_not_comparison(self):
        h = ('<table><tr><th>CPU</th><td>IPQ4018</td><td>MT7981B</td></tr></table><h2 class="x">Specifications</h2><table class="table">'
             '<tr><td class="td-left">CPU</td><td class="td-right">MediaTek Quad-core, @2.0 GHz</td></tr>'
             '<tr><td class="td-left">Memory / Storage</td><td class="td-right">DDR4 1GB / eMMC 8GB</td></tr>'
             '<tr><td class="td-left">Wi-Fi Speed</td><td class="td-right">688Mbps (2.4GHz), 2882Mbps (5GHz), 5765Mbps (6GHz)</td></tr></table>')
        c = claims(G.parse_html(snap("glinet-us-routers", "gl-be9300", {"title": "Flint 3 (GL-BE9300) Router", "product_type": "Home Router"}), h))
        self.assertEqual((c["hw.soc_vendor"], c["hw.ram_mb"], c["hw.flash_mb"], c["wifi.rate_6_mbps"]), ("mediatek", 1024, 8192, 5765))
        self.assertNotIn("hw.soc_model", c)


def benq_page(rows):
    blk = "".join(f'<li class="item"><div class="name">{n}</div><div class="detail">{d}</div></li>' for n, d in rows)
    return ('<p style="display: none;">localNavigation.type = g6-product-spec-page</p><p>PD2706U</p>'
            f'<div class="spec-container"><p class="category">All</p>{blk}</div>')


class Benq(unittest.TestCase):
    def test_flicker_and_pd(self):
        c = claims(B.parse_html(snap("benq-us-monitors", "pd2706u"), benq_page([("Flicker-free Technology", "Yes"), ("Power Delivery(USB C / Thunderbolt )", "90"),
                                                                                   ("USB Type-C Downstream (USB 3.2 Gen 1, 5 Gbps, power charging 15W)", "1")])))
        self.assertEqual((c["flk.pwm"], c["usb.usbc_pd_w"]), ("none", 90))
        c = claims(B.parse_html(snap("benq-us-monitors", "x"), benq_page([("Flicker-free Technology", "No"), ("Power Delivery(USB C / Thunderbolt )", "35W / 96W")])))
        self.assertNotIn("flk.pwm", c); self.assertNotIn("usb.usbc_pd_w", c)


if __name__ == "__main__":
    unittest.main()
