"""Acceptance test from reviews/2026-11-22-astra-datamodel-v1.md (P0-1/P1-7): deleting state/specsheet.sqlite and replaying raw/ +
data/ (decisions, id registry) reproduces the same accepted ids, links, claims and rejection states - independent of source order -
without minting any new id. Slow (3 full imports, ~2 min): python3 -m unittest tests.test_replay"""
import json, shutil, sqlite3, subprocess, sys, tempfile, unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
STATE = ROOT / "state" / "specsheet.sqlite"
sys.path.insert(0, str(ROOT / "crawler" / "adapters"))
import registry  # noqa: E402
CATS = ("laptops", "power-strips")      # categories under test; others (e.g. monitors) may be mid-crawl and change raw/ underneath
SRC = [a for sid, m in registry.SOURCES.items() if m["category"] in CATS for a in ("--source", sid)]


def run(db, data, *extra):
    p = subprocess.run([sys.executable, "-I", str(ROOT / "scripts" / "import.py"), "--db", str(db), "--data", str(data), "--no-mint", *SRC, *extra],
                       capture_output=True, text=True)
    if p.returncode:
        raise AssertionError(p.stderr[-2000:])
    return json.loads(p.stdout)


def snapshot(db):
    con = sqlite3.connect(db)
    w = "e.category IN ('laptops','power-strips')"
    q = lambda sql: sorted(tuple(r) for r in con.execute(sql))
    return {"entities": q(f"SELECT id, category, kind, parent_id, family_id FROM entities e WHERE {w}"),
            "links": q(f"SELECT r.entity_id, type, target_id, status, decision FROM relations r JOIN entities e ON e.id=r.entity_id WHERE {w}"),
            "accepted": q(f"SELECT c.entity_id, c.id, mapped_key, norm_value, decision FROM claims c JOIN entities e ON e.id=c.entity_id WHERE {w} AND review='accepted'"),
            "rejected": q(f"SELECT c.entity_id, c.id FROM claims c JOIN entities e ON e.id=c.entity_id WHERE {w} AND review='rejected'")}


@unittest.skipUnless(STATE.exists(), "needs a built state/specsheet.sqlite (run scripts/import.py once)")
class ReplayTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = Path(tempfile.mkdtemp())
        cls.live = snapshot(STATE)

    def test_1_delete_and_replay_reproduces_state(self):
        out = run(self.tmp / "replay.sqlite", ROOT / "data")
        self.assertEqual(out["ids"]["new"], 0, "replay must not mint")
        got = snapshot(self.tmp / "replay.sqlite")
        for k in ("entities", "links", "accepted", "rejected"):
            self.assertEqual(got[k], self.live[k], f"replay differs in {k}")

    def test_2_decisions_replay_in_any_source_order(self):
        data = self.tmp / "data"
        shutil.copytree(ROOT / "data" / "decisions", data / "decisions"); shutil.copytree(ROOT / "data" / "_ids", data / "_ids")
        con = sqlite3.connect(STATE)
        rej = con.execute("SELECT id FROM claims WHERE review='accepted' AND source_id='tripplite' ORDER BY id LIMIT 1").fetchone()[0]
        rel = con.execute("SELECT entity_id, type, target_id FROM relations WHERE status='proposed' AND type='package_of' ORDER BY entity_id LIMIT 1").fetchone()
        with (data / "decisions" / "ledger.jsonl").open("a") as f:
            f.write(json.dumps({"id": "d_test_1", "at": "2026-11-22T00:00:00Z", "by": "test-human", "action": "reject_claim", "claim": rej, "reason": "fixture"}) + "\n")
            f.write(json.dumps({"id": "d_test_2", "at": "2026-11-22T00:00:00Z", "by": "test-human", "action": "approve_relation",
                                "from": rel[0], "type": rel[1], "to": rel[2], "reason": "fixture"}) + "\n")
        run(self.tmp / "a.sqlite", data); run(self.tmp / "b.sqlite", data, "--reverse-sources")
        a, b = snapshot(self.tmp / "a.sqlite"), snapshot(self.tmp / "b.sqlite")
        self.assertEqual(a, b, "source order changed ids/links/claims/decisions")
        self.assertIn(rej, {c for _, c in a["rejected"]})
        self.assertNotIn(rej, {c for _, c, *_ in a["accepted"]})
        ent = {e[0]: e for e in a["entities"]}
        self.assertEqual((ent[rel[0]][2], ent[rel[0]][3]), ("package", rel[2]), "approved suffix link applies kind + parent")
        self.assertIn((rel[0], rel[1], rel[2], "approved", "d_test_2"), a["links"])
        self.assertEqual({e[0] for e in a["entities"]}, {e[0] for e in self.live["entities"]}, "decisions never remint ids")


if __name__ == "__main__":
    unittest.main()
