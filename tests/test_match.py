"""scripts/match.py title matcher: precision/recall on the fixture title sets (tests/fixtures/match_titles*.jsonl) and the lookalike rules.
Reads the built dataset (docs/api/v1); release.sh runs the tests after build.py.

  python3 -m unittest tests.test_match        # python3 tests/test_match.py -v prints the scores
"""
import json, sys, unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
import match as M  # noqa: E402

BUILT = (ROOT / "docs" / "api" / "v1" / "chargers" / "index.json").exists()


def score(path):
    tp = fp = fn = tn = 0
    wrong = []
    for ln in path.read_text().splitlines():
        if not ln.strip():
            continue
        x = json.loads(ln)
        r = M.match(x["title"])
        # consumer contract (bf-deals, API): a candidate carrying evidence.conflict is never a match
        got = r[0]["id"] if r and not (r[0].get("evidence") or {}).get("conflict") else None
        if x["expect"] and got == x["expect"]:
            tp += 1
        elif got:
            fp += 1; wrong.append((x["title"], x["expect"], got))
        elif x["expect"]:
            fn += 1
        else:
            tn += 1
    return {"tp": tp, "fp": fp, "fn": fn, "tn": tn, "precision": tp / max(1, tp + fp), "recall": tp / max(1, tp + fn), "wrong": wrong}


@unittest.skipUnless(BUILT, "dataset not built")
class Scores(unittest.TestCase):
    def test_tuning_set(self):
        s = score(ROOT / "tests" / "fixtures" / "match_titles.jsonl")
        self.assertGreaterEqual(s["tp"] + s["fp"] + s["fn"] + s["tn"], 60)
        self.assertGreaterEqual(s["precision"], 0.97, s["wrong"])
        self.assertGreaterEqual(s["recall"], 0.85)

    def test_heldout_set(self):
        s = score(ROOT / "tests" / "fixtures" / "match_titles_heldout.jsonl")
        self.assertGreaterEqual(s["precision"], 0.9, s["wrong"])
        self.assertGreaterEqual(s["recall"], 0.8)


@unittest.skipUnless(BUILT, "dataset not built")
class Lookalikes(unittest.TestCase):
    def ids(self, t, **kw):
        return [r["id"] for r in M.match(t, **kw)]

    def test_735_vs_737_and_nano_generations(self):
        self.assertEqual(self.ids("Anker 735 Charger (Nano II 65W)"), ["anker-a2667"])
        self.assertEqual(self.ids("Anker 737 Charger (GaNPrime 120W)"), [])
        self.assertEqual(self.ids("Anker Nano II 65W Charger"), [], "715 and 735 are both Nano II 65W")
        self.assertEqual(self.ids("Anker 711 Charger (Nano II 30W)"), [], "Nano II 30W is not the Nano 3 / Nano 30W A2147")
        self.assertEqual(self.ids("Anker 511 Charger (Nano 3) 30W"), ["anker-a2147"])

    def test_basis_and_api(self):
        r = M.match("Belkin BoostCharge Pro 108W WCH010 GaN charger $49 at Amazon")
        self.assertEqual((r[0]["id"], r[0]["basis"]), ("belkin-wch010", "exact_model_number"))
        self.assertGreater(r[0]["confidence"], 0.9)
        self.assertEqual(self.ids("Belkin BoostCharge Pro 108W WCH010", category="tvs"), [])
        self.assertEqual(self.ids("Anker 30W Nano USB-C Charger, 2 Pack"), [], "a multipack listing is a package, not the model")

    def test_cli_json(self):
        import subprocess
        out = subprocess.run([sys.executable, "-I", str(ROOT / "scripts" / "match.py"), "Anker 735 Charger (Nano II 65W) GaN 3-port $25.99 at Amazon", "--json"],
                             capture_output=True, text=True, check=True).stdout
        self.assertEqual(json.loads(out)["candidates"][0]["id"], "anker-a2667")


if __name__ == "__main__":
    if "-v" in sys.argv and BUILT:
        for f in ("match_titles.jsonl", "match_titles_heldout.jsonl"):
            s = score(ROOT / "tests" / "fixtures" / f)
            print(f, {k: (round(v, 3) if isinstance(v, float) else v) for k, v in s.items() if k != "wrong"}, s["wrong"])
    unittest.main()
