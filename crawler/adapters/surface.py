#!/usr/bin/env python3
"""Microsoft Surface laptops (US) adapter v2 (v2: learn "Ports and charging" list -> per-port port.usbc_list + port.tb_usb4 /
port.video_out / port.charge_port via _xports.surface, A2-lap r8), contract ARCHITECTURE 15.5.

discover : (a) Microsoft Store list pages /en-us/store/b/buy-surface-laptop + /store/b/shop-all-microsoft-surface -> every
               /en-us/store/configure/surface-laptop*/<productId> (consumer laptops; dev box excluded);
           (b) learn.microsoft.com/_sitemaps/surface_en-us_1.xml -> /en-us/surface/tech-specs/surface-laptop* (Surface for Business
               tech-spec pages, the official full spec tables; Surface Pro/accessories are out of scope).
fetch    : configure pages (3.5 MB; inline JSON `"skus":[...]` after "skuSelectionTitle": per orderable config
           {inventoryControlSku "ZGM-00062" = Microsoft part number, skuId "85S6" = store sku id, configuration{processor,color,memory,storage},
           price, title}); learn pages (HTML table Feature|Description).
parse    : pure. configure -> model ident x_ms_store_product (productId = size+edition) + per-config mfr_sku (ZGM-xxxxx) with
           cpu/memory/storage/colour/price claims; learn -> model ident x_ms_techspec_page (page slug) + spec-table claims (raw
           line lists; one page covers several sizes/CPU options). The two kinds are NOT merged here (no shared key published).
Not published anywhere fetched: regulatory model numbers (1xxx) and per-config weight (weight is per size, in the learn tables).
www.microsoft.com/en-us/surface/devices/* marketing pages were probed (table: processor/battery/display/ports/weight per size)
but dropped: strictly less than the learn pages.
"""
import json, re, subprocess, sys, time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import _contract as C
import _lt as L
import _run
import _xports

DELAY = 1.0
LISTS = ["https://www.microsoft.com/en-us/store/b/buy-surface-laptop", "https://www.microsoft.com/en-us/store/b/shop-all-microsoft-surface"]
LEARN_MAP = "https://learn.microsoft.com/_sitemaps/surface_en-us_1.xml"
MS = "https://www.microsoft.com"
LABELMAP = {
    "Processor": "cpu.model", "NPU": "cpu.npu_tops", "Graphics": "gpu.model", "Memory": "mem.size", "Storage": "stor.size", "Display": "disp.size",
    "Brightness": "disp.nits_sdr", "Battery life": "pwr.battery_life_claims", "Battery capacities": "pwr.battery_wh", "Ports & charging": "port.usbc_list",
    "Network & connectivity": "wl.wifi", "Security": "in.tpm", "Cameras": "in.webcam", "Audio": "in.speakers", "Software": "sw.os", "Warranty": "sw.warranty",
    "Exterior": "phys.material", "Size & weight": lambda ls: [("phys.dimensions", ls), ("phys.weight", [l for l in ls if re.search(r"[Ww]eight|lbs?\b|kg", l)])],
    "Sensors": None,
}
LABELMAP.update({"Memory and storage": "mem.size", "Keyboard": "in.kb_layout", "Keyboard layout": "in.kb_layout", "Battery capacity": "pwr.battery_wh", "Colors": "gen.color"})
LABELMAP = {k.lower().replace("&", "and"): v for k, v in LABELMAP.items() if v}


_LAST = [0.0]


def curl_get(url):
    """www.microsoft.com/en-us/store/* tarpits python-requests (HTTP/1.1) when the UA is ours (ReadTimeout; same URL answers
    in 0.2 s over curl HTTP/2 with the SAME honest UA). Same identity, different transport: robots checked through Net, 1 req/s."""
    if not C.NET.allowed(url):
        return 0, b""
    time.sleep(max(0.0, _LAST[0] + DELAY - time.time()))
    p = subprocess.run(["curl", "-s", "-L", "--max-time", "90", "-A", C.crawl.UA, "-o", "-", "-w", "\n%{http_code}", url], capture_output=True)
    _LAST[0] = time.time()
    body, _, code = p.stdout.rpartition(b"\n")
    return (int(code) if code.strip().isdigit() else 0), body


def curl_snapshot(store, ref, url, adapter, ext=".html"):
    code, body = curl_get(url)
    now = time.strftime("%FT%TZ", time.gmtime())
    if code != 200:
        snap = C.Snapshot("sha256:", ref, code or "curl-fail", now, url, {})
        store.append(snap, adapter, ext)
        return snap, None
    snap = C.Snapshot(store.put(body, ext), ref, 200, now, url, {})
    store.append(snap, adapter, ext)
    return snap, body


class Surface:
    id, version, source_id, categories = "surface", 3, "microsoft-surface", {"laptops"}

    def __init__(self):
        self.store = C.BlobStore(self.source_id)

    def discover(self, checkpoint, net):
        refs, seen = [], set()
        for u in LISTS:
            code, body = curl_get(u)
            if code != 200:
                return C.Discovery([], False, f"{u} -> {code}", checkpoint or {})
            self.store.put(body, ".html")
            for p in re.findall(r'/en-us/store/configure/(surface-laptop[a-z0-9-]*/[a-z0-9]+)', body.decode("utf-8", "replace")):
                if p not in seen:
                    seen.add(p)
                    slug, pid = p.split("/")
                    refs.append(C.Ref(self.source_id, f"store:{slug}", f"{MS}/en-us/store/configure/{p}", {"kind": "configure", "slug": slug, "product_id": pid}))
        r = net.get(LEARN_MAP, DELAY)
        if not hasattr(r, "status_code") or r.status_code != 200:
            return C.Discovery(refs, False, f"learn sitemap {getattr(r, 'status_code', r)}", checkpoint or {})
        for u in re.findall(r"<loc>(https://learn\.microsoft\.com/en-us/surface/tech-specs/surface-laptop[^<]*)</loc>", r.text):
            slug = u.rsplit("/", 1)[1]
            refs.append(C.Ref(self.source_id, f"learn:{slug}", u, {"kind": "learn", "slug": slug}))
        return C.Discovery(refs, True, None, {"configure": sum(r.hints["kind"] == "configure" for r in refs), "learn": sum(r.hints["kind"] == "learn" for r in refs)})

    def fetch(self, ref, prior, net):
        if "/store/" in ref.url:
            snap, _ = curl_snapshot(self.store, ref, ref.url, f"{self.id}@{self.version}")
        else:
            snap, _ = C.http_snapshot(self.store, ref, ref.url, DELAY, ".html", f"{self.id}@{self.version}")
        return snap

    def parse(self, snap, blobs, profile):
        t = blobs.read(snap.snapshot, ".html").decode("utf-8", "replace")
        kind = snap.ref.hints.get("kind") or snap.ref.key.split(":")[0].replace("store", "configure")
        pr = C.ParseResult(sources=[L.source(snap, "Microsoft Surface " + snap.ref.key)])
        return (self._configure if kind == "configure" else self._learn)(t, snap, pr)

    def _configure(self, t, snap, pr):
        a = f"{self.id}@{self.version}"
        pid = snap.ref.hints.get("product_id") or snap.ref.url.rsplit("/", 1)[1]
        i = t.find('"skuSelectionTitle"')
        j = t.find('"skus":[', i) if i >= 0 else -1
        title = re.search(r'"productConfigurationDrawerTitle":"([^"]*)"', t)
        name = title.group(1) if title else snap.ref.key
        pr.aliases.append({"text": name, "kind": "marketing_name"})
        pr.identifiers.append(L.ident("x_ms_store_product", pid, "model", "microsoft"))
        if j < 0:
            pr.absences.append({"key": "id.mpn", "status": "not_published", "source": "s1", "checked_at": snap.fetched_at})
            return pr
        arr, _ = json.JSONDecoder().raw_decode(t[j + 7:])
        n = 0
        for s in arr:
            cfg = s.get("configuration") or {}
            pn = (s.get("inventoryControlSku") or "").strip()
            if not (pn and cfg.get("processor")):
                continue   # warranty/accessory rows share the array
            n += 1
            pr.identifiers.append(L.ident("mfr_sku", pn, "configuration", "microsoft", parent=pid))
            if s.get("skuId"):
                pr.identifiers.append(L.ident("x_ms_store_sku", s["skuId"], "configuration", "microsoft", role="alias"))
            tt = s.get("tileText") or []
            if s.get("title"):
                pr.aliases.append({"text": s["title"], "kind": "retail_title"})
            L.add(pr, a, snap, "cpu.model", tt[0] if tt else cfg["processor"], tt[:1] or cfg["processor"], "sku", pn, "tileText[0]")
            for k, idx, lab in (("gen.color", 1, "tileText[1]"), ("mem.size", 2, "tileText[2]"), ("stor.size", 3, "tileText[3]")):
                if len(tt) > idx:
                    L.add(pr, a, snap, k, tt[idx], tt[idx], "sku", pn, lab)
            p = s.get("price") or {}
            if p.get("msrp"):
                L.add(pr, a, snap, "sw.msrp", f"{p['msrp']} {p.get('currencyCode', 'USD')}", f"store MSRP {p.get('displaymsrp')} (inStock={((s.get('inventory') or {}).get('inStock'))}) at fetch", "sku", pn, "price.msrp")
        pr.fingerprints["configs"] = n
        return pr

    def _learn(self, t, snap, pr):
        a = f"{self.id}@{self.version}"
        slug = snap.ref.hints.get("slug") or snap.ref.url.rsplit("/", 1)[1]
        h1 = re.search(r"<h1[^>]*>(.*?)</h1>", t, re.S)
        pr.aliases.append({"text": (L.lines(h1.group(1))[0] if h1 and L.lines(h1.group(1)) else slug).replace("Tech specs: ", ""), "kind": "marketing_name"})
        pr.identifiers.append(L.ident("x_ms_techspec_page", slug, "model", "microsoft"))
        main = re.search(r"<main.*?</main>", t, re.S)
        tb = re.search(r"<table.*?</table>", main.group(0) if main else t, re.S)
        rows = 0
        for r in re.findall(r"<tr.*?</tr>", tb.group(0), re.S) if tb else []:
            c = re.findall(r"<t[hd][^>]*>(.*?)</t[hd]>", r, re.S)
            if len(c) < 2 or not L.lines(c[0]) or L.lines(c[0])[0] == "Feature":
                continue
            rows += 1
            lab, ls = L.lines(c[0])[0].lower().replace("&", "and").strip(" :"), [re.sub(r"^[-•]\s*", "", l) for l in L.lines(c[1])]
            L.mapped(pr, a, snap, LABELMAP, lab, ls, "model_code", slug)
            if LABELMAP.get(lab) == "port.usbc_list" and pr.claims and pr.claims[-1]["key"] == "port.usbc_list":
                _xports.replace_claims(pr, C, pr.claims[-1], _xports.surface(ls), slug)
        pr.fingerprints["spec_rows"] = rows
        if not rows:
            pr.absences.append({"key": "disp.size", "status": "not_published", "source": "s1", "checked_at": snap.fetched_at})
        return pr


if __name__ == "__main__":
    _run.main(Surface())
