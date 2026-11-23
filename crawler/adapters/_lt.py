"""Shared helpers for the round-3 laptop adapters (dell, surface, framework, samsung, razer). Pure functions, no network.

Conventions (same as asus.py): identifiers carry package_level model|configuration; claims carry the source literal in `raw`
and locator {"sku": ...} (configuration) or {"model_code": ...} (model) or {"family": ...} (the ref itself); multi-line cells
become lists. An identifier may carry `parent` = the model-level identifier value its configuration belongs to
(import.py do_generic uses it; adapters still never mint entity ids).
"""
import html, json, re, sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import _contract as C


def lines(s):
    """HTML fragment -> list of non-empty text lines (li/br/p/div boundaries are line breaks)."""
    s = re.sub(r"<sup[^>]*>.*?</sup>", "", s, flags=re.S)
    s = re.sub(r"</(li|p|div|tr)>|<br\s*/?>|<li[^>]*>", "\n", s)
    s = html.unescape(re.sub(r"<[^>]+>", " ", s)).replace("​", "").replace("\xa0", " ")
    return [re.sub(r"[ \t]+", " ", l).strip() for l in s.split("\n") if l.strip()]


def val(ls):
    return ls if len(ls) > 1 else (ls[0] if ls else "")


def ident(scheme, value, level, issuer, role="key", market="US", **extra):
    d = {"scheme": scheme, "value": value, "value_raw": value, "issuer": issuer, "market": market, "package_level": level, "role": role, "sources": ["s1"]}
    d.update(extra)
    return d


def source(snap, title):
    return {"id": "s1", "url": snap.ref.url, "snapshot": snap.snapshot, "tier": "manufacturer", "title": title}


def add(pr, adapter, snap, key, value, raw, loc_kind, loc_val, label, entity=None):
    if value in (None, "", []):
        return
    pr.claims.append(C.claim(entity or loc_val, key, value, None, raw if isinstance(raw, str) else " | ".join(raw), "s1", adapter, "adapter",
                             snap.fetched_at, locator={loc_kind: loc_val, "label": label}))


def mapped(pr, adapter, snap, labelmap, label, ls, loc_kind, loc_val):
    """Emit claims for one labelled cell. labelmap[label] = key | [keys] | callable(lines)->[(key, value)]."""
    m = labelmap.get(label)
    if m is None:
        pr.fingerprints.setdefault("unmapped_labels", {})[label] = " | ".join(ls)[:100]
        return
    if callable(m):
        for k, v in m(ls):
            add(pr, adapter, snap, k, v, ls, loc_kind, loc_val, label)
        return
    for k in ([m] if isinstance(m, str) else m):
        add(pr, adapter, snap, k, val(ls), ls, loc_kind, loc_val, label)


def weight_lines(ls):
    return [l for l in ls if re.search(r"\b(lb|lbs|kg|g)\b\.?", l) and re.search(r"[Ww]eight|^\d", l)]
