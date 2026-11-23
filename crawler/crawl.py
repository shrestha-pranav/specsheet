#!/usr/bin/env python3
"""Manufacturer-first crawler: enumerate every product a brand sells, keep it all locally.

Stages (each resumable; re-running skips work already done):
  discover  enumerate products (Shopify products.json or sitemaps) -> raw/<slug>/index.jsonl
  pages     fetch each product page (gzip) + extract JSON-LD/OG/next-data, spec tables,
            image + document links, marketing text -> products/<key>/extract.json
  assets    download documents (PDF manuals, spec sheets, certificates) and gallery images,
            content-addressed and deduped per brand -> products/<key>/assets.json

Politeness: robots.txt honoured, one request at a time per host with a delay, Retry-After +
backoff on 429/503, per-host circuit breaker, conditional GET (ETag/Last-Modified) on refresh.
No proxies, no CAPTCHA solving. A blocked host is recorded, never treated as "product gone".

Usage: python3 -I crawler/crawl.py [--brands ugreen,anker] [--stage all|discover|pages|assets]
                                   [--limit N] [--refresh]
Output is local only (raw/ is gitignored).
"""
import argparse, gzip, hashlib, html, json, re, sys, threading, time, urllib.parse, urllib.robotparser
from html.parser import HTMLParser
from pathlib import Path

import requests, yaml

ROOT = Path(__file__).resolve().parent.parent
RAW = ROOT / "raw"
UA = "Mozilla/5.0 (compatible; specsheet-crawler/0.1; +https://github.com/shrestha-pranav/specsheet)"
CFG = yaml.safe_load((Path(__file__).parent / "manufacturers.yaml").read_text())
D = CFG["defaults"]

DOC_WORDS = re.compile(r"manual|user[\s_-]?guide|instruction|datasheet|data[\s_-]?sheet|spec(ification)?[\s_-]?sheet|"
                       r"quick[\s_-]?start|declaration|certificat|safety|warranty|download|\bqsg\b|\bdoc\b", re.I)
PDF_RE = re.compile(r"https?:[^\s\"'<>()\\]+?\.pdf(?:\?[^\s\"'<>()\\]*)?", re.I)
IMG_EXT = re.compile(r"\.(jpe?g|png|webp|avif|gif)(\?|$)", re.I)


# ---------------------------------------------------------------- HTTP with per-host politeness
class Net:
    def __init__(self):
        self.s = requests.Session()
        self.s.headers.update({"User-Agent": UA, "Accept-Language": "en-US,en;q=0.8"})
        self.locks, self.last, self.fails, self.robots = {}, {}, {}, {}
        self.g = threading.Lock()

    def _host(self, url):
        return urllib.parse.urlsplit(url).netloc.lower()

    def allowed(self, url):
        h = self._host(url)
        with self.g:
            rp = self.robots.get(h)
        if rp is None:
            rp = urllib.robotparser.RobotFileParser()
            try:
                r = self.s.get(f"https://{h}/robots.txt", timeout=20)
                rp.parse(r.text.splitlines() if r.status_code == 200 else [])
            except requests.RequestException:
                rp.parse([])
            with self.g:
                self.robots[h] = rp
        return rp.can_fetch("*", url)

    def get(self, url, delay, headers=None, stream=False):
        """Returns requests.Response or None. Records failures per host; opens the breaker at 15."""
        h = self._host(url)
        with self.g:
            lock = self.locks.setdefault(h, threading.Lock())
        if self.fails.get(h, 0) >= 15:
            return None
        if not self.allowed(url):
            return "robots"
        for attempt in range(4):
            with lock:
                wait = self.last.get(h, 0) + delay - time.time()
                if wait > 0:
                    time.sleep(wait)
                try:
                    r = self.s.get(url, timeout=40, headers=headers or {}, stream=stream, allow_redirects=True)
                except requests.RequestException:
                    r = None
                self.last[h] = time.time()
            if r is not None and r.status_code in (200, 304):
                self.fails[h] = 0
                return r
            if r is not None and r.status_code == 404:
                return r
            if r is not None and r.status_code in (429, 503, 502, 500, 520, 403):
                ra = r.headers.get("Retry-After", "")
                time.sleep(min(int(ra) if ra.isdigit() else 5 * 2 ** attempt, 120))
                if r.status_code == 403 and attempt >= 1:
                    break
            else:
                time.sleep(3 * (attempt + 1))
        self.fails[h] = self.fails.get(h, 0) + 1
        return r


NET = Net()


def log(slug, msg):
    line = f"{time.strftime('%F %T')} [{slug}] {msg}"
    print(line, flush=True)
    with open(RAW / "_crawl.log", "a") as f:
        f.write(line + "\n")


def key_for(s):
    return re.sub(r"[^a-z0-9._-]+", "-", s.lower()).strip("-")[:120] or "x"


# ---------------------------------------------------------------- discovery
def discover_shopify(m, out):
    items, page = [], 1
    while True:
        r = NET.get(f"{m['base']}/products.json?limit=250&page={page}", D["delay_s"])
        if not hasattr(r, "status_code") or r.status_code != 200:
            log(m["slug"], f"discovery stopped at page {page}: {getattr(r, 'status_code', r)}")
            return items, False
        prods = r.json().get("products", [])
        (out / "_discovery").mkdir(parents=True, exist_ok=True)
        (out / "_discovery" / f"products-{page}.json").write_text(json.dumps(prods))
        for p in prods:
            items.append({"key": key_for(p["handle"]), "url": f"{m['base']}/products/{p['handle']}",
                          "title": p.get("title"), "product_type": p.get("product_type"),
                          "vendor": p.get("vendor"), "tags": p.get("tags"), "source_id": p.get("id"),
                          "skus": [v.get("sku") for v in p.get("variants", []) if v.get("sku")],
                          "updated_at": p.get("updated_at"), "feed": f"_discovery/products-{page}.json"})
        if len(prods) < 250:
            return items, True
        page += 1


def discover_sitemap(m, out):
    pat, seen, urls, todo, complete = re.compile(m["product_url_regex"]), set(), [], list(m["sitemaps"]), True
    while todo:
        sm = todo.pop()
        if sm in seen:
            continue
        seen.add(sm)
        r = NET.get(sm, D["delay_s"])
        if not hasattr(r, "status_code") or r.status_code != 200:
            log(m["slug"], f"sitemap failed {sm}: {getattr(r, 'status_code', r)}")
            complete = False
            continue
        body = r.content
        if sm.endswith(".gz"):
            body = gzip.decompress(body)
        locs = re.findall(r"<loc>\s*([^<\s]+)\s*</loc>", body.decode("utf-8", "replace"))
        if b"<sitemapindex" in body[:2000]:
            todo += [html.unescape(l) for l in locs]
        else:
            urls += [html.unescape(l) for l in locs if pat.match(html.unescape(l))]
    items, keys = [], set()
    for u in dict.fromkeys(urls):
        k = key_for(urllib.parse.urlsplit(u).path.rstrip("/").split("/")[-1].removesuffix(".html"))
        while k in keys:
            k += "_"
        keys.add(k)
        items.append({"key": k, "url": u})
    return items, complete


def discover(m):
    out = RAW / m["slug"]
    out.mkdir(parents=True, exist_ok=True)
    items, complete = (discover_shopify if m["discovery"] == "shopify" else discover_sitemap)(m, out)
    idx = out / "index.jsonl"
    prev = {json.loads(l)["key"]: json.loads(l) for l in idx.read_text().splitlines()} if idx.exists() else {}
    now = time.strftime("%FT%T")
    for it in items:
        it["first_seen"] = prev.get(it["key"], {}).get("first_seen", now)
        it["last_seen"] = now
    if complete:  # only a complete enumeration may mark products as gone from the catalogue
        cur = {it["key"] for it in items}
        for k, old in prev.items():
            if k not in cur:
                old["gone_since"] = old.get("gone_since", now)
                items.append(old)
    else:
        cur = {it["key"] for it in items}
        items += [o for k, o in prev.items() if k not in cur]
    idx.write_text("".join(json.dumps(i) + "\n" for i in items))
    log(m["slug"], f"discovered {len(items)} products (complete={complete})")
    return items


# ---------------------------------------------------------------- page extraction
class PageParser(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.links, self.imgs, self.meta, self.jsonld, self.scripts = [], [], {}, [], []
        self.tables, self._t, self._row, self._cell, self._in = [], None, None, None, None
        self._a, self.title, self._title = None, "", False
        self.headings, self._h, self.bullets, self._li = [], None, [], None

    def handle_starttag(self, tag, a):
        a = dict(a)
        if tag == "a" and a.get("href"):
            self._a = [a["href"], ""]
        elif tag == "img":
            for k in ("data-zoom", "data-src", "data-original", "src"):
                if a.get(k):
                    self.imgs.append(a[k]); break
            if a.get("srcset"):
                self.imgs.append(a["srcset"].split(",")[-1].strip().split(" ")[0])
        elif tag == "meta" and (a.get("property") or a.get("name")) and a.get("content"):
            self.meta[(a.get("property") or a.get("name")).lower()] = a["content"]
        elif tag == "script":
            t = (a.get("type") or "").lower()
            self._in = "ld" if "ld+json" in t else ("json" if "json" in t or a.get("id") == "__NEXT_DATA__" else "js")
            self._buf = []
        elif tag == "title":
            self._title = True
        elif tag == "table":
            self._t = []
        elif tag == "tr" and self._t is not None:
            self._row = []
        elif tag in ("td", "th") and self._row is not None:
            self._cell = []
        elif tag in ("h1", "h2", "h3"):
            self._h = []
        elif tag == "li":
            self._li = []

    def handle_endtag(self, tag):
        if tag == "a" and self._a:
            self.links.append((self._a[0], " ".join(self._a[1].split())[:200])); self._a = None
        elif tag == "script" and self._in:
            txt = "".join(self._buf)
            (self.jsonld if self._in == "ld" else self.scripts).append(txt) if self._in != "js" or "pdf" in txt.lower() else None
            self._in = None
        elif tag == "title":
            self._title = False
        elif tag in ("td", "th") and self._cell is not None:
            self._row.append(" ".join("".join(self._cell).split())); self._cell = None
        elif tag == "tr" and self._row is not None:
            if any(self._row): self._t.append(self._row)
            self._row = None
        elif tag == "table" and self._t is not None:
            if self._t: self.tables.append(self._t)
            self._t = None
        elif tag in ("h1", "h2", "h3") and self._h is not None:
            h = " ".join("".join(self._h).split())
            if h: self.headings.append(h[:200])
            self._h = None
        elif tag == "li" and self._li is not None:
            t = " ".join("".join(self._li).split())
            if 15 < len(t) < 400: self.bullets.append(t)
            self._li = None

    def handle_data(self, d):
        if self._in:
            self._buf.append(d); return
        if self._title: self.title += d
        if self._a: self._a[1] += d
        if self._cell is not None: self._cell.append(d)
        if self._h is not None: self._h.append(d)
        if self._li is not None: self._li.append(d)


def absolute(base, u):
    u = html.unescape(u.strip())
    if u.startswith("//"):
        u = "https:" + u
    return urllib.parse.urljoin(base, u)


def extract(url, text, feed=None):
    p = PageParser()
    try:
        p.feed(text)
    except Exception as e:  # malformed HTML: keep what we got
        p.meta["_parse_error"] = str(e)[:200]
    ld = []
    for blob in p.jsonld:
        try:
            ld.append(json.loads(blob))
        except json.JSONDecodeError:
            pass
    docs = {}
    for href, t in p.links:
        u = absolute(url, href)
        if u.lower().split("?")[0].endswith(".pdf") or (DOC_WORDS.search(t) and DOC_WORDS.search(u)):
            docs.setdefault(u, {"url": u, "text": t, "via": "link"})
    blob_text = text + "\n".join(p.scripts) + ((feed or {}).get("body_html") or "")
    for u in PDF_RE.findall(blob_text.replace("\\/", "/")):
        u = absolute(url, u)
        docs.setdefault(u, {"url": u, "text": "", "via": "embedded"})
    imgs = []
    for src in ([i.get("src") for i in (feed or {}).get("images", [])] + [p.meta.get("og:image")] +
                [x for d in ld for x in _ld_images(d)] + p.imgs):
        if src and IMG_EXT.search(src.split("#")[0]):
            imgs.append(absolute(url, src))
    imgs = list(dict.fromkeys(imgs))
    products_ld = [d for d in _walk_ld(ld) if str(d.get("@type", "")).lower() in ("product", "productgroup")]
    return {
        "url": url, "title": " ".join(p.title.split()), "meta": p.meta,
        "jsonld_products": products_ld, "jsonld_all_types": sorted({str(d.get("@type")) for d in _walk_ld(ld)}),
        "has_next_data": "__NEXT_DATA__" in text, "headings": p.headings[:80], "bullets": p.bullets[:120],
        "spec_tables": p.tables[:30], "documents": list(docs.values()), "images": imgs,
    }


def _walk_ld(x):
    if isinstance(x, list):
        for i in x:
            yield from _walk_ld(i)
    elif isinstance(x, dict):
        yield x
        for k in ("@graph", "hasVariant", "mainEntity", "itemListElement"):
            if k in x:
                yield from _walk_ld(x[k])


def _ld_images(d):
    out = []
    for x in _walk_ld(d):
        im = x.get("image")
        for i in (im if isinstance(im, list) else [im]):
            if isinstance(i, str):
                out.append(i)
            elif isinstance(i, dict) and i.get("url"):
                out.append(i["url"])
    return out


def fetch_pages(m, items, limit, refresh):
    out = RAW / m["slug"] / "products"
    feeds = {}
    n = ok = 0
    for it in items:
        if it.get("gone_since"):
            continue
        if limit and n >= limit:
            break
        n += 1
        d = out / it["key"]
        if (d / "extract.json").exists() and not refresh:
            ok += 1
            continue
        d.mkdir(parents=True, exist_ok=True)
        feed = None
        if it.get("feed"):
            if it["feed"] not in feeds:
                feeds[it["feed"]] = {str(p["id"]): p for p in json.loads((RAW / m["slug"] / it["feed"]).read_text())}
            feed = feeds[it["feed"]].get(str(it.get("source_id")))
            if feed:
                (d / "feed.json").write_text(json.dumps(feed))
        hdrs = {}
        meta_f = d / "http.json"
        if refresh and meta_f.exists():
            hm = json.loads(meta_f.read_text())
            if hm.get("etag"): hdrs["If-None-Match"] = hm["etag"]
            if hm.get("last_modified"): hdrs["If-Modified-Since"] = hm["last_modified"]
        r = NET.get(it["url"], D["delay_s"], headers=hdrs)
        status = getattr(r, "status_code", r if isinstance(r, str) else "breaker")
        meta_f.write_text(json.dumps({"url": it["url"], "status": status, "fetched_at": time.strftime("%FT%T"),
                                      "final_url": getattr(r, "url", None),
                                      "etag": getattr(r, "headers", {}).get("ETag") if r is not None and not isinstance(r, str) else None,
                                      "last_modified": getattr(r, "headers", {}).get("Last-Modified") if r is not None and not isinstance(r, str) else None}))
        if status == 304:
            ok += 1
            continue
        if status != 200:
            continue
        body = r.content
        (d / "page.html.gz").write_bytes(gzip.compress(body))
        ex = extract(r.url, body.decode(r.encoding or "utf-8", "replace"), feed)
        ex["sha256"] = hashlib.sha256(body).hexdigest()
        (d / "extract.json").write_text(json.dumps(ex, ensure_ascii=False))
        ok += 1
        if n % 50 == 0:
            log(m["slug"], f"pages {n}/{len(items)}")
    log(m["slug"], f"pages done: {ok} ok of {n}")


# ---------------------------------------------------------------- assets
def sized(u):
    if "cdn.shopify.com" in u or "/cdn/shop/" in u:
        parts = urllib.parse.urlsplit(u)
        q = dict(urllib.parse.parse_qsl(parts.query))
        q["width"] = str(D["image_width"])
        return urllib.parse.urlunsplit(parts._replace(query=urllib.parse.urlencode(q)))
    return u


def fetch_assets(m, items, limit, refresh):
    base = RAW / m["slug"]
    store = base / "blobs"
    store.mkdir(parents=True, exist_ok=True)
    n = 0
    for it in items:
        d = base / "products" / it["key"]
        ex_f = d / "extract.json"
        if not ex_f.exists() or it.get("gone_since"):
            continue
        if limit and n >= limit:
            break
        n += 1
        af = d / "assets.json"
        if af.exists() and not refresh:
            continue
        ex = json.loads(ex_f.read_text())
        rec = {"documents": [], "images": []}
        for kind, lst in (("documents", ex["documents"]), ("images", [{"url": u} for u in ex["images"][: D["max_images"]]])):
            for a in lst:
                u = sized(a["url"]) if kind == "images" else a["url"]
                r = NET.get(u, D["cdn_delay_s"], stream=True)
                ent = dict(a, status=getattr(r, "status_code", r if isinstance(r, str) else "breaker"))
                if ent["status"] == 200:
                    ctype = r.headers.get("Content-Type", "").split(";")[0]
                    data, cap = b"", D["max_doc_mb"] * 2**20
                    for chunk in r.iter_content(65536):
                        data += chunk
                        if len(data) > cap:
                            ent["status"] = "too_large"; break
                    if ent["status"] == 200:
                        if kind == "documents" and not data[:5].startswith(b"%PDF") and "pdf" not in ctype:
                            ent["status"] = f"not_pdf:{ctype}"   # a link that looked like a manual but wasn't
                        else:
                            h = hashlib.sha256(data).hexdigest()
                            ext = ".pdf" if kind == "documents" else (Path(urllib.parse.urlsplit(u).path).suffix.lower() or ".img")
                            blob = store / f"{h}{ext}"
                            if not blob.exists():
                                blob.write_bytes(data)
                            ent.update(sha256=h, bytes=len(data), content_type=ctype, blob=f"blobs/{blob.name}")
                    r.close()
                rec[kind].append(ent)
        af.write_text(json.dumps(rec))
        if n % 50 == 0:
            log(m["slug"], f"assets {n}")
    log(m["slug"], f"assets done for {n} products")


# ---------------------------------------------------------------- main
def run(m, args):
    try:
        if args.stage in ("all", "discover"):
            items = discover(m)
        else:
            idx = RAW / m["slug"] / "index.jsonl"
            items = [json.loads(l) for l in idx.read_text().splitlines()] if idx.exists() else []
        if args.stage in ("all", "pages"):
            fetch_pages(m, items, args.limit, args.refresh)
        if args.stage in ("all", "assets"):
            fetch_assets(m, items, args.limit, args.refresh)
    except Exception as e:  # one brand failing must not stop the others
        log(m["slug"], f"FAILED: {type(e).__name__}: {e}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--brands", default="")
    ap.add_argument("--stage", default="all", choices=["all", "discover", "pages", "assets"])
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--refresh", action="store_true")
    args = ap.parse_args()
    RAW.mkdir(exist_ok=True)
    want = set(filter(None, args.brands.split(",")))
    ms = [m for m in CFG["manufacturers"] if not want or m["slug"] in want]
    ts = [threading.Thread(target=run, args=(m, args), name=m["slug"]) for m in ms]
    for t in ts:
        t.start()
    for t in ts:
        t.join()
    (RAW / "_last_run.json").write_text(json.dumps({"finished": time.strftime("%FT%T"), "brands": [m["slug"] for m in ms],
                                                    "stage": args.stage, "limit": args.limit}))


if __name__ == "__main__":
    main()
