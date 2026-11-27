#!/usr/bin/env python3
"""PECRON portable power station adapter v1 (contract ARCHITECTURE 15.5), category power-stations, source pecron-us-stations (A2-bat r11).

Host     : www.pecron.com, PECRON's own US store (Shopify). robots.txt is the Shopify default ('User-agent: *' path disallows for cart/checkout/
           account only; /products allowed). Terms of service (/policies/terms-of-service, read 2026-11-26) have no robot / scraping / automated-
           access or reproduction clause.
discover : {base}/products.json (public Shopify catalogue) -> titles naming a 'Power Station'; solar-generator kits, expansion batteries,
           carts, cables and chargers are packages / accessories and are not discovered.
fetch    : inherited from shopify_powerbanks._Shop (product page HTML + /products/<handle>.json in one gzip JSON blob, 1 req/s, crawler UA).
parse    : pure. The maker's spec table(s): <tr><th>label</th><td>value</td></tr> rows (never marketing prose), mapped by the shared station row
           mapper _powerstation.emit_rows (via shopify_powerstations.parse_station). A table headed 'Model | <other PECRON model>' or naming
           another model in a label is skipped. In the table headed 'Model | <own model>', the unsectioned inverter rows 'Rated Power',
           'Peak Power' and 'Output Volts' are read as 'AC Output / ...' (the page title and bullets name the same figure the AC inverter rating,
           e.g. '1800W AC Pure Sine Wave Inverter (3000W Surge)'); every other label is passed through literally.
Identity : the one PECRON model token in the title ('E1000LFP', 'F3000LFP'), which must equal the stem of a unit-only variant SKU ('E1000LFP',
           'E300LFP-1' -> E300LFP). Bundle variants ('E1000LFP-200W', 'E1000LFP+EP3800-48V', '+Cart') are packages, never aliases.
"""
import re, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
import _powerbank as P
import _powerstation as PS
import _run
import shopify_powerstations as SS

ID, VERSION, SOURCE = "pecron_stations", 1, "pecron-us-stations"
MODEL = re.compile(r"\b([EF]\d{3,4}LFP)\b")
NOT_STATION = re.compile(r"solar generator|\bkit\b|expansion|battery\b|cart\b|cable|charger|box\b|bag\b|panel", re.I)


class PecronStations(SS._Station):
    id, source_id, base, brand, version = ID, SOURCE, "https://www.pecron.com", "pecron", VERSION

    def keep(self, p):
        t = p.get("title") or ""
        return bool(re.search(r"power station", t, re.I)) and not NOT_STATION.search(t)

    def identity(self, prod, page, blocks):
        title = P.clean(prod.get("title"))
        toks = set(MODEL.findall(title))
        unit, pkg = [], []
        for v in SS._variants(prod):
            s, vt = v["sku"].strip().upper(), v.get("title") or ""
            # unit = the bare model SKU; 'E3600LFP / Without Trolley' is the unit, '... / With Cart', '+PV300' are packages
            (unit if re.fullmatch(r"[EF]\d{3,4}LFP(?:-\d)?", s) and not re.search(r"\+|\bwith\b(?!out)|solar|panel|\d\s*W\b", vt, re.I) else pkg).append(v)
        stems = {re.sub(r"-\d$", "", v["sku"].strip().upper()) for v in unit}
        if len(toks) != 1:
            return None, f"{len(toks)} PECRON model tokens in the title", unit, pkg
        m = toks.pop()
        if stems != {m}:
            return None, f"title model {m} != unit-variant SKU stems {sorted(stems)}", unit, pkg
        return m, None, unit, pkg

    def blocks(self, page, prod, title):
        page = re.sub(r"<style.*?</style>|<script.*?</script>|<svg.*?</svg>", " ", page, flags=re.S)
        own = set(MODEL.findall(P.clean(prod.get("title"))))
        out = []
        for i, tb in enumerate(re.findall(r"<table[^>]*>(.*?)</table>", page, re.S)):
            rows = {}
            head = re.search(r"<tr[^>]*>\s*<th[^>]*>\s*(?:<[^>]+>\s*)*Model\s*(?:<[^>]+>\s*)*</th>\s*<th[^>]*>(.*?)</th>", tb, re.S)
            printed = set(MODEL.findall(P.clean(head[1]))) if head else set()
            if printed - own:
                continue                                   # a table headed by another PECRON model
            for lab, val in re.findall(r"<tr[^>]*>\s*<th[^>]*>((?:(?!</?th\b).)*?)</th>\s*<td[^>]*>(.*?)</td>", tb, re.S):
                lab = P.clean(lab).rstrip(":").strip()
                if not lab:
                    continue
                if head and re.fullmatch(r"(?i)rated power|peak power|output volts", lab):
                    lab = "AC Output / " + lab               # the 'Model <X>' table's inverter rows (title: '1800W AC Pure Sine Wave Inverter')
                v = PS.txt(val)
                if re.match(r"(?i)\s*(around|about|approx\.?|approximately|~)\s", v):
                    continue                                   # 'Around 28.7kg': an approximate figure is never an exact value
                rows.setdefault(lab, v)
            others = {t for k in rows for t in MODEL.findall(k)} - own
            if rows and not others:
                out.append((f"Specs {i + 1}" if i else "Specs", rows))
        return out, (None if out else "no spec table rows")


CLASSES = (PecronStations,)

if __name__ == "__main__":
    _run.main(PecronStations())
