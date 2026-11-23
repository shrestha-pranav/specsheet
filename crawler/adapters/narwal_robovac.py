#!/usr/bin/env python3
"""Narwal US robot-vacuum adapter v1 (contract ARCHITECTURE 15.5), category robot-vacuums. Source = us.narwal.com (Shopify).

discover : /products.json (1 page) -> product_type 'Robot Vacuum Cleaner' / 'Vacuum Mop' whose title names a robot (wet-dry S20/S30 dropped).
fetch    : bundle = product page + /products/<handle>.json.
parse    : pure. 'Specifications.' block of ndev-ax26-spec-row rows (label cell / value cell, desktop span): Robot Vacuum Dimensions, Base Station
           Dimensions/Weight, Robot Vacuum Weight, Maximum Suction, Mop Lifting, Navigation, Objects Detection, Battery Capacity. Older pages
           (Freo X Plus, Flow) have an empty body and no block: absences, not guesses.
Identity : mfr_model = model name (Freo Z10 Turbo). Variant SKU CP-ZD-A00331-00-00_DTC_N_US_YJ_260510 = material code + channel/batch suffix;
           the suffix after '_' is a sales-channel/date tag, so the alias is the material code (CP-ZD-A00331-00-00, '-AC01' = accessory pack variant).
"""
import re, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
import _contract as C
import _robovac as RV
import _run

ID, VERSION, SOURCE = "narwal_robovac", 2, "narwal-us-robovac"     # v2: review-3 strict enums / identity / plausibility
CATEGORIES = {"robot-vacuums"}
ADAPTER = f"{ID}@{VERSION}"
HOST = "us.narwal.com"


def model_of(p):
    t = RV.text(p.get("title", ""))
    if p.get("product_type") not in ("Robot Vacuum Cleaner", "Vacuum Mop") or not RV.skus(p) or RV.NOISE_TITLE.search(t) or not re.search(r"(?i)robot", t):
        return None
    t = re.sub(r"(?i)^\s*narwal\s+", "", t)
    t = re.sub(r"(?i)\s*robot vacuum.*$", "", t).strip(" -–")
    return t if 2 <= len(t) <= 40 else None


def sku_norm(s):
    return s.split("_", 1)[0]


class NarwalRobovac:
    id, version, source_id, categories = ID, VERSION, SOURCE, CATEGORIES

    def __init__(self):
        self.store = C.BlobStore(SOURCE)

    def discover(self, checkpoint, net):
        ps, stop = RV.catalogue(net, HOST)
        refs = RV.refs_from_groups(SOURCE, HOST, RV.group(ps, model_of, lambda p: 0, conflicts := []))
        return C.Discovery(refs, stop is None, stop, {"products": len(ps), "models": len(refs), "identity_conflicts": conflicts})

    def fetch(self, ref, prior, net):
        return RV.fetch_bundle(self.store, ADAPTER, ref, net)

    def parse(self, snap, blobs, profile):
        return parse_bundle(snap, RV.read_bundle(blobs, snap))


CELL = re.compile(r'ndev-ax26-spec-row__cell--(label|value)">(.*?)<span class="ndev-text__content show-mb">', re.S)


def spec_rows(h):
    out, label = {}, None
    for kind, body in CELL.findall(h):
        t = RV.text(body)
        if kind == "label":
            label = t
        elif label:
            out.setdefault(label, t)
            label = None
    return out


def parse_bundle(snap, b):
    pr = C.ParseResult()
    pr.sources = [{"id": "s1", "url": snap.ref.url, "snapshot": snap.snapshot, "tier": "manufacturer", "title": "Narwal US product page " + snap.ref.key}]
    prods = b.get("products") or []
    canon = next((p for p in prods if snap.ref.url.endswith("/" + p.get("handle", ""))), prods[0] if prods else None)
    name = model_of(canon) if canon else None
    if not name:
        pr.absences.append({"key": "*", "reason": "no robot-vacuum product JSON in bundle", "source": "s1"})
        return pr
    fam = re.match(r"[A-Za-z]+", name)[0].upper()
    pr.identifiers.append(RV.ident("mfr_model", RV.plus(name), "model", "narwal", raw=name, series=fam))
    pr.aliases.append({"text": "Narwal " + name, "kind": "marketing_name"})
    prods, quarantined = RV.corroborate(prods, canon, model_of)
    RV.variant_idents(pr, prods, "narwal", RV.plus(name), sku_norm)
    rows = spec_rows(b.get("html") or "")

    def add(k, v, raw, label, cond=None):
        RV.add(pr, ADAPTER, snap, name, k, v, raw, label, cond)
    if not rows:
        pr.absences.append({"key": "*", "reason": "no Specifications block on the page", "source": "s1"})
    for lab, v in rows.items():
        l = lab.lower()
        if l == "maximum suction":
            add("clean.suction_pa", RV.pa(v), v, lab, {"claim_basis": "mfr_unstated"})
        elif l == "battery capacity":
            add("bat.capacity_mah", RV.mah(v), v, lab)
        elif l == "robot vacuum dimensions" and (d := RV.dims_mm(v)):
            d = RV.robot_dims(d)
            add("phys.robot_dimensions", d, v, lab); add("phys.robot_height_mm", RV.robot_height(d), v, lab)
        elif l == "base station dimensions":
            add("phys.dock_dimensions", RV.dims_mm(v), v, lab)
        elif l == "robot vacuum weight":
            add("phys.robot_weight_g", RV.robot_weight(RV.weight_g(v)), v, lab)
        elif l == "base station weight":
            add("phys.dock_weight_g", RV.weight_g(v), v, lab)
        elif l == "mop lifting" and re.search(r"\d", v):
            add("mop.lifting", True, v, lab); add("mop.lift_height_mm", RV.length_mm(v), v, lab)
        elif l == "navigation":
            add("nav.type", RV.navigation(v), v, lab)
        elif l == "mop extension":
            add("mop.extending", True, v, lab)
        elif l in ("dustbin capacity", "dust box capacity"):
            add("clean.dustbin_ml", RV.ml(v), v, lab)
    pr.fingerprints = {"raw": snap.snapshot, "labels": sorted(rows), "members": [p.get("handle") for p in prods], "quarantined_members": quarantined,
                       "unmapped": {k: v[:100] for k, v in rows.items() if k.lower() not in ("maximum suction", "battery capacity", "robot vacuum dimensions",
                                    "base station dimensions", "robot vacuum weight", "base station weight", "mop lifting", "navigation", "mop extension", "product name")}}
    return pr


if __name__ == "__main__":
    _run.main(NarwalRobovac())
