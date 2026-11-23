#!/usr/bin/env python3
"""CSA Matter Distributed Compliance Ledger (DCL) adapter v1 for robot vacuums (contract ARCHITECTURE 15.5). Certification source for smart.matter.

Source   : the public DCL REST mirror https://on.dcl.csa-iot.org (Cosmos SDK REST; robots.txt answers 501 'Not Implemented' -> no rules).
           /dcl/model/models (all registered device models; deviceTypeId 116 = 0x0074 Robotic Vacuum Cleaner), /dcl/vendorinfo/vendors,
           /dcl/compliance/compliance-info (softwareVersionCertificationStatus 2 = certified, cDCertificateId, date, certificationRoute).
discover : page the three lists (pagination.limit=1000, next_key). Ledger rows are GLOBAL and include regional / kit / colour names
           (Dreame 'L60s Pro Ultra Kit', 'L50 Ultra CE') and generic names ('Floor Cleaning Robot', 'Robotic Vacuum Cleaner', 'Roomba'):
           minting models from them would invent US models. So a row becomes a ref ONLY when its vendor is a brand with a US-store adapter here
           and its product name (minus the brand word) normalises to EXACTLY a model name that store's discovery.json lists. Everything else is
           counted in the checkpoint (unmatched / generic), never fetched. The DCL rows only enrich existing US models.
fetch    : per ref: /dcl/model/models/{vid}/{pid} and /dcl/compliance/compliance-info/{vid}/{pid}/{softwareVersion}/matter for every certified
           software version the list showed -> one JSON bundle snapshot.
parse    : pure. mfr_model = the matched store model name (issuer = brand), alias 'certifier_listing' = DCL productName, alias x_dcl_vid_pid.
           Claim smart.matter = true ONLY when at least one compliance record has status 2 (certified) with a cDCertificateId; quote = certificate
           id + date + route. A registered-but-uncertified model gives an absence, not false.
"""
import gzip, json, re, sys, time, urllib.parse
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
import _contract as C
import _robovac as RV
import _run

ID, VERSION, SOURCE = "csa_dcl_robovac", 1, "csa-dcl-robovac"
CATEGORIES = {"robot-vacuums"}
ADAPTER = f"{ID}@{VERSION}"
BASE = "https://on.dcl.csa-iot.org"
ROBOVAC = 116
# DCL vendor name (lower) -> (brand, store source whose discovery.json lists the US model names, brand words stripped from productName)
VENDORS = {"dreame": ("dreame", "dreame-us-robovac", r"dreame"), "narwal": ("narwal", "narwal-us-robovac", r"narwal"),
           "roborock": ("roborock", "roborock-us-robovac", r"roborock"), "ecovacs": ("ecovacs", "ecovacs-us-robovac", r"ecovacs"),
           "mova": ("mova", "mova-us-robovac", r"mova")}


def norm(s):
    return re.sub(r"[^A-Z0-9]", "", RV.plus(s or "").upper())


def pages(net, path, key):
    out, nk = [], None
    for _ in range(100):
        q = "pagination.limit=1000" + (f"&pagination.key={urllib.parse.quote(nk)}" if nk else "")
        r = net.get(f"{BASE}{path}?{q}", RV.DELAY)
        if not hasattr(r, "status_code") or r.status_code != 200:
            raise RuntimeError(f"{path}: {getattr(r, 'status_code', r)}")
        d = r.json()
        out += d.get(key) or []
        nk = (d.get("pagination") or {}).get("next_key")
        if not nk:
            return out
    raise RuntimeError(f"{path}: page cap")


def store_models(source_id):
    p = C.ROOT / "raw" / source_id / "discovery.json"
    if not p.exists():
        return {}
    return {norm(r["hints"].get("model")): r["hints"]["model"] for r in json.loads(p.read_text())["refs"] if r.get("hints", {}).get("model")}


class CsaDclRobovac:
    id, version, source_id, categories = ID, VERSION, SOURCE, CATEGORIES

    def __init__(self):
        self.store = C.BlobStore(SOURCE)

    def discover(self, checkpoint, net):
        try:
            models = [m for m in pages(net, "/dcl/model/models", "model") if m.get("deviceTypeId") == ROBOVAC]
            vendors = {v["vendorID"]: v["vendorName"] for v in pages(net, "/dcl/vendorinfo/vendors", "vendorInfo")}
            comp = pages(net, "/dcl/compliance/compliance-info", "complianceInfo")
        except RuntimeError as e:
            return C.Discovery([], False, str(e), {})
        cert = {}
        for c in comp:
            cert.setdefault((c["vid"], c["pid"]), []).append(c["softwareVersion"])
        refs, stats, seen = [], {"robovac_rows": len(models), "matched": 0, "unmatched": {}, "other_vendor": {}}, set()
        known = {k: store_models(src) for k, (_, src, _) in VENDORS.items()}
        for m in models:
            vn = (vendors.get(m["vid"]) or "").lower()
            vk = next((k for k in VENDORS if k in vn), None)
            if not vk:
                stats["other_vendor"][vn or str(m["vid"])] = stats["other_vendor"].get(vn or str(m["vid"]), 0) + 1
                continue
            brand, src, word = VENDORS[vk]
            name = re.sub(rf"(?i)^\s*{word}\s+", "", (m.get("productName") or "").strip())
            us = known[vk].get(norm(name))
            if not us:
                stats["unmatched"][vk] = stats["unmatched"].get(vk, 0) + 1
                continue
            key = f"{m['vid']}-{m['pid']}"
            if key in seen:
                continue
            seen.add(key)
            stats["matched"] += 1
            refs.append(C.Ref(SOURCE, key, f"{BASE}/dcl/model/models/{m['vid']}/{m['pid']}",
                              {"vid": m["vid"], "pid": m["pid"], "brand": brand, "model": us, "vendor": vendors.get(m["vid"]),
                               "software_versions": sorted(set(cert.get((m["vid"], m["pid"]), [])))}))
        return C.Discovery(refs, True, None, stats)

    def fetch(self, ref, prior, net):
        now = time.strftime("%FT%TZ", time.gmtime())
        r = net.get(ref.url, RV.DELAY)
        if not hasattr(r, "status_code") or r.status_code != 200:
            s = C.Snapshot("sha256:", ref, getattr(r, "status_code", r) or "breaker", now, ref.url, {})
            self.store.append(s, ADAPTER, ".json.gz")
            return s
        comp = []
        for sv in ref.hints.get("software_versions") or []:
            c = net.get(f"{BASE}/dcl/compliance/compliance-info/{ref.hints['vid']}/{ref.hints['pid']}/{sv}/matter", RV.DELAY)
            if hasattr(c, "status_code") and c.status_code == 200:
                comp.append(c.json().get("complianceInfo") or c.json())
        body = {"model": r.json().get("model") or r.json(), "compliance": comp, "vendor": ref.hints.get("vendor"),
                "matched_store_model": ref.hints.get("model"), "brand": ref.hints.get("brand")}
        blob = gzip.compress(json.dumps(body, sort_keys=True).encode(), 6, mtime=0)
        s = C.Snapshot(self.store.put(blob, ".json.gz"), ref, 200, now, r.url, {"etag": None, "last_modified": None})
        self.store.append(s, ADAPTER, ".json.gz")
        return s

    def parse(self, snap, blobs, profile):
        return parse_bundle(snap, RV.read_bundle(blobs, snap))


def parse_bundle(snap, b):
    pr = C.ParseResult()
    m = b.get("model") or {}
    pr.sources = [{"id": "s1", "url": snap.ref.url, "snapshot": snap.snapshot, "tier": "certifier", "source_id": SOURCE,
                   "title": f"CSA Matter DCL model {m.get('vid')}/{m.get('pid')}"}]
    name, brand = b.get("matched_store_model"), b.get("brand")
    if not name or not brand or m.get("deviceTypeId") != ROBOVAC:
        pr.absences.append({"key": "*", "reason": "not a matched robotic-vacuum DCL row", "source": "s1"})
        return pr
    model = RV.plus(name)
    pr.identifiers.append(RV.ident("mfr_model", model, "model", brand, market=None, raw=name))
    pr.identifiers.append(RV.ident("x_dcl_vid_pid", f"{m['vid']}:{m['pid']}", "model", "csa", role="alias", market=None, parent=model))
    pr.aliases.append({"text": RV.text(m.get("productName")), "kind": "certifier_listing"})
    if m.get("partNumber") and m["partNumber"] not in ("-", "0", "1") and norm(m["partNumber"]) != norm(name):
        pr.aliases.append({"text": RV.text(m["partNumber"]), "kind": "part_number"})
    certs = [c for c in b.get("compliance") or [] if c.get("softwareVersionCertificationStatus") == 2 and c.get("cDCertificateId")]
    if certs:
        c = sorted(certs, key=lambda c: c.get("date") or "")[0]
        q = f"CSA Matter certificate {c['cDCertificateId']} ({(c.get('date') or '')[:10]}, {c.get('certificationRoute')}, {c.get('transport')})"
        pr.claims.append(C.claim(model, "smart.matter", True, None, f"DCL compliance-info status 2 (certified) {c['cDCertificateId']}", "s1", ADAPTER,
                                 "adapter", snap.fetched_at, locator={"model_code": model, "dcl": f"{m['vid']}:{m['pid']}:{c['softwareVersion']}"}, quote=q))
    else:
        pr.absences.append({"key": "smart.matter", "reason": "registered in the DCL but no certified compliance record", "source": "s1"})
    pr.fingerprints = {"raw": snap.snapshot, "vid_pid": f"{m.get('vid')}:{m.get('pid')}", "certs": len(certs)}
    return pr


if __name__ == "__main__":
    _run.main(CsaDclRobovac())
