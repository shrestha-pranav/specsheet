#!/usr/bin/env python3
"""Razer (US) adapter v1, contract ARCHITECTURE 15.5.

discover : https://www.razer.com/sitemap.xml -> its Product-en-US-USD sitemap (hosted on api-p1.phoenix.razer.com; the context= query
           belongs to that sitemap URL, razer.com's own robots rule `Disallow: /*?*` is respected for razer.com pages) -> unique
           /gaming-laptops/<series>/<RZ09-...> URLs (refurbished /refurb-laptops/ and accessories skipped). One page per orderable SKU.
fetch    : the SKU page (1.4 MB Angular SSR). Embedded state: <script id="ng-state"> JSON -> razerBtoVariants {code, name, price,
           stock, description, classifications[system-laptops-facets, laptop-specifications], marketingPageUrl, baseProductName}.
parse    : pure. configuration identifier mfr_sku = RZ09-xxxxxEN3-R3U1 (R3U1 = US keyboard/region), model identifier mfr_model =
           RZ09-xxxx (platform: first 4 digits of the code; a platform covers the config digit + CPU/GPU suffix), series = marketing
           page slug (razer-blade-16). Claims = raw literal rows of the `laptop-specifications` table (+ facets: refresh rate, TGP,
           panel technology) at locator.sku. Price/stock are claims on sw.msrp only (store price at fetch).
"""
import json, re, sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import _contract as C
import _lt as L
import _run

DELAY = 1.0
ROOT_SM = "https://www.razer.com/sitemap.xml"
LABELMAP = {
    "Color": "gen.color", "Operating System": "sw.os", "Processor": "cpu.model", "Graphics": "gpu.model", "Display": "disp.size", "Memory": "mem.size",
    "Storage": "stor.size", "I/O Ports": "port.usbc_list", "Audio": "in.speakers", "Battery": "pwr.battery_wh", "Chassis": "phys.material",
    "Weight": "phys.weight", "Dimensions": "phys.dimensions", "Warranty": "sw.warranty", "Graphic Features": "gpu.vram", "Connectivity": "wl.wifi",
    "Touch Pad": "input.touchpad", "Keyboard and Touchpad": "in.kb_layout", "Additional features": "input.security_other",
    "Neural Processor": "cpu.npu_tops", "Storage (Installed)": "stor.size", "Storage (Expandable)": "stor.slots", "Camera": "in.webcam",
    "Network and Communication": "wl.wifi", "Power Supply": "pwr.charger_w", "Security": "in.tpm", "Expansion Slots (Including Used)": "port.card_reader",
}
FACET = {"Refresh rate": "disp.refresh", "TGP": "gpu.tgp", "Screen Technology": "disp.panel_type"}


class Razer:
    id, version, source_id, categories = "razer", 1, "razer-us", {"laptops"}

    def __init__(self):
        self.store = C.BlobStore(self.source_id)

    def discover(self, checkpoint, net):
        r = net.get(ROOT_SM, DELAY)
        if not hasattr(r, "status_code") or r.status_code != 200:
            return C.Discovery([], False, f"sitemap index {getattr(r, 'status_code', r)}", checkpoint or {})
        u = next((x for x in re.findall(r"<loc>([^<]+)</loc>", r.text) if "/Product-en-US-" in x), None)
        if not u:
            return C.Discovery([], False, "no Product-en-US sitemap", checkpoint or {})
        r = net.get(u.replace("&amp;", "&"), DELAY)
        if not hasattr(r, "status_code") or r.status_code != 200:
            return C.Discovery([], False, f"product sitemap {getattr(r, 'status_code', r)}", checkpoint or {})
        urls = sorted({x for x in re.findall(r"<loc>([^<]+)</loc>", r.text) if "/gaming-laptops/" in x and "/RZ09-" in x})
        refs = [C.Ref(self.source_id, x.rsplit("/", 1)[1], x, {"series": x.split("/")[-2]}) for x in urls]
        return C.Discovery(refs, True, None, {"skus": len(refs)})

    def fetch(self, ref, prior, net):
        snap, _ = C.http_snapshot(self.store, ref, ref.url, DELAY, ".html", f"{self.id}@{self.version}")
        return snap

    def parse(self, snap, blobs, profile):
        a = f"{self.id}@{self.version}"
        t = blobs.read(snap.snapshot, ".html").decode("utf-8", "replace")
        pr = C.ParseResult(sources=[L.source(snap, "Razer " + snap.ref.key)])
        m = re.search(r'<script id="ng-state"[^>]*>(.*?)</script>', t, re.S)
        try:
            v = json.loads(m.group(1))["razerBtoVariants"]
        except (AttributeError, KeyError, ValueError):
            pr.absences.append({"key": "id.mpn", "status": "not_published", "source": "s1", "reason": "no ng-state product JSON", "checked_at": snap.fetched_at})
            return pr
        sku = v.get("code") or snap.ref.key
        series = (v.get("marketingPageUrl") or "").rstrip("/").rsplit("/", 1)[-1] or snap.ref.hints.get("series")
        plat = sku[:9] if re.match(r"RZ09-\d{4}", sku) else sku
        pr.identifiers.append(L.ident("mfr_model", plat, "model", "razer", series=series))
        pr.identifiers.append(L.ident("mfr_sku", sku, "configuration", "razer", parent=plat))
        for k, kind in (("name", "retail_title"), ("baseProductName", "marketing_name")):
            if v.get(k):
                pr.aliases.append({"text": v[k], "kind": kind})
        for c in v.get("classifications", []):
            for f in c.get("features", []):
                ls = [x for fv in f.get("featureValues", []) for x in L.lines(fv["value"])]
                if c["code"] == "laptop-specifications":
                    L.mapped(pr, a, snap, LABELMAP, f["name"], ls, "sku", sku)
                elif f["name"] in FACET:
                    L.add(pr, a, snap, FACET[f["name"]], L.val(ls), ls, "sku", sku, "facet:" + f["name"])
        p = v.get("price") or {}
        if p.get("value"):
            L.add(pr, a, snap, "sw.msrp", f"{p['value']} {p.get('currencyIso', 'USD')}", f"store price {p.get('formattedValue')} (stock {((v.get('stock') or {}).get('stockLevelStatus'))}) at fetch", "sku", sku, "price")
        pr.fingerprints["claims"] = len(pr.claims)
        return pr


if __name__ == "__main__":
    _run.main(Razer())
