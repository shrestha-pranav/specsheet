#!/usr/bin/env python3
"""scripts/coverage_guard.py (A3-rob r11): a > 5% per-category drop in free records or values fails the release unless allowed."""
import json, os, sys, tempfile, unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
import coverage_guard as G  # noqa: E402


def cov(**cats):
    return {"categories": {c: {"free": {"records": r, "values": v}} for c, (r, v) in cats.items()}}


class Guard(unittest.TestCase):
    def run_guard(self, old, new, *extra):
        with tempfile.TemporaryDirectory() as d:
            (Path(d) / "o.json").write_text(json.dumps(old))
            (Path(d) / "n.json").write_text(json.dumps(new))
            env = os.environ.pop("RELEASE_ALLOW_DROP", None)
            try:
                return G.main(["--old", f"{d}/o.json", "--new", f"{d}/n.json", *extra])
            finally:
                if env is not None:
                    os.environ["RELEASE_ALLOW_DROP"] = env

    def test_small_drop_and_growth_pass(self):
        self.assertEqual(self.run_guard(cov(a=(100, 1000), b=(10, 10)), cov(a=(96, 951), b=(50, 500))), 0)

    def test_record_drop_fails(self):
        self.assertEqual(self.run_guard(cov(a=(100, 1000)), cov(a=(94, 1000))), 1)

    def test_value_drop_fails(self):
        self.assertEqual(self.run_guard(cov(a=(100, 1000)), cov(a=(100, 940))), 1)

    def test_vanished_category_fails(self):
        self.assertEqual(self.run_guard(cov(a=(100, 1000), b=(5, 5)), cov(a=(100, 1000))), 1)

    def test_allow_drop(self):
        self.assertEqual(self.run_guard(cov(a=(100, 1000)), cov(a=(10, 10)), "--allow-drop"), 0)

    def test_compare_rows(self):
        rows, drops = G.compare(cov(a=(100, 1000)), cov(a=(90, 1000)), 0.05)
        self.assertEqual([r[:4] for r in drops], [("a", "records", 100, 90)])


if __name__ == "__main__":
    unittest.main()
