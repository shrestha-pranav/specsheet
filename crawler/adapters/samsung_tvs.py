#!/usr/bin/env python3
"""Samsung US televisions adapter v1 (contract ARCHITECTURE 15.5), category tvs.

discover : https://www.samsung.com/us/vd-sitemap.xml (robots: the `User-agent: *` group disallows only /us/api/, search, dealer/epp paths;
           the 'Disallow: /us/' line belongs to the Yandex group) -> product pages /us/(tvs|lifestyle-tvs)/<line>/<slug>-sku-<modelcode>/.
           One Ref per model code (QN65S90FAFXZA). Commercial/hotel TVs are out of scope.
fetch    : the product page embeds the size group id ("groupId"); the spec API the buy page itself calls
           GET /us/gapi/v1/bridge/cacheable/bridge-data?data_type=Specs&store_type=B2C&group_id=<id>   (/us/gapi/ is not disallowed; same
           API samsung.py uses for laptops) returns fullSpecs[groupName -> specList[name, value]] for EVERY size of the line. Blob =
           {group_id, page_url, page_model_codes, specs}. Sibling sizes reuse the group bundle fetched earlier in the same run (no re-GET).
parse    : pure. The ref's own model code is picked from the group (absence if it is not in it); labelled rows -> _tv.emit().
Identity : mfr_model = the full Samsung model code incl. the US tail (QN65S90FAFXZA). ENERGY STAR certifies the code without 'XZA'
           (QN65S90FAF) and lists retailer designations (QN65S92FAF) as 'same as basic model except model designation': that statement is
           the corroboration used in research/tvs/identity.md, never a spec match.
"""
import json, re, sys, time
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
import _contract as C
import _tv as T
import _run

ID, VERSION, SOURCE = "samsung_tvs", 3, "samsung-us-tvs"
CATEGORIES = {"tvs"}
ADAPTER = f"{ID}@{VERSION}"
DELAY = 1.0
BASE = "https://www.samsung.com"
SITEMAP = BASE + "/us/vd-sitemap.xml"
API = BASE + "/us/gapi/v1/bridge/cacheable/bridge-data?data_type=Specs&store_type=B2C&group_id={g}"
URL = re.compile(r"<loc>(https://www\.samsung\.com/us/(?:tvs|lifestyle-tvs)/[a-z0-9-]+/[a-z0-9-]+-sku-([a-z0-9]+)/)</loc>")


class SamsungTvs:
    id, version, source_id, categories = ID, VERSION, SOURCE, CATEGORIES

    def __init__(self):
        self.store = C.BlobStore(SOURCE)
        self.groups = {}        # model code -> (sha, body) of a group bundle fetched in this run

    def discover(self, checkpoint, net):
        r = net.get(SITEMAP, DELAY)
        if not hasattr(r, "status_code") or r.status_code != 200:
            return C.Discovery([], False, f"sitemap {getattr(r, 'status_code', r)}", checkpoint or {})
        seen, refs = set(), []
        for url, code in URL.findall(r.text):
            code = code.upper()
            if code not in seen:
                seen.add(code)
                refs.append(C.Ref(SOURCE, code, url, {"line": url.split("/")[5]}))
        refs.sort(key=lambda x: x.key)
        return C.Discovery(refs, True, None, {"models": len(refs)})

    def fetch(self, ref, prior, net):
        now = time.strftime("%FT%TZ", time.gmtime())

        def snap(sha, st, url):
            s = C.Snapshot(sha, ref, st, now, url, {})
            self.store.append(s, ADAPTER, ".json")
            return s
        if ref.key in self.groups:
            sha, body = self.groups[ref.key]
            return snap(sha, 200, ref.url)
        page = net.get(ref.url, DELAY)
        if not hasattr(page, "status_code") or page.status_code != 200:
            return snap("sha256:", getattr(page, "status_code", page) or "breaker", ref.url)
        g = re.search(r'"groupId":"(\d+)"', page.text)
        if not g:
            return snap("sha256:", "no-groupId", ref.url)
        sp = net.get(API.format(g=g.group(1)), DELAY)
        if not hasattr(sp, "status_code") or sp.status_code != 200:
            return snap("sha256:", getattr(sp, "status_code", sp) or "breaker", ref.url)
        specs = sp.json()
        codes = sorted({m.upper() for m in re.findall(r'"modelCode":"([A-Z0-9]{8,20})"', page.text)})
        bundle = {"group_id": g.group(1), "page_url": ref.url, "page_model_codes": codes, "specs": specs}
        body = json.dumps(bundle, sort_keys=True).encode()
        sha = self.store.put(body, ".json")
        for m in specs if isinstance(specs, list) else []:
            if m.get("modelCode"):
                self.groups[m["modelCode"].upper()] = (sha, body)
        return snap(sha, 200, ref.url)

    def parse(self, snap, blobs, profile):
        b = json.loads(blobs.read(snap.snapshot, ".json"))
        pr, obs, code = C.ParseResult(), snap.fetched_at, snap.ref.key.upper()
        mdl = next((m for m in b.get("specs") or [] if str(m.get("modelCode", "")).upper() == code), None)
        if mdl is None:
            pr.absences.append({"key": "*", "reason": f"model code {code} not in spec group {b.get('group_id')}", "source": "s1"})
            return pr
        pr.sources = [{"id": "s1", "url": snap.ref.url, "label": f"Samsung US {code} (spec group {b.get('group_id')})", "source_id": SOURCE,
                       "tier": "manufacturer", "retrieved_at": obs, "snapshot": snap.snapshot}]
        pr.identifiers.append({"scheme": "mfr_model", "value": code, "value_raw": mdl["modelCode"], "issuer": "samsung", "market": "US",
                               "package_level": "model", "role": "key", "sources": ["s1"]})
        rows = {}
        for g in mdl.get("fullSpecs") or []:
            for s in g.get("specList") or []:
                if s.get("name"):
                    rows.setdefault(T.clean(s["name"]), T.clean(re.sub(r"<br\s*/?>", "; ", str(s.get("value") or ""))))
        slug = snap.ref.url.rstrip("/").rsplit("/", 1)[-1]
        pr.aliases.append({"text": slug, "kind": "retail_slug", "source": "s1", "observed_at": obs})
        used = T.emit(pr, "samsung", code, rows, ADAPTER, "feed", obs)
        pr.fingerprints = {"raw": snap.snapshot, "model": code, "group_id": b.get("group_id"), "group_size": len(b.get("specs") or []),
                           "terms": len(rows), "unmapped": {k: v for k, v in rows.items() if k not in used}}
        return pr


if __name__ == "__main__":
    _run.main(SamsungTvs())
