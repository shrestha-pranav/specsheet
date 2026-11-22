#!/usr/bin/env python3
"""Build the static site + static JSON API into docs/ (served by GitHub Pages).

API (static, read-only, v1):
  /api/v1/categories.json
  /api/v1/gan-chargers/products.json     all records (resolved view, with sources)
  /api/v1/gan-chargers/products/<id>.json
  /api/v1/gan-chargers/schema.json
  /api/v1/lookup/models.json             normalised model number -> product id
Usage: python3 -I scripts/build.py
"""
import json, re, shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data" / "gan-chargers"
OUT = ROOT / "docs"
API = OUT / "api" / "v1"


def slug(s):
    return re.sub(r"[^a-z0-9]+", "-", s.lower()).strip("-")


def norm_model(m):
    return re.sub(r"[^A-Z0-9]", "", m.upper())


def main():
    recs = []
    for f in sorted(DATA.glob("*.json")):
        if f.name == "all.json":
            continue
        recs += json.loads(f.read_text())
    for r in recs:
        r["model_numbers"] = [m for m in (r.get("model_numbers") or []) if m and m.strip().lower() not in
                              {"unknown", "n/a", "na", "none", "null", "-", "tbd"}]

    ids, lookup = set(), {}
    for r in recs:
        base = slug(f"{r.get('brand','')}-{(r.get('model_numbers') or [None])[0] or r.get('product_name','')}")
        rid, n = base, 2
        while rid in ids:
            rid, n = f"{base}-{n}", n + 1
        ids.add(rid)
        r["id"] = rid
        r.pop("_file", None)
        for m in r.get("model_numbers") or []:
            lookup.setdefault(norm_model(m), []).append(rid)

    if OUT.exists():
        shutil.rmtree(API, ignore_errors=True)
    (API / "gan-chargers" / "products").mkdir(parents=True, exist_ok=True)
    (API / "lookup").mkdir(parents=True, exist_ok=True)

    dump = lambda p, o: p.write_text(json.dumps(o, indent=1, ensure_ascii=False))
    dump(API / "categories.json", [{"id": "gan-chargers", "name": "USB-C GaN wall chargers",
                                    "count": len(recs), "products": "gan-chargers/products.json"}])
    dump(API / "gan-chargers" / "products.json", recs)
    for r in recs:
        dump(API / "gan-chargers" / "products" / f"{r['id']}.json", r)
    shutil.copy(ROOT / "schema.json", API / "gan-chargers" / "schema.json")
    dump(API / "lookup" / "models.json", lookup)
    (OUT / ".nojekyll").write_text("")
    # guard: a JS syntax error silently empties the page (shipped once, 2026-11-22)
    import subprocess, tempfile
    html = (OUT / "index.html").read_text()
    js = html.split("<script>", 1)[1].split("</script>", 1)[0]
    with tempfile.NamedTemporaryFile("w", suffix=".js", delete=False) as t:
        t.write(js)
    r = subprocess.run(["node", "--check", t.name], capture_output=True, text=True)
    if r.returncode:
        raise SystemExit(f"index.html script has a syntax error:\n{r.stderr}")
    print(f"built {len(recs)} products into {OUT}")


if __name__ == "__main__":
    main()
