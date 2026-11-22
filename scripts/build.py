#!/usr/bin/env python3
"""Build the versioned, category-agnostic static dataset in docs/api/v1."""
import json
import re
import shutil
import subprocess
import tempfile
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data" / "gan-chargers"
OUT = ROOT / "docs"
API = OUT / "api" / "v1"


def field(key, label, group, kind, unit=None, facet=False, priority=100, options=None, column=False):
    result = dict(key=key, label=label, group=group, type=kind, unit=unit,
                  facet=facet, priority=priority, column=column)
    if options:
        result["options"] = options
    return result


CHARGER_FIELDS = [
    field("max_total_w", "Total output", "Power", "number", "W", True, 10, column=True),
    field("max_single_port_w", "Single-port output", "Power", "number", "W", True, 20, column=True),
    field("port_count", "Ports", "Ports & distribution", "number", None, True, 10, column=True),
    field("ports", "Port details", "Ports & distribution", "list", None, False, 20),
    field("port_sharing", "Power sharing", "Ports & distribution", "text", None, False, 30),
    field("usb_pd_version", "USB PD version", "Protocols", "enum", None, True, 10, column=True),
    field("pd_fixed_pdos", "Fixed PDOs", "Protocols", "text", None, False, 20),
    field("pps", "USB PD PPS", "Protocols", "bool", None, True, 30, column=True),
    field("pps_ranges", "PPS ranges", "Protocols", "text", "V / A", True, 40, column=True),
    field("pps_max_w", "Maximum PPS output", "Protocols", "number", "W", True, 50),
    field("epr_avs", "EPR / AVS", "Protocols", "bool", None, True, 60),
    field("other_protocols", "Other protocols", "Protocols", "list", None, True, 70),
    field("gan", "GaN", "Construction", "bool", None, True, 10),
    field("foldable_plug", "Foldable plug", "Construction", "bool", None, True, 20),
    field("plug_region", "Plug region", "Construction", "enum", None, True, 30, column=True),
    field("display", "Display", "Construction", "bool", None, True, 40),
    field("weight_g", "Weight", "Construction", "number", "g", True, 50),
    field("dimensions_mm", "Dimensions", "Construction", "text", "mm", False, 60),
    field("safety_certs", "Safety certifications", "Construction", "list", None, True, 70),
    field("cable_included", "Cable included", "Package", "text", None, False, 10),
    field("release_year", "Release year", "Catalogue", "number", None, True, 10),
    field("status", "Catalogue status", "Catalogue", "enum", None, True, 20),
    field("msrp_usd", "Recorded MSRP", "Historical price observations", "number", "USD", False, 10),
    field("typical_price_usd", "Recorded price", "Historical price observations", "number", "USD", False, 20),
]

STRIP_FIELDS = [
    field("outlet_count", "AC outlets", "Capacity", "number", None, True, 10, column=True),
    field("usb_port_count", "USB ports", "Capacity", "number", None, True, 20, column=True),
    field("max_load_w", "Rated load", "Capacity", "number", "W", True, 30, column=True),
    field("cord_length_m", "Cord length", "Form", "number", "m", True, 10),
    field("mounting", "Mounting", "Form", "enum", None, True, 20, ["none", "wall", "desk"], True),
    field("surge_protection", "Surge protection", "Protection", "bool", None, True, 10, column=True),
    field("joule_rating", "Surge rating", "Protection", "number", "J", True, 20),
    field("clamping_range", "Clamping range", "Protection", "range", "V", True, 30),
    field("indicator_lights", "Indicator lights", "Protection", "list", None, True, 40),
    field("notes_on_layout", "Outlet layout", "Form", "text", None, True, 30),
]


def slug(value):
    return re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")


def norm_model(value):
    return re.sub(r"[^A-Z0-9]", "", value.upper())


def source_object(url, number):
    host = urlparse(url).hostname or "Source"
    return {"id": f"s{number}", "url": url, "label": host.removeprefix("www."),
            "kind": "manufacturer" if host and any(x in host for x in ("anker", "ugreen", "baseus", "belkin", "satechi", "spigen", "iniu", "ecoflow", "cuktech")) else "other"}


def spec(value, status="known", sources=None, confidence=None, scope="record_context"):
    return {"value": value, "status": status, "sources": sources or [],
            "confidence": confidence, "source_scope": scope}


def charger_spec(record, key, sources):
    if key != "port_count" and key not in record:
        return spec(None, "not_yet_extracted", scope="none")
    if key == "port_count":
        value = len(record["ports"]) if record.get("ports") else None
    else:
        value = record.get(key)
    if value is None:
        return spec(None, "unknown", scope="none")
    # Empty legacy lists were often uncollected; do not imply verified absence.
    if isinstance(value, list) and not value:
        return spec(None, "unknown", scope="none")
    model = (record.get("model_numbers") or [""])[0]
    indices = record.get("field_sources", {}).get(key)
    if indices is not None:
        indices = indices if isinstance(indices, list) else [indices]
    valid_source_ids = {source["id"] for source in sources}
    field_ids = [f"s{i}" for i in (indices or []) if isinstance(i, int) and f"s{i}" in valid_source_ids]
    scope = "field" if field_ids else "record_context"
    conflict = ((model == "A2697" and key == "weight_g") or
                (model == "A2687" and key == "max_single_port_w") or
                (model == "A2683" and key == "cable_included") or
                (model == "CCGP150513" and key == "port_sharing") or
                (model == "CCGP110101" and key == "port_sharing") or
                (model.startswith("WCH018") and key == "dimensions_mm") or
                (model == "75752" and key == "port_count") or
                (model == "55549" and key == "ports") or
                (model == "40737" and key == "port_sharing") or
                (model == "AD1404U" and key == "weight_g") or
                (model.startswith("WCH014") and key == "max_single_port_w") or
                (model.startswith("WCH022") and key == "port_count") or
                (key == "cable_included" and isinstance(value, str) and "conflict" in value.lower()))
    if conflict:
        return spec(value, "conflicted", sources=field_ids, scope=scope)
    return spec(value, sources=field_ids, confidence=None, scope=scope)


def charger_records():
    raw = []
    for path in sorted(DATA.glob("*.json")):
        if path.name != "all.json":
            raw.extend(json.loads(path.read_text()))
    ids, lookup, records = set(), {}, []
    for r in raw:
        models = [m for m in r.get("model_numbers", []) if isinstance(m, str) and m.strip().lower() not in
                  {"unknown", "n/a", "na", "none", "null", "-", "tbd"}]
        base = slug(f"{r.get('brand', '')}-{models[0] if models else r.get('product_name', '')}")
        rid, n = base, 2
        while rid in ids:
            rid, n = f"{base}-{n}", n + 1
        ids.add(rid)
        for model in models:
            lookup.setdefault(norm_model(model), []).append(rid)
        # Legacy field_sources use indices in the original, ordered source array.
        sources = [source_object(u, i) for i, u in enumerate(r.get("sources", [])) if isinstance(u, str) and u.startswith(("https://", "http://"))]
        identifiers = [{"scheme": "brand_model", "value": m, "issuer": r.get("brand"),
                        "market": None, "package_level": "unverified"} for m in models]
        specs = {f["key"]: charger_spec(r, f["key"], sources) for f in CHARGER_FIELDS}
        record = {"id": rid, "category": "gan-chargers", "brand": r.get("brand", ""),
                  "name": r.get("product_name", ""), "family": r.get("series"),
                  "model": models[0] if models else None, "variant": None,
                  "identifiers": identifiers, "specs": specs, "media": [], "documents": [],
                  "marketing_terms": r.get("other_protocols") or [], "sources": sources,
                  "confidence": {"level": r.get("confidence", "unrated"), "scope": "legacy_record"},
                  "notes": r.get("notes") or "", "identity_caveat": "Pilot identity and package/configuration have not been independently resolved.",
                  "demo": False}
        if "AD1404U" in models:
            record["identity_caveat"] += " AD1404U and AD1404US are reported regional codes; their hardware equivalence is unverified."
        records.append(record)
    return records, lookup


DEMO_STRIPS = [
    ("demo-strip-4", "Demo Lab", "Desk strip — four outlet", "DS-04", {"outlet_count": 4, "usb_port_count": 2, "max_load_w": 1800, "cord_length_m": 1.5, "mounting": "desk", "surge_protection": True, "joule_rating": 600, "clamping_range": {"min": 330, "max": 400}, "indicator_lights": ["grounded", "protected"], "notes_on_layout": "Wide-spaced outer outlets"}),
    ("demo-strip-6", "Demo Lab", "Wall strip — six outlet", "WS-06", {"outlet_count": 6, "usb_port_count": 0, "max_load_w": 1875, "cord_length_m": 0, "mounting": "wall", "surge_protection": False, "joule_rating": None, "clamping_range": None, "indicator_lights": [], "notes_on_layout": "Two rows of three"}),
    ("demo-strip-8", "Demo Lab", "Workshop strip — eight outlet", "WK-08", {"outlet_count": 8, "usb_port_count": 4, "max_load_w": 1800, "cord_length_m": 3, "mounting": "none", "surge_protection": True, "joule_rating": 1200, "clamping_range": {"min": 300, "max": 420}, "indicator_lights": ["protected"], "notes_on_layout": "Spaced for adapters"}),
    ("demo-strip-3", "Demo Lab", "Travel strip — three outlet", "TV-03", {"outlet_count": 3, "usb_port_count": 2, "max_load_w": 1500, "cord_length_m": 1, "mounting": "none", "surge_protection": None, "joule_rating": None, "clamping_range": None, "indicator_lights": None, "notes_on_layout": "Compact layout"}),
]


def strip_records():
    result = []
    for rid, brand, name, model, raw in DEMO_STRIPS:
        specs = {}
        for f in STRIP_FIELDS:
            key = f["key"]
            if rid == "demo-strip-8" and key == "joule_rating":
                specs[key] = spec("1200 J or 900 J", "conflicted", scope="none")
            elif rid == "demo-strip-3" and key == "indicator_lights":
                specs[key] = spec(None, "not_yet_extracted", scope="none")
            elif rid == "demo-strip-6" and key in ("joule_rating", "clamping_range"):
                specs[key] = spec(None, "not_applicable", scope="none")
            elif raw[key] is None:
                specs[key] = spec(None, "unknown", scope="none")
            else:
                specs[key] = spec(raw[key], confidence="illustrative", scope="demo")
        result.append({"id": rid, "category": "power-strips-demo", "brand": brand, "name": name,
                       "family": "Fictional demonstration", "model": model, "variant": None,
                       "identifiers": [{"scheme": "demo_model", "value": model, "issuer": brand, "market": None, "package_level": "single"}],
                       "specs": specs, "media": [], "documents": [], "marketing_terms": [], "sources": [],
                       "confidence": {"level": "illustrative", "scope": "demo"},
                       "notes": "Fictional values for interface testing only. No product or source is claimed.",
                       "identity_caveat": "Fictional demo product; not a purchasable catalogue entry.", "demo": True})
    return result


class ScriptCollector(HTMLParser):
    def __init__(self):
        super().__init__()
        self.inside = False
        self.kind = None
        self.chunks = []
        self.scripts = []

    def handle_starttag(self, tag, attrs):
        if tag == "script":
            attrs = dict(attrs)
            self.inside = "src" not in attrs and attrs.get("type", "text/javascript") in ("text/javascript", "module", "")
            self.kind = attrs.get("type")
            self.chunks = []

    def handle_data(self, data):
        if self.inside:
            self.chunks.append(data)

    def handle_endtag(self, tag):
        if tag == "script" and self.inside:
            self.scripts.append(("".join(self.chunks), self.kind))
            self.inside = False


def check_js():
    checked = 0
    for path in OUT.rglob("*"):
        if path.is_file() and path.suffix in (".js", ".mjs"):
            checked += 1
            proc = subprocess.run(["node", "--check", str(path)], capture_output=True, text=True)
            if proc.returncode:
                raise SystemExit(f"JavaScript syntax error in {path}:\n{proc.stderr}")
        if path.is_file() and path.suffix == ".html":
            parser = ScriptCollector()
            parser.feed(path.read_text())
            for index, (script, kind) in enumerate(parser.scripts):
                with tempfile.NamedTemporaryFile("w", suffix=".mjs" if kind == "module" else ".js") as temp:
                    temp.write(script)
                    temp.flush()
                    checked += 1
                    proc = subprocess.run(["node", "--check", temp.name], capture_output=True, text=True)
                    if proc.returncode:
                        raise SystemExit(f"JavaScript syntax error in {path} inline script {index}:\n{proc.stderr}")
    return checked


def dump(path, obj):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=1, ensure_ascii=False) + "\n")


def stamp_build():
    """Cache-bust: browsers/Pages cache JSON ~10 min, and a stale products.json from an older
    schema crashed the category page (2026-11-22). Every asset and data URL carries the build id."""
    import hashlib, re as _re
    h = hashlib.sha256()
    for f in sorted(API.rglob("*.json")) + [OUT / "app.js", OUT / "styles.css"]:
        h.update(f.read_bytes())
    build = h.hexdigest()[:12]
    dump(API / "build.json", {"build": build})
    idx = OUT / "index.html"
    html = idx.read_text()
    html = _re.sub(r'href="styles\.css(\?v=[0-9a-f]+)?"', f'href="styles.css?v={build}"', html)
    html = _re.sub(r'src="app\.js(\?v=[0-9a-f]+)?"', f'src="app.js?v={build}"', html)
    html = _re.sub(r'<meta name="specsheet-build" content="[0-9a-f]*">\n?', '', html)
    html = html.replace('<meta charset="utf-8">', f'<meta charset="utf-8">\n  <meta name="specsheet-build" content="{build}">', 1)
    idx.write_text(html)
    return build


def main():
    chargers, lookup = charger_records()
    strips = strip_records()
    categories = [
        {"id": "gan-chargers", "name": "USB-C wall chargers", "description": "Cross-brand power, ports, and USB PD capability.", "count": len(chargers), "demo": False, "products": "gan-chargers/products.json", "fields": CHARGER_FIELDS},
        {"id": "power-strips-demo", "name": "Power strips", "description": "Fictional demonstration of a second category schema.", "count": len(strips), "demo": True, "products": "power-strips-demo/products.json", "fields": STRIP_FIELDS},
    ]
    if API.exists():
        shutil.rmtree(API)
    for category, records in ((categories[0], chargers), (categories[1], strips)):
        folder = API / category["id"]
        dump(folder / "schema.json", {"id": category["id"], "fields": category["fields"], "version": 1})
        index = []
        for record in records:
            dump(folder / "products" / f"{record['id']}.json", record)
            index.append({k: record[k] for k in ("id", "category", "brand", "name", "family", "model", "variant", "identifiers", "specs", "confidence", "demo")})
        dump(folder / "products.json", index)
    dump(API / "categories.json", categories)
    dump(API / "lookup" / "models.json", lookup)
    (API / "README.md").write_text("# Static dataset v1\n\n`categories.json` contains category schemas and counts. Each category has an index `products.json`, detail records under `products/<id>.json`, and `schema.json`. These are versioned static JSON files, not a dynamic API. Every specification has `{value,status,sources,confidence,source_scope}`. `status` is known, unknown, conflicted, not_yet_extracted, or not_applicable. Only known values are established for filtering. Source IDs refer to the detail record's `sources`; `record_context` means no direct field citation was supplied. Legacy charger records are unreviewed. The power-strip entries are fictional demo data.\n")
    (OUT / ".nojekyll").write_text("")
    stamp_build()
    checked = check_js()
    print(f"built {len(chargers)} charger and {len(strips)} demo products; checked {checked} JavaScript files/scripts")


if __name__ == "__main__":
    main()
