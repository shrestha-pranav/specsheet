#!/usr/bin/env python3
"""A3-fix (2026-11-26, Codex review-10 item 4): zero trace of free: false hosts (scripts/zero_trace.py).

Fixture: a throwaway root whose docs/ and api-worker/pack/ plant each kind of trace (URL, bare domain, credit label, a value only the
free: false host supports as headline / alternative / index value / bulk row) -> every one is reported; a clean tree -> none. Live: the
real docs/ + api-worker/pack/ against state/specsheet.sqlite carry no trace (skipped when the store is absent)."""
import gzip, json, shutil, sqlite3, sys, tempfile, unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import source_policy  # noqa: E402
import zero_trace as Z  # noqa: E402

POL = source_policy.load(ROOT / "data" / "source-policy.yaml")
AOC = "https://www.aoc.com/us/gaming/products/monitors/q27g3xmn"
MAKER = "https://www.dell.com/en-us/shop/u2723qe"


def rec(eid, specs):
    return {"id": eid, "category": "monitors", "specs": specs, "sources": [{"id": "s1", "url": MAKER}]}


class Fixture(unittest.TestCase):
    def setUp(self):
        self.t = Path(tempfile.mkdtemp(prefix="zt-")); self.addCleanup(shutil.rmtree, self.t, True)
        (self.t / "docs" / "api" / "v1" / "monitors" / "products").mkdir(parents=True)
        (self.t / "api-worker" / "pack" / "bulk").mkdir(parents=True)
        db = self.db = self.t / "s.sqlite"
        con = sqlite3.connect(db)
        con.execute("CREATE TABLE entity_sources(entity_id TEXT, sid TEXT, url TEXT, tier TEXT, label TEXT, snapshot TEXT, retrieved_at TEXT)")
        con.execute("CREATE TABLE source_links(entity_id TEXT, sid TEXT, linked_from TEXT)")
        con.execute("CREATE TABLE claims(entity_id TEXT, mapped_key TEXT, source TEXT, norm_ok INT, norm_value TEXT, value TEXT, review TEXT, status TEXT)")
        con.executemany("INSERT INTO entity_sources VALUES (?,?,?,?,?,?,?)", [("aoc-q27", "s1", AOC, "manufacturer", "", "", ""),
                                                                             ("aoc-q27", "s2", MAKER, "manufacturer", "", "", "")])
        con.executemany("INSERT INTO claims VALUES (?,?,?,?,?,?,?,?)", [
            ("aoc-q27", "res.refresh_max", "s1", 1, "180", "180", "accepted", "known"),        # only AOC says 180
            ("aoc-q27", "panel.technology", "s1", 1, '"ips"', '"ips"', "candidate", "known"),  # AOC + a free source agree: not tainted
            ("aoc-q27", "panel.technology", "s2", 1, '"ips"', '"ips"', "accepted", "known")])
        con.commit(); con.close()

    def write(self, rel, obj):
        p = self.t / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps(obj))

    def checks(self):
        return sorted({(h["check"], h.get("where", "")) for h in Z.run(self.t, self.db, POL)["hits"]})

    def test_clean_tree_passes(self):
        self.write("docs/api/v1/monitors/products/aoc-q27.json", rec("aoc-q27", {"panel.technology": {"value": "ips", "sources": ["s1"]},
                                                                               "res.refresh_max": {"value": None, "status": "not_published"}}))
        self.assertEqual(self.checks(), [])

    def test_every_trace_kind_is_caught(self):
        self.write("docs/api/v1/monitors/products/aoc-q27.json", rec("aoc-q27", {"res.refresh_max": {"value": 180}}))
        self.write("docs/api/v1/preview/monitors/products/aoc-q27.json",
                   rec("aoc-q27", {"res.refresh_max": {"value": 165, "alternatives": [{"value": 180, "kind": "official"}]}}))
        self.write("api-worker/pack/index/monitors.json", [{"id": "aoc-q27", "v": {"res.refresh_max": 180}}])
        with gzip.open(self.t / "api-worker" / "pack" / "bulk" / "monitors.jsonl.gz", "wt") as f:
            f.write(json.dumps(rec("aoc-q27", {"res.refresh_max": {"value": 180}})) + "\n")
        (self.t / "docs" / "llms.txt").write_text(f"see {AOC}\nmirror: www.aoc.com\n")
        (self.t / "docs" / "sources.json").write_text(json.dumps({"credit": "AOC official specification pages"}))
        self.assertEqual(self.checks(), [("label", ""), ("url", ""), ("value", "alternative"), ("value", "index"), ("value", "value")])
        files = {Path(h["file"]).name for h in Z.run(self.t, self.db, POL)["hits"] if h["check"] == "value"}
        self.assertEqual(files, {"aoc-q27.json", "monitors.json", "monitors.jsonl.gz"})

    def test_path_prefix_and_document_hosts(self):
        (self.t / "docs" / "a.txt").write_text("https://www.techpowerup.com/review/x/ https://cdn.shopify.com/s/files/1/manual.pdf")
        self.assertEqual(self.checks(), [], "a review path of a path_prefix host and a document_host CDN are not free:false traces")
        (self.t / "docs" / "b.txt").write_text("https://www.techpowerup.com/ssd-specs/samsung-990-pro.d861")
        self.assertEqual(self.checks(), [("url", "")])


@unittest.skipUnless((ROOT / "state" / "specsheet.sqlite").exists() and (ROOT / "api-worker" / "pack").exists(), "needs the built store + pack")
class Live(unittest.TestCase):
    def test_no_trace_in_served_artifacts(self):
        r = Z.run(ROOT, ROOT / "state" / "specsheet.sqlite", POL)
        self.assertEqual(r["hits"], [], r["hits"][:5])
        self.assertGreater(r["files"], 1000)


if __name__ == "__main__":
    unittest.main()
