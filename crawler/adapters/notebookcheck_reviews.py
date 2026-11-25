#!/usr/bin/env python3
"""Notebookcheck review adapter v1 (contract ARCHITECTURE 15.5): independent MEASURED flicker values (product/decisions.md D9 (c), D10).
Policy 2026-11-25.1: notebookcheck.net is kind measurement, crawl: agent; robots.txt (`*`) disallows only /nbcbattery/ and /cdn-cgi/. Terms
(Contact.270.0.html): quotes of 100 words or less with a visible link and the name. We keep quotes <= 125 characters, the review URL is the
value's source and the credit 'Notebookcheck (measured)' names it on every value.

discover : review pages only, from SEEDS (review URL + the exact maker model it reviews, set by a person or an agent from a web search).
           Never the 1.1 MB PWM ranking page, never /nbcbattery/. An empty SEEDS list is a valid run (monitor reviews are rare).
fetch    : one GET per review page, 1 req/s, honest UA.
parse    : pure. Identity = the seed's model, which must appear verbatim in the review <title> (else nothing). From the review's own
           'Screen flickering / PWM' box:
             'Screen flickering / PWM not detected'                 -> flk.pwm none
             'Screen flickering / PWM detected <N> Hz ... <= B % brightness setting' -> flk.pwm_freq N (condition brightness_pct B when stated)
           kind measured, measurement.mode optical. flk.pwm low-freq / high-freq is NOT written from a detection: the profile has no
           frequency threshold yet (A1 to rule; proposal in the A2 report). One box per page; two disagreeing boxes = nothing.
"""
import gzip, html, re, sys, time
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
import _contract as C
import _lt as L
import _run

ID, VERSION, SOURCE = "notebookcheck_reviews", 1, "notebookcheck-reviews"
CATEGORIES = {"monitors"}
ADAPTER = f"{ID}@{VERSION}"
DELAY = 1.0
SEEDS = []          # [{"url": "https://www.notebookcheck.net/...Review.N.0.html", "brand": "lenovo", "model": "<exact mfr model>"}]
NOT_DET = re.compile(r"Screen flickering\s*/\s*PWM not detected", re.I)
DET = re.compile(r"Screen flickering\s*/\s*PWM detected\s*(\d[\d,]*(?:\.\d+)?)\s*Hz(.{0,200})", re.I)
BRIGHT = re.compile(r"[≤<]=?\s*(\d{1,3})\s*%\s*brightness setting", re.I)


def page_text(h):
    s = re.sub(r"<script.*?</script>|<style.*?</style>", " ", h, flags=re.S | re.I)
    return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", s)))


def measured(pr, snap, model, key, value, raw, conditions=None):
    c = C.claim(model, key, value, "Hz" if key == "flk.pwm_freq" else None, raw, "s1", ADAPTER, "review_box", snap.fetched_at,
                {"label": "Screen flickering / PWM", "credit": "Notebookcheck (measured)"}, raw[:125], conditions=conditions)
    c["kind"] = "measured"
    c["measurement"] = {"mode": "optical", "by": "Notebookcheck", "url": snap.ref.url}
    pr.claims.append(c)


def parse_page(snap, h):
    pr = C.ParseResult()
    model, brand = (snap.ref.hints or {}).get("model"), (snap.ref.hints or {}).get("brand")
    tm = re.search(r"<title>(.*?)</title>", h, re.S)
    title = html.unescape(re.sub(r"\s+", " ", tm[1])).strip() if tm else ""
    src = L.source(snap, f"Notebookcheck review: {title[:90]}")
    src["tier"] = "measurement"
    pr.sources = [src]
    if not model or not brand or not re.search(r"(?<![A-Za-z0-9])" + re.escape(model) + r"(?![A-Za-z0-9])", title, re.I):
        pr.absences.append({"key": "*", "reason": f"review title does not name the seed model {model!r}", "source": "s1"})
        pr.fingerprints = {"raw": snap.snapshot, "title": title}
        return pr
    pr.identifiers.append(L.ident("mfr_model", model, "model", brand, market=None))
    t = page_text(h)
    nd, det = NOT_DET.findall(t), list(DET.finditer(t))
    freqs = {float(m[1].replace(",", "")) for m in det}
    if nd and not det:
        measured(pr, snap, model, "flk.pwm", "none", nd[0])
    elif det and not nd and len(freqs) == 1:
        m = det[0]
        b = BRIGHT.search(m[2])
        f = freqs.pop()
        measured(pr, snap, model, "flk.pwm_freq", int(f) if f == int(f) else f, (m[0])[:300],
                 {"brightness_pct": int(b[1])} if b else None)
    pr.fingerprints = {"raw": snap.snapshot, "title": title, "not_detected": len(nd), "detected": [m[1] for m in det][:3]}
    return pr


class NotebookcheckReviews:
    id, version, source_id, categories = ID, VERSION, SOURCE, CATEGORIES

    def __init__(self):
        self.store = C.BlobStore(SOURCE)

    def discover(self, checkpoint, net):
        refs = [C.Ref(SOURCE, re.sub(r"\W+", "-", s["model"]).lower(), s["url"], {"model": s["model"], "brand": s["brand"]}) for s in SEEDS
                if "/nbcbattery/" not in s["url"]]
        return C.Discovery(refs, True, None, {"seeds": len(refs)})

    def fetch(self, ref, prior, net):
        now = time.strftime("%FT%TZ", time.gmtime())
        r = net.get(ref.url, DELAY)
        if r is None or isinstance(r, str) or r.status_code != 200:
            st = r if (r is None or isinstance(r, str)) else r.status_code
            s = C.Snapshot("sha256:", ref, st or "breaker", now, ref.url, {})
            self.store.append(s, ADAPTER, ".html.gz")
            return s
        s = C.Snapshot(self.store.put(gzip.compress(r.content, 6, mtime=0), ".html.gz"), ref, 200, now, r.url, {})
        self.store.append(s, ADAPTER, ".html.gz")
        return s

    def parse(self, snap, blobs, profile):
        return parse_page(snap, gzip.decompress(blobs.read(snap.snapshot, ".html.gz")).decode("utf-8", "replace"))


if __name__ == "__main__":
    _run.main(NotebookcheckReviews())
