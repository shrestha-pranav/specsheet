#!/usr/bin/env python3
"""Merge data/gan-chargers/<brand>.json into all.json and print a quality report.

Checks: valid JSON, required fields, sources present, duplicate model numbers across files,
and the "PPS unknown" share (unknown must stay null, never false).
Usage: python3 -I scripts/merge.py [--find]   (--find lists >=65W single-port PPS chargers <=$25)
"""
import json, sys
from collections import Counter
from pathlib import Path

DIR = Path(__file__).resolve().parent.parent / "data" / "gan-chargers"
PLACEHOLDERS = {"unknown", "n/a", "na", "none", "null", "-", "tbd"}
REQUIRED = ["brand", "product_name", "model_numbers", "max_total_w", "ports", "pps", "sources"]


def main():
    records, problems = [], []
    for f in sorted(DIR.glob("*.json")):
        if f.name == "all.json":
            continue
        try:
            data = json.loads(f.read_text())
        except json.JSONDecodeError as e:
            problems.append(f"{f.name}: invalid JSON ({e})")
            continue
        for i, r in enumerate(data):
            miss = [k for k in REQUIRED if k not in r]
            if miss:
                problems.append(f"{f.name}[{i}] {r.get('product_name')}: missing {miss}")
            if not r.get("sources"):
                problems.append(f"{f.name}[{i}] {r.get('product_name')}: no sources")
            r["model_numbers"] = [m for m in (r.get("model_numbers") or [])
                                  if m and m.strip().lower() not in PLACEHOLDERS]
            r["_file"] = f.name
            records.append(r)

    models = Counter(m.strip().upper() for r in records for m in (r.get("model_numbers") or []) if m)
    dups = [m for m, n in models.items() if n > 1]

    print(f"{len(records)} SKUs from {len({r['_file'] for r in records})} files")
    for brand, n in Counter(r.get("brand") for r in records).most_common():
        rs = [r for r in records if r.get("brand") == brand]
        pps_t = sum(r.get("pps") is True for r in rs)
        pps_u = sum(r.get("pps") is None for r in rs)
        rng = sum(bool(r.get("pps_ranges")) for r in rs)
        print(f"  {brand:10} {n:3} SKUs  PPS yes {pps_t:3}  unknown {pps_u:3}  ranges {rng:3}")
    if dups:
        print(f"duplicate model numbers: {', '.join(dups[:30])}")
    for p in problems[:40]:
        print("PROBLEM", p)

    (DIR / "all.json").write_text(json.dumps(records, indent=1))

    if "--find" in sys.argv:
        print("\n>=65W single-port + PPS, typical <= $25:")
        for r in records:
            sp = r.get("max_single_port_w") or r.get("max_total_w") or 0
            price = r.get("typical_price_usd")
            if sp >= 65 and r.get("pps") is True and price is not None and price <= 25:
                print(f"  ${price:<6} {r['brand']} {r['product_name']} ({', '.join(r.get('model_numbers') or [])})"
                      f"  ports={len(r.get('ports') or [])}  PPS {r.get('pps_ranges')}")


if __name__ == "__main__":
    main()
