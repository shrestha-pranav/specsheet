#!/usr/bin/env python3
"""Ubiquiti UniFi gateways + access points adapter v1 (contract ARCHITECTURE 15.5), category routers. Source = techspecs.ui.com (Ubiquiti's own
tech-spec site; no robots.txt is served, the path answers the app shell, so nothing is disallowed).

discover : the two category listing pages /unifi/cloud-gateways and /unifi/wifi (2 requests). Their __NEXT_DATA__ lists every product slug per
           sub-collection. Kept: every cloud-gateway (device_type router) and the Wi-Fi AP collections (enterprise, flagship, wall, outdoor,
           mega-capacity); bridging (UBB/UDB) and special devices (AirWire, travel router UTR) are dropped: not routers/APs in the profile's sense.
fetch    : the product page /unifi/<category>/<slug> (SSR Next.js, ~0.7 MB) stored gzip. 1 req/s.
parse    : pure. The page's __NEXT_DATA__ product.technicalSpecification is a labelled tree: sections -> features {label, parentId, value|flag}.
           Per-band rows are children of 'MIMO', 'Max. Data Rate' / 'Throughput' whose label IS the band ('6 GHz', '5 GHz', '2.4 GHz'), so per-band
           streams, rates and widths come from the band row itself, never from a class number. mfr_model = product.name (UDR7); the store SKU
           (UDR7-US) is a configuration alias; the retail title ('Dream Router 7') is a marketing-name alias.
Traps    : 'Spatial Streams 6' is a sum over radios (not a per-band figure): not mapped. 'Processor: Quad-core ARM Cortex-A53 at 1.5 GHz' names the CPU
           core, not the SoC: cores/GHz only, hw.soc_* only when the cell names a chip vendor + part. Width comes from '(BW320)' on that band's
           max-rate row only (the 'Channel Bandwidth' row is not per band). Gateway LAN count = Port Layout total minus the stated default WAN ports
           (ports are re-assignable: wan_lan_configurable when Max. WAN Port Count exceeds the default). Weights with two labelled figures
           (with/without SSD) keep 'Device:' or nothing. has_6ghz is only ever True (a 6 GHz band row); silence is not False.
"""
import gzip, json, re, sys, time
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
import _contract as C
import _router as R
import _lt as L
import _run

ID, VERSION, SOURCE = "ubiquiti_routers", 1, "ubiquiti-us-routers"
CATEGORIES = {"routers"}
ADAPTER = f"{ID}@{VERSION}"
BASE = "https://techspecs.ui.com"
LISTS = {"cloud-gateways": "router", "wifi": "access_point"}
KEEP_WIFI = re.compile(r"^wifi-(enterprise|flagship|wall|outdoor|mega-capacity|whole-home-wifi)$")
DELAY = 1.0
ND = re.compile(r'<script id="__NEXT_DATA__"[^>]*>(.*?)</script>', re.S)
BAND = {"2.4 GHz": "24", "5 GHz": "5", "6 GHz": "6"}
SOC_VENDOR = (("qualcomm", "qualcomm"), ("mediatek", "mediatek"), ("broadcom", "broadcom"), ("annapurna", "annapurna"), ("marvell", "marvell"),
              ("realtek", "realtek"), ("intel", "intel"))


def next_data(h):
    m = ND.search(h)
    return json.loads(m[1]) if m else {}


class UbiquitiRouters:
    id, version, source_id, categories = ID, VERSION, SOURCE, CATEGORIES

    def __init__(self):
        self.store = C.BlobStore(SOURCE)

    def discover(self, checkpoint, net):
        seen = {}
        for cat, dtype in LISTS.items():
            r = net.get(f"{BASE}/unifi/{cat}", DELAY)
            if not hasattr(r, "status_code") or r.status_code != 200:
                return C.Discovery([], False, f"listing {cat} {getattr(r, 'status_code', r)}", checkpoint or {})
            pp = next_data(r.text).get("props", {}).get("pageProps", {})
            for sc in pp.get("subCategoriesWithProducts") or []:
                if cat == "wifi" and not KEEP_WIFI.match(sc.get("id", "")):
                    continue
                for p in sc.get("products") or []:
                    seen.setdefault(p["slug"], {"url": f"{BASE}/unifi/{cat}/{p['slug']}", "category": cat, "device_type": dtype,
                                                "collection": sc.get("id")})
        refs = [C.Ref(SOURCE, s, d.pop("url"), d) for s, d in sorted(seen.items())]
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


def tree(product):
    """-> {(parent_label|None, label): value_text} plus a list in page order. Flags become 'True'/'False' strings."""
    ts = product.get("technicalSpecification") or {}
    labels, rows = {}, {}
    for s in ts.get("sections") or []:
        for f in s.get("features") or []:
            ft = f.get("feature") or {}
            labels[ft.get("id")] = ft.get("label")
            par = labels.get(ft.get("parentId")) if ft.get("parentId") else None
            v = f.get("value") if f.get("value") is not None else f.get("flag")
            if v is None:
                continue
            rows.setdefault((par, (ft.get("label") or "").strip()), str(v).strip())
    return rows


def _num_unit_mbps(s):
    m = re.match(r"\s*(\d+(?:\.\d+)?)\s*(Gbps|Mbps)", s or "", re.I)
    if not m:
        return None
    v = float(m[1]) * (1000 if m[2].lower() == "gbps" else 1)
    return int(v) if v == int(v) else v


def _port_speed(label):
    """Port Layout child label -> per-port max Mbps ('2.5 GbE RJ45' 2500, '10G SFP+' 10000, 'GbE RJ45' 1000, '25G SFP28' 25000)."""
    m = re.match(r"\s*(\d+(?:\.\d+)?)\s*G(?:bE)?\b", label)
    if m:
        return int(float(m[1]) * 1000)
    if re.match(r"\s*GbE\b", label):
        return 1000
    return None


def parse_html(snap, h):
    pr = C.ParseResult()
    pr.sources = [L.source(snap, "Ubiquiti tech specs " + snap.ref.key)]
    p = next_data(h).get("props", {}).get("pageProps", {}).get("product") or {}
    rows = tree(p)
    if not p.get("name") or not rows:
        pr.absences.append({"key": "*", "reason": "no technicalSpecification tree (not a product page)", "source": "s1"})
        return pr
    model = p["name"].strip()
    hints = snap.ref.hints or {}
    pr.identifiers.append(L.ident("mfr_model", model, "model", "ubiquiti", series="unifi"))
    for v in p.get("variants") or []:
        if v.get("sku") and v["sku"] != model:
            pr.identifiers.append(L.ident("mfr_sku", v["sku"], "configuration", "ubiquiti", parent=model, role="alias"))
    for t in dict.fromkeys(x for x in (p.get("title"), p.get("shortTitle")) if x and x != model):
        pr.aliases.append({"text": t, "kind": "marketing_name"})

    def add(k, v, raw, label):
        L.add(pr, ADAPTER, snap, k, v, raw, "model_code", model, label)

    def get(label, parent=None):
        return rows.get((parent, label))

    add("gen.device_type", hints.get("device_type"), f"techspecs.ui.com/unifi/{hints.get('category')}", "URL section")
    add("gen.product_line", "UniFi", f"techspecs.ui.com/unifi/{hints.get('category')}", "URL section")
    std = get("WiFi Standard")
    add("wifi.generation", R.generation(std), std, "WiFi Standard")
    mimo = {b: rows[(par, b)] for (par, b) in rows if par == "MIMO" and b in BAND}
    rate_par = "Max. Data Rate" if any(par == "Max. Data Rate" for par, _ in rows) else "Throughput"
    rates = {b: rows[(par, b)] for (par, b) in rows if par == rate_par and b in BAND}
    if mimo:
        add("wifi.band_count", len(mimo), " | ".join(f"{b}: {v}" for b, v in mimo.items()), "MIMO (one row per radio)")
    for b, v in mimo.items():
        s = re.match(r"\s*(\d)\s*x\s*(\d)\b", v)
        if s and s[1] == s[2]:
            add(f"wifi.streams_{BAND[b]}", int(s[1]), f"{b}: {v}", "MIMO")
    if any("MU-MIMO" in v for v in mimo.values()):
        add("wifi.mu_mimo", True, " | ".join(mimo.values()), "MIMO")
    for b, v in rates.items():
        add(f"wifi.rate_{BAND[b]}_mbps", _num_unit_mbps(v), f"{b}: {v}", rate_par)
        w = re.search(r"\bBW\s*(\d{2,3})\b", v)
        if w and BAND[b] in ("5", "6"):
            key = "wifi.max_width_5_mhz" if BAND[b] == "5" else "wifi.max_width_6_mhz"
            add(key, w[1], f"{b}: {v}", rate_par)
    if "6 GHz" in mimo or "6 GHz" in rates:
        add("wifi.has_6ghz", True, "6 GHz: " + (mimo.get("6 GHz") or rates.get("6 GHz")), "MIMO / " + rate_par)
    sec = get("Wireless Security")
    if sec and "WPA3" in sec:
        add("wifi.wpa3", True, sec, "Wireless Security")
    # silicon
    proc = get("Processor")
    if proc:
        cores, ghz = R.cpu(proc)
        if cores is None and (n := re.search(r"\b(\d{1,2})-core\b", proc, re.I)):
            cores = int(n[1])
        add("hw.cpu_cores", cores, proc, "Processor")
        add("hw.cpu_ghz", ghz, proc, "Processor")
        for pat, ven in SOC_VENDOR:
            if re.search(r"\b" + pat + r"\b", proc, re.I):
                add("hw.soc_vendor", ven, proc, "Processor")
                part = re.search(r"\b(IPQ\d{4}\w*|MT\d{4}\w*|BCM\d{4,5}\w*|Alpine\s*\w+|AL-?\d{3}\w*|CN\d{4}\w*)\b", proc)
                if part:
                    add("hw.soc_model", part[1], proc, "Processor")
                break
    mem = get("System Memory")
    if mem and (m := re.fullmatch(r"\s*(\d+(?:\.\d+)?)\s*(GB|MB)\b(?:\s*(?:DDR\d\w*|LPDDR\d\w*))?\s*", mem)):
        add("hw.ram_mb", int(float(m[1]) * (1024 if m[2] == "GB" else 1)), mem, "System Memory")
    fl = get("On-Board Flash Storage") or get("Flash Storage")
    if fl and (m := re.fullmatch(r"\s*(\d+(?:\.\d+)?)\s*(GB|MB)\b.*", fl)):
        add("hw.flash_mb", int(float(m[1]) * (1024 if m[2] == "GB" else 1)), fl, "Flash Storage")
    # ports (gateways)
    layout = {lab: v for (par, lab), v in rows.items() if par == "Port Layout"}
    if layout:
        total, mg, mx = 0, 0, 0
        ok = True
        for lab, v in layout.items():
            if re.match(r"\s*(Console|MGMT|Management)\b", lab, re.I):
                continue        # out-of-band ports are neither LAN nor WAN
            c = re.match(r"\s*(\d+)", v)
            sp = _port_speed(lab)
            if not c or not sp:
                ok = False
                continue
            total += int(c[1]); mx = max(mx, sp)
            if sp >= 2500 and re.search(r"RJ45", lab):
                mg += int(c[1])
        wan = get("Default WAN Ports") or ""
        wl = re.findall(r"\((\d+)\)\s*([^\n(]+)", wan)
        wan_n = sum(int(n) for n, _ in wl)
        wsp = [_port_speed(lab) for _, lab in wl]
        if wl and all(wsp):
            add("port.wan_speed_mbps", max(wsp), wan, "Default WAN Ports")
            kinds = {"sfp_plus" if re.search(r"SFP\+|SFP28", lab) else "sfp" if "SFP" in lab else "rj45" if "RJ45" in lab else None for _, lab in wl}
            if len(kinds) == 1 and None not in kinds:
                add("port.wan_type", kinds.pop(), wan, "Default WAN Ports")
        raw = " | ".join(f"{k}: {v}" for k, v in layout.items())
        if ok and wl and all(wsp):
            add("port.lan_count", total - wan_n, raw + " || Default WAN: " + wan, "Port Layout minus Default WAN Ports")
            add("port.lan_max_mbps", mx, raw, "Port Layout")
            if mg:
                add("port.multigig_count", mg, raw, "Port Layout (RJ45 >= 2.5 GbE)")
        mw = get("Max. WAN Port Count")
        if mw and wl and re.fullmatch(r"\d+", mw) and int(mw) > wan_n:
            add("port.wan_lan_configurable", True, f"Max. WAN Port Count {mw}; Default WAN Ports {wan}", "Max. WAN Port Count")
    # PoE
    pm = get("Power Method")
    budget = get("PoE Budget")
    if hints.get("device_type") == "access_point" and pm and re.search(r"\bPoE", pm):
        m = re.match(r"\s*((?:802\.3\w+\s*)?(?:PoE\+\+|PoE\+|PoE)(?:\s*\(802\.3\w+\))?)", pm)
        add("port.poe", (m[1].strip() if m else pm.split("\n")[0].strip()) + " in", pm, "Power Method")
    elif budget:
        poe_ports = [f"{lab} {re.search(r'\(([^)\n]*PoE[^)\n]*)\)', v)[1]}" for lab, v in layout.items() if re.search(r"\([^)\n]*PoE[^)\n]*\)", v)]
        txt = f"PoE out, {'; '.join(x.strip() for x in budget.splitlines() if x.strip())} budget" + (f" ({'; '.join(poe_ports)})" if poe_ports else "")
        add("port.poe", txt, f"PoE Budget {budget}" + (" | " + " | ".join(poe_ports) if poe_ports else ""), "PoE Budget")
    pw = get("Max. Power Consumption")
    if pw and (m := re.match(r"\s*(\d+(?:\.\d+)?)\s*W\b", pw)):
        add("pwr.max_w", float(m[1]) if "." in m[1] else int(m[1]), pw, "Max. Power Consumption")
    # coverage / mesh
    cov = get("Coverage Area")
    if cov and (m := re.search(r"\(([\d,]+)\s*ft", cov)):
        add("mesh.coverage_sqft", int(m[1].replace(",", "")), cov, "Coverage Area")
    if get("Wireless Meshing") == "True":
        add("mesh.supported", True, "Wireless Meshing: True", "Wireless Meshing")
    # software
    vs = [lab for (par, lab), v in rows.items() if par == "VPN Server" and v == "True"]
    vc = [lab for (par, lab), v in rows.items() if par == "VPN Client" and v == "True"]
    m_ = {"OpenVPN": "openvpn", "WireGuard": "wireguard", "L2TP": "l2tp_ipsec", "IPsec": "ipsec", "PPTP": "pptp"}
    if vs:
        add("sw.vpn_server", [m_[x] for x in vs if x in m_], "VPN Server: " + ", ".join(vs), "VPN Server")
        if "WireGuard" in vs:
            add("sw.wireguard", True, "VPN Server: WireGuard", "VPN Server")
    if vc:
        add("sw.vpn_client", [m_[x] for x in vc if x in m_], "VPN Client: " + ", ".join(vc), "VPN Client")
    if get("IPv6 ISP Support") == "True":
        add("isp.ipv6", True, "IPv6 ISP Support: True", "IPv6 ISP Support")
    # physical
    wt = get("Weight") or ""
    if wt:
        parts = [x for x in wt.split("\n") if x.strip()]
        pick = parts[0] if len(parts) == 1 or parts[0].startswith("Device:") else None
        if pick and (m := re.search(r"(\d+(?:\.\d+)?)\s*(kg|g)\b", pick)):
            add("phys.weight", round(float(m[1]) * (1000 if m[2] == "kg" else 1), 1), wt, "Weight")
    dm = get("Dimensions") or ""
    if "⌀" not in dm:
        add("phys.dimensions", R.dims_mm(dm), dm, "Dimensions")
    pr.fingerprints = {"raw": snap.snapshot, "labels": sorted({f"{a}>{b}" if a else b for a, b in rows})[:400], "sku": [v.get("sku") for v in p.get("variants") or []],
                       "unmapped": {k: rows[(None, k)][:100] for k in ("Spatial Streams", "Uplink", "Networking Interface", "Channel Bandwidth") if (None, k) in rows}}
    return pr


if __name__ == "__main__":
    _run.main(UbiquitiRouters())
