#!/usr/bin/env python3
"""TCL US televisions adapter v1 (contract ARCHITECTURE 15.5), category tvs.

discover : https://us.tcl.com/products.json (public Shopify catalogue; robots `User-agent: *` Allow /) -> TV products (title says TV;
           remotes, sound bars, mounts, installation and warranty items dropped). One Ref per variant SKU = TCL model number (65QM8K);
           a series page sells every size as a variant.
fetch    : the series product page HTML (one GET per handle; sibling sizes reuse it within the run) + the catalogue's variant list, stored
           as one gzip JSON blob {handle, url, variants[{sku, title}], page}.
parse    : pure. The page carries one 'specifications_box' per screen size: label/value cells (div.specifications_time pairs) under
           MODEL / DISPLAY / ... headings, or (newer theme) one 'variant-specs-panel' per variant with a 'Model' row. A box is attributed
           to a model ONLY when its Model row equals the SKU, or (no Model row) its 'Screen Class'/'Screen Size' equals the variant's size
           AND exactly one box has that size AND exactly one variant has that size, and the box size never contradicts the SKU's size
           (conflict-aware: anything else = absence).
           Labelled rows -> _tv.emit(). TCL is the one maker here that prints the LCD panel family per size ('Screen: HVA Screen').
"""
import gzip, html, json, re, sys, time
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
import _contract as C
import _tv as T
import _run

ID, VERSION, SOURCE = "tcl_tvs", 3, "tcl-us-tvs"
CATEGORIES = {"tvs"}
ADAPTER = f"{ID}@{VERSION}"
DELAY = 1.0
BASE = "https://us.tcl.com"
NOT_TV = re.compile(r"remote|install|mount|sound ?bar|warranty|projector|placeholder|\bstand\b|cable|fee\b", re.I)
SKU = re.compile(r"^\d{2,3}[A-Z][A-Z0-9]{1,8}$")


def size_of(s):
    m = re.search(r"(\d{2,3}(?:\.\d)?)\s*(?:\"|”|''|-inch|in\b|”)", s or "")
    return m.group(1) if m else None


class TclTvs:
    id, version, source_id, categories = ID, VERSION, SOURCE, CATEGORIES

    def __init__(self):
        self.store = C.BlobStore(SOURCE)
        self.pages = {}

    def discover(self, checkpoint, net):
        refs, page = [], 1
        while page <= 10:
            r = net.get(f"{BASE}/products.json?limit=250&page={page}", DELAY)
            if not hasattr(r, "status_code") or r.status_code != 200:
                return C.Discovery(refs, False, f"products.json page {page}: {getattr(r, 'status_code', r)}", {"page": page})
            ps = r.json().get("products") or []
            if not ps:
                break
            for p in ps:
                if not re.search(r"\bTV\b", p.get("title") or "") or NOT_TV.search(p.get("title") or ""):
                    continue
                vs = [{"sku": (v.get("sku") or "").strip().upper(), "title": v.get("title") or ""} for v in p.get("variants") or []]
                for v in vs:
                    if SKU.match(v["sku"]):
                        refs.append(C.Ref(SOURCE, v["sku"], f"{BASE}/products/{p['handle']}",
                                          {"handle": p["handle"], "variant_title": v["title"], "variants": vs, "title": p.get("title")}))
            page += 1
        seen, out = set(), []
        for r in refs:
            if r.key not in seen:
                seen.add(r.key); out.append(r)
        return C.Discovery(out, True, None, {"models": len(out)})

    def fetch(self, ref, prior, net):
        now = time.strftime("%FT%TZ", time.gmtime())
        h = ref.hints.get("handle")
        if h not in self.pages:
            r = net.get(ref.url, DELAY)
            if not hasattr(r, "status_code") or r.status_code != 200:
                s = C.Snapshot("sha256:", ref, getattr(r, "status_code", r) or "breaker", now, ref.url, {})
                self.store.append(s, ADAPTER, ".json.gz")
                return s
            body = json.dumps({"handle": h, "url": ref.url, "title": ref.hints.get("title"), "variants": ref.hints.get("variants"),
                               "page": r.text}, sort_keys=True).encode()
            self.pages[h] = self.store.put(gzip.compress(body, 6, mtime=0), ".json.gz")
        s = C.Snapshot(self.pages[h], ref, 200, now, ref.url, {})
        self.store.append(s, ADAPTER, ".json.gz")
        return s

    def parse(self, snap, blobs, profile):
        d = json.loads(gzip.decompress(blobs.read(snap.snapshot, ".json.gz")))
        return parse_page(snap, d)


def boxes(page):
    """-> [{label: value}] one dict per size. Two theme layouts: (a) one 'specifications_box' per size, (b) 'variant-specs-panel' blocks
    (one per Shopify variant, several sub-boxes each, a 'Model' row naming the variant SKU)."""
    rx = r'<div class="variant-specs-panel"' if '<div class="variant-specs-panel"' in page else r'<div class="specifications_box"'
    starts = [m.start() for m in re.finditer(rx, page)]
    out = []
    for a, b in zip(starts, starts[1:] + [len(page)]):
        cells = [T.clean(re.sub(r"<[^>]+>", " ", c)) for c in re.findall(r'<div class="specifications_time">(.*?)</div>', page[a:b], re.S)]
        rows = {}
        for k, v in zip(cells[::2], cells[1::2]):
            if k:
                rows.setdefault(k, v)
        out.append(rows)
    return out


def box_size(b):
    for lab in ("Screen Class", "Screen Size"):
        v = b.get(lab, "")
        if re.fullmatch(r"\d{2,3}", v):
            v += '"'
        if size_of(v):
            return size_of(v)
    return None


def parse_page(snap, d):
    pr, obs, sku = C.ParseResult(), snap.fetched_at, snap.ref.key.upper()
    variants = d.get("variants") or []
    mine = next((v for v in variants if v["sku"] == sku), None)
    if mine is None:
        pr.absences.append({"key": "*", "reason": f"{sku} not a variant of {d.get('handle')}", "source": "s1"})
        return pr
    size = size_of(mine["title"]) or (re.match(r"^(\d{2,3})", sku).group(1) if mine["title"] == "Default Title" else None)
    pr.sources = [{"id": "s1", "url": d["url"], "label": f"TCL US {d.get('title') or d['handle']}", "source_id": SOURCE, "tier": "manufacturer",
                   "retrieved_at": obs, "snapshot": snap.snapshot}]
    pr.identifiers.append({"scheme": "mfr_model", "value": sku, "value_raw": sku, "issuer": "tcl", "market": "US", "package_level": "model",
                           "role": "key", "sources": ["s1"]})
    if d.get("title"):
        pr.aliases.append({"text": T.clean(d["title"]), "kind": "marketing_name", "source": "s1", "observed_at": obs})
    bx = boxes(d.get("page") or "")
    same_size = [v for v in variants if (size_of(v["title"]) or (re.match(r"^(\d{2,3})", v["sku"]) or [None, None])[1]) == size]
    hits = [b for b in bx if b.get("Model", "").upper() == sku]          # a box that names the SKU itself
    how = "model_row"
    if not hits:
        hits, how = [b for b in bx if box_size(b) == size and not b.get("Model")], "size"
    if hits and any(b.get("Model") and b["Model"].upper() != sku for b in hits):
        hits = []
    if not size or len(same_size) != 1 or len(hits) != 1 or (box_size(hits[0]) not in (None, size)):
        pr.absences.append({"key": "*", "reason": f"spec box not attributable: size {size!r}, {len(same_size)} variants of that size, {len(hits)} boxes "
                                                  f"with that Screen Class (of {len(bx)})", "source": "s1"})
        pr.fingerprints = {"raw": snap.snapshot, "model": sku, "boxes": len(bx), "attributed": False}
        return pr
    rows = hits[0]
    used = T.emit(pr, "tcl", sku, rows, ADAPTER, "table", obs)
    pr.fingerprints = {"raw": snap.snapshot, "model": sku, "boxes": len(bx), "attributed": how, "terms": len(rows),
                       "unmapped": {k: v for k, v in rows.items() if k not in used}}
    return pr


if __name__ == "__main__":
    _run.main(TclTvs())
