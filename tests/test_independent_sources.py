"""A2 independent sources (2026-11-25, brief pm-2026-11-25-independent-sources-a2.md): Belkin support articles, Lenovo datasheets,
Notebookcheck review boxes. Pure fixtures (no network). The TÜV 5-star rule itself is tested in tests/test_source_policy.py (TestTuvRule).

  python3 -I tests/test_independent_sources.py
"""
import sys, unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "crawler" / "adapters"))
import _contract as C  # noqa: E402
import belkin_support as B  # noqa: E402
import lenovo_datasheets as LD  # noqa: E402
import notebookcheck_reviews as N  # noqa: E402


def snap(source, key, url, hints):
    return C.Snapshot("sha256:x", C.Ref(source, key, url, hints), 200, "2026-11-25T00:00:00Z", url, {})


def belkin(title, body, model):
    h = f"<html><head><title>Belkin Official Support - {title}</title></head><body><nav>Power Bank 45W max USB-C</nav><h1>{title}</h1>{body}" \
        "<h3>Additional Support Questions?</h3><p>USB-C port: 100W max</p></body></html>"
    pr = B.parse_page(snap(B.SOURCE, "1", "https://www.belkin.com/support-article/?articleNum=1", {"model": model}), h)
    return {c["key"]: c["value"] for c in pr.claims}, pr


class BelkinSupport(unittest.TestCase):
    def test_pps_affirmative_output(self):
        v, pr = belkin("Belkin BoostCharge Power Bank 20K (BPB024) FAQs", "<p>Input</p><p>USB-C PD 30W Max</p><p>Output</p><p>USB-C port: 30W Max PPS</p>"
                       "<p>USB-A port: 18W Max</p>", "BPB024")
        self.assertEqual(v, {"pd.pps": True, "out.max_single_port_w": 30})
        self.assertEqual(pr.identifiers[0]["value"], "BPB024")
        self.assertTrue(all(len(c["quote"]) <= 125 for c in pr.claims))

    def test_never_pps(self):
        for body in ("<p>Does it support PPS?</p><p>Yes.</p>", "<p>USB-C port does not support PPS</p>",
                     "<tr><td>USB-C PPS charging support</td><td>Yes</td><td>No</td></tr>", "<p>USB-C: 45W, PPS</p><p>No PPS on the USB-A port</p>",
                     "<p>Input:</p><p>USB-C PPS 30W</p>"):
            v, _ = belkin("Meet the Belkin Power Bank (BPB029)", body, "BPB029")
            self.assertNotIn("pd.pps", v, body)

    def test_single_port(self):
        self.assertEqual(belkin("X (BPB029)", "<p>USB-C port / USB-C cable output: up to 45W max (profiles include 5V/3A)</p>", "BPB029")[0],
                         {"out.max_single_port_w": 45})
        self.assertEqual(belkin("X (BPB011)", "<p>Output:</p><p>USB-C ⎓ 5V/3A (15W max)</p><p>USB-A #1 ⎓ 5V/2.4A (12W max)</p>", "BPB011")[0],
                         {"out.max_single_port_w": 15})
        for body in ("<p>Input:</p><p>USB-C port: Power Delivery (PD) 20W max</p>",                 # the recharge port
                     "<p>The USB-C port supports charging output up to 5W when used simultaneously</p>",
                     "<p>USB-C: 20W max</p><p>USB-C port: 30W max</p>",                                # two figures
                     "<p>Output:</p><p>USB-C: 5V/3A (15W Max)</p><p>USB-A: 18W max</p>"):             # a better USB-A port
            self.assertEqual(belkin("X (BPB012)", body, "BPB012")[0], {}, body)

    def test_identity(self):
        for title in ("UltraCharge 10K 45W Power Bank (BPB035/BBA007) FAQs", "Belkin Power Bank Comparison Chart", "Meet the Power Bank (BPB012)"):
            v, pr = belkin(title, "<p>USB-C port: 30W Max PPS</p>", "BBA007")
            self.assertEqual((v, pr.identifiers), ({}, []), title)
        self.assertEqual(B.codes("Getting to know the Belkin BOOST↑CHARGE™ Power Bank 20K, BPB012"), ["BPB012"])


class LenovoDatasheet(unittest.TestCase):
    def parse(self, txt, key="ThinkVision_T27QD_40_Monitor"):
        pr = LD.parse_text(snap(LD.SOURCE, key, "https://psrefstuff.lenovo.com/x.pdf", {}), txt)
        return [(c["key"], c["value"], c["kind"]) for c in pr.claims]

    def test_name(self):
        self.assertEqual(LD.sheet_name("ThinkVision_T27QD_40_Monitor"), "ThinkVision_T27QD-40")
        self.assertEqual(LD.sheet_name("Legion_Y32p_30_Monitor"), "Legion_Y32p-30")

    def test_rules(self):
        self.assertEqual(self.parse("ThinkVision T27QD-40\nThinkVision Eye Comfort 5-star certified"), [("flk.pwm", "none", "derived")])
        self.assertEqual(self.parse("ThinkVision T27QD-40\n11.1 kg   TÜV Rheinland Flicker Free"), [("flk.pwm", "none", "official")])
        for line in ("TÜV Rheinland Eye Comfort", "Eye Comfort 4-star certified", "reduces flicker", "flat panel displays do not flicker the way CRTs do",
                     "low flicker-free mode not supported"):
            self.assertEqual(self.parse("ThinkVision T27QD-40\n" + line), [], line)
        self.assertEqual(self.parse("ThinkVision T32P-30\nTÜV Rheinland Flicker Free"), [], "the sheet must name the model")


class NotebookcheckBox(unittest.TestCase):
    def parse(self, body, model="ProArt P14"):
        h = f"<title>Asus ProArt P14 Review - Notebookcheck Review</title><div>{body}</div>"
        pr = N.parse_page(snap(N.SOURCE, "x", "https://www.notebookcheck.net/x.0.html", {"model": model, "brand": "asus"}), h)
        return [(c["key"], c["value"], c.get("conditions"), c["kind"], c["measurement"]["mode"]) for c in pr.claims]

    def test_detected(self):
        self.assertEqual(self.parse("Screen flickering / PWM detected 960 Hz Amplitude: 30 % &le; 70 % brightness setting"),
                         [("flk.pwm_freq", 960, {"brightness_pct": 70}, "measured", "optical")])

    def test_not_detected(self):
        self.assertEqual(self.parse("Screen flickering / PWM not detected"), [("flk.pwm", "none", None, "measured", "optical")])

    def test_identity_and_conflict(self):
        self.assertEqual(self.parse("Screen flickering / PWM not detected", model="Zenbook 14"), [])
        h = "<title>Asus ProArt P14 Review</title>Screen flickering / PWM not detected ... Screen flickering / PWM detected 240 Hz"
        self.assertEqual(N.parse_page(snap(N.SOURCE, "x", "u", {"model": "ProArt P14", "brand": "asus"}), h).claims, [])


if __name__ == "__main__":
    unittest.main()
