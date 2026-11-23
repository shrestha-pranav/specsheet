"""Identity primitives for import.py (review P0-3, P1-7). Pure except IdRegistry (append-only file in data/_ids/, git).

Scoped key   = (scheme, issuer, normalised value, market, level). Matching only within the same scope; level = entity kind, so a
               package GTIN can never collapse a model/configuration, and a model key never matches a configuration.
GTIN         = digits only after removing spaces/hyphens; length 8/12/13/14 and a valid GS1 check digit, then zero-padded to 14.
               Invalid -> None (kept as raw alias, never a key). Never a merge key for model/configuration (package level only).
Normalisers  = scheme/issuer specific: mtm = uppercase, whitespace removed; mfr_model/mfr_sku = uppercase, whitespace removed, and
               '-', '.', '_', ' ' removed only for issuers whose identity.md says separators are cosmetic (power-strip brands);
               commas/slashes/# are kept (Apple `Mac14,5`, HP `#ABA`).
Conflicts    = an observation whose key identifiers hit two different existing entities is QUARANTINED (not attached, event logged)
               unless the decision ledger approved a merge of exactly those anchors.
Registry     = anchor -> id, append-only. IDs are reused on replay, never reminted; new ids are minted in sorted anchor order with a
               collision counter that skips every id ever issued or tombstoned.
Anchors v2   = "v2|category|level|scheme|issuer|value|market" (review 2 risk 4): the level is part of the durable anchor, so a model and a
               configuration with the same scheme/issuer/value/market can never share an id. Legacy v1 lines ("category|scheme|issuer|
               value|market", no level) are MIGRATED on load using the line's recorded `kind` (the level it was minted at), so every
               existing public id keeps resolving; a legacy anchor recorded under two different ids at the same level is AMBIGUOUS and
               is reported (`ambiguous`), never silently resolved. New lines are always written as v2.
Kind/rebind  = lookup() callers compare the registered kind (`kind_of`); add() never rebinds an anchor already bound to another id and
               records the attempt in `rebinds` for the importer's identity_conflicts table.
"""
import json, re, time
from pathlib import Path

LEVELS = {"family": 0, "model": 1, "configuration": 2, "package": 3, "listing": 4, "revision": 2}
SEPARATOR_COSMETIC = {"tripplite", "cyberpower", "belkin", "anker", "baseus", "ugreen", "byjasco", "furman", "austere", "apc"}


def gtin_valid(d):
    if not d.isdigit() or len(d) not in (8, 12, 13, 14):
        return False
    body, check = d[:-1], int(d[-1])
    s = sum(int(c) * (3 if i % 2 == 0 else 1) for i, c in enumerate(reversed(body)))
    return (10 - s % 10) % 10 == check


def norm_gtin(raw):
    d = re.sub(r"[\s-]", "", str(raw))
    if not gtin_valid(d):
        return None
    return d.zfill(14)


def norm_value(scheme, value, issuer=None):
    v = str(value).strip()
    if scheme == "gtin":
        return norm_gtin(v)
    if scheme == "mtm":
        return re.sub(r"\s+", "", v.upper())
    if scheme in ("mfr_model", "mfr_sku") or scheme.startswith("x_"):
        v = re.sub(r"\s+", "" if issuer in SEPARATOR_COSMETIC else " ", v.upper()).strip()
        if issuer in SEPARATOR_COSMETIC:
            v = re.sub(r"[-._]", "", v)
        return v or None
    return v.upper() or None   # retailer:*, fcc_id, ul_file: aliases only


def scope(scheme, issuer, market):
    """Which scope fields a scheme keys on. GTIN is global (GS1); mfr ids are issuer scoped; retailer ids store scoped."""
    if scheme == "gtin":
        return "GS1", None
    return issuer, market


def key(scheme, value, issuer, market, level):
    nv = norm_value(scheme, value, issuer)
    if nv is None:
        return None
    iss, mk = scope(scheme, issuer, market)
    return (scheme, iss, nv, mk, level)


ANCHOR_V = "v2"


def anchor(category, k):
    scheme, iss, nv, mk, level = k
    return "|".join([ANCHOR_V, category, level or "", scheme, iss or "", nv, mk or ""])


def legacy_anchor(a):
    """v2 anchor -> the v1 form (no level) it migrates from; v1 anchors are returned unchanged."""
    p = a.split("|")
    if p[0] == ANCHOR_V and len(p) == 7:
        return "|".join([p[1]] + p[3:])
    return a


def migrate_anchor(a, kind):
    """v1 anchor + the kind its registry line recorded -> v2 anchor. v2 anchors pass through."""
    if a.startswith(ANCHOR_V + "|"):
        return a
    p = a.split("|")
    return "|".join([ANCHOR_V, p[0], kind or ""] + p[1:])


def keystr(k):
    return "|".join("" if x is None else str(x) for x in k)


class IdRegistry:
    """data/_ids/registry.jsonl: {"id", "anchors": [...], "category", "kind", "at"} lines; later lines may add anchors to an id."""
    def __init__(self, path: Path, tombstones: Path | None = None, readonly=False):
        self.path, self.readonly = path, readonly
        self.by_anchor, self.ids, self.new = {}, set(), []
        self.kind_of, self.ambiguous, self.rebinds, self.migrated = {}, [], [], 0
        if path.exists():
            for ln in path.read_text().splitlines():
                if ln.strip():
                    r = json.loads(ln)
                    self.ids.add(r["id"])
                    self.kind_of.setdefault(r["id"], r.get("kind"))
                    for a0 in r["anchors"]:
                        a = migrate_anchor(a0, r.get("kind"))
                        self.migrated += a != a0
                        cur = self.by_anchor.setdefault(a, r["id"])
                        if cur != r["id"]:
                            self.ambiguous.append({"anchor": a, "ids": sorted({cur, r["id"]}), "legacy": a != a0})
        if tombstones and tombstones.exists():
            for ln in tombstones.read_text().splitlines():
                if ln.strip():
                    self.ids.add(json.loads(ln)["id"])

    def lookup(self, anchors):
        return sorted({self.by_anchor[a] for a in anchors if a in self.by_anchor})

    @staticmethod
    def fit(base, room=90):
        """entityId pattern ^[a-z0-9][a-z0-9-]{1,95}$: cut long slugs at a hyphen, leaving room for a -N counter."""
        base = re.sub(r"[^a-z0-9-]+", "-", base.lower()).strip("-") or "entity"
        if len(base) > room:
            base = base[:room].rsplit("-", 1)[0] if "-" in base[:room] else base[:room]
        return base

    def mint(self, base, anchors, category, kind, taken):
        base = self.fit(base)
        i, n = base, 2
        while i in self.ids or i in taken:
            i, n = f"{base}-{n}", n + 1
        self.ids.add(i)
        self.add(i, anchors, category, kind)
        return i

    def add(self, i, anchors, category, kind):
        for a in anchors:
            if a in self.by_anchor and self.by_anchor[a] != i:
                self.rebinds.append({"anchor": a, "bound": self.by_anchor[a], "attempted": i})
        new = [a for a in anchors if a not in self.by_anchor]
        if not new:
            return
        for a in new:
            self.by_anchor[a] = i
        self.kind_of.setdefault(i, kind)
        self.new.append({"id": i, "anchors": sorted(new), "category": category, "kind": kind, "at": time.strftime("%FT%TZ", time.gmtime())})

    def flush(self):
        if self.readonly or not self.new:
            return 0
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("a") as f:
            for r in self.new:
                f.write(json.dumps(r, sort_keys=True) + "\n")
        n = len(self.new); self.new = []
        return n
