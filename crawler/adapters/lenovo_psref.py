#!/usr/bin/env python3
"""Lenovo PSREF adapter v4 (v4: Standard Ports cell -> per-port port.usbc_list + port.tb_usb4/video_out/charge_port, see _lports;
v3: platform-labelled Max Memory cells, see max_memory) (contract: ARCHITECTURE 15.5). Official, structured, per-MTM specs.

PSREF is a SPA over a JSON API. The API wants a short-lived anonymous JWT that the site issues to every
browser (POST /api/home/auth/issue, Origin+Referer set); no login/CAPTCHA; robots.txt is 404.
  discover : /api/ph/ProductCategoryTree (classification Laptops, non-withdrawn) -> one Ref per ProductKey
  fetch    : one bundle per ProductKey = GetInfoByKey + LoadSpecData + every ShowModel page (30 MTMs/page;
             only page 1 carries `total`+`cols`). Stored as one content-addressed JSON blob; append-only log.
  parse    : pure; emits mtm/gtin/mfr_model identifiers, raw-literal claims per MTM (locator.mtm), absences.
Region of an MTM = last 2 chars; US = 'US' (Region NA, Country 'USA').
"""
import gzip, json, re, sys, time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import _contract as C
import _lports
import _run

BASE = "https://psref.lenovo.com"
DELAY = 1.1
PAGE = 500  # server honours pagesize up to at least 500 (default UI uses 30)
HDR = {"Origin": BASE, "Referer": BASE + "/"}
# PSREF column -> profile key (value = source literal, never coerced; normalisation happens downstream)
COLMAP = {"Processor": "cpu.model", "NPU": "cpu.npu_tops", "Graphics": "gpu.model", "Memory": "mem.size", "Max Memory": "mem.max",
          "Memory Slots": "mem.slots", "Storage": "stor.size", "Storage Slot": "stor.slots", "Display": "disp.size",
          "Touchscreen": "disp.touch", "Battery": "pwr.battery_wh", "Power Adapter": "pwr.charger_w", "Standard Ports": "port.usbc_list",
          "WLAN + Bluetooth": "wl.wifi", "WWAN": "wl.wwan", "Ethernet": "port.ethernet", "Card Reader": "port.card_reader",
          "Keyboard": "in.kb_layout", "Camera": "in.webcam", "Fingerprint Reader": "in.fingerprint", "Security Chip": "in.tpm",
          "Weight": "phys.weight", "Dimensions (WxDxH)": "phys.dimensions", "Case Material": "phys.material",
          "Operating System": "sw.os", "Base Warranty": "sw.warranty", "Case Color": "id.color", "Country/Region": "id.region"}


PLATFORM = re.compile(r"^([A-Z][A-Za-z0-9 ,-]*?):\s*(?=\S)")       # "Arrow Lake: up to 64GB ..." / "Models with Non-ECC memory: Up to 192GB ..."
ECC = re.compile(r"^Models with (Non-ECC|ECC) memory$")


def max_memory(v, row):
    """PSREF Max Memory cell of ONE MTM row -> the value to normalise (v3). Newer PSREF layouts prefix the MTM's own cell with the platform
    it applies to ("Lunar Lake: 32GB soldered memory, not upgradable"): the row is already this MTM's, so the label is dropped (raw keeps it).
    A cell listing several variants (sep "^|^") is resolved only by the ECC/Non-ECC split, read from this MTM's own Memory cell; any other
    multi-variant cell, or an ECC split the Memory cell does not settle, stays the literal (it does not normalise: unknown, never a guess)."""
    parts = [x.strip() for x in v.split("^|^") if x.strip()]
    if len(parts) == 1:
        m = PLATFORM.match(parts[0])
        return parts[0][m.end():] if m and not re.search(r"\d\s*GB", m.group(1), re.I) else parts[0]
    mem = row.get("Memory") or ""
    want = "Non-ECC" if re.search(r"\bNon-ECC\b", mem) else ("ECC" if re.search(r"(?<!Non-)\bECC\b", mem) else None)
    hit = []
    for x in parts:
        m = PLATFORM.match(x)
        e = ECC.match(m.group(1)) if m else None
        if not e:
            return v
        if e.group(1) == want:
            hit.append(x[m.end():])
    return hit[0] if want and len(hit) == 1 else v


PORT_KEYS = {"usbc_list": "port.usbc_list", "tb_usb4": "port.tb_usb4", "video_out": "port.video_out", "charge_port": "port.charge_port"}


def port_claims(mtm, v, ex, obs):
    """Standard Ports cell of ONE MTM row -> claims (v4). A fully understood cell (crawler/adapters/_lports.py) yields the structured per-port
    port.usbc_list plus the stated port.tb_usb4 / port.video_out / port.charge_port, each located at the segment(s) that state it; any other
    cell keeps the v3 literal port.usbc_list claim (raw = the cell, value unchanged) and nothing else."""
    p = _lports.ports(v)
    if "usbc_list" not in p:
        return [C.claim(mtm, "port.usbc_list", v, None, v, "s1", ex, "adapter", obs, locator={"mtm": mtm, "column": "Standard Ports"})]
    return [C.claim(mtm, key, p[f], None, v, "s1", ex, "adapter", obs, locator={"mtm": mtm, "column": "Standard Ports", "segments": p["segments"][f]})
            for f, key in PORT_KEYS.items() if f in p]


def mtm_region(m):
    return m[-2:] if len(m) == 10 else None


class LenovoPsref:
    id, version, source_id, categories = "lenovo_psref", 5, "lenovo-psref", {"laptops"}

    def __init__(self):
        self.store = C.BlobStore(self.source_id)
        self.tok, self.tok_exp = None, 0

    # ---- network (shared Net: robots, per-host delay, breaker)
    def _token(self, force=False):
        if force or not self.tok or time.time() > self.tok_exp - 120:
            w = C.NET.last.get("psref.lenovo.com", 0) + DELAY - time.time()
            if w > 0:
                time.sleep(w)
            r = C.NET.s.post(BASE + "/api/home/auth/issue", json={}, headers=HDR, timeout=30)
            C.NET.last["psref.lenovo.com"] = time.time()
            if r.status_code != 200:
                raise _run.StopCrawl(f"token issue http {r.status_code}")
            j = r.json(); self.tok, self.tok_exp = j["access_token"], time.time() + int(j.get("expires_in", 600))
        return self.tok

    def _get(self, path, **q):
        q["t"] = int(time.time() * 1000)
        url = BASE + path + "?" + "&".join(f"{k}={v}" for k, v in q.items())
        for _ in range(2):
            r = C.NET.get(url, DELAY, headers={**HDR, "Authorization": "Bearer " + self._token()})
            if hasattr(r, "status_code") and r.status_code == 200:
                return r.json()
            if hasattr(r, "status_code") and r.status_code in (401, 403):
                self._token(force=True); continue
            break
        raise _run.StopCrawl(f"GET {path} -> {getattr(r, 'status_code', r)}")

    def _snap(self, ref, body, status=200):
        raw = json.dumps(body, sort_keys=True, separators=(",", ":")).encode()
        sha = self.store.put(gzip.compress(raw, 6, mtime=0), ".json.gz")  # rows repeat 55 column values: ~15x smaller gzipped
        s = C.Snapshot(sha, ref, status, time.strftime("%FT%TZ", time.gmtime()), ref.url, {})
        self.store.append(s, f"{self.id}@{self.version}", ".json.gz")
        return s

    # ---- contract
    def discover(self, checkpoint, net):
        r = net.get(BASE + "/api/ph/ProductCategoryTree", DELAY, headers=HDR)
        if not hasattr(r, "status_code") or r.status_code != 200:
            return C.Discovery([], False, f"tree http {getattr(r, 'status_code', r)}", checkpoint or {})
        tree = r.json()["data"]["ProductClassificationList"]
        self.store.put(r.content, ".json")
        refs, total, withdrawn = [], 0, 0
        for cl in tree:
            for pl in cl["ProductLineList"]:
                for se in pl["ProductSeriesList"]:
                    for p in se["ProductList"]:
                        if cl["ClassificationName"] != "Laptops":
                            continue
                        total += 1
                        if p["Withdraw"]:
                            withdrawn += 1; continue
                        refs.append(C.Ref(self.source_id, p["ProductKey"], f"{BASE}/product/{p['ProductID']}",
                                          {"title": p["ProductName"], "line": pl["ProductLine"], "series": se["SeriesName"],
                                           "product_id": p["ProductID"], "is_new": bool(p["IsNewProduct"])}))
        return C.Discovery(refs, True, None, {"laptops_total": total, "withdrawn_skipped": withdrawn})

    def fetch(self, ref, prior, net):
        key = ref.key
        info = self._get("/api/product/Info/GetInfoByKey", ProductKey=key)
        plat = self._get("/api/product/Compare/LoadSpecData", ProductKey=key)
        rows, cols, total, page = [], None, None, 1
        while True:
            d = self._get("/api/search/DefinitionFilterAndSearch/ShowModel", pageindex=page, pagesize=PAGE, product_key=key, filter="[]",
                          search="", search_rule=1, orderby="", In_positive_or_reverse_order=0, filter_option="", mt="", vertical="true")["data"]
            if not isinstance(d, dict) or "rows" not in d:
                break
            cols = d.get("cols") or cols
            total = d.get("total") or total
            rows += [dict(zip(cols, r), _withdrawn=w) for r, w in zip(d["rows"], d["withdraws"])]
            if len(d["rows"]) < PAGE:
                break
            page += 1
        return self._snap(ref, {"product_key": key, "info": info.get("data"), "platform_spec": plat.get("data"),
                                "models_total": total, "models": rows})

    def parse(self, snap, blobs, profile):
        try:
            b = json.loads(gzip.decompress(blobs.read(snap.snapshot, ".json.gz")))
        except FileNotFoundError:  # first 16 snapshots were stored uncompressed
            b = json.loads(blobs.read(snap.snapshot, ".json"))
        src = [{"id": "s1", "url": snap.ref.url, "snapshot": snap.snapshot, "tier": "manufacturer", "title": "Lenovo PSREF " + b["product_key"]}]
        pr = C.ParseResult(sources=src)
        obs = snap.fetched_at
        pr.aliases.append({"text": (b["info"] or {}).get("ProductName") or snap.ref.hints.get("title", b["product_key"]), "kind": "marketing_name"})
        pr.identifiers.append({"scheme": "mfr_model", "value": b["product_key"], "value_raw": b["product_key"], "issuer": "lenovo",
                               "package_level": "model", "role": "key", "sources": ["s1"]})
        mts = set()
        for m in b["models"]:
            mtm = m.get("Model", "")
            if not re.fullmatch(r"[0-9A-Z]{10}", mtm):
                pr.absences.append({"key": "id.mpn", "status": "ambiguous_identity", "source": "s1", "checked_at": obs}); continue
            mts.add(m.get("Machine Type"))
            pr.identifiers.append({"scheme": "mtm", "value": mtm, "value_raw": mtm, "issuer": "lenovo", "market": "US" if mtm.endswith("US") else None,
                                   "package_level": "configuration", "role": "key", "sources": ["s1"]})
            ean = re.sub(r"\D", "", m.get("EAN / UPC / JAN", "") or "")
            if ean:
                pr.identifiers.append({"scheme": "gtin", "value": ean.zfill(14), "value_raw": m["EAN / UPC / JAN"], "issuer": "GS1",
                                       "package_level": "configuration", "role": "alias", "sources": ["s1"]})
            for col, key in COLMAP.items():
                v = (m.get(col) or "").strip()
                if v and col == "Standard Ports":
                    pr.claims += port_claims(mtm, v, f"{self.id}@{self.version}", obs)
                elif v:
                    c = C.claim(mtm, key, max_memory(v, m) if col == "Max Memory" else v, None, v, "s1", f"{self.id}@{self.version}", "adapter", obs, locator={"mtm": mtm, "column": col})
                    pr.claims.append(c)
        for mt in sorted(x for x in mts if x):
            pr.identifiers.append({"scheme": "x_lenovo_machine_type", "value": mt, "value_raw": mt, "issuer": "lenovo", "package_level": "model", "sources": ["s1"]})
        pr.fingerprints = {"models": len(b["models"]), "models_total": b["models_total"], "us": sum(m.get("Model", "").endswith("US") for m in b["models"])}
        return pr


if __name__ == "__main__":
    _run.main(LenovoPsref())
