"""Category metadata loader (ARCHITECTURE 15.9). A category is `research/<cat>/spec-profile.yaml` (A1: specs, facets, identity levels)
plus an optional `research/<cat>/category.yaml` (A3: publication metadata the profile deliberately does not carry) plus adapter
registration in crawler/adapters/registry.py. Nothing else names a category. Root is overridable (SPECSHEET_ROOT) for fixture tests.

category.yaml keys (all optional; defaults in DEFAULTS):
  name, description        published label (default: profile label / description)
  columns: [spec keys]     table columns of the category page
  market_filter            {markets: [US], identifier_suffix: {mtm: US}}  a row is published only if one of its identifiers is in a market
                           or carries a suffix listed here; absent = publish everything
  variant_label            {specs: [keys]} joined with " / " | {entity_variant: {color: "colour {}", pack: "multi-pack ({})"}}
  features                 importer behaviours the category opts into: cpu_split, psref_split, strip_variants, stem_links
  stem                     {cut_at: ["/", "#"], strip_market_suffix: true}   model-string stem used by stem_links (proposals only)
  brand_aliases / brand_names   issuer string -> canonical brand id / display name (certifier sources spell brands their own way)
  skip_alias_pattern       regex; a certifier row whose listing text matches is out of category (e.g. laptops in the DisplayHDR table)
  revision_rows            true = publish kind=revision entities as index rows too (default: only in the model detail's revisions[] and as detail files)
  package_markets          {mtm: {suffix: US}}  package entities are minted only for these identifiers (others counted as regional)
  crosswalks               {file, compare_keys}  feature model_crosswalks: reviewed model-string pairs in data/decisions/<file> (scripts/xwalk.py)
  same_hardware            {source, extractor, transfer_keys, compare_keys}  feature same_hardware_relations (scripts/xwalk.py)
The profile's own `index_rows` {substantive_keys, certification_keys} decides default grid rows (substantive_keys() below, r8).
"""
import os, re
from pathlib import Path

import yaml

ROOT = Path(os.environ.get("SPECSHEET_ROOT") or Path(__file__).resolve().parent.parent)
DEFAULTS = {"columns": [], "market_filter": None, "variant_label": None, "features": [], "stem": None, "brand_aliases": {}, "brand_names": {},
            "skip_alias_pattern": None, "package_markets": None, "revision_rows": False}


def load(cat, root=None):
    root = Path(root or ROOT)
    prof = yaml.safe_load((root / "research" / cat / "spec-profile.yaml").read_text())
    cp = root / "research" / cat / "category.yaml"
    meta = dict(DEFAULTS, **(yaml.safe_load(cp.read_text()) or {} if cp.exists() else {}))
    meta.setdefault("name", prof.get("label") or cat)
    meta.setdefault("description", prof.get("description") or prof.get("scope") or "")
    meta["id"] = cat
    meta["profile"] = prof
    meta["skip_rx"] = re.compile(meta["skip_alias_pattern"], re.I) if meta.get("skip_alias_pattern") else None
    meta["substantive"] = substantive_keys(cat, prof)
    return meta


def substantive_keys(cat, prof):
    """r8: profile `index_rows` -> the set of substantive keys (None = no rule: every entity with a trusted value is a grid row). The two
    declared lists must partition the profile's spec keys exactly, so a new spec key cannot silently hide or show rows."""
    ir = prof.get("index_rows")
    if not ir:
        return None
    keys = {s["key"] for s in prof["specs"]}
    sub, cert = set(ir.get("substantive_keys") or []), set(ir.get("certification_keys") or [])
    if sub & cert or (sub | cert) != keys:
        raise SystemExit(f"research/{cat}/spec-profile.yaml index_rows: substantive_keys + certification_keys must partition the spec keys "
                         f"(both: {sorted(sub & cert)}, unknown: {sorted((sub | cert) - keys)}, missing: {sorted(keys - sub - cert)})")
    return sub


def passes_market_filter(meta, idents):
    f = meta.get("market_filter")
    if not f:
        return True
    suf = f.get("identifier_suffix") or {}
    return any((i.get("market") in (f.get("markets") or [])) or (i["scheme"] in suf and i["value"].endswith(suf[i["scheme"]])) for i in idents)
