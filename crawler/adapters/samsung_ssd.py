#!/usr/bin/env python3
"""Samsung US consumer SSD adapter v1 (contract ARCHITECTURE 15.5), category ssds. Source = samsung.com/us (NOT semiconductor.samsung.com:
that site now only carries OEM/datacenter parts; consumer storage redirects to samsung.com/us/memory-storage/).

discover : https://www.samsung.com/us/memory-sitemap.xml (one request) -> /us/memory-storage/{nvme-ssd,sata-ssd,portable-ssd}/<slug>-sku-<part>/ pages
           (+ the odd portable SSD filed under /memory-card/). One buyable SKU per page (capacity x colour x heatsink). robots: only /us/api/ etc.
fetch    : page (0.9 MB, not stored) -> groupId + Product JSON-LD (sku, name, offers.price) ; spec API
           GET /us/gapi/v1/bridge/cacheable/bridge-data?data_type=Specs&store_type=B2C&group_id=<id> (same API samsung.py uses for laptops)
           = fullSpecs for every SKU in the group. Stored: small JSON bundle {page_url, group_id, jsonld, specs}.
parse    : pure. configuration identifier mfr_sku = orderable part (MZ-V9P4T0B/AM), model identifier mfr_model = stem before the capacity
           (MZ-V9P), series = product line slug; only THIS page's SKU row of the group is emitted.
Traps    : 'Storage Memory: V-NAND 3-bit MLC' means TLC (raw kept); 'Sequential Read: Up to ...' is the marketed in-cache number; 'Capacity' appears
           twice per SKU (marketing '1TB' and decimal '1,000GB (1GB=1 billion bytes)'); no TBW row on the page (datasheet PDF only), no NAND layer count.
v4 (2026-11-26, A2-lap r8): the Product JSON-LD name alias carries sku = the page SKU when the JSON-LD sku equals it (import.py bound_label
           names the configuration from it, never from the model's first page). Claims and identifiers unchanged.
"""
import json, re, sys, time
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
import _contract as C
import _ssd as S
import _lt as L
import _run

ID, VERSION, SOURCE = "samsung_ssd", 4, "samsung-us-ssd"
CATEGORIES = {"ssds"}
ADAPTER = f"{ID}@{VERSION}"
BASE = "https://www.samsung.com"
SITEMAP = BASE + "/us/memory-sitemap.xml"
API = BASE + "/us/gapi/v1/bridge/cacheable/bridge-data?data_type=Specs&store_type=B2C&group_id={g}"
DELAY = 1.0
URL_RX = re.compile(r"https://www\.samsung\.com/us/memory-storage/(nvme-ssd|sata-ssd|portable-ssd|memory-card)/([a-z0-9-]*-sku-[a-z0-9-]+)/")


def norm(sku):
    return re.sub(r"[^A-Z0-9]", "", sku.upper())


class SamsungSsd:
    id, version, source_id, categories = ID, VERSION, SOURCE, CATEGORIES

    def __init__(self):
        self.store = C.BlobStore(SOURCE)
        self._specs = {}

    def discover(self, checkpoint, net):
        r = net.get(SITEMAP, DELAY)
        if not hasattr(r, "status_code") or r.status_code != 200:
            return C.Discovery([], False, f"sitemap {getattr(r, 'status_code', r)}", checkpoint or {})
        refs = []
        for u in sorted(set(re.findall(r"<loc>([^<]+)</loc>", r.text))):
            m = URL_RX.fullmatch(u)
            if not m or (m[1] == "memory-card" and not re.search(r"portable-ssd", m[2])):
                continue
            part = m[2].split("-sku-")[1]
            refs.append(C.Ref(SOURCE, part, u, {"slug": m[2], "path": m[1]}))
        return C.Discovery(refs, True, None, {"ssd_urls": len(refs)})

    def fetch(self, ref, prior, net):
        now = time.strftime("%FT%TZ", time.gmtime())

        def fail(st):
            s = C.Snapshot("sha256:", ref, st, now, ref.url, {})
            self.store.append(s, ADAPTER, ".json")
            return s
        page = net.get(ref.url, DELAY)
        if not hasattr(page, "status_code") or page.status_code != 200:
            return fail(getattr(page, "status_code", page))
        t = page.text
        g = re.search(r'"groupId":"(\d+)"', t)
        if not g:
            return fail("no-groupId")
        want = norm(ref.key)
        prod = None
        for m in re.finditer(r'<script[^>]*ld\+json[^>]*>(.*?)</script>', t, re.S):
            try:
                j = json.loads(m.group(1))
            except ValueError:
                continue
            if isinstance(j, dict) and j.get("@type") == "Product" and norm(str(j.get("sku", ""))) == want:
                prod = j
                break
        gid = g.group(1)
        if gid not in self._specs:
            sp = net.get(API.format(g=gid), DELAY)
            if not hasattr(sp, "status_code") or sp.status_code != 200:
                return fail(getattr(sp, "status_code", sp))
            self._specs[gid] = sp.json()
        bundle = {"page_url": ref.url, "group_id": gid, "product_jsonld": prod, "specs": self._specs[gid]}
        s = C.Snapshot(self.store.put(json.dumps(bundle, sort_keys=True).encode(), ".json"), ref, 200, now, ref.url, {})
        self.store.append(s, ADAPTER, ".json")
        return s

    def parse(self, snap, blobs, profile):
        b = json.loads(blobs.read(snap.snapshot, ".json"))
        obs, pr = snap.fetched_at, C.ParseResult()
        pr.sources = [L.source(snap, "Samsung US " + snap.ref.key)]
        want = norm(snap.ref.key)
        row = next((m for m in b["specs"] if norm(m["modelCode"]) == want), None)
        if row is None:
            pr.absences.append({"key": "*", "reason": f"spec API group {b['group_id']} has no row for {snap.ref.key}", "source": "s1"})
            return pr
        code = row["modelCode"].upper()
        m = re.match(r"([A-Z]{2}-[A-Z0-9]+?)(?:\d{1,3}T\d|\d{3})[A-Z0-9/]*$", code)
        stem = m[1] if m else code
        series = snap.ref.hints.get("slug", "").split("-sku-")[0]
        pr.identifiers.append(L.ident("mfr_model", stem, "model", "samsung", series=series))
        pr.identifiers.append(L.ident("mfr_sku", code, "configuration", "samsung", parent=stem))
        j = b.get("product_jsonld") or {}
        if j.get("name"):                       # v4: the page's own Product name names THIS SKU when its JSON-LD sku is the page SKU
            pr.aliases.append({"text": j["name"], "kind": "marketing_name", **({"sku": code} if norm(j.get("sku") or "") == want else {})})
        pr.aliases.append({"text": snap.ref.hints.get("slug", ""), "kind": "retail_slug"})
        T = {}                                  # label -> values in page order, across all groups (layout differs per product group)
        for g in row.get("fullSpecs", []):
            for sp in g.get("specList", []):
                T.setdefault(S.clean(sp["name"]), []).append(S.clean(sp.get("value")))
        used = set()

        def get(*names, i=0):
            for nme in names:
                v = T.get(nme)
                if v and len(v) > i:
                    used.add(nme)
                    return v[i]
            return None

        def add(k, v, raw, label):
            S.add(pr, ADAPTER, snap, k, v, raw, "sku", code, label)
        pt = get("Product Type") or ""
        portable = bool(re.search(r"portable", pt, re.I)) or code.startswith("MU-")
        add("gen.device_class", "portable_usb" if portable else ("sata_2_5" if code.startswith("MZ-77") else "m2_nvme"), pt or code, "Product Type")
        if (v := get("Interface (thru IMB)", "Interface")):
            if portable:
                add("if.usb_standard", S.usb(v), v, "Interface")
                add("if.protocol", S.usb_protocol(v), v, "Interface")      # v3: affirmative USB interface only (ruling 4)
            elif re.search(r"SATA", v, re.I):
                add("if.protocol", "sata_ahci", v, "Interface")
            else:
                for k, x in S.interface(v):
                    add(k, x, v, "Interface")
        if not portable and not any(c["key"] == "if.protocol" for c in pr.claims) and re.search(r"\bNVMe\b", j.get("name") or ""):
            add("if.protocol", "nvme", j["name"], "Product name")        # v3: the maker's own product name ('990 PRO ... SSD NVMe™ M.2') where no Interface row
        if (v := get("Controller")) and not re.search(r"DDR|DRAM", v, re.I):    # some rows carry the DRAM string in the Controller cell (source defect)
            add("hw.controller", v, v, "Controller")
            if re.search(r"Samsung|in-?house", v, re.I):
                add("hw.controller_vendor", "in_house", v, "Controller")
        if (v := get("Weight")):
            if (m := re.search(r"([\d.]+)\s*lb", v)):
                add("gen.weight", round(float(m[1]) * 453.59237, 1), v, "Weight")
            elif (m := re.search(r"([\d.]+)\s*g\b", v)):
                add("gen.weight", float(m[1]), v, "Weight")
        caps = T.get("Capacity") or []
        if caps:
            used.add("Capacity")
            dec = next((c for c in caps if re.search(r"\d\s*GB\s*\(", c)), None)
            add("gen.capacity", S.capacity_gb(dec or "") or S.capacity_gb(caps[0]), dec or caps[0], "Capacity")
        if (v := get("Form Factor")):
            add("gen.form_factor", S.form_factor(v) or ("portable" if portable else None), v, "Form Factor")
        elif portable:
            add("gen.form_factor", "portable", pt or code, "Product Type")
        if (v := get("Storage Memory")):
            add("hw.nand_type", S.nand_type(v), v, "Storage Memory")
            add("hw.nand_vendor", S.nand_vendor(v), v, "Storage Memory")
        if (v := get("Cache Memory")):
            for k, x in S.dram(v):
                add(k, x, v, "Cache Memory")
        for lab, k, fn in (("Sequential Read", "perf.seq_read", S.speed_mbs), ("Sequential Write", "perf.seq_write", S.speed_mbs),
                           ("Random Read (4KB, QD32)", "perf.rand_read_iops_qd32", S.iops), ("Random Write (4KB, QD32)", "perf.rand_write_iops_qd32", S.iops),
                           ("Random Read (4KB, QD1)", "perf.rand_read_iops_qd1", S.iops), ("Random Write (4KB, QD1)", "perf.rand_write_iops_qd1", S.iops)):
            if (v := get(lab)):
                add(k, fn(v), v, lab)
        if (v := get("Random Read", "Random Write")) is not None:
            for lab, k in (("Random Read", "perf.rand_read_iops_qd32"), ("Random Write", "perf.rand_write_iops_qd32")):
                vv = (T.get(lab) or [None])[0]
                if vv and "QD" not in lab and not any(c["key"] == k for c in pr.claims) and S.iops(vv):
                    used.add(lab)
                    add(k, S.iops(vv), vv, lab)    # portable pages print 'Random Read 850KIOPS' without the queue depth: kept only as the unconditioned number
        # older/portable pages print combined or differently labelled rows
        have = lambda k: any(c["key"] == k for c in pr.claims)
        if not have("perf.seq_read") and (v := get("Read/Write Speeds", "Seq. Read/Write (MB/s)", "Speed", "Transfer Speed")):
            if (m := re.search(r"(?:Sequential )?Read:?\s*(?:up to\s*)?([\d,]+)\s*MB/s.*?Write:?\s*(?:up to\s*)?([\d,]+)\s*MB/s", v, re.I)) or \
               (m := re.search(r"([\d,]+)\s*/\s*([\d,]+)\s*MB/s", v)) or (m := re.search(r"up to\s*([\d,]+)\s*/\s*([\d,]+)", v, re.I)):
                add("perf.seq_read", S.n(m[1]), v, "Read/Write Speeds")
                add("perf.seq_write", S.n(m[2]), v, "Read/Write Speeds")
        if not have("perf.seq_read") and (v := get("Sequential Read Speed")):
            add("perf.seq_read", S.speed_mbs(v), v, "Sequential Read Speed")
        if not have("perf.seq_write") and (v := get("Sequential Write Speed")):
            add("perf.seq_write", S.speed_mbs(v), v, "Sequential Write Speed")
        if not have("perf.rand_read_iops_qd32") and (v := get("Ran. Read/Write (IOPS ,QD32)")) and (m := re.search(r"([\d.,]+)\s*K?\s*/\s*([\d.,]+)\s*K", v)):
            add("perf.rand_read_iops_qd32", int(S.n(m[1]) * 1000), v, "Ran. Read/Write (IOPS ,QD32)")
            add("perf.rand_write_iops_qd32", int(S.n(m[2]) * 1000), v, "Ran. Read/Write (IOPS ,QD32)")
        if (v := get("Total Bytes Written (TBW)", "TBW")) and re.fullmatch(r"[\d,]+(\s*TBW?)?", v):
            add("end.tbw", S.n(re.match(r"[\d,]+", v)[0]), v, "Total Bytes Written (TBW)")
        if not have("hw.nand_type") and (v := get("NAND")):
            add("hw.nand_type", S.nand_type(v), v, "NAND")
            add("hw.nand_vendor", S.nand_vendor(v), v, "NAND")
        if (v := get("Data Encryption")) and re.search(r"Opal\s*v?2", v, re.I):
            add("sec.encryption", "opal_2_ieee1667" if re.search(r"1667", v) else "opal_2", v, "Data Encryption")
        if not have("pwr.idle_mw") and (v := get("Device Sleep (L1.2)")) and (m := re.search(r"([\d.]+)\s*mW", v)):
            add("pwr.l1_2_mw", float(m[1]), v, "Device Sleep (L1.2)")
        if (v := get("Power consumption (Idle)")) and (m := re.search(r"([\d.]+)\s*mW", v)):
            add("pwr.idle_mw", float(m[1]), v, "Power consumption (Idle)")
        if (v := get("Reliability (MTBF)")) and (m := re.search(r"([\d.]+)\s*Million", v)):
            add("end.mtbf", int(float(m[1]) * 1000000), v, "Reliability (MTBF)")
        if (v := get("Operating Temperature")) and (r := S.temp_range(v)):
            add("therm.temp_operating", r, v, "Operating Temperature")
        w = next((x for x in (T.get("Warranty") or []) if S.years(x) or re.search(r"\((\d+)\)\s*year", x, re.I)), None)
        if w:
            used.add("Warranty")
            add("end.warranty_years", S.years(w) or int(re.search(r"\((\d+)\)\s*year", w, re.I)[1]), w, "Warranty")
        if (v := get("Encryption Support", "Encryption")) and re.search(r"AES", v) and not re.search(r"Opal", v, re.I):
            add("sec.encryption", "aes256", v, "Encryption")
        if (v := get("Durability")) and (m := re.search(r"([\d.]+)[- ]*(?:meter|m)\b", v, re.I)):
            add("port.drop", float(m[1]), v, "Durability")
        if isinstance(j.get("offers"), dict) and j["offers"].get("price"):
            p = j["offers"]["price"]
            add("id.msrp_us", float(p), f"{p} USD (samsung.com price at fetch)", "Offer.price")
        pr.fingerprints = {"raw": snap.snapshot, "model": stem, "sku": code, "group_id": b["group_id"], "siblings": [m["modelCode"] for m in b["specs"]],
                           "unmapped": {k: v for k, v in T.items() if k not in used}}
        return pr


if __name__ == "__main__":
    _run.main(SamsungSsd())
