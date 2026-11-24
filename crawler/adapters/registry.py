"""One entry point over all adapters (ARCHITECTURE 15.5): iter_observations(source_id) yields (snapshot record, ParseResult dict, extra)
for the latest 200 snapshot of every ref, whichever adapter style produced it.

- class adapters (lenovo_psref, asus, apple; runner _run.py): parse(snap, blobs, profile) is called directly.
- tripplite and cyberpower are class adapters too (round 3); the FnAdapter compatibility shim is gone.
- default reads the derived raw/<src>/parsed/<key>.json cache (rebuildable) ONLY when it was written for this snapshot by this exact
  parser (id@version + parser_fingerprint = sha256 of the adapter module and every crawler/adapters module it imports). Any parser
  edit, version bump or snapshot change is a cache miss: the snapshot is re-parsed and the cache rewritten (review 2, SSD hazard).
  reparse=True re-parses every snapshot and rewrites the cache too.
- snapshot identity is (source, ref, snapshot sha) and does NOT depend on the parser version: a parser bump re-parses existing
  snapshots instead of orphaning them. An adapter may narrow which fetchers' snapshots it reads with `snapshot_formats`
  (adapter tags or 'id@*' globs); default = any version of its own id.
- lenovo-psref is always re-parsed from blobs through a US-only view of the bundle (a full run is ~1M MTMs; the catalogue is US-market),
  and its non-US rows are summarised in `extra` instead of becoming 28 claims each.
Nothing here writes to raw/ except the derived parsed/ cache.
"""
import dataclasses, fnmatch, gzip, hashlib, importlib, json, re, sys
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
    "tplink-us-routers": {"brand": "tp_link", "brand_name": "TP-Link", "category": "routers", "module": "tplink_routers", "importer": "model"},
    "netgear-us-routers": {"brand": "netgear", "brand_name": "NETGEAR", "category": "routers", "module": "netgear_routers", "importer": "model"},
    "asus-us-routers": {"brand": "asus", "brand_name": "ASUS", "category": "routers", "module": "asus_routers", "importer": "model"},
    "anker-us-powerbanks": {"brand": "anker", "brand_name": "Anker", "category": "power-banks", "module": "anker_powerbanks", "importer": "model"},
    "belkin-us-powerbanks": {"brand": "belkin", "brand_name": "Belkin", "category": "power-banks", "module": "belkin_powerbanks", "importer": "model"},
    "iniu-us-powerbanks": {"brand": "iniu", "brand_name": "INIU", "category": "power-banks", "module": "shopify_powerbanks", "importer": "model"},
    "cuktech-us-powerbanks": {"brand": "cuktech", "brand_name": "CUKTECH", "category": "power-banks", "module": "shopify_powerbanks", "importer": "model"},
    "ugreen-us-powerbanks": {"brand": "ugreen", "brand_name": "UGREEN", "category": "power-banks", "module": "shopify_powerbanks", "importer": "model"},
    "ecoflow-us-powerbanks": {"brand": "ecoflow", "brand_name": "EcoFlow", "category": "power-banks", "module": "shopify_powerbanks2", "importer": "model"},
    "sharge-us-powerbanks": {"brand": "sharge", "brand_name": "SHARGE", "category": "power-banks", "module": "shopify_powerbanks2", "importer": "model"},
    "kuxiu-us-powerbanks": {"brand": "kuxiu", "brand_name": "KUXIU", "category": "power-banks", "module": "shopify_powerbanks2", "importer": "model"},
    "mophie-us-powerbanks": {"brand": "mophie", "brand_name": "mophie", "category": "power-banks", "module": "shopify_powerbanks2", "importer": "model"},
    "anker-us-chargers": {"brand": "anker", "brand_name": "Anker", "category": "chargers", "module": "anker_chargers", "importer": "model"},
    "belkin-us-chargers": {"brand": "belkin", "brand_name": "Belkin", "category": "chargers", "module": "belkin_chargers", "importer": "model"},
    "ugreen-us-chargers": {"brand": "ugreen", "brand_name": "UGREEN", "category": "chargers", "module": "shopify_chargers", "importer": "model"},
    "iniu-us-chargers": {"brand": "iniu", "brand_name": "INIU", "category": "chargers", "module": "shopify_chargers", "importer": "model"},
    "cuktech-us-chargers": {"brand": "cuktech", "brand_name": "CUKTECH", "category": "chargers", "module": "shopify_chargers", "importer": "model"},
    "satechi-us-chargers": {"brand": "satechi", "brand_name": "Satechi", "category": "chargers", "module": "shopify_chargers", "importer": "model"},
    "sharge-us-chargers": {"brand": "sharge", "brand_name": "SHARGE", "category": "chargers", "module": "shopify_chargers", "importer": "model"},
    "mophie-us-chargers": {"brand": "mophie", "brand_name": "mophie", "category": "chargers", "module": "shopify_chargers", "importer": "model"},
    "aukey-us-chargers": {"brand": "aukey", "brand_name": "AUKEY", "category": "chargers", "module": "shopify_chargers", "importer": "model"},
    "hyper-us-chargers": {"brand": "hyper", "brand_name": "HyperJuice (Targus)", "category": "chargers", "module": "shopify_chargers", "importer": "model"},
    "nativeunion-us-chargers": {"brand": "native_union", "brand_name": "Native Union", "category": "chargers", "module": "shopify_chargers", "importer": "model"},
    "plugable-us-chargers": {"brand": "plugable", "brand_name": "Plugable", "category": "chargers", "module": "shopify_chargers", "importer": "model"},
    "nekteck-us-chargers": {"brand": "nekteck", "brand_name": "Nekteck", "category": "chargers", "module": "shopify_chargers", "importer": "model"},
    "choetech-us-chargers": {"brand": "choetech", "brand_name": "CHOETECH", "category": "chargers", "module": "shopify_chargers", "importer": "model"},
    "ecoflow-us-stations": {"brand": "ecoflow", "brand_name": "EcoFlow", "category": "power-stations", "module": "shopify_powerstations", "importer": "model"},
    "bluetti-us-stations": {"brand": "bluetti", "brand_name": "BLUETTI", "category": "power-stations", "module": "shopify_powerstations", "importer": "model"},
    "jackery-us-stations": {"brand": "jackery", "brand_name": "Jackery", "category": "power-stations", "module": "shopify_powerstations", "importer": "model"},
    "goalzero-us-stations": {"brand": "goal_zero", "brand_name": "Goal Zero", "category": "power-stations", "module": "shopify_powerstations", "importer": "model"},
    "ankersolix-us-stations": {"brand": "anker", "brand_name": "Anker", "category": "power-stations", "module": "ankersolix_stations", "importer": "model"},
    "dreame-us-robovac": {"brand": "dreame", "brand_name": "Dreame", "category": "robot-vacuums", "module": "dreame_robovac", "importer": "model"},
    "roborock-us-robovac": {"brand": "roborock", "brand_name": "Roborock", "category": "robot-vacuums", "module": "roborock_robovac", "importer": "model"},
    "narwal-us-robovac": {"brand": "narwal", "brand_name": "Narwal", "category": "robot-vacuums", "module": "narwal_robovac", "importer": "model"},
    "ecovacs-us-robovac": {"brand": "ecovacs", "brand_name": "ECOVACS", "category": "robot-vacuums", "module": "ecovacs_robovac", "importer": "model"},
    "irobot-us-robovac": {"brand": "irobot", "brand_name": "iRobot", "category": "robot-vacuums", "module": "irobot_robovac", "importer": "model"},
    "mova-us-robovac": {"brand": "mova", "brand_name": "MOVA", "category": "robot-vacuums", "module": "mova_robovac", "importer": "model"},
    "csa-dcl-robovac": {"brand": "csa", "brand_name": "CSA Matter DCL (cross-brand)", "category": "robot-vacuums", "module": "csa_dcl_robovac", "importer": "model"},
    "energystar-tvs": {"brand": "energystar", "brand_name": "ENERGY STAR (cross-brand)", "category": "tvs", "module": "energystar_tvs", "importer": "model"},
    "samsung-us-tvs": {"brand": "samsung", "brand_name": "Samsung", "category": "tvs", "module": "samsung_tvs", "importer": "model"},
    "lg-us-tvs": {"brand": "lg", "brand_name": "LG", "category": "tvs", "module": "lg_tvs", "importer": "model"},
    "tcl-us-tvs": {"brand": "tcl", "brand_name": "TCL", "category": "tvs", "module": "tcl_tvs", "importer": "model"},
    "vizio-us-tvs": {"brand": "vizio", "brand_name": "Vizio", "category": "tvs", "module": "vizio_tvs", "importer": "model"},
    "energystar-airpurifiers": {"brand": "energystar", "brand_name": "ENERGY STAR (cross-brand)", "category": "air-purifiers", "module": "energystar_airpurifiers", "importer": "model"},
    "carb-airpurifiers": {"brand": "carb", "brand_name": "CARB certified air cleaners (cross-brand)", "category": "air-purifiers", "module": "carb_airpurifiers", "importer": "model"},
    "levoit-us-airpurifiers": {"brand": "levoit", "brand_name": "Levoit", "category": "air-purifiers", "module": "levoit_airpurifiers", "importer": "model"},
    "winix-us-airpurifiers": {"brand": "winix", "brand_name": "Winix", "category": "air-purifiers", "module": "winix_airpurifiers", "importer": "model"},
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


ADAPTERS = Path(__file__).resolve().parent


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


CACHE_FORMAT = 2
_FP = {}


NOT_PARSER = {"_run", "registry"}      # CLI runner + this module: not parsing code (and _run imports registry lazily)


def _module_deps(name, seen):
    """Local crawler/adapters modules `name` imports (transitively), minus NOT_PARSER."""
    if name in seen or name in NOT_PARSER:
        return
    p = ADAPTERS / f"{name}.py"
    if not p.exists():
        return
    seen[name] = p
    for m in re.findall(r"^\s*(?:import|from)\s+([A-Za-z_][A-Za-z0-9_]*)", p.read_text(), re.M):
        _module_deps(m, seen)


def parser_fingerprint(module):
    """sha256 over the adapter module + every local module it imports (sorted by name). Any parser edit changes it."""
    if module not in _FP:
        seen = {}
        _module_deps(module, seen)
        h = hashlib.sha256()
        for n in sorted(seen):
            h.update(n.encode() + b"\0" + seen[n].read_bytes() + b"\0")
        _FP[module] = "sha256:" + h.hexdigest()[:20]
    return _FP[module]


def adapter_for(source_id):
    meta = SOURCES[source_id]
    mod = importlib.import_module(meta["module"])
    return next(getattr(mod, n)() for n in dir(mod) if isinstance(getattr(mod, n), type) and getattr(getattr(mod, n), "source_id", None) == source_id)


def parser_info(source_id):
    """-> {"parser": "id@ver", "fingerprint": ...} for the code that parses this source now (release manifest + cache key)."""
    meta = SOURCES[source_id]
    if meta.get("legacy"):
        return {"parser": "crawlpy-strips@1", "fingerprint": parser_fingerprint("crawlpy_strips")}
    try:
        mod = importlib.import_module(meta["module"])
    except ModuleNotFoundError:     # fixture source: declared parser tag, no code to fingerprint
        return {"parser": meta.get("parser"), "fingerprint": None}
    cls = next(getattr(mod, n) for n in dir(mod) if isinstance(getattr(mod, n), type) and getattr(getattr(mod, n), "source_id", None) == source_id)
    return {"parser": f"{cls.id}@{cls.version}", "fingerprint": parser_fingerprint(meta["module"])}


def compatible(ad_cls, rec):
    """Snapshot selection by fetcher id, never by parser version (review 2 risk 1)."""
    pats = getattr(ad_cls, "snapshot_formats", None) or [f"{ad_cls.id}@*"]
    return any(fnmatch.fnmatchcase(rec.get("adapter") or "", p) for p in pats)


def cache_read(p, parser, fp, snapshot):
    try:
        d = json.loads(p.read_text())
    except (OSError, ValueError):
        return None
    if not isinstance(d, dict) or d.get("cache_format") != CACHE_FORMAT:
        return None          # legacy bare ParseResult: unknown parser -> miss
    if d.get("parser") != parser or d.get("parser_fingerprint") != fp or d.get("snapshot") != snapshot:
        return None
    return d["result"]


def cache_write(p, parser, fp, snapshot, result):
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_suffix(".tmp")
    tmp.write_text(json.dumps({"cache_format": CACHE_FORMAT, "parser": parser, "parser_fingerprint": fp, "snapshot": snapshot, "result": result}))
    tmp.replace(p)


def iter_observations(source_id, reparse=False, stats=None):
    """stats (optional dict) receives cache_hits / cache_misses / reparsed counters."""
    meta = SOURCES[source_id]
    stats = stats if stats is not None else {}
    if meta.get("legacy"):
        yield from importlib.import_module("crawlpy_strips").iter_legacy(source_id)
        return
    store = C.BlobStore(source_id)
    try:
        mod = importlib.import_module(meta["module"])
    except ModuleNotFoundError:     # fixture sources (sources.extra.json, module "none"): pre-parsed results only, no parser to validate
        for key, rec in sorted(store.latest().items()):
            p = store.dir / "parsed" / (safe(key) + ".json")
            if p.exists():
                d = json.loads(p.read_text())
                stats["cache_only"] = stats.get("cache_only", 0) + 1
                yield rec, (d["result"] if isinstance(d, dict) and d.get("cache_format") else d), {}
        return
    cls = next(getattr(mod, n) for n in dir(mod) if isinstance(getattr(mod, n), type) and getattr(getattr(mod, n), "source_id", None) == source_id)
    latest = {}
    for s in store.snapshots():
        if s["status"] == 200 and compatible(cls, s):
            latest[s["ref"]] = s
    if source_id == "cyberpower":   # the log also holds datasheet PDFs (documents); entities come from the item JSON only
        latest = {k: r for k, r in latest.items() if k.isdigit() and r["blob"].endswith(".json")}
    if source_id == "lenovo-psref":
        yield from _lenovo(source_id, store, latest)
        return
    parser, fp = f"{cls.id}@{cls.version}", parser_fingerprint(meta["module"])
    refs = {}
    d = store.dir / "discovery.json"
    if d.exists():
        for r in json.loads(d.read_text()).get("refs", []):
            refs[r["key"]] = C.Ref(source_id, r["key"], r["url"], r.get("hints") or {k: v for k, v in r.items() if k not in ("key", "url")})
    ad = None
    for key, rec in sorted(latest.items()):
        if key not in refs and meta.get("importer") != "strip":   # laptop adapters: only refs the discovery knows
            continue
        p = store.dir / "parsed" / (safe(key) + ".json")
        hit = None if reparse else cache_read(p, parser, fp, rec["snapshot"])
        if hit is not None:
            stats["cache_hits"] = stats.get("cache_hits", 0) + 1
            yield rec, hit, {}
            continue
        if ad is None:
            ad = cls()
        snap = C.Snapshot(rec["snapshot"], refs.get(key) or C.Ref(source_id, key, rec["url"]), 200, rec["fetched_at"], rec["final_url"], {})
        try:
            res = dataclasses.asdict(ad.parse(snap, store, None))
        except Exception as e:  # noqa
            print(f"[registry] parse failed {source_id}/{key}: {e!r}", file=sys.stderr)
            continue
        cache_write(p, parser, fp, rec["snapshot"], res)
        stats["cache_misses"] = stats.get("cache_misses", 0) + 1
        yield rec, res, {}
