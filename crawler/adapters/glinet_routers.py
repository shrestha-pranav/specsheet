#!/usr/bin/env python3
"""GL.iNet US router adapter v1 (contract ARCHITECTURE 15.5), category routers. Source = www.gl-inet.com/en-us/products/<handle> (GL.iNet's own
Shopify store; robots.txt allows product HTML and /products.json).

discover : https://www.gl-inet.com/en-us/products.json?limit=250 (one request) -> handles whose product_type is a router type (Home Router, Travel
           Router, VPN Gateway, Mini Router, 4G/5G router types) plus untyped gl-* legacy handles; KVMs (gl-rm*), private-access dongles (gl-pas*),
           IoT gateways, accessories and boards are dropped.
fetch    : the product HTML page (~1.9 MB, the spec table is a theme section, not in body_html), stored gzip. 1 req/s.
parse    : pure. Only the first table after the '(Technical) Specification(s)' heading (td-left label / td-right value). Comparison tables elsewhere on the page put two
           models side by side and are never read. mfr_model = the parenthesised code of the title ('Flint 2 (GL-MT6000) ...'), else the title's
           leading GL-code; the Shopify variant SKU (GL-MT6000-US-4PX) is a configuration alias; the title is a marketing-name alias.
Traps    : GL.iNet is the rare maker that names the SoC vendor ('MediaTek Quad-core, @2.0 GHz') and sometimes the part ('IPQ6000 1.2 GHz
           Quad-core', 'QCA9531 @650Mhz SoC'): soc_vendor from the vendor word or part family, soc_model only from an explicit part number.
           'Wi-Fi Speed: 1148Mbps (2.4GHz), 4804Mbps (5GHz)' puts the rate BEFORE the band, so _router.per_band (band-first) is not used.
           Interface 'N x LAN Ethernet ports' without a speed gives the count only. 'Power Consumption: <20W' is a bound, not mapped.
"""
import gzip, html, json, re, sys, time
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
import _contract as C
import _router as R
import _nowifi as NW
import _lt as L
import _run

ID, VERSION, SOURCE = "glinet_routers", 3, "glinet-us-routers"
CATEGORIES = {"routers"}
ADAPTER = f"{ID}@{VERSION}"
BASE = "https://www.gl-inet.com/en-us"
DELAY = 1.0
TYPES = {"Home Router": "router", "Travel Router": "travel_router", "VPN Gateway": "router", "Mini Router": "travel_router",
         "4G LTE Router Gateway": "gateway_modem_router", "4G LTE Router": "gateway_modem_router", "5G SIM Card Router": "gateway_modem_router"}
DROP = re.compile(r"^gl-(rm|pas|s\d|m2|thread|inet|usb|moto)", re.I)
SPEC = re.compile(r'<h2[^>]*>\s*(?:Technical\s+)?Specifications?\s*</h2>((?:(?!<table|<h2).){0,1500})<table[^>]*>(.*?)</table>', re.S)
ROW = re.compile(r'<td class="td-left">(.*?)</td>\s*<td class="td-right">(.*?)</td>', re.S)
PART = re.compile(r"\b(IPQ\d{4}\w*|QCA\d{4}\w*|QCN\d{4}\w*|MT\d{4}\w*|SF\d{2}A\d{4}\w*|BCM\d{4,5}\w*)\b")
VENDOR = (("mediatek", "mediatek"), ("qualcomm", "qualcomm"), ("broadcom", "broadcom"), ("realtek", "realtek"), ("siflower", "other"))


def cell(s):
    s = re.sub(r"<br\s*/?>", "\n", s)
    s = html.unescape(re.sub(r"<[^>]+>", " ", s)).replace("\xa0", " ")
    return [re.sub(r"\s+", " ", x).strip() for x in s.split("\n") if x.strip()]


class GlinetRouters:
    id, version, source_id, categories = ID, VERSION, SOURCE, CATEGORIES

    def __init__(self):
        self.store = C.BlobStore(SOURCE)

    def discover(self, checkpoint, net):
        r = net.get(BASE + "/products.json?limit=250", DELAY)
        if not hasattr(r, "status_code") or r.status_code != 200:
            return C.Discovery([], False, f"products.json {getattr(r, 'status_code', r)}", checkpoint or {})
        refs = []
        for p in sorted(r.json().get("products", []), key=lambda p: p["handle"]):
            h, t = p["handle"], p.get("product_type") or ""
            if t in TYPES or (t == "" and h.startswith("gl-") and not DROP.match(h)):
                refs.append(C.Ref(SOURCE, h, f"{BASE}/products/{h}", {"product_type": t, "title": p.get("title"),
                                                                       "skus": [v.get("sku") for v in p.get("variants") or [] if v.get("sku")]}))
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


def _mb(num, unit):
    return int(float(num) * (1024 if unit.upper() == "GB" else 1))


def parse_html(snap, h):
    pr = C.ParseResult()
    pr.sources = [L.source(snap, "GL.iNet US product page " + snap.ref.key)]
    hints = snap.ref.hints or {}
    sec = SPEC.search(h)
    if sec is None:      # some theme sections only exist JSON-escaped inside a script payload
        u = h.replace("\\u003c", "<").replace("\\u003e", ">").replace("\\u0026", "&").replace('\\"', '"').replace("\\/", "/").replace("\\n", "\n")
        sec = SPEC.search(u)
    rows = {}
    for a, b in ROW.findall(sec[2] if sec else ""):
        rows.setdefault(" ".join(cell(a)), cell(b))
    title = hints.get("title") or ""
    m = re.search(r"\((GL-[A-Z0-9]+(?:-[A-Z0-9]+)?)(?:/[A-Z0-9]+)?\)", title) or re.match(r"\s*(GL-[A-Z0-9]+(?:-[A-Z0-9]+)?)\b", title)
    if not rows or not m or not (rows.get("CPU") or rows.get("Interface")):
        pr.absences.append({"key": "*", "reason": "no specification table / model code (not a router spec page)", "source": "s1"})
        return pr
    model = m[1]
    pr.identifiers.append(L.ident("mfr_model", model, "model", "gl_inet", series=snap.ref.key))
    for s in hints.get("skus") or []:
        if s != model:
            pr.identifiers.append(L.ident("mfr_sku", s, "configuration", "gl_inet", parent=model, role="alias"))
    if title:
        pr.aliases.append({"text": title, "kind": "marketing_name"})

    def add(k, v, raw, label):
        L.add(pr, ADAPTER, snap, k, v, raw, "model_code", model, label)

    add("gen.device_type", TYPES.get(hints.get("product_type")), hints.get("product_type"), "Shopify product_type")
    proto = " ".join(rows.get("Protocol", []) or rows.get("Wi-Fi Protocol", []))
    std = re.search(r"802\.11\s*([a-z/]+)", proto)
    last = std[1].split("/")[-1] if std else None
    gen = {"be": "wifi7", "ax": "wifi6", "ac": "wifi5", "n": "wifi4"}.get(last)      # v3: 'IEEE 802.11b/g/n' = Wi-Fi 4 (highest listed standard)
    sp = " ".join(rows.get("Wi-Fi Speed", []) or rows.get("WiFi Speed", []))
    found = {}
    for rate, band in re.findall(r"(\d[\d,]*)\s*Mbps\s*\(\s*(2\.4|5|6)\s*GHz\s*\)", sp, re.I):
        b = {"2.4": "24", "5": "5", "6": "6"}[band]
        found.setdefault(b, []).append(int(rate.replace(",", "")))
    for b, rs in found.items():
        if len(rs) == 1:
            add(f"wifi.rate_{b}_mbps", rs[0], sp, "Wi-Fi Speed")
    if "6" in found:
        add("wifi.has_6ghz", True, sp, "Wi-Fi Speed")
    elif found and all(len(v) == 1 for v in found.values()) and \
            R.rates_cover_class({b: {"rate": v[0]} for b, v in found.items()}, R.marketing_class(title + " " + sp)) and R.band_enum(sp) is False:
        # v2: a per-band rate list that sums to the class number (GL-BE3600: 688 + 2882) names every radio: complete enumeration
        R.add_6ghz(pr, ADAPTER, snap, False, sp, "model_code", model, "Wi-Fi Speed")
    if gen == "wifi6" and "6" in found:
        gen = "wifi6e"
    add("wifi.generation", gen, proto, "Protocol")
    cpu = " ".join(rows.get("CPU", []))
    if cpu:
        cores, ghz = R.cpu(cpu)
        if ghz is None and (mh := re.search(r"(\d{3,4})\s*MHz", cpu, re.I)):
            ghz = round(int(mh[1]) / 1000, 3)
        add("hw.cpu_cores", cores, cpu, "CPU"); add("hw.cpu_ghz", ghz, cpu, "CPU")
        part = PART.search(cpu)
        ven = next((v for pat, v in VENDOR if re.search(r"\b" + pat + r"\b", cpu, re.I)), None)
        if ven is None and part:
            ven = next(v for pre, v in (("IPQ", "qualcomm"), ("QCA", "qualcomm"), ("QCN", "qualcomm"), ("MT", "mediatek"), ("BCM", "broadcom"),
                                         ("SF", "other")) if part[1].startswith(pre))
        add("hw.soc_vendor", ven, cpu, "CPU")
        if part:
            add("hw.soc_model", part[1], cpu, "CPU")
    mem = " ".join(rows.get("Memory / Storage", []) or rows.get("Memory", []))
    ram = fl = None
    for seg in re.split(r"/|,", mem):
        x = re.search(r"(\d+(?:\.\d+)?)\s*(MB|GB)\b", seg, re.I)
        if not x:
            continue
        if re.search(r"DDR|RAM", seg, re.I) and ram is None:
            ram = _mb(x[1], x[2])
        elif re.search(r"flash|eMMC|NAND|NOR", seg, re.I) and fl is None:
            fl = _mb(x[1], x[2])
    add("hw.ram_mb", ram, mem, "Memory / Storage"); add("hw.flash_mb", fl, mem, "Memory / Storage")
    itf = rows.get("Interface", [])
    lan = wanlan = 0; wan_sp = []; seen_lan = False; usb_lines = []
    for l in itf:
        x = re.match(r"\s*(\d+)\s*[x×]\s*(?:(\d+(?:\.\d+)?)\s*G(?:bps|igabit)?\s+|Gigabit\s+)?(WAN/LAN|LAN/WAN|WAN|LAN)\b", l, re.I)
        if x:
            n, kind = int(x[1]), x[3].upper()
            spd = int(float(x[2]) * 1000) if x[2] else (1000 if re.search(r"Gigabit", l, re.I) else None)
            if kind == "LAN":
                lan += n; seen_lan = True
            elif kind == "WAN":
                wan_sp.append(spd)
            else:
                wanlan += n; wan_sp.append(spd)
        if re.search(r"USB", l):
            usb_lines.append(l)
    if seen_lan:
        add("port.lan_count", lan, itf, "Interface")
    if wan_sp and all(wan_sp):
        add("port.wan_speed_mbps", max(wan_sp), itf, "Interface")
    if wanlan:
        add("port.wan_lan_configurable", True, itf, "Interface")
    es = rows.get("Ethernet Speed", [])
    uni = re.fullmatch(r"\s*10/100(?:/1000(?:/2500)?)?\s*Mbps\s*", " ".join(es)) if len(es) == 1 else None
    if uni:      # one speed list for every port: it is each port's speed, WAN included
        top = int(re.findall(r"\d+", es[0])[-1])
        if not (wan_sp and all(wan_sp)) and wan_sp:
            add("port.wan_speed_mbps", top, es + itf, "Ethernet Speed (all ports)")
        if seen_lan or wanlan:
            add("port.lan_max_mbps", top, es, "Ethernet Speed (all ports)")
    sps = [float(g) * 1000 for g in re.findall(r"(\d+(?:\.\d+)?)\s*G\s*Ports?", " ".join(es), re.I)]
    if sps:
        add("port.lan_max_mbps", int(max(sps)), es, "Ethernet Speed")
        mg = sum(int(n) for n, g in re.findall(r"(\d+)\s*[x×]\s*(\d+(?:\.\d+)?)\s*G\s*Ports?", " ".join(es), re.I) if float(g) >= 2.5)
        if mg:
            add("port.multigig_count", mg, es, "Ethernet Speed")
    if usb_lines:
        n, st = R.usb(" | ".join(usb_lines))
        add("port.usb_count", n, usb_lines, "Interface"); add("port.usb_standard", st, usb_lines, "Interface")
    # v3, coordinator ruling 2 (2026-11-24 r2): a VPN gateway whose Interface row enumerates every port/slot/button ('N x ...' lines) and whose
    # whole spec table and title name no Wi-Fi radio (no Protocol / Wi-Fi Speed row, no Wi-Fi / wireless / antenna / band word; CPU clock
    # excluded) is wired-only (Brume 2 GL-MT2500, Brume 3 GL-MT5000): the Wi-Fi keys are not_applicable. Brume GL-MV1000 ('Brume-W only:
    # 300Mbps (2.4GHz)') is not.
    items, cur = [], None
    for l in itf:
        if re.match(r"\s*\d+\s*[x×]\s", l, re.I):
            cur = l; items.append(l)
        elif items:
            items[-1] += " " + l            # a wrapped line ('1 x Type-C power' / 'port')
        else:
            items = None; break
    if (items and seen_lan and wan_sp and gen is None and not found and not proto and not sp
            and not NW.WIFI_WORDS.search(title) and not any(NW.WIFI_WORDS.search(f"{k} {' '.join(v)}") for k, v in rows.items() if k != "CPU")):
        NW.add_no_wifi(pr, ADAPTER, snap, "Interface: " + " | ".join(items), "model_code", model, "Interface (complete port list, no Wi-Fi row)")
    dw = " ".join(rows.get("Dimension / Weight", []))
    add("phys.dimensions", R.dims_mm(dw.replace("mm", " mm")), dw, "Dimension / Weight")
    if (w := re.search(r"(\d+(?:\.\d+)?)\s*g\b", dw)):
        add("phys.weight", float(w[1]), dw, "Dimension / Weight")
    pr.fingerprints = {"raw": snap.snapshot, "labels": list(rows), "product_type": hints.get("product_type"),
                       "unmapped": {k: " | ".join(v)[:100] for k, v in rows.items() if k in ("Antennas", "Power Input", "Power Consumption", "TX Power")}}
    return pr


if __name__ == "__main__":
    _run.main(GlinetRouters())
