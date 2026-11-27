#!/usr/bin/env python3
"""Coverage regression guard (A3-rob r11). Compares the freshly built docs/api/v1/coverage.json with the one currently published on gh-pages
and fails when any category's free-tier records or values drop by more than the threshold (default 5%), or a category disappears.
Catches silent data loss before it ships: a policy held at `approval: pending` moving its values to preview, a discovery run that shrank,
an adapter regression. RELEASE_ALLOW_DROP=1 (or --allow-drop) prints the same table and passes. Exit 0 ok / 1 drop / 2 usage.

  python3 -I scripts/coverage_guard.py [--new docs/api/v1/coverage.json] [--ref origin/gh-pages] [--old FILE] [--threshold 0.05]

--ref: the git ref holding the live site (gh-pages snapshot, api/v1/coverage.json); default origin/gh-pages, falling back to local gh-pages
(note: a release dry run moves local gh-pages, origin/ is what is live). No published coverage yet (first release) = pass with a note.
"""
import argparse, json, os, subprocess, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TIER = "free"


def published(ref):
    for r in ([ref] if ref else ["origin/gh-pages", "gh-pages"]):
        p = subprocess.run(["git", "-C", str(ROOT), "show", f"{r}:api/v1/coverage.json"], capture_output=True, text=True)
        if p.returncode == 0:
            return r, json.loads(p.stdout)
    return None, None


def compare(old, new, threshold):
    """-> (rows, drops): rows = [(cat, metric, old, new, frac)], drops = the rows over the threshold (frac = relative change)."""
    oc, nc = old.get("categories") or {}, new.get("categories") or {}
    rows, drops = [], []
    for cat in sorted(set(oc) | set(nc)):
        for metric in ("records", "values"):
            a = ((oc.get(cat) or {}).get(TIER) or {}).get(metric, 0)
            b = ((nc.get(cat) or {}).get(TIER) or {}).get(metric, 0)
            frac = (b - a) / a if a else 0.0
            row = (cat, metric, a, b, frac)
            if a != b:
                rows.append(row)
            if a and -frac > threshold:
                drops.append(row)
    return rows, drops


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--new", default=str(ROOT / "docs/api/v1/coverage.json"))
    ap.add_argument("--old", default="", help="compare against this file instead of the gh-pages one")
    ap.add_argument("--ref", default="")
    ap.add_argument("--threshold", type=float, default=0.05)
    ap.add_argument("--allow-drop", action="store_true", default=os.environ.get("RELEASE_ALLOW_DROP") == "1")
    a = ap.parse_args(argv)
    new = json.loads(Path(a.new).read_text())
    if a.old:
        ref, old = a.old, json.loads(Path(a.old).read_text())
    else:
        ref, old = published(a.ref)
    if old is None:
        print("coverage guard: no published coverage.json to compare against (first release?): pass")
        return 0
    rows, drops = compare(old, new, a.threshold)
    print(f"coverage guard vs {ref} ({TIER} tier, fail if a category drops > {a.threshold:.0%} records or values):")
    for cat, metric, x, y, f in rows:
        flag = "  DROP" if (cat, metric, x, y, f) in drops else ""
        print(f"  {cat:<18} {metric:<7} {x:>8} -> {y:>8}  {f:+.1%}{flag}")
    if not rows:
        print("  no change")
    if drops and not a.allow_drop:
        print(f"coverage guard: FAILED, {len(drops)} drop(s) over {a.threshold:.0%}. Find the cause (pending policy hold? shrunk discovery?) "
              f"or re-run with RELEASE_ALLOW_DROP=1 if the drop is intended.", file=sys.stderr)
        return 1
    if drops:
        print(f"coverage guard: {len(drops)} drop(s) allowed by RELEASE_ALLOW_DROP=1", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
