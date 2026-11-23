#!/usr/bin/env python3
"""Counts per family/line + US-suffix MTMs from raw/lenovo-psref snapshots (reads latest 200 snapshot per ProductKey)."""
import collections, gzip, json
from pathlib import Path
R = Path(__file__).resolve().parents[1] / "raw" / "lenovo-psref"
disc = {r["key"]: r for r in json.loads((R / "discovery.json").read_text())["refs"]}
latest = {}
for l in open(R / "snapshots.jsonl"):
    s = json.loads(l)
    if s["status"] == 200:
        latest[s["ref"]] = s
fam = collections.defaultdict(lambda: [0, 0, 0])
for k, s in latest.items():
    p = R / s["blob"]
    b = json.loads(gzip.decompress(p.read_bytes()) if p.suffix == ".gz" else p.read_bytes())
    m = b["models"]; f = fam[disc[k]["hints"]["line"] + " / " + disc[k]["hints"]["series"]]
    f[0] += 1; f[1] += len(m); f[2] += sum(x["Model"].endswith("US") for x in m)
print(f"{'line / series':45} products  MTMs   US-MTMs")
for k, v in sorted(fam.items()):
    print(f"{k:45} {v[0]:5} {v[1]:8} {v[2]:6}")
print(f"TOTAL products {sum(v[0] for v in fam.values())}/{len(disc)}  MTMs {sum(v[1] for v in fam.values())}  US {sum(v[2] for v in fam.values())}")
