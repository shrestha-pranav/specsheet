#!/usr/bin/env python3
"""Dell (US) adapter v2 (v2: Ports list -> per-port port.usbc_list + port.tb_usb4 / port.video_out / port.charge_port via _xports.dell,
A2-lap r8), contract ARCHITECTURE 15.5.

discover : https://www.dell.com/index-product-pages-hreflang-sitemap.xml.gz -> dhs-product-urls-hreflang-sitemap-000N.xml.gz;
           keep en-us /shop/laptop-computers/spd/<slug> (tablets dropped). ~100 platform pages.
fetch    : the spd page (server-rendered, ~600 kB). Embedded data: <meta name=products content=pa14250_fixed_06;..._reg_01> (the
           platform's config pseudo-SKUs), schema.org Product JSON-LD (sku/mpn = pa14250_reg_01, offer price/availability),
           #tech-spec-container <li><div class="h5">Label</div>value</li> = the spec table of the DEFAULT configuration, and one
           customisation module per component (<h2 module-title> + option buttons) = the orderable option lists.
           <spd>/<pseudo-sku> 302-redirects to the base page, so there is no per-config page to fetch.
parse    : pure. Model identifier = platform code (pa14250). Dell publishes NO orderable per-config part number/order code and no
           regulatory model on these pages (A2 r2 finding re-confirmed): configurations are NOT emitted, the default-config spec
           table is claimed on the model with locator.config="default", component option lists go to fingerprints.options.
Blocked: support.dell.com (Akamai 403) is not used.
"""
import gzip, html, json, re, sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import _contract as C
import _lt as L
import _run
import _xports

IDX = "https://www.dell.com/index-product-pages-hreflang-sitemap.xml.gz"
DELAY = 1.0
UNIT = lambda ls: [("phys.weight", [l for l in ls if re.search(r"weight", l, re.I)])] if any(re.search(r"weight", l, re.I) for l in ls) else []
PALM = lambda ls: [("in.fingerprint", ls)] if any("ingerprint" in l for l in ls) else []
LABELMAP = {
    "Processor": "cpu.model", "Operating System": "sw.os", "Displays": "disp.size", "Display": "disp.size", "Memory": "mem.size", "Storage": "stor.size",
    "Video Card": "gpu.model", "Graphics Card": "gpu.model", "Graphics": "gpu.model", "Keyboard": "in.kb_layout", "Ports": "port.usbc_list", "Battery": "pwr.battery_wh",
    "Power Supply": "pwr.charger_w", "Wireless": "wl.wifi", "Bluetooth": "wl.bluetooth", "Mobile Broadband": "wl.wwan",
    "Camera Software": "in.webcam", "Camera": "in.webcam", "Base Warranty": "sw.warranty", "Systems Management": "cpu.vpro",
    "Dimensions & Weight": lambda ls: [("phys.dimensions", [l for l in ls if not re.search(r"weight", l, re.I)]), *UNIT(ls)],
    "PalmRest": PALM, "Palmrest": PALM, "Fingerprint Reader": "in.fingerprint", "Color": "gen.color", "Chassis": "phys.material", "Slots": "port.card_reader", "Audio and Speakers": "in.speakers", "Chassis Material": "phys.material",
}
LABELMAP = {k: v for k, v in LABELMAP.items() if v}


def codeof(t, slug):
    m = re.search(r"<meta name=products content=([^>\s]+)", t)
    if m:
        c = re.sub(r"_(reg|fixed|ltd|so)_?\w*$", "", m.group(1).split(";")[0])
        if c:
            return c, m.group(1).split(";")
    return slug, []


class Dell:
    id, version, source_id, categories = "dell", 2, "dell-us", {"laptops"}

    def __init__(self):
        self.store = C.BlobStore(self.source_id)

    def _xml(self, net, url):
        r = net.get(url, DELAY)
        if not hasattr(r, "status_code") or r.status_code != 200:
            return None
        b = r.content
        if b[:2] == b"\x1f\x8b":
            b = gzip.decompress(b)
        return b.decode("utf-8", "replace")

    def discover(self, checkpoint, net):
        idx = self._xml(net, IDX)
        if idx is None:
            return C.Discovery([], False, "sitemap index unavailable", checkpoint or {})
        slugs = {}
        for u in re.findall(r"<loc>([^<]+)</loc>", idx):
            x = self._xml(net, u)
            if x is None:
                return C.Discovery([], False, f"sitemap {u} unavailable", checkpoint or {})
            for p in re.findall(r"<loc>(https://www\.dell\.com/en-us/shop/laptop-computers/spd/[^<]+)</loc>", x):
                slug = p.rsplit("/", 1)[1]
                if "tablet" not in slug:
                    slugs[slug] = p
        refs = [C.Ref(self.source_id, s, u, {"slug": s}) for s, u in sorted(slugs.items())]
        return C.Discovery(refs, True, None, {"pages": len(refs)})

    def fetch(self, ref, prior, net):
        snap, _ = C.http_snapshot(self.store, ref, ref.url, DELAY, ".html", f"{self.id}@{self.version}")
        return snap

    def parse(self, snap, blobs, profile):
        t = blobs.read(snap.snapshot, ".html").decode("utf-8", "replace")
        slug = snap.ref.key
        pr = C.ParseResult(sources=[L.source(snap, "Dell " + slug)])
        code, products = codeof(t, slug)
        up = code.upper()
        pr.identifiers.append(L.ident("mfr_model", up, "model", "dell", series=slug))
        if products:
            pr.fingerprints["config_pseudo_skus"] = products   # platform's config tiers (reg/fixed/ltd/so); not orderable part numbers
        name = None
        for m in re.finditer(r'<script[^>]*ld\+json[^>]*>(.*?)</script>', t, re.S):
            try:
                j = json.loads(m.group(1))
            except ValueError:
                continue
            if isinstance(j, dict) and j.get("@type") == "Product":
                name = (j.get("name") or "").strip()
                off = j.get("offers") or {}
                if off.get("price"):
                    L.add(pr, f"{self.id}@{self.version}", snap, "sw.msrp", f"{off['price']} {str(off.get('priceCurrency', '')).upper()}",
                          f"store price {off['price']} {off.get('priceCurrency')} ({str(off.get('availability', '')).rsplit('/', 1)[-1]}) at fetch, default config",
                          "model_code", up, "Offer.price")
                pr.fingerprints["availability"] = str(off.get("availability", "")).rsplit("/", 1)[-1]
        title = re.search(r"<title>(.*?)</title>", t, re.S)
        pr.aliases.append({"text": name or (html.unescape(title.group(1)).split("|")[0].strip() if title else slug), "kind": "marketing_name"})
        i = t.find("id=tech-spec-container")
        spec = t[i:i + 40000] if i >= 0 else ""
        n, ports_cells = 0, []
        for lab, body in re.findall(r'<li class=mb-2><div class="h5 fw-bold mb-0">(.*?)</div>(.*?)</li>', spec, re.S):
            lab = L.lines(lab)[0].rstrip(" *") if L.lines(lab) else ""
            ls = L.lines(body)
            if lab and ls:
                n += 1
                if LABELMAP.get(lab) == "port.usbc_list":
                    ports_cells.append((lab, ls))
                L.mapped(pr, f"{self.id}@{self.version}", snap, LABELMAP, lab, ls, "model_code", up)
        for c in [c for c in pr.claims if c["key"] == "port.usbc_list" and (c.get("locator") or {}).get("label") == "Ports"]:
            v = next(ln for lab_, ln in ports_cells if lab_ == "Ports") if ports_cells else None
            if v is not None:
                _xports.replace_claims(pr, C, c, _xports.dell(v), up)
        for c in pr.claims:
            c["locator"]["config"] = "default"
        # component option lists (orderable choices on this platform): kept as fingerprints, no claim (they are not the default config)
        opts = {}
        mods = [(m.start(), L.lines(m.group(1))[0]) for m in re.finditer(r'<h2 class="h3 font-weight-md mb-0 me-3 module-title[^>]*>(.*?)</h2>', t) if L.lines(m.group(1))]
        for k, (pos, title_) in enumerate(mods):
            end = mods[k + 1][0] if k + 1 < len(mods) else pos + 60000
            seg = t[pos:end]
            names = []
            for b in re.findall(r'<div class="btn option detailed-option[^>]*aria-label="([^"]*)"', seg):
                b = re.sub(r"\s*\.\s*(\+ )?\$[\d,.]+\s*$|\s*\.\s*Selected\s*$", "", html.unescape(b).strip())
                if b and b not in names:
                    names.append(b)
            if names:
                opts[title_] = names
        pr.fingerprints["options"] = opts
        pr.fingerprints["spec_rows"] = n
        if not n:
            pr.absences.append({"key": "id.mpn", "status": "not_published", "source": "s1", "checked_at": snap.fetched_at})
        pr.absences.append({"key": "id.config_code", "status": "not_published", "source": "s1", "checked_at": snap.fetched_at,
                            "reason": "Dell spd pages publish platform code + pseudo-SKUs only; orderable configs are configure-to-order"})
        return pr


if __name__ == "__main__":
    _run.main(Dell())
