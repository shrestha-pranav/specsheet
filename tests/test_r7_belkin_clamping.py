"""r7 coordinator ruling 2026-11-26: Belkin clamping voltage as printed, never a VPR (crawler/adapters/crawlpy_strips_belkin.py)."""
import inspect, sys, unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "crawler" / "adapters"))
import crawlpy_strips_belkin as B  # noqa: E402


def v(t):
    r = B.clamping(t)
    return r and r[0]


class BelkinClamping(unittest.TestCase):
    def test_single(self):
        self.assertEqual(v("Technical Specifications Circuit Total Joules 2160J Clamping Voltage 330V EMI/RFI Noise Filter 150K Hz"), 330)

    def test_mode_split_highest_raw_keeps_all(self):
        r = B.clamping("Clamping Voltage L-N: 400V, L-G: 500V, N-G: 500V EMI/RFI")
        self.assertEqual(r[0], 500)
        self.assertIn("L-N: 400V", r[1])
        self.assertIn("N-G: 500V", r[1])

    def test_test_current_skipped(self):
        self.assertIsNone(v("Clamping Voltage 340V(@50A) Surge Protection Yes"))
        self.assertIsNone(v("Clamping Voltage 340(@ 100A) Surge Protection Yes"))

    def test_chart_cell_skipped(self):
        self.assertIsNone(v("Clamping Voltage 330V No 400V No"))

    def test_kv_ul1449_not_read(self):
        self.assertIsNone(v("Clamping Voltage UL1449 1.2 KV Emi/RFI Noise"))

    def test_no_vpr_keys_emitted(self):
        self.assertNotIn("surge.vpr", inspect.getsource(B.iter_legacy))

    def test_crawlpy_strips_untouched_tag(self):
        import registry
        self.assertEqual(registry.parser_info("belkin")["parser"], "crawlpy-strips@1")
        self.assertIn("crawlpy-strips-belkin@1", registry.supplement_parsers())


if __name__ == "__main__":
    unittest.main()
