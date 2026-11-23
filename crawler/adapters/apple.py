#!/usr/bin/env python3
"""Apple Mac laptops adapter v1 (contract ARCHITECTURE 15.5). Source: support.apple.com (stable, server-rendered).

discover : support.apple.com/en-us/108052 (MacBook Pro) + 102869 (MacBook Air) identify pages -> per model: name, year, colors,
           Model Identifier(s) (Mac17,2), part-number FAMILIES (MDE04xx/A; xx = region), Tech Specs KB link.
           Models with year >= MIN_YEAR and a Tech Specs link become Refs (hints carry the index facts).
fetch    : the Tech Specs KB page (en-us/<id>).
parse    : pure. Specs = <h3> sections (Chip, Memory, Storage, Display, Battery and Power, ...) as literal line lists.
           Identifiers: mfr_model = Model Identifier (model level); mfr_sku = part-number pattern with xx -> LL (US
           retail: 'MDE04LL/A', value_raw keeps 'MDE04xx/A', package_level configuration).
Limits: Apple does NOT publish which part number is which chip/RAM/SSD/colour; that mapping needs the apple.com/shop
buy pages or retailer feeds. Tech specs list BTO option sets per chip, so claims are option lists, not one config.
"""
import html, re, sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import _contract as C
import _run

INDEXES = ["https://support.apple.com/en-us/108052", "https://support.apple.com/en-us/102869"]  # MacBook Pro, MacBook Air
MIN_YEAR = 2022
DELAY = 1.0
SECMAP = {"Chip": "cpu.model", "Memory": "mem.size", "Storage": "stor.size", "Display": "disp.size", "Battery and Power": "pwr.battery_wh",
          "Charging and Expansion": "port.usbc_list", "Camera": "in.webcam", "Wireless": "wl.wifi", "Size and Weight": "phys.weight",
          "Operating System": "sw.os", "Finish": "id.color", "Audio": "in.speakers", "Keyboard and Trackpad": "in.kb_layout"}
T = lambda s: re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", s)).replace("\xa0", " ")).strip()


def parse_index(t):
    out = []
    for blk in re.split(r'<h2 class="gb-header">', t)[1:]:
        name = T(blk.split("</h2>")[0])
        if "MacBook" not in name:
            continue
        def field(label):
            m = re.search(r"<b>\s*" + label + r"[^<]*</b>(.*?)</p>", blk, re.S)
            return T(m.group(1)) if m else ""
        link = re.search(r'href="(https://support.apple.com/en-us/\d+)"[^>]*>\s*Tech Specs', blk)
        yr = field("Year introduced")
        out.append({"name": name, "year": int(yr[:4]) if yr[:4].isdigit() else (int(re.findall(r"20\d\d", name)[-1]) if re.findall(r"20\d\d", name) else None), "colors": field("Colors"),
                    "identifiers": re.findall(r"[A-Za-z]+\d+,\d+", field("Model Identifier")),
                    "part_numbers": [x.strip() for x in field("Part Numbers").split(",") if x.strip()],
                    "techspecs": link.group(1) if link else None})
    return out


def parse_specs(t):
    secs = {}
    for m in re.finditer(r'<h3 class="gb-header[^"]*">(.*?)</h3>(.*?)(?=<h3 class="gb-header|<div class="gb-group group-wrap-layout|$)', t, re.S):
        name = re.sub(r"\d+$", "", T(m.group(1)))  # footnote digits glued to titles ('Storage1')
        lines = [T(x) for x in re.findall(r"<(?:p|li)[^>]*>(.*?)</(?:p|li)>", m.group(2), re.S)]
        secs[name] = [x for x in lines if x]
    return secs


class Apple:
    id, version, source_id, categories = "apple", 1, "apple-support", {"laptops"}

    def __init__(self):
        self.store = C.BlobStore(self.source_id)

    def discover(self, checkpoint, net):
        models = []
        for u in INDEXES:
            r = net.get(u, DELAY)
            if not hasattr(r, "status_code") or r.status_code != 200:
                return C.Discovery([], False, f"index {u} http {getattr(r, 'status_code', r)}", checkpoint or {})
            self.store.put(r.content, ".html")
            models += parse_index(r.text)
        refs = [C.Ref(self.source_id, m["techspecs"].rsplit("/", 1)[1], m["techspecs"], {"title": m["name"], **m})
                for m in models if m["techspecs"] and (m["year"] or 0) >= MIN_YEAR]
        return C.Discovery(refs, True, None, {"index_models": len(models), "with_techspecs_since_%d" % MIN_YEAR: len(refs)})

    def fetch(self, ref, prior, net):
        snap, _ = C.http_snapshot(self.store, ref, ref.url, DELAY, ".html", f"{self.id}@{self.version}")
        return snap

    def parse(self, snap, blobs, profile):
        t = blobs.read(snap.snapshot, ".html").decode("utf-8", "replace")
        h = snap.ref.hints
        pr = C.ParseResult(sources=[{"id": "s1", "url": snap.ref.url, "snapshot": snap.snapshot, "tier": "manufacturer", "title": "Apple Tech Specs " + h.get("title", "")}])
        obs = snap.fetched_at
        pr.aliases.append({"text": h.get("title", snap.ref.key), "kind": "marketing_name"})
        for mid in h.get("identifiers", []):
            pr.identifiers.append({"scheme": "mfr_model", "value": mid, "value_raw": mid, "issuer": "apple", "package_level": "model", "role": "key", "sources": ["s1"]})
        for pn in h.get("part_numbers", []):
            pr.identifiers.append({"scheme": "mfr_sku", "value": pn.replace("xx", "LL"), "value_raw": pn, "issuer": "apple", "market": "US",
                                   "package_level": "configuration", "role": "key", "sources": ["s1"]})
        key = h.get("identifiers", ["?"])[0]
        for sec, lines in parse_specs(t).items():
            k = SECMAP.get(sec)
            if k and lines:
                pr.claims.append(C.claim(key, k, lines, None, " | ".join(lines), "s1", f"{self.id}@{self.version}", "adapter", obs,
                                         locator={"selector": f"h3:{sec}", "model_identifier": key}))
        pr.fingerprints = {"sections": len(parse_specs(t)), "part_number_families": len(h.get("part_numbers", []))}
        if not pr.claims:
            pr.absences.append({"key": "cpu.model", "status": "not_published", "source": "s1", "checked_at": obs})
        return pr


if __name__ == "__main__":
    _run.main(Apple())
