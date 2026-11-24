#!/usr/bin/env python3
"""ASUS US router + ZenWiFi/AiMesh adapter v1 (contract ARCHITECTURE 15.5), category routers. Source = www.asus.com/us/ techspec pages.

discover : https://www.asus.com/sitemap.xml (index; robots Allow) -> the /us/sitemap/usN.xml children (about 10 requests) -> .../networking-iot-servers/
           {wifi-routers,whole-home-mesh-systems,wifi-6,wifi-7}/<group>/<model>/techspec/ pages (one Ref per page).
fetch    : the techspec page (SSR, ~300 KB), stored gzip. 1 req/s, same markup as asus.py laptops ('rowTable' label/value rows), parsed with asus.parse_table.
parse    : pure. Rows used: Network Standard, Product Segment ('AX5700 ultimate AX performance : 861+4804 Mbps'), WiFi Data Rate (per band, with
           legacy Wi-Fi 5/4 lines cut off), Transmit / Receive ('5GHz 4x4 2.4GHz 3x3'), Processor, Memory ('256 MB Flash and 1 GB RAM'), Boosts Speed
           (160 MHz, 1024/4096-QAM), I/O Ports, VPN, AiMesh, Operating Mode, Product Weight (g). mfr_model comes from the page title (RT-AX86U Pro;
           ZenWiFi 'XT8' = the parenthesised code); pack variants of a ZenWiFi page ('XT8 (W-3-PK)') are aliases.
Traps    : ASUS is the one maker that prints flash and RAM; no SoC vendor/model is printed. A page covers several unit variants for mesh kits; the 160 MHz line
           carries a regulatory footnote (may be unavailable in some regions) so it is a capability, not a guarantee. Wi-Fi 6E/7 pages: the 160 MHz
           statement cannot be pinned to 5 vs 6 GHz, so widths are only set for dual-band Wi-Fi 6 and for the Wi-Fi 7 '320' statement.
v2 (2026-11-24, preset fill): wifi.has_6ghz also from the 'Operating Frequency' band list: True when it names 6 GHz, False (condition
           basis=complete_enumeration, list kept as raw) only when it enumerates exactly 2.4 + 5 GHz radios and no data-rate line names 6 GHz.
"""
import gzip, re, sys, time
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
import _contract as C
import _router as R
import _lt as L
import _run
import asus as A

ID, VERSION, SOURCE = "asus_routers", 2, "asus-us-routers"
CATEGORIES = {"routers"}
ADAPTER = f"{ID}@{VERSION}"
INDEX = "https://www.asus.com/sitemap.xml"
DELAY = 1.0
LOC = re.compile(r"<loc>(https://www\.asus\.com/us/networking-iot-servers/(wifi-routers|whole-home-mesh-systems|wifi-6|wifi-7)/([a-z0-9-]+)/([a-z0-9-]+)/techspec/)</loc>")
CHILD = re.compile(r"<loc>(https://www\.asus\.com/us/sitemap/us\d+\.xml)</loc>")


class AsusRouters:
    id, version, source_id, categories = ID, VERSION, SOURCE, CATEGORIES

    def __init__(self):
        self.store = C.BlobStore(SOURCE)

    def discover(self, checkpoint, net):
        r = net.get(INDEX, DELAY)
        if not hasattr(r, "status_code") or r.status_code != 200:
            return C.Discovery([], False, f"index {getattr(r, 'status_code', r)}", checkpoint or {})
        seen = {}
        for u in CHILD.findall(r.text):
            x = net.get(u, DELAY)
            if not hasattr(x, "status_code") or x.status_code != 200:
                return C.Discovery([], False, f"child sitemap {u} {getattr(x, 'status_code', x)}", checkpoint or {})
            for url, sect, group, slug in LOC.findall(x.text):
                seen.setdefault(slug, {"url": url, "section": sect, "group": group})
        refs = [C.Ref(SOURCE, s, d["url"], {"section": d["section"], "group": d["group"]}) for s, d in sorted(seen.items())]
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


def cell(rows, *labs):
    for l_ in labs:
        if l_ in rows and rows[l_]:
            c = rows[l_][0]
            return " ".join(c) if isinstance(c, list) else str(c)
    return ""


def parse_html(snap, h):
    pr = C.ParseResult()
    pr.sources = [L.source(snap, "ASUS US techspec " + snap.ref.key)]
    rows = A.parse_table(h)
    tm = re.search(r"<title>(.*?)\s+-\s+Tech Specs", h)
    if len(rows) < 4 or not tm:
        pr.absences.append({"key": "*", "reason": "no techspec rows (not a router techspec page)", "source": "s1"})
        return pr
    head = R.clean(tm[1]).replace("ASUS ", "", 1)
    par = re.search(r"\(([A-Z0-9][A-Za-z0-9 -]{1,14})\)\s*$", head)
    mesh = snap.ref.hints.get("section") == "whole-home-mesh-systems"
    model = (par[1] if (mesh and par) else head).strip()
    group = snap.ref.hints.get("group", "")
    line = "ZenWiFi" if "zenwifi" in group else "ROG Rapture" if "gaming" in group else "ExpertWiFi" if "expert" in group else "RT" if re.match(r"RT-", model) else None
    pr.identifiers.append(L.ident("mfr_model", model, "model", "asus", series=group or snap.ref.key))
    pr.aliases.append({"text": head, "kind": "marketing_name"})
    for v in re.findall(r"[A-Z0-9]+ \([WB]-\d-PK\)", cell(rows, "Model Name")):
        pr.aliases.append({"text": v, "kind": "retail_slug"})

    def add(k, v, raw, label):
        L.add(pr, ADAPTER, snap, k, v, raw, "model_code", model, label)
    std, seg = cell(rows, "Network Standard"), cell(rows, "Product Segment")
    data, tr = cell(rows, "WiFi Data Rate"), cell(rows, "Transmit / Receive")
    boost, io, vpn = cell(rows, "Boosts Speed"), cell(rows, "I/O Ports"), cell(rows, "VPN")
    gen = R.generation(data) or R.generation(seg) or R.generation(std)
    add("gen.device_type", "mesh_system" if mesh else "router", snap.ref.hints.get("section"), "URL class")
    add("gen.product_line", line, group, "URL group")
    add("wifi.generation", R.generation(data.split(" : ")[0]) or R.generation(seg), data or seg, "WiFi Data Rate")
    add("wifi.marketing_class", R.marketing_class(seg), seg, "Product Segment")
    toks = list(re.finditer(r"WiFi\s*\d[E]?\s*\(802\.11\w+\)[^:]{0,30}:|(?:IEEE\s*)?802\.11[gba]\s*:", data))
    g0 = R.generation(toks[0][0]) if toks else None
    nxt = next((t for t in toks[1:] if R.generation(t[0]) != g0), None)
    cut = data[:nxt.start()] if nxt else data
    # keep only Wi-Fi 6/6E/7 band lines: stop before the first lines of an older standard
    hi = R.generation(cut.split(":")[0]) if cut else None
    bands = R.per_band(cut)
    st = R.per_band(tr)
    for b, d in bands.items():
        if "rate" in d:
            add(f"wifi.rate_{b}_mbps", d["rate"], cut, "WiFi Data Rate")
    for b, d in st.items():
        if "streams" in d:
            add(f"wifi.streams_{b}", d["streams"], tr, "Transmit / Receive")
    if gen == "wifi7" and "6" in bands and re.search(r"320\s*MHz", boost + data):
        add("wifi.max_width_6_mhz", "320", boost, "Boosts Speed")
    if gen == "wifi6" and "6" not in bands and re.search(r"20/40/80/160\s*MHz", boost):
        add("wifi.max_width_5_mhz", "160", boost, "Boosts Speed")
    if len(bands) > 1:
        add("wifi.band_count", len(bands), cut, "WiFi Data Rate")
    freq = cell(rows, "Operating Frequency")
    if "6" in bands:
        add("wifi.has_6ghz", True, cut, "WiFi Data Rate")
    elif "6" not in R.per_band(data):
        # v2: the 'Operating Frequency' row is the maker's complete band list ('5 GHz 2.4 GHz'): True when it names 6 GHz,
        # False (basis=complete_enumeration, list kept as raw) when it enumerates 2.4 + 5 GHz and nothing else (R.band_enum)
        R.add_6ghz(pr, ADAPTER, snap, R.band_enum(freq), freq, "model_code", model, "Operating Frequency")
    q = [int(x) for x in re.findall(r"(\d{3,4})\s*-?\s*QAM", boost)]
    if q and max(q) in (1024, 4096):
        add("wifi.qam_max", str(max(q)), boost, "Boosts Speed")
    alltxt = " ".join(" ".join(" ".join(c) if isinstance(c, list) else str(c) for c in v) for v in rows.values())
    for pat, k, nm in ((r"\bMLO\b|Multi-Link", "wifi.mlo", "MLO"), (r"\bOFDMA\b", "wifi.ofdma", "OFDMA"), (r"\bMU-?MIMO\b", "wifi.mu_mimo", "MU-MIMO"), (r"WPA3", "wifi.wpa3", "WPA3")):
        if re.search(pat, alltxt):
            add(k, True, nm + " listed in techspec", nm)
    fl, ra = R.memory(cell(rows, "Memory"))
    add("hw.flash_mb", fl, cell(rows, "Memory"), "Memory"); add("hw.ram_mb", ra, cell(rows, "Memory"), "Memory")
    cores, ghz = R.cpu(cell(rows, "Processor"))
    add("hw.cpu_cores", cores, cell(rows, "Processor"), "Processor"); add("hw.cpu_ghz", ghz, cell(rows, "Processor"), "Processor")
    lines = [x for x in re.split(r"(?=RJ45 for)", io.split("USB")[0]) if x.strip()]
    p = R.ports(lines)
    mgm = re.search(r"\((\d)\)\s*([\d.]+)\s*G(?:/\d+G(?:bps)?)?\s*multi-?Gig", io)
    if mgm and p["wan_lan_cfg"] is None and re.search(r"WAN/LAN", io):
        p["wan_lan_cfg"] = True
        p["multigig"] = (p["multigig"] or 0) + int(mgm[1])
        p["wan_mbps"] = max(p["wan_mbps"] or 0, int(float(mgm[2]) * 1000))
    for k, v in (("port.wan_speed_mbps", p["wan_mbps"]), ("port.lan_count", p["lan_count"]), ("port.lan_max_mbps", p["lan_max"]),
                 ("port.multigig_count", p["multigig"]), ("port.wan_lan_configurable", p["wan_lan_cfg"])):
        add(k, v, io[:200], "I/O Ports")
    if re.search(r"\bUSB\b", io):
        n, su = R.usb(io[io.index("USB"):])
        add("port.usb_count", n, io[io.index("USB"):], "I/O Ports"); add("port.usb_standard", su, io[io.index("USB"):], "I/O Ports")
    srv = re.findall(r"VPN Server ([A-Za-z ]+?)(?:,|$)", vpn); cli = re.findall(r"VPN Client ([A-Za-z0-9 ]+?)(?:,|$)", vpn)
    add("sw.vpn_server", R.vpn(" ".join(srv), "server"), vpn[:160], "VPN") if srv else None
    add("sw.vpn_client", R.vpn(" ".join(cli), "client"), vpn[:160], "VPN") if cli else None
    add("sw.wireguard", True if re.search(r"WireGuard", vpn) else None, vpn[:160], "VPN")
    mode = cell(rows, "Operating Mode")
    om = [v for pat, v in ((r"router mode", "router"), (r"access point", "access_point"), (r"media bridge", "media_bridge"), (r"repeater", "repeater"), (r"aimesh node", "mesh_node")) if re.search(pat, mode, re.I)]
    add("sw.operating_modes", om, mode, "Operating Mode")
    am = cell(rows, "AiMesh")
    if am or mesh:
        add("mesh.supported", True, am or "mesh page", "AiMesh")
        add("mesh.systems", ["aimesh"] + (["easymesh"] if re.search(r"easy\s*mesh", alltxt, re.I) else []), am or "mesh page", "AiMesh")
    wt = cell(rows, "Product Weight (g)")
    if (m := re.match(r"\s*([\d.]+)\s*g\b", wt)):
        add("phys.weight", float(m[1]), wt, "Product Weight (g)")
    pr.fingerprints = {"raw": snap.snapshot, "labels": list(rows), "unmapped": {k: cell(rows, k)[:100] for k in ("Antenna", "Power Supply", "Product Dimensions")}}
    return pr


if __name__ == "__main__":
    _run.main(AsusRouters())
