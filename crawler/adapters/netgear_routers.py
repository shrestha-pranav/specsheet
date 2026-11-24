#!/usr/bin/env python3
"""NETGEAR US router + Orbi mesh adapter v1 (contract ARCHITECTURE 15.5), category routers. Source = www.netgear.com/home/wifi/.

discover : https://www.netgear.com/sitemap.xml (one request; robots allows product pages) -> /home/wifi/{routers,mesh}/<model>/ whose slug is a model code
           (rax*, rs*, rbe*, rbk*, rbs*, rbr*, rbse*, mk*, ms*, cbk*). Series landing pages, campaign pages (nighthawk-wifi7-gaming) are dropped.
fetch    : the product page (SSR React shell ~0.7 MB) stored gzip. 1 req/s.
parse    : pure. Two structured sources inside the page: (1) schema.org Product JSON-LD (sku RAX54S-2AZNAS, gtin, additionalProperty[] such as 'WiFi Technology',
           'WiFi Band Type', 'WiFi Coverage (sq. ft.)', offers.price); (2) the 'Technical Specs' <td> label ':' / value pairs (Router pages: WiFi Technology
           with per-band '5GHz AX: 4x4 (Tx/Rx) 1024-QAM 20/40/80/160MHz, up to 4.8Gbps', Ethernet Ports, Processor, USB Ports, Weight, Dimensions;
           some Orbi pages: Memory '128MB flash and 512MB RAM'). mfr_model = slug upper (RAX54S); mfr_sku = JSON-LD sku.
Traps    : Orbi kits are named by pack (RBE972 = router+1 satellite, RBE973 = router+2): the kit code IS the model here, so pack_count is a model fact.
           Newer Orbi/Nighthawk pages carry only the JSON-LD headline properties (no per-band rows); those claims stay absent. 'up to 27Gbps' is a class
           sum. The JSON-LD price is list price at fetch time (candidate only). 'Powerful triple-core 1.5GHz' names no SoC vendor.
v2 (2026-11-24, preset fill): Wi-Fi 7 pages carry two-cell spec tables. has_6ghz = True from any band row naming 6 GHz; False only when every
           band row is a band-list row ('WiFi Bands', 'Simultaneous Dual-Band WiFi ...') that enumerates 2.4 + 5 GHz completely (R.band_enum,
           condition basis=complete_enumeration, list kept as raw). 'WiFi Bands' per-band rates/streams (RS150 '5 GHz (3x3), 4.3 Gbps'), else from the page's own
           product-attribute record c_wifiBands (one distinct value only; RBE870 '5 GHz (4x4/240 MHz, 4K-QAM): 8,640 Mbps').
"""
import gzip, json, re, sys, time
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
import _contract as C
import _router as R
import _lt as L
import _run

ID, VERSION, SOURCE = "netgear_routers", 2, "netgear-us-routers"
CATEGORIES = {"routers"}
ADAPTER = f"{ID}@{VERSION}"
BASE = "https://www.netgear.com"
SITEMAP = BASE + "/sitemap.xml"
DELAY = 1.0
LOC = re.compile(r"<loc>https://www\.netgear\.com/home/wifi/(routers|mesh)/([a-z0-9]+)/</loc>")
KEEP = re.compile(r"^(rax|rs|rbe|rbk|rbs|rbr|rbse|mk|ms|cbk)\d", re.I)
TR2 = re.compile(r"<tr[^>]*>\s*<td[^>]*>(.*?)</td>\s*<td[^>]*>(.*?)</td>\s*</tr>", re.S)
# v2: the Wi-Fi 7 pages' two-cell spec tables. A band-list row is a complete enumeration ('WiFi Bands', 'Simultaneous Dual-Band WiFi ...');
# any other row naming bands ('Multi-link Operation: Combines two WiFi bands') can only say True.
ENUM_LABEL = re.compile(r"^(?:WiFi Bands?|(?:Simultaneous\s+)?(?:Dual|Tri|Quad)-Band\b.*)$", re.I)
LD = re.compile(r'<script[^>]*type="application/ld\+json"[^>]*>(.*?)</script>', re.S)


class NetgearRouters:
    id, version, source_id, categories = ID, VERSION, SOURCE, CATEGORIES

    def __init__(self):
        self.store = C.BlobStore(SOURCE)

    def discover(self, checkpoint, net):
        r = net.get(SITEMAP, DELAY)
        if not hasattr(r, "status_code") or r.status_code != 200:
            return C.Discovery([], False, f"sitemap {getattr(r, 'status_code', r)}", checkpoint or {})
        seen = {}
        for sect, slug in LOC.findall(r.text):
            if KEEP.match(slug):
                seen.setdefault(slug, {"url": f"{BASE}/home/wifi/{sect}/{slug}/", "section": sect})
        refs = [C.Ref(SOURCE, s, d["url"], {"section": d["section"]}) for s, d in sorted(seen.items())]
        return C.Discovery(refs, True, None, {"models": len(refs)})

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
        return parse_html(snap, gzip.decompress(blobs.read(snap.snapshot, ".html.gz")).decode("utf-8", "replace"))


def td_pairs(h):
    out, cur = {}, None
    for x in re.findall(r"<td[^>]*>(.*?)</td>", h, re.S):
        t = L.lines(x)
        if not t:
            continue
        if len(t) == 1 and t[0].endswith(":") and len(t[0]) < 40:
            cur = t[0][:-1].strip()
            out.setdefault(cur, [])
        elif cur:
            out[cur] += t
    return out


def spec_rows(h):
    """-> [(label, value)] of the two-cell <td> spec rows; <br> becomes ' | ', footnote <sup> marks are dropped."""
    out = []
    for a, b in TR2.findall(h):
        lab = R.clean(re.sub(r"<sup>.*?</sup>", "", a, flags=re.S))
        val = R.clean(re.sub(r"<br\s*/?>", " | ", re.sub(r"<sup>.*?</sup>", "", b, flags=re.S)))
        val = re.sub(r"(?:\s*\|\s*)+", " | ", val).strip(" |")
        if lab and val and len(lab) < 80:
            out.append((lab, val))
    return out


def product_ld(h):
    for m in LD.finditer(h):
        try:
            d = json.loads(m[1])
        except ValueError:
            continue
        if isinstance(d, dict) and d.get("@type") == "Product":
            return d
    return {}


def parse_html(snap, h):
    pr = C.ParseResult()
    pr.sources = [L.source(snap, "NETGEAR US product page " + snap.ref.key)]
    ld = product_ld(h)
    props = {p.get("name"): str(p.get("value")) for p in ld.get("additionalProperty", []) if isinstance(p, dict)}
    rows = td_pairs(h)
    if not ld or not (props or rows):
        pr.absences.append({"key": "*", "reason": "no Product JSON-LD properties / spec rows (not a product page)", "source": "s1"})
        return pr
    slug = snap.ref.key
    model = slug.upper()
    mesh = snap.ref.hints.get("section") == "mesh"
    title = R.clean(re.search(r"<title[^>]*>(.*?)</title>", h, re.S)[1]) if re.search(r"<title[^>]*>(.*?)</title>", h, re.S) else model
    fam = re.match(r"[a-z]+", slug)[0]
    pr.identifiers.append(L.ident("mfr_model", model, "model", "netgear", series=fam))
    if ld.get("sku"):
        pr.identifiers.append(L.ident("mfr_sku", ld["sku"], "configuration", "netgear", parent=model))
    if ld.get("gtin"):
        pr.identifiers.append(L.ident("gtin", str(ld["gtin"]), "configuration", "netgear", role="alias"))
    pr.aliases.append({"text": title, "kind": "marketing_name"})

    def add(k, v, raw, label):
        L.add(pr, ADAPTER, snap, k, v, raw, "model_code", model, label)
    tech = " ".join(rows.get("WiFi Technology", [])) or props.get("WiFi Technology", "")
    speed = " ".join(rows.get("WiFi Speed", [])) or props.get("WiFi Speed", "")
    band = " ".join(rows.get("WiFi Band", [])) + " " + props.get("WiFi Band Type", "") + " " + tech
    base = tech + " " + speed + " " + title
    stype = "mesh_node" if re.match(r"(rbs|rbse)", slug) else "mesh_system" if (mesh and re.match(r"(rbk|rbe|mk|cbk)", slug)) else "router"
    add("gen.device_type", stype, snap.ref.hints.get("section"), "URL class")
    pl = re.search(r"\b(Orbi|Nighthawk|Armor|Insight)\b", title + " " + props.get("WiFi Technology", ""), re.I)
    add("gen.product_line", pl[1].title() if pl else None, title, "page title")
    add("wifi.generation", R.generation(tech or title), tech or title, "WiFi Technology")
    add("wifi.marketing_class", R.marketing_class(speed + " " + tech + " " + title), speed or title, "WiFi Speed")
    add("wifi.band_count", R.bands(band), band.strip(), "WiFi Band")
    for b, d in R.per_band(tech).items():
        if "rate" in d:
            add(f"wifi.rate_{b}_mbps", d["rate"], tech, "WiFi Technology")
        if "streams" in d:
            add(f"wifi.streams_{b}", d["streams"], tech, "WiFi Technology")
        if "width" in d and b in ("5", "6"):
            add("wifi.max_width_5_mhz" if b == "5" else "wifi.max_width_6_mhz", str(d["width"]), tech, "WiFi Technology")
    qam = [int(x) for x in re.findall(r"(\d{3,4})-QAM", tech)]
    if qam and max(qam) in (256, 1024, 4096):
        add("wifi.qam_max", str(max(qam)), tech, "WiFi Technology")
    if re.search(r"\bMLO\b|Multi-Link", base + " ".join(props.values()), re.I):
        add("wifi.mlo", True, base, "title/description")
    srows = spec_rows(h)
    brows = [(a, b) for a, b in srows if re.search(r"band", a, re.I) and R.BAND_TOK.search(b)]
    if re.search(r"\b6\s*GHz\b", band + tech):
        add("wifi.has_6ghz", True, band, "WiFi Band")
    elif brows:
        aff = next(((a, b) for a, b in brows if R.band_enum(b) is True), None)
        enum = [(a, b) for a, b in brows if ENUM_LABEL.match(a)]
        if aff:
            R.add_6ghz(pr, ADAPTER, snap, True, f"{aff[0]}: {aff[1]}", "model_code", model, aff[0])
        elif enum and len(enum) == len(brows):
            res = [R.band_enum(b, R.bands(a) or R.bands(props.get("WiFi Band Type", ""))) for a, b in enum]
            if all(r is False for r in res):
                R.add_6ghz(pr, ADAPTER, snap, False, f"{enum[0][0]}: {enum[0][1]}", "model_code", model, enum[0][0])
    done = {c["key"] for c in pr.claims}
    lists = [(next((b for a, b in srows if re.fullmatch(r"WiFi Bands?", a, re.I)), ""), "WiFi Bands")]
    mods = [(m.start(), m[1]) for m in re.finditer(r'"c_modelNumber":"([^"]+)"', h)]
    cw = {json.loads('"' + m[1] + '"') for m in re.finditer(r'"c_wifiBands":"((?:[^"\\]|\\.)*)"', h)       # this product's record only:
          if mods and min(mods, key=lambda x: abs(x[0] - m.start()))[1] == model}                               # nearest c_modelNumber
    if len(cw) == 1:    # the page's own product-attribute record carries the same per-band list, often with the rates the table omits
        lists.append((R.clean(cw.pop()), "c_wifiBands (product attributes)"))
    for wb, wlab in lists:
        for b, d in R.per_band(wb).items():   # per-band streams and rate, first statement wins; '160 to 20MHz' widths are not read
            for k, v in ((f"wifi.rate_{b}_mbps", d.get("rate")), (f"wifi.streams_{b}", d.get("streams"))):
                if v is not None and k not in done:
                    add(k, v, wb, wlab); done.add(k)
    cov = re.search(r"([\d,]+)\s*sq", props.get("WiFi Coverage (sq. ft.)", "") or " ".join(rows.get("WiFi Coverage", [])))
    if cov:
        add("mesh.coverage_sqft", int(cov[1].replace(",", "")), props.get("WiFi Coverage (sq. ft.)") or rows.get("WiFi Coverage"), "WiFi Coverage")
    if mesh:
        add("mesh.supported", True, snap.ref.hints.get("section"), "URL class")
        add("mesh.systems", ["orbi"], "Orbi mesh page", "URL class")
    kit = re.search(r"\(\s*(\d)\s*Router\s*\+\s*(\d)\s*Satellites?\s*\)", title, re.I)
    pk = re.search(r"\b(\d)[- ]Pack\b", title, re.I)
    if kit:
        add("gen.pack_count", int(kit[1]) + int(kit[2]), title, "page title")
    elif pk:
        add("gen.pack_count", int(pk[1]), title, "page title")
    eth = rows.get("Ethernet Ports") or rows.get("Ports") or []
    p = R.ports(eth)
    for k, v in (("port.wan_speed_mbps", p["wan_mbps"]), ("port.lan_count", p["lan_count"]), ("port.lan_max_mbps", p["lan_max"]), ("port.multigig_count", p["multigig"])):
        add(k, v, eth, "Ethernet Ports")
    wan = props.get("Internet Port WAN", "")
    if wan and p["wan_mbps"] is None and (g := re.fullmatch(r"\s*(\d+(?:\.\d+)?)\s*G(?:bps)?(?: speeds?)?\s*", wan, re.I)):
        add("port.wan_speed_mbps", int(float(g[1]) * 1000), wan, "Internet Port WAN")
    cores, ghz = R.cpu(" ".join(rows.get("Processor", [])))
    add("hw.cpu_cores", cores, rows.get("Processor"), "Processor"); add("hw.cpu_ghz", ghz, rows.get("Processor"), "Processor")
    fl, ra = R.memory(" ".join(rows.get("Memory", [])))
    add("hw.flash_mb", fl, rows.get("Memory"), "Memory"); add("hw.ram_mb", ra, rows.get("Memory"), "Memory")
    usb = rows.get("USB Ports", [])
    n, st = R.usb(" ".join(usb))
    add("port.usb_count", n, usb, "USB Ports"); add("port.usb_standard", st, usb, "USB Ports")
    wt = " ".join(rows.get("Weight", []))
    if (m := re.search(r"\(\s*([\d.]+)\s*kg\s*\)|\(\s*([\d.]+)\s*g\s*\)", wt)):
        add("phys.weight", round(float(m[1]) * 1000, 1) if m[1] else float(m[2]), wt, "Weight")
    elif (m := re.search(r"([\d.]+)\s*lb", wt)):
        add("phys.weight", round(float(m[1]) * 453.592, 1), wt, "Weight")
    dm = " ".join(rows.get("Dimensions", []))
    add("phys.dimensions", R.dims_mm(dm), dm, "Dimensions")
    vp = props.get("VPN Support", "") + " " + " ".join(rows.get("VPN Support", []))
    if re.search(r"open\s*vpn|wire\s*guard", vp, re.I):
        add("sw.vpn_server", R.vpn(vp, "server"), vp[:120], "VPN Support")
    if "WPA3" in rows:
        add("wifi.wpa3", True, "WPA3 row", "WPA3")
    if ld.get("offers", {}).get("price"):
        try:
            add("id.msrp_us", float(ld["offers"]["price"]), ld["offers"]["price"], "JSON-LD offers.price")
        except (TypeError, ValueError):
            pass
    pr.fingerprints = {"raw": snap.snapshot, "labels": list(rows), "props": list(props), "sku": ld.get("sku"),
                       "unmapped": {k: " | ".join(v)[:100] for k, v in rows.items() if k in ("System Requirements", "WiFi Range", "Beamforming")}}
    return pr


if __name__ == "__main__":
    _run.main(NetgearRouters())
