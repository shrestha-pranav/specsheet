#!/usr/bin/env python3
"""Belkin US support-article adapter v1 (contract ARCHITECTURE 15.5), category power-banks. Source = www.belkin.com/support-article/?articleNum=N
(Belkin's own per-SKU knowledge articles: "Getting to know the ... BPB012", "Belkin BPB012 Frequently Asked Questions", "Meet the ... (BPB036)").
Why (product/decisions.md D9 decision 1a): Belkin product pages never print PPS; its support articles do, per SKU.

discover : one GET per power-bank model to the product page's own Support tab feed (the `data-href` of #supportTab on every /p/ page:
           /on/demandware.store/Sites-BELKUS-Site/en_US/Product-GetPDPSupportArticles?pid=<first colour SKU>; robots.txt allows it, the
           site search `Search-Show` is never used). Models and SKUs come from the stored belkin-us-powerbanks discovery (no request).
           An article becomes a Ref only when its title names exactly ONE Belkin model code and that code is a known power-bank model.
           The feed bodies are stored as blobs (provenance of the discovery); claims are never read from them.
fetch    : the article page itself, 1 req/s, honest UA, one GET per article.
parse    : pure. Identity = the single model code printed in the page title (must equal the Ref's model; several codes = nothing).
           pd.pps true ONLY from an affirmative statement in one block (bullet / paragraph / table row) that names PPS and a USB-C output
           ("45W max USB-C fast charging (PPS supported)", "USB-C port supports PD 3.1 and PPS"); questions, negations ("no", "not",
           "does not") or any negative PPS block anywhere on the page = nothing. Never false (A1 complete-enumeration rule, not met here).
           out.max_single_port_w only from a figure that says it is the maximum of ONE named USB-C port or integrated USB-C cable ("45W max
           USB-C", "up to 30W from a single USB-C port", "USB-C: 5V/3A (15W Max)", "USB-C port: Power Delivery (PD) 20W max", "The USB-C port
           supports charging output up to 18W"); blocks about input/recharging, simultaneous/shared/combined/total output or several ports are
           skipped, and so is every line under an 'Input:' heading (the recharge port); two different figures on the page, or a USB-A output
           line with a higher figure, = nothing.
Traps    : comparison charts and multi-product FAQs name several products (or none) in the title: they attach nothing. A PPS cell in a
           comparison table is never read.
"""
import gzip, html, json, re, sys, time
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
import _contract as C
import _lt as L
import _run

ID, VERSION, SOURCE = "belkin_support", 1, "belkin-us-support"
CATEGORIES = {"power-banks"}
ADAPTER = f"{ID}@{VERSION}"
FEED = "https://www.belkin.com/on/demandware.store/Sites-BELKUS-Site/en_US/Product-GetPDPSupportArticles?pid="
ARTICLE = "https://www.belkin.com/support-article/?articleNum="
PRODUCTS = "belkin-us-powerbanks"
DELAY = 1.0
CODE = re.compile(r"(?<![A-Za-z0-9])((?:B[A-Z]{2}|ENA)\d{3})(?=[a-z]{2}[A-Z]{2}|[^A-Za-z0-9]|$)")
NEG = re.compile(r"\b(?:no|not|doesn['’]?t|does not|without|isn['’]?t|unsupported|non-PPS)\b", re.I)
USBC = re.compile(r"USB[- ]?C|Type[- ]C", re.I)
SP_W = [re.compile(r"(?<![\d.])(\d{2,3}(?:\.\d)?)\s*W\s+max(?:imum)?\s+USB[- ]?C\b", re.I),                    # '45W max USB-C fast charging'
        re.compile(r"up to\s+(\d{2,3}(?:\.\d)?)\s*W\s+(?:from|via|through)\s+(?:a|one)\s+single\s+USB[- ]?C\s+port", re.I),
        re.compile(r"\bsingle\s+USB[- ]?C\s+port[^.;|]{0,30}?up to\s+(\d{2,3}(?:\.\d)?)\s*W\b", re.I),
        # one named USB-C port (or integrated cable) and its own maximum: 'USB-C: 5V/3A (15W Max)', 'USB-C port: Power Delivery (PD) 20W max',
        # 'USB-C port / USB-C cable output: up to 45W max', 'The USB-C port supports charging output up to 18W'
        re.compile(r"^(?:Integrated\s+)?USB[- ]?C(?:\s+port)?(?:\s*/\s*USB[- ]?C\s+cable)?(?:\s+output)?\s*[:⎓]\s*[^|]{0,40}?\(?(\d{1,3}(?:\.\d)?)\s*W\s*max\b", re.I),
        re.compile(r"^The (?:integrated\s+)?USB[- ]?C (?:port|cable) supports (?:charging )?output (?:of )?up to (\d{1,3}(?:\.\d)?)\s*W\b", re.I)]
NOT_SINGLE = re.compile(r"input|recharg|simultaneous|shared|combined|total|\bports\b|\bboth\b", re.I)


def codes(title):
    return sorted(set(CODE.findall(title or "")))


def blocks(h):
    """Article body -> text blocks (li / p / tr / headings), markup stripped. The article body is the main content: page chrome is dropped by
    cutting at the article title heading."""
    s = re.sub(r"<script.*?</script>|<style.*?</style>|<nav.*?</nav>|<header.*?</header>|<footer.*?</footer>", " ", h, flags=re.S | re.I)
    s = re.sub(r"(?i)</?(?:li|p|tr|h[1-6]|br|div)[^>]*>", "\n", s)
    s = re.sub(r"(?i)</t[dh]>", " | ", s)
    t = html.unescape(re.sub(r"<[^>]+>", " ", s))
    return [re.sub(r"\s+", " ", b).strip(" |") for b in t.split("\n") if re.sub(r"\s+", " ", b).strip(" |")]


def article_text(h, title):
    bs = blocks(h)
    t0 = (title or "")[:40]
    start = next((i for i, b in enumerate(bs) if t0 and b.startswith(t0) and i > 0), 0)
    if not start:                    # the article heading was not found: page chrome only, read nothing
        return []
    end = next((i for i in range(start + 1, len(bs)) if re.match(r"^(Was this article helpful|Related Articles|Still need help|Additional Support Questions)", bs[i], re.I)),
               len(bs))
    return bs[start + 1:end]


SECTION = re.compile(r"(?:^|\|)\s*(Input|Output)s?\s*:?\s*$", re.I)


def sections(bs):
    """-> [(block, section)] where section is 'input' / 'output' / None: the last 'Input:' / 'Output:' heading above the block, reset by a
    question. Port lines under an Input heading are the recharge port, never an output."""
    out, sec = [], None
    for b in bs:
        m = SECTION.search(b)
        if m:
            sec = m[1].lower()
            continue
        if b.rstrip().endswith("?"):
            sec = None
        out.append((b, sec))
    return out


def pps(bs):
    """-> (True, block) | None. Affirmative only; any negative or question PPS block on the page voids it."""
    pos, neg = [], []
    for b, sec in sections(bs):
        if sec == "input":
            continue
        if not re.search(r"\bPPS\b|Programmable Power Supply", b):
            continue
        if b.rstrip().endswith("?"):
            continue
        if NEG.search(b) or "|" in b:            # a negated statement, or a table row (comparison charts): never read as affirmative
            neg.append(b)
        elif USBC.search(b):
            pos.append(b)
    if neg or not pos:
        return None
    return True, pos[0]


def single_port_w(bs):
    found = {}
    for b, sec in sections(bs):
        if sec == "input" or b.rstrip().endswith("?") or NOT_SINGLE.search(b):
            continue
        for rx in SP_W:
            for m in rx.finditer(b):
                found.setdefault(float(m[1]), b)
    usba = [float(m[1]) for b, sec in sections(bs) if sec != "input" and re.match(r"^USB[- ]?A\b", b, re.I)
            for m in re.finditer(r"(?<![\d.])(\d{1,3}(?:\.\d)?)\s*W\b", b)]
    if len(found) == 1 and not any(x > next(iter(found)) for x in usba):     # a USB-A line above the USB-C figure: the best port is not USB-C
        (w, b), = found.items()
        return (int(w) if w == int(w) else w), b
    return None


def parse_page(snap, h):
    pr, key = C.ParseResult(), snap.ref.key
    model = (snap.ref.hints or {}).get("model")
    tm = re.search(r"<title>(.*?)</title>", h, re.S)
    title = html.unescape(re.sub(r"\s+", " ", tm[1])).strip() if tm else ""
    title = re.sub(r"^Belkin Official Support\s*-\s*", "", title)
    pr.sources = [L.source(snap, f"Belkin US support article {key}: {title[:80]}")]
    cs = codes(title)
    if len(cs) != 1 or cs[0] != model:
        pr.absences.append({"key": "*", "reason": f"title names {cs or 'no'} model code(s), not exactly the Ref's {model}", "source": "s1"})
        pr.fingerprints = {"raw": snap.snapshot, "title": title, "codes": cs}
        return pr
    pr.identifiers.append(L.ident("mfr_model", model, "model", "belkin"))
    bs = article_text(h, title)

    def add(k, val, raw, label):
        L.add(pr, ADAPTER, snap, k, val, raw, "model_code", model, label)
        if pr.claims and pr.claims[-1]["key"] == k:
            pr.claims[-1]["quote"] = raw[:125]
    p = pps(bs)
    if p:
        add("pd.pps", True, p[1], "support article (PPS statement)")
    w = single_port_w(bs)
    if w:
        add("out.max_single_port_w", w[0], w[1], "support article (single-port USB-C statement)")
    pr.fingerprints = {"raw": snap.snapshot, "title": title, "blocks": len(bs),
                       "pps_blocks": [b[:160] for b in bs if re.search(r"\bPPS\b", b)][:6]}
    return pr


class BelkinSupport:
    id, version, source_id, categories = ID, VERSION, SOURCE, CATEGORIES

    def __init__(self):
        self.store = C.BlobStore(SOURCE)

    def discover(self, checkpoint, net):
        ps = C.BlobStore(PRODUCTS)
        models = [(r["key"].upper(), (r.get("hints") or {}).get("skus") or []) for r in json.loads((ps.dir / "discovery.json").read_text())["refs"]]
        known = {m for m, _ in models}
        refs, feeds, seen = [], {}, set()
        for model, skus in models:
            if not skus:
                continue
            r = net.get(FEED + skus[0], DELAY)
            st = getattr(r, "status_code", r)
            if st != 200:
                feeds[model] = {"status": st}
                continue
            feeds[model] = {"status": 200, "blob": self.store.put(gzip.compress(r.content, 6, mtime=0), ".json.gz")}
            try:
                arts = ((r.json() or {}).get("productModel") or {}).get("supportArticles") or []
            except ValueError:
                continue
            for a in arts:
                num, title = str(a.get("articleNum") or ""), html.unescape(str(a.get("title") or ""))
                cs = codes(title)
                if not num.isdigit() or num in seen or len(cs) != 1 or cs[0] not in known:
                    continue
                seen.add(num)
                refs.append(C.Ref(SOURCE, num, ARTICLE + num, {"model": cs[0], "title": title, "type": a.get("type"), "via_feed": model}))
        return C.Discovery(refs, True, None, {"models": len(models), "feeds": feeds, "articles": len(refs)})

    def fetch(self, ref, prior, net):
        now = time.strftime("%FT%TZ", time.gmtime())
        r = net.get(ref.url, DELAY)
        if r is None or isinstance(r, str) or r.status_code != 200:
            st = r if (r is None or isinstance(r, str)) else r.status_code
            s = C.Snapshot("sha256:", ref, st or "breaker", now, ref.url, {})
            self.store.append(s, ADAPTER, ".html.gz")
            return s
        s = C.Snapshot(self.store.put(gzip.compress(r.content, 6, mtime=0), ".html.gz"), ref, 200, now, r.url,
                       {"etag": r.headers.get("ETag"), "last_modified": r.headers.get("Last-Modified")})
        self.store.append(s, ADAPTER, ".html.gz")
        return s

    def parse(self, snap, blobs, profile):
        return parse_page(snap, gzip.decompress(blobs.read(snap.snapshot, ".html.gz")).decode("utf-8", "replace"))


if __name__ == "__main__":
    _run.main(BelkinSupport())
