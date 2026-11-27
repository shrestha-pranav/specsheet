"""Generic runner for contract adapters (ARCHITECTURE 15.5): discover -> fetch (append-only, resumable) -> parse.

python3 -I crawler/adapters/<x>.py discover|fetch|parse [--limit N] [--match REGEX] [--refresh]
fetch skips refs that already have a status-200 snapshot in raw/<source>/snapshots.jsonl (unless --refresh) -- except a re-listed delisted ref
(review-11), which is always re-fetched and stays delisted until that fresh fetch passes the identity check (revalidate),
stops after STOP_AFTER consecutive failures (token/403/breaker) and records stop_reason. parse is offline.
"""
import argparse, dataclasses, json, re, sys, time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import _contract as C  # noqa: E402

STOP_AFTER = 4


class StopCrawl(Exception):
    pass


def _refs(store, ad):
    p = store.dir / "discovery.json"
    if not p.exists():
        raise SystemExit("run discover first")
    d = json.loads(p.read_text())
    # tolerate pre-contract discovery.json rows ({key,url,<hints inline>}) written by the round-2 function adapters
    return [C.Ref(source_id=r.get("source_id", ad.source_id), key=r["key"], url=r["url"],
                  hints=r.get("hints") or {k: v for k, v in r.items() if k not in ("source_id", "key", "url", "hints")}) for r in d["refs"]], d


RELIST_MARKS = ("listing", "delisted_at", "relisted_at", "revalidate_failed_at", "pinned_snapshot")


def carry_delisted(prev_doc, doc, today=None):
    """Delisting safety (A3-rob r11): a ref the previous discovery listed and this one does not is KEPT in refs (so its stored snapshot keeps
    feeding the importer and every consumer of discovery.json), hints marked listing: delisted + delisted_at (first date it went missing;
    kept across runs). Only a complete discovery marks; an incomplete one carries the ref unmarked. Returns the number of refs carried.
    A release must never lose records because discovery shrank.
    Review-11: a delisted ref listed again is NOT resurrected by discovery alone -- it keeps listing: delisted + delisted_at and gains
    relisted_at; fetch must re-fetch it and only a fresh 200 that passes revalidate() clears the marks (a failed re-fetch keeps them)."""
    today = today or time.strftime("%Y-%m-%d", time.gmtime())
    have = {r["key"] for r in doc["refs"]}
    old = {r["key"]: (r.get("hints") or {k: v for k, v in r.items() if k not in ("source_id", "key", "url", "hints")})
           for r in (prev_doc or {}).get("refs", [])}
    for r in doc["refs"]:
        oh = old.get(r["key"]) or {}
        if oh.get("listing") == "delisted":
            r["hints"] = dict(r.get("hints") or {}, **{k: oh[k] for k in RELIST_MARKS if k in oh})
            r["hints"].setdefault("relisted_at", today)
    n = 0
    for r in (prev_doc or {}).get("refs", []):
        if r["key"] in have:
            continue
        r = dict(r, hints=dict(old[r["key"]]))
        r["hints"].pop("relisted_at", None)          # listed again, then dropped again: back to plain delisted
        if doc.get("complete") and r["hints"].get("listing") != "delisted":
            r["hints"].update(listing="delisted", delisted_at=today)
        doc["refs"].append(r); have.add(r["key"]); n += 1
    return n


def _key_ids(pr):
    ids = pr.identifiers if hasattr(pr, "identifiers") else (pr or {}).get("identifiers") or []
    return {(i.get("scheme"), str(i.get("value") or "").strip().upper()) for i in ids if i.get("role", "key") == "key" and i.get("value")}


def revalidate(ad, store, snap, prior=None):
    """Identity check for a re-listed delisted ref (review-11). True only when `snap` is a fresh status-200 snapshot whose parse yields key
    identifiers, overlapping those of `prior` (the last good snapshot record before this fetch) when that one parses to any."""
    if snap is None or getattr(snap, "status", None) != 200:
        return False
    try:
        fresh = _key_ids(ad.parse(snap, store, None))
    except Exception:  # noqa: BLE001  an unparseable fresh page proves nothing
        return False
    if not fresh:
        return False
    if prior is None:
        return True
    try:
        before = _key_ids(ad.parse(C.Snapshot(prior["snapshot"], snap.ref, 200, prior["fetched_at"], prior.get("final_url") or prior.get("url"), {}),
                                   store, None))
    except Exception:  # noqa: BLE001
        before = set()
    return not before or bool(fresh & before)


def settle_relisted(doc, key, ok, today=None, prior=None):
    """Record a re-listed ref's revalidation in discovery.json: ok -> marks cleared + verified_at; failed -> stays delisted,
    revalidate_failed_at, and pinned_snapshot = the last good snapshot before it, so parse/import never switch to an unverified newer 200
    (registry.apply_pins)."""
    today = today or time.strftime("%Y-%m-%d", time.gmtime())
    for r in doc["refs"]:
        if r["key"] != key:
            continue
        h = r.setdefault("hints", {})
        if ok:
            for k in RELIST_MARKS:
                h.pop(k, None)
            h["verified_at"] = today
        else:
            h["revalidate_failed_at"] = today
            if prior is not None:
                h.setdefault("pinned_snapshot", prior["snapshot"])


def main(ad):
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["discover", "fetch", "parse", "run"])
    ap.add_argument("--limit", type=int)
    ap.add_argument("--match", help="regex on ref key")
    ap.add_argument("--refresh", action="store_true")
    a = ap.parse_args()
    store = ad.store
    if a.cmd in ("discover", "run"):
        prev_doc = json.loads((store.dir / "discovery.json").read_text()) if (store.dir / "discovery.json").exists() else None
        d = ad.discover(prev_doc["checkpoint"] if prev_doc else None, C.NET)
        doc = dataclasses.asdict(d)
        kept = carry_delisted(prev_doc, doc)
        (store.dir / "discovery.json").write_text(json.dumps(doc, indent=0))
        print(f"discover: refs={len(d.refs)} complete={d.complete} stop={d.stop_reason} carried_not_listed={kept}")
    if a.cmd in ("fetch", "run"):
        refs, disc_doc = _refs(store, ad)
        import registry as REG      # lazy: registry imports adapter modules
        good = {s["ref"]: s for s in store.snapshots() if s["status"] == 200 and REG.compatible(type(ad), s)}   # any parser version (review 2 risk 1)
        done = set(good)
        relisted = lambda r: r.hints.get("listing") == "delisted" and bool(r.hints.get("relisted_at"))
        todo = [r for r in refs if (a.refresh or r.key not in done or relisted(r)) and (not a.match or re.search(a.match, r.key))
                and (r.hints.get("listing") != "delisted" or relisted(r))]      # delisted: keep the stored snapshot; re-listed: must re-fetch
        settled = 0
        if a.limit:
            todo = todo[:a.limit]
        fails = n = 0
        for r in todo:
            try:
                s = ad.fetch(r, None, C.NET)
            except StopCrawl as e:
                print("STOP:", e); break
            except Exception as e:  # noqa
                s = None; print("error", r.key, repr(e)[:150])
            if relisted(r):
                prior = REG.pinned_record(store.snapshots(), r.key, r.hints.get("pinned_snapshot")) or good.get(r.key)
                settle_relisted(disc_doc, r.key, revalidate(ad, store, s, prior), prior=prior); settled += 1
            if s is None or s.status != 200:
                fails += 1
                if fails >= STOP_AFTER:
                    print(f"STOP: {fails} consecutive failures (last {r.key})"); break
            else:
                fails = 0; n += 1
                if n % 10 == 0:
                    print(f"fetched {n}/{len(todo)} ({r.key})", flush=True)
        if settled:
            (store.dir / "discovery.json").write_text(json.dumps(disc_doc, indent=0))
        print(f"fetch: {n} fetched, {len(todo)} planned, {len(done)} already done, {settled} re-listed refs revalidated/failed")
    if a.cmd in ("parse", "run"):
        import registry as REG
        pdir = store.dir / "parsed"; pdir.mkdir(exist_ok=True)
        parser, fp = f"{ad.id}@{ad.version}", REG.parser_fingerprint(Path(sys.modules[type(ad).__module__].__file__).stem)
        latest, snaps = {}, store.snapshots()
        for s in snaps:
            if s["status"] == 200 and REG.compatible(type(ad), s):
                latest[s["ref"]] = s
        refs = {r.key: r for r in _refs(store, ad)[0]} if (store.dir / "discovery.json").exists() else {}
        REG.apply_pins(latest, snaps, {k: r.hints for k, r in refs.items()})
        n = 0
        for k, s in latest.items():
            if (a.match and not re.search(a.match, k)) or (hasattr(ad, "wants") and not ad.wants(s)):
                continue
            snap = C.Snapshot(s["snapshot"], refs.get(k) or C.Ref(ad.source_id, k, s["url"]), 200, s["fetched_at"], s["final_url"], {})
            pr = ad.parse(snap, store, None)
            REG.cache_write(pdir / (REG.safe(k) + ".json"), parser, fp, s["snapshot"], dataclasses.asdict(pr))   # same cache format the importer validates
            n += 1
        print(f"parse: {n} snapshots -> {pdir}")
