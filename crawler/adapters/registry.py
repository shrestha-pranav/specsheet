"""One entry point over all adapters (ARCHITECTURE 15.5): iter_observations(source_id) yields (snapshot record, ParseResult dict, extra)
for the latest 200 snapshot of every ref, whichever adapter style produced it.

- class adapters (lenovo_psref, asus, apple; runner _run.py): parse(snap, blobs, profile) is called directly.
- tripplite and cyberpower are class adapters too (round 3); the FnAdapter compatibility shim is gone.
- default reads the derived raw/<src>/parsed/<key>.json (rebuildable); reparse=True re-runs parse() over the blobs (offline, pure).
- lenovo-psref is always re-parsed from blobs through a US-only view of the bundle (a full run is ~1M MTMs; the catalogue is US-market),
  and its non-US rows are summarised in `extra` instead of becoming 28 claims each.
Nothing here writes to raw/.
"""
import dataclasses, gzip, importlib, json, re, sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import _contract as C  # noqa: E402

SOURCES = {
    "lenovo-psref": {"brand": "lenovo", "brand_name": "Lenovo", "category": "laptops", "module": "lenovo_psref", "importer": "lenovo-psref"},
    "asus-us": {"brand": "asus", "brand_name": "ASUS", "category": "laptops", "module": "asus", "importer": "asus"},
    "apple-support": {"brand": "apple", "brand_name": "Apple", "category": "laptops", "module": "apple", "importer": "apple"},
    "dell-us": {"brand": "dell", "brand_name": "Dell", "category": "laptops", "module": "dell", "importer": "generic"},
    "microsoft-surface": {"brand": "microsoft", "brand_name": "Microsoft Surface", "category": "laptops", "module": "surface", "importer": "generic"},
    "framework-us": {"brand": "framework", "brand_name": "Framework", "category": "laptops", "module": "framework", "importer": "generic"},
    "samsung-us": {"brand": "samsung", "brand_name": "Samsung", "category": "laptops", "module": "samsung", "importer": "generic"},
    "razer-us": {"brand": "razer", "brand_name": "Razer", "category": "laptops", "module": "razer", "importer": "generic"},
    "energystar-monitors": {"brand": "energystar", "brand_name": "ENERGY STAR (cross-brand)", "category": "monitors", "module": "energystar_monitors", "importer": "model"},
    "lenovo-psref-monitors": {"brand": "lenovo", "brand_name": "Lenovo", "category": "monitors", "module": "lenovo_monitors", "importer": "model"},
    "displayhdr": {"brand": "vesa", "brand_name": "VESA DisplayHDR", "category": "monitors", "module": "displayhdr", "importer": "model"},
    "lg-us": {"brand": "lg", "brand_name": "LG", "category": "monitors", "module": "lg_us", "importer": "model"},
    "asus-us-monitors": {"brand": "asus", "brand_name": "ASUS", "category": "monitors", "module": "asus_monitors", "importer": "model"},
    "samsung-us-ssd": {"brand": "samsung", "brand_name": "Samsung", "category": "ssds", "module": "samsung_ssd", "importer": "generic"},
    "sandisk-us-ssd": {"brand": "western digital", "brand_name": "WD / SanDisk", "category": "ssds", "module": "sandisk_ssd", "importer": "generic"},
    "teamgroup-us-ssd": {"brand": "team", "brand_name": "TEAMGROUP", "category": "ssds", "module": "teamgroup_ssd", "importer": "generic"},
    "tripplite": {"brand": "tripplite", "brand_name": "Tripp Lite", "category": "power-strips", "module": "tripplite", "importer": "strip"},
    "cyberpower": {"brand": "cyberpower", "brand_name": "CyberPower", "category": "power-strips", "module": "cyberpower", "importer": "strip"},
    # crawl.py v0 stores (raw/<slug>/products/<key>/{extract,feed}.json, no snapshot log): read through crawlpy_strips, never written
    **{slug: {"brand": slug, "brand_name": name, "category": "power-strips", "module": "crawlpy_strips", "legacy": True, "importer": "strip"}
       for slug, name in (("anker", "Anker"), ("belkin", "Belkin"), ("ugreen", "UGREEN"), ("baseus", "Baseus"),
                          ("byjasco", "Jasco (GE / Philips)"), ("furman", "Furman"), ("austere", "Austere"))},
}

# importer = which scripts/import.py handler reads the source: lenovo-psref | asus | apple | generic (model->configuration pages) | strip | model
# (one page = one model, optional MTM packages, claims on the model). A new category adds its sources here (or, in fixture tests, in
# $SPECSHEET_ROOT/sources.extra.json) and ships research/<cat>/{spec-profile,category}.yaml: nothing else names it.
_extra = Path(C.ROOT) / "sources.extra.json"
if _extra.exists() and C.ROOT != C.CODE:
    SOURCES.update(json.loads(_extra.read_text()))


def safe(k):
    return re.sub(r"[^A-Za-z0-9._-]", "_", k)


class UsBlobs:
    """BlobReader over a PSREF bundle restricted to US MTMs; always serves '.json.gz'."""
    def __init__(self, bundle):
        self.bundle = bundle

    def read(self, snapshot, ext):
        if ext != ".json.gz":
            raise FileNotFoundError(ext)
        return gzip.compress(json.dumps(self.bundle).encode())


def _load_bundle(store, rec):
    b = store.read_rec(rec)
    if rec["blob"].endswith(".gz"):
        b = gzip.decompress(b)
    return json.loads(b)


def _lenovo(source_id, store, latest):
    mod = importlib.import_module("lenovo_psref")
    ad = mod.LenovoPsref()
    refs = {}
    d = store.dir / "discovery.json"
    if d.exists():
        refs = {r["key"]: C.Ref(**r) for r in json.loads(d.read_text())["refs"]}
    for key, rec in sorted(latest.items()):
        b = _load_bundle(store, rec)
        rows = b["models"]
        us = [m for m in rows if str(m.get("Model", "")).endswith("US")]
        nonus = [(m.get("Model"), (m.get("EAN / UPC / JAN") or "").strip(), m.get("Country/Region")) for m in rows if m not in us]   # raw EAN: import.py validates
        cols = {}
        for m in rows:
            for c, v in m.items():
                if isinstance(v, str) and v.strip():
                    cols[c] = cols.get(c, 0) + 1
        fb = dict(b, models=us)
        snap = C.Snapshot(rec["snapshot"], refs.get(key) or C.Ref(source_id, key, rec["url"]), 200, rec["fetched_at"], rec["final_url"], {})
        pr = ad.parse(snap, UsBlobs(fb), None)
        yield rec, dataclasses.asdict(pr), {"us_rows": us, "nonus": nonus, "columns": cols, "total": len(rows), "info": b.get("info") or {}}


def iter_observations(source_id, reparse=False):
    meta = SOURCES[source_id]
    if meta.get("legacy"):
        yield from importlib.import_module("crawlpy_strips").iter_legacy(source_id)
        return
    store = C.BlobStore(source_id)
    latest = store.latest()
    if source_id == "cyberpower":   # the log also holds datasheet PDFs (documents); entities come from the item JSON only
        latest = {k: r for k, r in latest.items() if k.isdigit() and r["blob"].endswith(".json")}
    if source_id == "lenovo-psref":
        yield from _lenovo(source_id, store, latest)
        return
    refs = {}
    d = store.dir / "discovery.json"
    if d.exists():
        for r in json.loads(d.read_text()).get("refs", []):
            refs[r["key"]] = C.Ref(source_id, r["key"], r["url"], r.get("hints") or {k: v for k, v in r.items() if k not in ("key", "url")})
    ad = None
    for key, rec in sorted(latest.items()):
        p = store.dir / "parsed" / (safe(key) + ".json")
        if reparse or not p.exists():
            if ad is None:
                mod = importlib.import_module(meta["module"])
                ad = next(getattr(mod, n)() for n in dir(mod) if isinstance(getattr(mod, n), type) and getattr(getattr(mod, n), "source_id", None) == source_id)
            if key not in refs and meta.get("importer") != "strip":   # laptop adapters: only refs the discovery knows
                continue
            snap = C.Snapshot(rec["snapshot"], refs.get(key) or C.Ref(source_id, key, rec["url"]), 200, rec["fetched_at"], rec["final_url"], {})
            try:
                yield rec, dataclasses.asdict(ad.parse(snap, store, None)), {}
            except Exception as e:  # noqa
                print(f"[registry] parse failed {source_id}/{key}: {e!r}", file=sys.stderr)
            continue
        yield rec, json.loads(p.read_text()), {}
