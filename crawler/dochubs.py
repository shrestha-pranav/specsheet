#!/usr/bin/env python3
"""Document hub pages (data/document-hubs.yaml, kind: hub). `fetch` GETs each hub once through crawl.Net (robots.txt, honest UA, per-host
delay; a block is recorded, never worked around), stores the body in raw/_documents/hubs/ (content addressed, append-only log) and writes
raw/_documents/hub-links.json: every PDF link on the latest 200 snapshot of each hub, with the hub's brand and categories. crawler/documents.py
discover merges these as found_on edges {source_id: None, link_role: hub, hub: url, brand, category}; scripts/hubattach.py binds them.

    python3 -I crawler/dochubs.py fetch | links
"""
import gzip, hashlib, json, sys, time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE / "adapters")); sys.path.insert(0, str(HERE))
import _contract as C  # noqa: E402
import documents as D  # noqa: E402
import yaml  # noqa: E402

DIR = C.ROOT / "raw" / "_documents" / "hubs"
CONF = C.ROOT / "data" / "document-hubs.yaml"


def hubs():
    return [h for h in yaml.safe_load(CONF.read_text())["hubs"] if h.get("kind") == "hub"]


def log():
    p = DIR / "snapshots.jsonl"
    return [json.loads(l) for l in p.read_text().splitlines()] if p.exists() else []


def fetch():
    import crawl
    net = crawl.Net()
    DIR.mkdir(parents=True, exist_ok=True)
    out = []
    for h in hubs():
        r = net.get(h["url"], 1.0)
        now = time.strftime("%FT%TZ", time.gmtime())
        rec = {"url": h["url"], "fetched_at": now, "status": r if isinstance(r, str) or r is None else r.status_code}
        if not isinstance(r, str) and r is not None and r.status_code == 200:
            body = r.content
            sha = hashlib.sha256(body).hexdigest()
            (DIR / f"{sha}.html.gz").write_bytes(gzip.compress(body, 6, mtime=0))
            rec.update(snapshot=f"sha256:{sha}", blob=f"{sha}.html.gz", final_url=r.url)
        with open(DIR / "snapshots.jsonl", "a") as f:
            f.write(json.dumps(rec) + "\n")
        out.append(rec)
    links()
    return out


def links():
    latest = {}
    for r in log():
        if r.get("status") == 200 and r.get("blob"):
            latest[r["url"]] = r
    res = []
    for h in hubs():
        r = latest.get(h["url"])
        if not r:
            continue
        body = gzip.decompress((DIR / r["blob"]).read_bytes()).decode("utf-8", "replace")
        for u, t in sorted(D.links_in(r.get("final_url") or h["url"], body).items()):
            res.append({"url": u, "text": t, "hub": h["url"], "brand": h["brand"], "categories": h["categories"], "hub_snapshot": r["snapshot"],
                        "hub_fetched_at": r["fetched_at"]})
    (C.ROOT / "raw" / "_documents" / "hub-links.json").write_text(json.dumps({"format": 1, "links": res}, indent=0))
    return res


if __name__ == "__main__":
    if sys.argv[1:] == ["fetch"]:
        print(json.dumps(fetch(), indent=1))
    else:
        print(len(links()))
