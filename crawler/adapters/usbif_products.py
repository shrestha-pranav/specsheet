#!/usr/bin/env python3
"""USB-IF Certified Product List adapter v1 (A2-usbif r12; brief coord-2026-11-26-r12). Source www.usb.org (kind certification, crawl agent,
data/source-policy.yaml 2026-11-26.11: robots allows /vtm-products/, no site terms published; free only, no licence grant).

discover : ONE GET of https://www.usb.org/vtm-products/v1/all (the JSON the public /products page's app.js loads), stored as the snapshot
           '_all' (raw JSON as served) through the shared crawl.Net client (own UA, robots + Crawl-delay checked on every hop).
fetch    : no network (the one snapshot is the whole list).
parse    : pure; used by scripts/usbif.py (the overlay transform), which attaches cert.usb_if facts to EXISTING entities only, by exact maker
           model. This adapter mints nothing and is not an importer source.
Usage    : python3 -I crawler/adapters/usbif_products.py discover
"""
import json, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
import _contract as C
from _contract import Ref

ID, VERSION = "usbif_products", 1
ADAPTER = f"{ID}@{VERSION}"
SOURCE_ID = "usbif-certified-products"
URL = "https://www.usb.org/vtm-products/v1/all"
PAGE_URL = "https://www.usb.org/products"
DELAY = 2.0


def discover():
    store = C.BlobStore(SOURCE_ID)
    snap, body = C.http_snapshot(store, Ref(SOURCE_ID, "_all", URL, {}), URL, DELAY, ".json", ADAPTER)
    n = None
    if body is not None:
        d = json.loads(body)
        n = len(d) if isinstance(d, (list, dict)) else None
    doc = {"refs": [{"source_id": SOURCE_ID, "key": "_all", "url": URL, "hints": {"snapshot": snap.snapshot}}],
           "complete": body is not None, "stop_reason": None if body is not None else f"status {snap.status}", "checkpoint": {"rows": n}}
    (store.dir / "discovery.json").write_text(json.dumps(doc, indent=0))
    print("discover:", snap.status, snap.snapshot, n)
    return snap


def latest(store=None):
    """(snapshot record, rows) of the newest status-200 '_all' snapshot, or (None, [])."""
    store = store or C.BlobStore(SOURCE_ID)
    recs = [r for r in store.snapshots() if r.get("status") == 200 and r.get("ref") == "_all"]
    if not recs:
        return None, []
    rec = max(recs, key=lambda r: r["fetched_at"])
    return rec, json.loads(store.read(rec["snapshot"], ".json"))


if __name__ == "__main__":
    if sys.argv[1:] != ["discover"]:
        raise SystemExit("usage: usbif_products.py discover")
    discover()
