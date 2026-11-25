#!/usr/bin/env python3
"""Maker spec-image OCR input stage (A3 document pipeline, 2026-11-25). Store: raw/_specimages/ (derived, rebuildable; no new crawl).

    python3 -I crawler/specimages.py discover        # offline: v0 Anker gallery images (raw/anker/products/*/assets.json) -> discovery.json
    python3 -I crawler/specimages.py ocr [--workers N]  # tesseract on the bytes already on disk -> ocr/<sha>.json
    python3 -I crawler/specimages.py stats

discover  Reads only what we hold. Every gallery image whose file name marks it a spec/detail image (coverage_audit.SPEC_IMG: spec, param,
          label, rating, _TDnn, ...) on a crawl.py v0 Anker page is tied to the REGISTERED page it was found on: the v0 page URL must equal the
          URL of a v1 snapshot of a registered source (same rule as crawler/documents.py). For that linking page we record its variant SKUs
          (the page's own __NEXT_DATA__ product.variants, bundles/combos excluded): a page with exactly one SKU is single-SKU. The image file
          name's model-like tokens (A2667111_TD02 -> A2667111) are recorded too; they are never identity evidence on their own, only a veto
          (scripts/imgattach.py). Images must already be on disk (v0 assets blob with a matching sha256) -- this stage makes NO request; an image
          that is not on disk is counted, never fetched. Host: cdn.shopify.com only (a document_host in data/source-policy.yaml).
ocr       Preprocess (grayscale, 2x Lanczos upscale, PIL) then `tesseract --psm 3 tsv`; per image {lines: [[word, conf]], text, mean_conf}.
          Content addressed by the image sha256; extractor id `imgocr@1` (a preprocessing or tool change = new id = cache miss).
"""
import argparse, gzip, json, re, subprocess, sys, tempfile, time
from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE / "adapters"))
sys.path.insert(0, str(HERE))
import _contract as C  # noqa: E402
import documents as D  # noqa: E402

ROOT = C.ROOT
STORE = ROOT / "raw" / "_specimages"
OCR = "imgocr@1"
SLUGS = ("anker",)
HOSTS = {"cdn.shopify.com"}
SPEC_IMG = re.compile(r"spec|param|label|rating|dimension|size[-_]chart|_td\d|detail[-_]?page", re.I)   # = coverage_audit.SPEC_IMG
FILE_MODEL = re.compile(r"(?<![A-Z0-9])([A-Z]\d{4}[A-Z0-9]{0,4})(?![A-Z0-9])")


def file_models(url):
    base = url.split("?")[0].rsplit("/", 1)[-1].upper()
    return sorted(set(FILE_MODEL.findall(re.sub(r"[_\-.]", " ", base))))


def page_skus(store_dir, rec):
    """-> sorted non-bundle variant SKUs of one Anker page snapshot (None when the page has no product JSON)."""
    p = store_dir / (rec.get("blob") or "")
    if not p.exists():
        return None
    h = gzip.decompress(p.read_bytes()).decode("utf-8", "replace") if p.name.endswith(".gz") else p.read_text("utf-8", "replace")
    m = re.search(r'<script id="__NEXT_DATA__"[^>]*>(.*?)</script>', h, re.S)
    if not m:
        return None
    prod = (json.loads(m[1]).get("props", {}).get("pageProps", {}) or {}).get("product") or {}
    return sorted({str(v["sku"]).upper() for v in prod.get("variants") or []
                   if v.get("sku") and not str(v["sku"]).upper().startswith(("BUNDLE", "COMBO"))})


def discover():
    reg = D._registry()
    pages = {}
    for sid, meta in sorted(reg.SOURCES.items()):
        if meta.get("legacy") or meta.get("category") not in ("chargers", "power-banks"):
            continue
        st = C.BlobStore.__new__(C.BlobStore)
        st.dir = ROOT / "raw" / sid; st.log = st.dir / "snapshots.jsonl"
        if not st.log.exists():
            continue
        for ref, rec in st.latest().items():
            if rec.get("status") != 200:
                continue
            for u in (rec.get("url"), rec.get("final_url")):
                if u:
                    pages.setdefault(D.page_key(u), (sid, str(ref), rec["url"], meta["category"], st.dir, rec))
    imgs = defaultdict(lambda: {"found_on": {}})
    c = Counter()
    sku_cache = {}
    for slug in SLUGS:
        for f in sorted((ROOT / "raw" / slug / "products").glob("*/assets.json")):
            key = f.parts[-2]
            try:
                a = json.loads(f.read_text())
                purl = json.loads((f.parent / "extract.json").read_text()).get("url")
            except (ValueError, OSError):
                continue
            bind = pages.get(D.page_key(purl)) if purl else None
            for im in a.get("images") or []:
                u = im.get("url") if isinstance(im, dict) else im
                if not u or not SPEC_IMG.search(u.split("?")[0].rsplit("/", 1)[-1]):
                    continue
                c["spec_image_links"] += 1
                if u.split("/")[2] not in HOSTS:
                    c["host_not_listed"] += 1; continue
                blob = f.parents[2] / im["blob"] if isinstance(im, dict) and im.get("blob") else None
                if not (blob and blob.exists() and im.get("sha256")):
                    c["not_on_disk"] += 1; continue
                if bind is None:
                    c["page_not_registered"] += 1; continue
                sid, ref, pu, cat, sdir, rec = bind
                if (sid, ref) not in sku_cache:
                    sku_cache[(sid, ref)] = page_skus(sdir, rec)
                sha = "sha256:" + im["sha256"]
                I = imgs[sha]
                I.setdefault("url", u.split("&width=")[0])
                I.setdefault("blob", str(blob.relative_to(ROOT)))
                I.setdefault("file_models", file_models(u))
                I["found_on"][(sid, ref)] = {"source_id": sid, "ref": ref, "page_url": pu, "category": cat, "via": f"v0:{slug}/{key}",
                                             "page_skus": sku_cache[(sid, ref)], "retrieved_at": rec.get("fetched_at")}
                c["bound_links"] += 1
    out = [{"sha": s, **{k: v for k, v in I.items() if k != "found_on"}, "found_on": sorted(I["found_on"].values(), key=lambda x: (x["source_id"], x["ref"]))}
           for s, I in sorted(imgs.items())]
    c["unique_bound_images"] = len(out)
    STORE.mkdir(parents=True, exist_ok=True)
    tmp = STORE / "discovery.json.tmp"
    tmp.write_text(json.dumps({"generated_at": time.strftime("%FT%TZ", time.gmtime()), "format": 1, "counts": dict(c), "images": out}, indent=0, sort_keys=True))
    tmp.replace(STORE / "discovery.json")
    return dict(c)


def ocr_path(sha):
    return STORE / "ocr" / f"{sha.split(':', 1)[-1]}.json"


def ocr_one(path):
    """Grayscale + 2x upscale, tesseract TSV -> {extractor, lines [[word, conf]], text, mean_conf, words}."""
    from PIL import Image
    with tempfile.TemporaryDirectory() as td:
        im = Image.open(path)
        im.load()
        if im.width * im.height > 12e6:
            im.thumbnail((3000, 3000))
        im = im.convert("L")
        im = im.resize((im.width * 2, im.height * 2), Image.LANCZOS)
        p = Path(td) / "i.png"
        im.save(p)
        lines, confs = D._ocr_tsv(p)
    text = "\n".join(" ".join(w for w, _ in ws) for ws in lines)
    return {"extractor": OCR, "lines": [[[w, c] for w, c in ws] for ws in lines], "text": text,
            "mean_conf": round(sum(confs) / len(confs), 1) if confs else 0.0, "words": len(confs)}


def ocr(workers=8, force=False):
    disc = json.loads((STORE / "discovery.json").read_text())
    todo = []
    st = Counter()
    for im in disc["images"]:
        op = ocr_path(im["sha"])
        if op.exists() and not force:
            try:
                if json.loads(op.read_text()).get("extractor") == OCR:
                    st["cached"] += 1; continue
            except ValueError:
                pass
        todo.append(im)

    def run(im):
        try:
            res = ocr_one(ROOT / im["blob"])
        except Exception as ex:      # noqa: BLE001  (a corrupt image is recorded, never fatal)
            res = {"extractor": OCR, "lines": [], "text": "", "mean_conf": 0.0, "words": 0, "error": type(ex).__name__}
        op = ocr_path(im["sha"])
        op.parent.mkdir(parents=True, exist_ok=True)
        tmp = op.with_suffix(".tmp"); tmp.write_text(json.dumps(res)); tmp.replace(op)
        return "error" if res.get("error") else "ocr"
    with ThreadPoolExecutor(workers) as ex:
        for i, r in enumerate(ex.map(run, todo), 1):
            st[r] += 1
            if i % 100 == 0:
                print(f"[specimages] ocr {i}/{len(todo)}", file=sys.stderr, flush=True)
    return dict(st)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["discover", "ocr", "stats"])
    ap.add_argument("--workers", type=int, default=8)
    ap.add_argument("--force", action="store_true")
    a = ap.parse_args()
    if a.cmd == "discover":
        print(json.dumps(discover(), indent=1))
    elif a.cmd == "ocr":
        print(json.dumps(ocr(a.workers, a.force), indent=1))
    else:
        print(json.dumps(json.loads((STORE / "discovery.json").read_text())["counts"], indent=1))


if __name__ == "__main__":
    main()
