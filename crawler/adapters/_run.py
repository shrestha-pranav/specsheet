"""Generic runner for contract adapters (ARCHITECTURE 15.5): discover -> fetch (append-only, resumable) -> parse.

python3 -I crawler/adapters/<x>.py discover|fetch|parse [--limit N] [--match REGEX] [--refresh]
fetch skips refs that already have a status-200 snapshot in raw/<source>/snapshots.jsonl (unless --refresh),
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


def main(ad):
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["discover", "fetch", "parse", "run"])
    ap.add_argument("--limit", type=int)
    ap.add_argument("--match", help="regex on ref key")
    ap.add_argument("--refresh", action="store_true")
    a = ap.parse_args()
    store = ad.store
    if a.cmd in ("discover", "run"):
        prev = json.loads((store.dir / "discovery.json").read_text())["checkpoint"] if (store.dir / "discovery.json").exists() else None
        d = ad.discover(prev, C.NET)
        (store.dir / "discovery.json").write_text(json.dumps(dataclasses.asdict(d), indent=0))
        print(f"discover: refs={len(d.refs)} complete={d.complete} stop={d.stop_reason}")
    if a.cmd in ("fetch", "run"):
        refs, _ = _refs(store, ad)
        done = {s["ref"] for s in store.snapshots() if s["status"] == 200 and s["adapter"] == f"{ad.id}@{ad.version}"}
        todo = [r for r in refs if (a.refresh or r.key not in done) and (not a.match or re.search(a.match, r.key))]
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
            if s is None or s.status != 200:
                fails += 1
                if fails >= STOP_AFTER:
                    print(f"STOP: {fails} consecutive failures (last {r.key})"); break
            else:
                fails = 0; n += 1
                if n % 10 == 0:
                    print(f"fetched {n}/{len(todo)} ({r.key})", flush=True)
        print(f"fetch: {n} fetched, {len(todo)} planned, {len(done)} already done")
    if a.cmd in ("parse", "run"):
        pdir = store.dir / "parsed"; pdir.mkdir(exist_ok=True)
        latest = {}
        for s in store.snapshots():
            if s["status"] == 200 and s["adapter"] == f"{ad.id}@{ad.version}":
                latest[s["ref"]] = s
        refs = {r.key: r for r in _refs(store, ad)[0]} if (store.dir / "discovery.json").exists() else {}
        n = 0
        for k, s in latest.items():
            if (a.match and not re.search(a.match, k)) or (hasattr(ad, "wants") and not ad.wants(s)):
                continue
            snap = C.Snapshot(s["snapshot"], refs.get(k) or C.Ref(ad.source_id, k, s["url"]), 200, s["fetched_at"], s["final_url"], {})
            pr = ad.parse(snap, store, None)
            (pdir / (re.sub(r"[^A-Za-z0-9._-]", "_", k) + ".json")).write_text(json.dumps(dataclasses.asdict(pr)))
            n += 1
        print(f"parse: {n} snapshots -> {pdir}")
