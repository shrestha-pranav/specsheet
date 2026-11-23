#!/usr/bin/env python3
"""TP-Link US router + Deco mesh adapter v1 (contract ARCHITECTURE 15.5), category routers. Source = www.tp-link.com/us/.

discover : https://www.tp-link.com/us/sitemap.xml (one request, 1 MB; robots allows) -> /us/home-networking/wifi-router/<model>/ (Archer, TL-, ER, mobile)
           and /us/deco-mesh-wifi/product-family/<model>/ (Deco). One Ref per model page (hints.kind router|mesh, hints.support = the matching
           /us/support/download/<model>/ page). Range extenders, switches, 5G hotspots and promo pages are dropped.
fetch    : product page (SSR spec table, ~250 KB) + support download page (~300 KB): hardware-version selector and the firmware list with
           'Published Date'. Stored together as one gzip JSON blob {"product":..., "support":...}. 2 requests per model, 1 req/s.
parse    : pure. Spec rows = <th width=35%>label</th><td>value</td> inside the 'mobile-spec-*' blocks (value lines separated by </br>).
           mfr_model = the page's model name (Archer AX55); every hardware version in the support selector becomes a REVISION entity (identifier scheme
           hw_version, value "<model> <version>" so versions of different models never collide, extra revision_label=<version>; link variant_of the model
           via the importer). Each revision carries sup.hardware_version. The spec table describes only the default version (support page's current
           version), so the revision-level specs it prints (hw.cpu_*, hw.ram_mb, hw.flash_mb, sup.latest_firmware_date) are attributed to THAT revision
           (locator hw_rev) and not to the model; other revisions stay unknown for them. A model without a version list keeps them on the model.
Traps    : the spec table is the CURRENT hardware version only (the /v1/ and /v4/ URLs serve the same HTML; versions switch client-side), so the
           per-version chipset/RAM differences stay unknown here. The processor row is 'Dual-Core CPU' (no vendor, no clock); RAM/flash are
           never printed. 'AX3000' is a class sum. 'Dual-Band' + '4 Streams' is total streams over bands, not 4x4: only an explicit NxN
           (never present on TP-Link pages) would set wifi.streams_*. Firmware list is the US region; its newest 'Published Date' is
           a fetch-time fact (observed_at).
"""
import gzip, json, re, sys, time
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
import _contract as C
import _router as R
import _lt as L
import _run

ID, VERSION, SOURCE = "tplink_routers", 1, "tplink-us-routers"
CATEGORIES = {"routers"}
ADAPTER = f"{ID}@{VERSION}"
BASE = "https://www.tp-link.com"
SITEMAP = BASE + "/us/sitemap.xml"
DELAY = 1.0
LOC = re.compile(r"<loc>https://www\.tp-link\.com/us/(home-networking/wifi-router|deco-mesh-wifi/product-family)/([a-z0-9][a-z0-9-]*)/</loc>")
DROP = re.compile(r"^(m\d|mifi|tl-mr|all-|archer-mr|archer-air-|promotion|buying-guide|ne\d|touch)", re.I)
ROW = re.compile(r'<tr id="tr_\d+">\s*<th width="[^"]*">(.*?)</th>\s*<td[^>]*>(.*?)</td>', re.S)


class TplinkRouters:
    id, version, source_id, categories = ID, VERSION, SOURCE, CATEGORIES

    def __init__(self):
        self.store = C.BlobStore(SOURCE)

    def discover(self, checkpoint, net):
        r = net.get(SITEMAP, DELAY)
        if not hasattr(r, "status_code") or r.status_code != 200:
            return C.Discovery([], False, f"sitemap {getattr(r, 'status_code', r)}", checkpoint or {})
        seen = {}
        for sect, slug in LOC.findall(r.text):
            if DROP.search(slug):
                continue
            kind = "mesh" if sect.startswith("deco") else "router"
            seen.setdefault(slug, {"url": f"{BASE}/us/{sect}/{slug}/", "kind": kind, "support": f"{BASE}/us/support/download/{slug}/"})
        refs = [C.Ref(SOURCE, slug, d["url"], {"kind": d["kind"], "support": d["support"]}) for slug, d in sorted(seen.items())]
        return C.Discovery(refs, True, None, {"models": len(refs)})

    def fetch(self, ref, prior, net):
        now = time.strftime("%FT%TZ", time.gmtime())
        r = net.get(ref.url, DELAY)
        if r is None or isinstance(r, str) or r.status_code != 200:
            st = r if (r is None or isinstance(r, str)) else r.status_code
            s = C.Snapshot("sha256:", ref, st or "breaker", now, ref.url, {})
            self.store.append(s, ADAPTER, ".json.gz")
            return s
        sup = net.get(ref.hints["support"], DELAY)
        sup_html = sup.text if (not isinstance(sup, str) and sup is not None and sup.status_code == 200) else None
        body = json.dumps({"product": r.text, "support": sup_html, "support_url": ref.hints["support"]}).encode()
        s = C.Snapshot(self.store.put(gzip.compress(body, 6, mtime=0), ".json.gz"), ref, 200, now, r.url,
                       {"etag": r.headers.get("ETag"), "last_modified": r.headers.get("Last-Modified")})
        self.store.append(s, ADAPTER, ".json.gz")
        return s

    def parse(self, snap, blobs, profile):
        d = json.loads(gzip.decompress(blobs.read(snap.snapshot, ".json.gz")))
        return parse_pages(snap, d["product"], d.get("support"))


def fw_list(sup):
    """-> [(name, 'YYYY-MM-DD')] for the Firmware rows of the support page."""
    out = []
    for m in re.finditer(r'<tr class="basic-info">(.*?)</tr>\s*<tr class="detail-info">(.*?)</tr>', sup or "", re.S):
        if "Download-Detail-Firmware" not in m[1]:
            continue
        name = R.clean(re.search(r"<p>(.*?)</p>", m[1], re.S)[1]) if re.search(r"<p>(.*?)</p>", m[1], re.S) else ""
        dt = re.search(r"Published Date:\s*</span>\s*<span>\s*(\d{4}-\d{2}-\d{2})", m[2])
        if dt:
            out.append((name, dt[1]))
    return out


def parse_pages(snap, h, sup):
    pr, obs = C.ParseResult(), snap.fetched_at
    pr.sources = [L.source(snap, "TP-Link US product page " + snap.ref.key)]
    h = h.replace("</br>", "<br>")
    rows = {}
    for a, b in ROW.findall(h):
        lab = R.clean(a)
        if lab and lab not in rows:
            rows[lab] = L.lines(b)
    nm = re.search(r'model-name">([^<]+)<', h) or re.search(r"<title>([^|<]+?)\s*\|", h)
    if not rows or not nm:
        pr.absences.append({"key": "*", "reason": "no spec rows / model name (not a product page)", "source": "s1"})
        return pr
    model = R.clean(nm[1])
    mesh = snap.ref.hints.get("kind") == "mesh"
    fam = re.sub(r"[\d-]+.*$", "", snap.ref.key).strip("-") or snap.ref.key
    title = re.search(r"<h1[^>]*>(.*?)</h1>", h, re.S)
    pr.identifiers.append(L.ident("mfr_model", model, "model", "tp_link", series=fam))
    pr.aliases.append({"text": model, "kind": "marketing_name"})
    if title and R.clean(title[1]):
        pr.aliases.append({"text": R.clean(title[1]), "kind": "marketing_name"})

    # hardware versions + firmware (support page); the default version owns the revision-level spec-table claims
    ver_hits = re.findall(r'<li data-value="(V[\d.]+)"', sup or "")
    vers = list(dict.fromkeys(ver_hits))
    cur = re.search(r'class="current-version"[^>]*>\s*(V[\d.]+)', sup or "")
    dflt = cur[1] if (cur and cur[1] in vers) else None
    for v in vers:
        pr.identifiers.append(L.ident("hw_version", f"{model} {v}", "revision", "tp_link", revision_label=v))

    def add(k, v, raw, label):
        L.add(pr, ADAPTER, snap, k, v, raw, "model_code", model, label)

    def radd(k, v, raw, label):
        """Revision-level spec from the spec table: default revision when the version list names it, else the model (no list / no default)."""
        if dflt:
            L.add(pr, ADAPTER, snap, k, v, raw, "hw_rev", dflt, label)
        else:
            add(k, v, raw, label)

    def row(*labs):
        for l_ in labs:
            if l_ in rows:
                return rows[l_]
        return []
    std = " ".join(row("Standards and Protocols")); spd = " ".join(row("WiFi Speeds", "Wi-Fi Speeds")); cap = " ".join(row("WiFi Capacity", "Wi-Fi Capacity"))
    adv = " ".join(row("Advanced Features"))
    allw = " ".join([std, spd, adv, " ".join(row("WiFi Range"))])
    add("gen.product_line", fam.replace("-", " ").title(), snap.ref.key, "URL")
    add("gen.device_type", "mesh_system" if mesh else "router", snap.ref.hints.get("kind"), "URL class")
    add("wifi.generation", R.generation(std) or R.generation(spd), std or spd, "Standards and Protocols" if std else "WiFi Speeds")
    if std or spd:
        add("wifi.has_6ghz", True if re.search(r"6\s*GHz", std + " " + spd) else None, std or spd, "Standards and Protocols")
    mc = R.marketing_class(spd or allw)
    add("wifi.marketing_class", mc, spd, "WiFi Speeds")
    add("wifi.band_count", R.bands(cap) or R.bands(spd), cap, "WiFi Capacity")
    pb = R.per_band(spd)
    for b, d in pb.items():
        if "rate" in d:
            add(f"wifi.rate_{b}_mbps", d["rate"], spd, "WiFi Speeds")
        if "width" in d and b in ("5", "6"):
            add("wifi.max_width_5_mhz" if b == "5" else "wifi.max_width_6_mhz", str(d["width"]), spd, "WiFi Speeds")
    if re.search(r"320\s*MHz", allw) and "6" in pb:       # 320 MHz exists only on 6 GHz: a dual-band 'BE' page that lists it states no 6 GHz radio
        add("wifi.max_width_6_mhz", "320", adv or allw, "Advanced Features")
    if re.search(r"\bMLO\b|Multi-Link", allw, re.I):
        add("wifi.mlo", True, adv or allw, "Advanced Features")
    if re.search(r"4K-?QAM|4096", allw, re.I):
        add("wifi.qam_max", "4096", adv or allw, "Advanced Features")
    if re.search(r"MU-?MIMO", " ".join(rows[x][0] for x in rows if rows[x]) , re.I) or re.search(r"MU-?MIMO", cap):
        add("wifi.mu_mimo", True, cap, "WiFi Capacity")
    if re.search(r"OFDMA", cap + adv):
        add("wifi.ofdma", True, cap or adv, "WiFi Capacity")
    enc = " ".join(row("WiFi Encryption", "Wi-Fi Encryption"))
    if "WPA3" in enc:
        add("wifi.wpa3", True, enc, "WiFi Encryption")
    wr = " ".join(row("WiFi Range", "Wi-Fi Range"))
    if (a := re.search(r"(\d)×\s*(?:Fixed |High-Performance |Detachable )*.*?Antennas?(?:\s*\((Internal|External)\))?", wr)):
        add("wifi.antennas", a[0][:80], wr[:200], "WiFi Range")
    # silicon: only what is printed
    cores, ghz = R.cpu(" ".join(row("Processor")))
    radd("hw.cpu_cores", cores, row("Processor"), "Processor")
    radd("hw.cpu_ghz", ghz, row("Processor"), "Processor")
    fl, ra = R.memory(" ".join(row("Memory", "Flash", "RAM")))
    radd("hw.flash_mb", fl, row("Memory"), "Memory"); radd("hw.ram_mb", ra, row("Memory"), "Memory")
    # ports: the 'Ethernet Ports' row, else the first line that carries Gbps counts (Deco prints it under HARDWARE as a bullet)
    eth = row("Ethernet Ports") or [l for k, v in rows.items() for l in v if re.search(r"\d\s*×\s*(?:Gigabit|[\d.]+\s*G)", l)]
    p = R.ports(eth)
    for k, v in (("port.wan_speed_mbps", p["wan_mbps"]), ("port.lan_count", p["lan_count"]), ("port.lan_max_mbps", p["lan_max"]),
                 ("port.multigig_count", p["multigig"]), ("port.wan_lan_configurable", p["wan_lan_cfg"])):
        add(k, v, eth, "Ethernet Ports")
    if not row("USB Support") and not mesh:
        pass
    n, std_u = R.usb(" ".join(row("USB Support")))
    add("port.usb_count", n, row("USB Support"), "USB Support"); add("port.usb_standard", std_u, row("USB Support"), "USB Support")
    vs = row("VPN Server"); vc = row("VPN Client")
    if vs:
        add("sw.vpn_server", R.vpn(" ".join(vs), "server"), vs, "VPN Server")
    if vc:
        add("sw.vpn_client", R.vpn(" ".join(vc), "client"), vc, "VPN Client")
    ms = R.mesh_systems(" ".join(row("OneMesh™", "OneMesh", "EasyMesh")) + " " + " ".join(rows.get("OneMesh™", [])) + (" EasyMesh" if "EasyMesh" in rows else ""))
    if mesh:
        ms = ["deco"] + ms
        add("mesh.supported", True, "Deco family page", "URL class")
    elif ms:
        add("mesh.supported", True, ms, "OneMesh/EasyMesh")
    add("mesh.systems", ms, ms, "OneMesh/EasyMesh")
    modes = " ".join(row("Working Modes"))
    om = [v for pat, v in ((r"Router", "router"), (r"Access Point", "access_point"), (r"Bridge", "bridge"), (r"Repeater|Range Extender", "repeater")) if re.search(pat, modes, re.I)]
    add("sw.operating_modes", om, modes, "Working Modes")
    if row("Parental Controls"):
        add("sw.parental_controls", True, row("Parental Controls")[:2], "Parental Controls")
    if row("Quality of Service"):
        add("sw.qos", " ".join(row("Quality of Service"))[:80], row("Quality of Service"), "Quality of Service")
    if "IPv6" in " ".join(row("Protocols")) or "IPv6" in " ".join(row("SOFTWARE")):
        add("isp.ipv6", True, row("Protocols") or row("SOFTWARE"), "Protocols")
    ph = " ".join(row("PHYSICAL", "Dimensions (W x D x H)", "Dimensions"))
    add("phys.dimensions", R.dims_mm(ph), ph, "PHYSICAL")
    if row("Power"):
        add("pwr.input", " ".join(row("Power"))[:80], row("Power"), "Power")
    for v in vers:
        L.add(pr, ADAPTER, snap, "sup.hardware_version", v, v, "hw_rev", v, "support version selector")
    fw = fw_list(sup)
    if fw:
        newest = max(fw, key=lambda x: x[1])
        radd("sup.latest_firmware_date", newest[1], f"{newest[0]} Published {newest[1]}" + (f" (page default version {cur[1]})" if cur else ""), "support firmware list")
    pr.fingerprints = {"raw": snap.snapshot, "labels": list(rows), "versions": vers, "default_version": dflt, "firmware_n": len(fw),
                       "unmapped": {k: " | ".join(v)[:100] for k, v in rows.items() if k in ("Certifications", "Service Kits")}}
    return pr


if __name__ == "__main__":
    _run.main(TplinkRouters())
