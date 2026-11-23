#!/usr/bin/env python3
"""Samsung (US) Galaxy Book adapter v1, contract ARCHITECTURE 15.5.

discover : https://www.samsung.com/us/im-sitemap.xml -> /us/computers/galaxy-book/<family>/ pages; each family page links its buy-SPA
           URLs (/us/computers/galaxy-book/<series>/buy/<slug-with-sku-npXXXXXX-xxxus>/ or the bare .../buy/). One Ref per buy-series
           folder (galaxy-book6-series, -edge, -intel-core), pointing at one representative buy page.
fetch    : bundle (one gz-free JSON blob per ref): the representative buy page's embedded state (groupId, every sibling modelCode,
           Product JSON-LD with the page SKU/price/colour) + the buy SPA's own spec API
           GET /us/gapi/v1/bridge/cacheable/bridge-data?data_type=Specs&store_type=B2C&group_id=<id>  (robots: only /us/api/ is
           disallowed; /us/gapi/ is not) = fullSpecs[groupName -> specList[name,value]] for EVERY model code in the group.
parse    : pure. configuration identifier mfr_sku = NP960XJG-KA1US (the Samsung orderable model code, US market), model identifier
           mfr_model = NP960XJG (platform, before the dash). Claims = fullSpecs rows at locator.sku (raw literal; lines split on <br>).
"""
import html, json, re, sys, time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import _contract as C
import _lt as L
import _run

DELAY = 1.0
BASE = "https://www.samsung.com"
API = BASE + "/us/gapi/v1/bridge/cacheable/bridge-data?data_type=Specs&store_type=B2C&group_id={g}"
SKU = re.compile(r"NP[0-9A-Z]{5,8}-[A-Z0-9]{3,6}US", re.I)
MAP = {
    ("Processor", "CPU"): "cpu.model", ("Processor", "Processor / Chipset"): "cpu.model", ("Processor", "GPU"): "gpu.model", ("Processor", "GPU Type"): "gpu.type", ("Processor", "NPU"): "cpu.npu_tops",
    ("Memory", "Memory Capacity"): "mem.size", ("Memory", "Memory"): "mem.type", ("Memory", "Storage Capacity"): "stor.size",
    ("Memory", "Storage Type"): "stor.form_factor", ("Memory", "Number of Storage Slots"): "stor.slots",
    ("Display", "Size (inch)"): "disp.size", ("Display", "Resolution"): "disp.resolution", ("Display", "Type"): "disp.panel_type", ("Display", "Touch Screen"): "disp.touch",
    ("Physical specification", "Weight (kg)"): "phys.weight", ("Physical specification", "Dimension (WxDxH, mm)"): "phys.dimensions",
    ("Battery", "Battery Capacity (Typical, Wh)"): "pwr.battery_wh", ("Power", "AC Adapter"): "pwr.charger_w",
    ("Network", "Wi-Fi"): "wl.wifi", ("Network", "Bluetooth Version"): "wl.bluetooth", ("Network", "Ethernet"): "port.ethernet",
    ("Ports", "USB"): "port.usbc_list", ("Ports", "HDMI"): "port.video_out", ("Ports", "Earjack"): "port.audio", ("Ports", "External Storage Support"): "port.card_reader",
    ("Input", "Keyboard Backlit"): "in.kb_backlit", ("Input", "Keyboard"): "in.kb_layout", ("Input", "Touchpad"): "input.touchpad",
    ("Multimedia", "Camera"): "in.webcam", ("Multimedia", "Speaker"): "in.speakers", ("Security", "FingerPrint Reader"): "in.fingerprint", ("Security", "TPM"): "in.tpm",
    ("General Information", "Color"): "gen.color", ("Operating System", "Operating System"): "sw.os",
}


def _get(net, url):
    r = net.get(url, DELAY)
    return r if hasattr(r, "status_code") and r.status_code == 200 else None


class Samsung:
    id, version, source_id, categories = "samsung", 1, "samsung-us", {"laptops"}

    def __init__(self):
        self.store = C.BlobStore(self.source_id)

    def discover(self, checkpoint, net):
        sm = _get(net, BASE + "/us/im-sitemap.xml")
        if sm is None:
            return C.Discovery([], False, "im-sitemap unavailable", checkpoint or {})
        fams = sorted({u for u in re.findall(r"<loc>([^<]+)</loc>", sm.text) if re.fullmatch(BASE + r"/us/computers/galaxy-book/[a-z0-9-]+/", u)})
        folders = {}
        for f in fams:
            r = _get(net, f)
            if r is None:
                return C.Discovery([], False, f"{f} unavailable", checkpoint or {})
            for m in re.findall(r"/us/computers/galaxy-book/([a-z0-9-]+)/buy/([^\"\\\s?#<]*)", r.text):
                folder, slug = m[0], m[1].strip("/")
                cur = folders.get(folder)
                if cur is None or (not cur[1] and slug):
                    folders[folder] = (f, slug)
        refs = [C.Ref(self.source_id, fo, f"{BASE}/us/computers/galaxy-book/{fo}/buy/{sl}/".replace("//", "/").replace("https:/", "https://") if sl else f"{BASE}/us/computers/galaxy-book/{fo}/buy/",
                      {"family_page": fam}) for fo, (fam, sl) in sorted(folders.items())]
        return C.Discovery(refs, True, None, {"families": fams, "buy_folders": sorted(folders)})

    def fetch(self, ref, prior, net):
        now = time.strftime("%FT%TZ", time.gmtime())
        ad = f"{self.id}@{self.version}"

        def fail(st):
            snap = C.Snapshot("sha256:", ref, st, now, ref.url, {})
            self.store.append(snap, ad, ".json")
            return snap
        page = net.get(ref.url, DELAY)
        if not hasattr(page, "status_code") or page.status_code != 200:
            return fail(getattr(page, "status_code", page))
        t = page.text
        g = re.search(r'"groupId":"(\d+)"', t)
        if not g:
            return fail("no-groupId")
        specs = net.get(API.format(g=g.group(1)), DELAY)
        if not hasattr(specs, "status_code") or specs.status_code != 200:
            return fail(getattr(specs, "status_code", specs))
        jl = []
        for m in re.finditer(r'<script[^>]*ld\+json[^>]*>(.*?)</script>', t, re.S):
            try:
                j = json.loads(m.group(1))
            except ValueError:
                continue
            if isinstance(j, dict) and j.get("@type") == "Product":
                jl.append(j)
        codes = sorted({m.upper() for m in re.findall(r'"modelCode":"(NP[^"]+)"', t)})
        urls = dict(re.findall(r'"modelCode":"(NP[^"]+)"[^{}]{0,400}?"consumerUrl":"([^"]+)"', t))
        bundle = {"group_id": g.group(1), "buy_url": ref.url, "page_model_codes": codes, "consumer_urls": urls, "product_jsonld": jl, "specs": specs.json()}
        body = json.dumps(bundle).encode()
        snap = C.Snapshot(self.store.put(body, ".json"), ref, 200, now, ref.url, {})
        self.store.append(snap, ad, ".json")
        return snap

    def parse(self, snap, blobs, profile):
        a = f"{self.id}@{self.version}"
        b = json.loads(blobs.read(snap.snapshot, ".json"))
        pr = C.ParseResult(sources=[L.source(snap, "Samsung " + snap.ref.key)])
        urls = b.get("consumer_urls") or {}
        jl = {(j.get("sku") or "").upper(): j for j in b.get("product_jsonld", [])}
        for mdl in b["specs"]:
            code = mdl["modelCode"].upper()
            plat = code.split("-")[0]
            pr.identifiers.append(L.ident("mfr_model", plat, "model", "samsung", series=snap.ref.key))
            pr.identifiers.append(L.ident("mfr_sku", code, "configuration", "samsung", parent=plat))
            slug = (urls.get(mdl["modelCode"]) or urls.get(code) or "").rstrip("/").rsplit("/", 1)[-1]
            if slug:
                pr.aliases.append({"text": slug, "kind": "retail_slug"})
            j = jl.get(code)
            if j:
                pr.aliases.append({"text": j.get("name"), "kind": "marketing_name"})
                p = ((j.get("offers") or {}).get("price"))
                if p:
                    L.add(pr, a, snap, "sw.msrp", f"{p} USD", f"samsung.com price {p} USD ({str((j.get('offers') or {}).get('availability', '')).rsplit('/', 1)[-1]}) at fetch", "sku", code, "Offer.price")
            for g in mdl.get("fullSpecs", []):
                for s in g.get("specList", []):
                    key = MAP.get((g["groupName"], html.unescape(s["name"])))
                    ls = L.lines(s.get("value") or "")
                    if key is None:
                        pr.fingerprints.setdefault("unmapped_labels", {})[f"{g['groupName']}/{s['name']}"] = " | ".join(ls)[:80]
                    else:
                        L.add(pr, a, snap, key, L.val(ls), ls, "sku", code, f"{g['groupName']}/{s['name']}")
        pr.fingerprints["models"] = len(b["specs"])
        return pr


if __name__ == "__main__":
    _run.main(Samsung())
