"""A new category works through research/<cat>/{spec-profile,category}.yaml + source registration ONLY (review "Before category #3" item 5).

Builds a throwaway data root (SPECSHEET_ROOT) holding a made-up `widgets` category with two sources, runs the real scripts/import.py and
v1_publish.publish() against it, and checks the published result. No script, adapter module or constant in the repo knows about widgets.

  python3 -m unittest tests.test_new_category
"""
import json, os, shutil, subprocess, sys, tempfile, unittest
from pathlib import Path

CODE = Path(__file__).resolve().parent.parent
PROFILE = """
profile_format: specsheet.category-profile/1
category: widgets
version: 0.1.0
label: Widgets (profile label)
identity:
  levels: [family, model, revision, package]
  primary_key: manufacturer model number
groups:
  - {id: general, label: General}
specs:
  - {key: gen.size, label: Size, group: general, type: number, unit: in, tier: core, level: model,
     facet: {kind: range, bins: [10, 20]}, sources: [spec page]}
  - {key: gen.kind, label: Kind, group: general, type: enum, enum: [alpha, beta], tier: core, level: model, facet: true, sources: [spec page]}
  - {key: cert.tier, label: Certification tier, group: general, type: enum, enum: [gold, silver], tier: core, level: model, facet: true, sources: [cert list]}
"""
CATEGORY = """
name: Widgets
description: Fixture category.
columns: [gen.size, gen.kind, cert.tier]
features: [stem_links]
stem: {cut_at: ["/"], strip_market_suffix: true}
variant_label: {specs: [gen.size, gen.kind]}
market_filter: {markets: [US]}
"""
POLICIES = """
format: specsheet.policies/1
claim_policies:
  - id: claim/widgetco-spec@1
    since: "2026-11-23"
    rationale: fixture
    match: {extractors: [widgetco@1], source_ids: [widgetco-us], kinds: [official], tiers: [manufacturer], statuses: [known], require_normalized: true}
  - id: claim/widget-cert@1
    since: "2026-11-23"
    rationale: fixture
    match: {extractors: [widgetcert@1], source_ids: [widget-cert], kinds: [official], tiers: [certifier], keys: [cert.tier], statuses: [known]}
relation_policies:
  - {id: rel/fixture-adapter@1, since: "2026-11-23", rationale: fixture, methods: ["adapter:*"], types: [variant_of, package_of]}
"""


def claim(key, value, ext, stage="table", unit=None):
    return {"id": f"c_{key}_{value}", "key": key, "status": "known", "kind": "official", "unit": unit, "raw": f"{key}={value}", "source": "s1",
            "method": {"stage": stage, "extractor": ext}, "observed_at": "2026-11-23T00:00:00Z", "value": value, "locator": {}}


def rclaim(key, value, ext, rev):
    return dict(claim(key, value, ext), id=f"c_{key}_{value}_{rev}", locator={"hw_rev": rev})


def parsed(model, market, tier, claims, ext, extra_ids=(), aliases=(), extra_claims=()):
    ids = [{"scheme": "mfr_model", "value": model, "value_raw": model, "issuer": "widgetco", "market": market, "package_level": "model", "role": "key", "sources": ["s1"]}]
    return {"identifiers": ids + list(extra_ids), "aliases": list(aliases), "claims": [claim(k, v, ext, unit=u) for k, v, u in claims] + list(extra_claims),
            "media": [], "documents": [], "absences": [], "links": [], "fingerprints": {},
            "sources": [{"id": "s1", "url": f"https://example.invalid/{model}", "label": "page", "tier": tier}]}


class NewCategory(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = Path(tempfile.mkdtemp(prefix="specsheet-fixture-"))
        t = cls.tmp
        os.symlink(CODE / "schemas", t / "schemas")
        (t / "research" / "widgets").mkdir(parents=True)
        (t / "research" / "widgets" / "spec-profile.yaml").write_text(PROFILE)
        (t / "research" / "widgets" / "category.yaml").write_text(CATEGORY)
        (t / "data" / "decisions").mkdir(parents=True)
        (t / "data" / "decisions" / "policies.yaml").write_text(POLICIES)
        (t / "data" / "decisions" / "ledger.jsonl").write_text("")
        (t / "sources.extra.json").write_text(json.dumps({
            "widgetco-us": {"brand": "widgetco", "brand_name": "WidgetCo", "category": "widgets", "module": "none", "importer": "model"},
            "widget-cert": {"brand": "certbody", "brand_name": "Cert Body", "category": "widgets", "module": "none", "importer": "model"}}))
        rev = {"scheme": "hw_rev", "value": "B", "value_raw": "B", "issuer": "widgetco", "package_level": "revision", "role": "key", "sources": ["s1"]}
        # W-500 sells under two hardware versions (TP-Link style): model-scoped identifier value + revision_label; claims address a revision by locator
        v = lambda lab: {"scheme": "hw_version", "value": f"W-500 {lab}", "value_raw": f"W-500 {lab}", "issuer": "widgetco", "package_level": "revision", "role": "key",
                         "sources": ["s1"], "revision_label": lab}
        rows = {
            "widgetco-us": [parsed("W-500", "US", "manufacturer", [("gen.size", 12, "in"), ("gen.kind", "alpha", None)], "widgetco@1", extra_ids=[v("V1"), v("V2")],
                                   extra_claims=[rclaim("gen.size", 14, "widgetco@1", "V2"), rclaim("gen.kind", "beta", "widgetco@1", "V2")]),
                            parsed("W-100", "US", "manufacturer", [("gen.size", 12, "in"), ("gen.kind", "alpha", None)], "widgetco@1", aliases=[{"text": "Widget One", "kind": "marketing_name"}]),
                            parsed("W-200-B", "US", "manufacturer", [("gen.size", 24, "in"), ("gen.kind", "beta", None)], "widgetco@1", extra_ids=[rev]),
                            parsed("W-300", "EU", "manufacturer", [("gen.size", 15, "in")], "widgetco@1"),                      # outside market_filter
                            parsed("W-400", "US", "manufacturer", [("gen.kind", "alpha", None)], "unaudited@1")],               # no policy: preview only
            "widget-cert": [parsed("w-100", None, "certifier", [("cert.tier", "gold", None)], "widgetcert@1"),                   # exact normalised match of W-100
                            parsed("W-200", "US", "certifier", [("cert.tier", "silver", None)], "widgetcert@1")],               # stem match of W-200-B: proposal only
        }
        for src, items in rows.items():
            d = t / "raw" / src
            (d / "parsed").mkdir(parents=True)
            log = []
            for n, pr in enumerate(items):
                key = f"r{n}"
                (d / "parsed" / f"{key}.json").write_text(json.dumps(pr))
                log.append({"snapshot": f"sha256:{n + (0 if src == 'widgetco-us' else 100):064x}", "ref": key, "url": pr["sources"][0]["url"], "final_url": pr["sources"][0]["url"], "status": 200,
                            "fetched_at": "2026-11-23T00:00:00Z", "etag": None, "last_modified": None, "adapter": "fixture@1", "blob": f"blobs/{n:064x}.json"})
            (d / "snapshots.jsonl").write_text("".join(json.dumps(x) + "\n" for x in log))
        env = dict(os.environ, SPECSHEET_ROOT=str(t))
        r = subprocess.run([sys.executable, "-I", str(CODE / "scripts" / "import.py"), "--data", str(t / "data")], env=env, capture_output=True, text=True)
        assert r.returncode == 0, r.stderr[-2000:]
        cls.imp = json.loads(r.stdout[r.stdout.index("{"):])
        code = "import sys, json; sys.path.insert(0, %r); import v1_publish as P; from pathlib import Path; st = {}; cats, man, rel = P.publish(Path(%r), st); print(json.dumps([cats, st]))" % (str(CODE / "scripts"), str(t / "api"))
        r = subprocess.run([sys.executable, "-I", "-c", code], env=env, capture_output=True, text=True)
        assert r.returncode == 0, r.stderr[-3000:]
        cls.cats, cls.stats = json.loads(r.stdout.splitlines()[-1])
        cls.api = t / "api"

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.tmp, ignore_errors=True)

    def test_published_from_profile_and_category_yaml(self):
        (c,) = self.cats
        self.assertEqual((c["id"], c["name"], c["description"]), ("widgets", "Widgets", "Fixture category."))
        sch = json.loads((self.api / "widgets" / "schema.json").read_text())
        self.assertEqual([f["key"] for f in sch["fields"] if f["column"]], ["gen.size", "gen.kind", "cert.tier"])
        facets = json.loads((self.api / "widgets" / "facets.json").read_text())
        self.assertEqual(set(facets), {"gen.size", "gen.kind", "cert.tier"})

    def test_trusted_preview_and_market_filter(self):
        rows = {r["id"]: r for r in json.loads((self.api / "widgets" / "index.json").read_text())}
        self.assertEqual(set(rows), {"widgetco-w-100", "widgetco-w-200-b", "widgetco-w-200", "widgetco-w-500"}, rows.keys())   # no revision rows by default
        self.assertEqual(rows["widgetco-w-100"]["v"], {"gen.size": 12, "gen.kind": "alpha", "cert.tier": "gold"})     # one entity, two sources
        self.assertEqual(rows["widgetco-w-100"]["variant_label"], "12 in / alpha")
        prev = {r["id"] for r in json.loads((self.api / "preview" / "widgets" / "index.json").read_text())}
        self.assertIn("widgetco-w-400", prev)                  # unaudited extractor -> candidate -> preview only
        self.assertNotIn("widgetco-w-400", rows)
        self.assertNotIn("widgetco-w-300", rows)               # EU identifier fails market_filter

    def test_policy_ids_and_cross_source_identity(self):
        d = json.loads((self.api / "widgets" / "products" / "widgetco-w-100.json").read_text())
        self.assertEqual({s["url"] for s in d["sources"]}, {"https://example.invalid/W-100", "https://example.invalid/w-100"})
        self.assertEqual(self.imp["claims_review"]["widgets"]["accepted"], 11)
        # stem match is a proposal, not a merge: W-200 (cert) vs W-200-B (maker) stay two entities linked by a proposed possible_match
        rels = [r for p in ("widgetco-w-200", "widgetco-w-200-b") for r in json.loads((self.api / "widgets" / "products" / f"{p}.json").read_text())["relations"]]
        self.assertEqual(rels, [], "proposed links never appear in the trusted dataset")
        self.assertEqual(self.imp["identity"]["relations"].get("proposed:stem"), 1)

    def test_revision_identifier_becomes_a_child_entity(self):
        self.assertIn("revision", self.imp["entities"]["widgets"])
        kinds = {json.loads(f.read_text())["id"]: json.loads(f.read_text())["kind"] for f in (self.api / "widgets" / "products").glob("*.json")}
        self.assertEqual(sorted(i for i, k in kinds.items() if k == "revision"), ["widgetco-w-200-b-b", "widgetco-w-500-v1", "widgetco-w-500-v2"], kinds)

    def test_revisions_published_in_model_detail(self):
        m = json.loads((self.api / "widgets" / "products" / "widgetco-w-500.json").read_text())
        self.assertEqual(m["children"], ["widgetco-w-500-v1", "widgetco-w-500-v2"])
        self.assertEqual([(r["id"], r["label"], r["name"]) for r in m["revisions"]],
                         [("widgetco-w-500-v1", "V1", "W-500 (rev V1)"), ("widgetco-w-500-v2", "V2", "W-500 (rev V2)")])
        v1, v2 = m["revisions"]
        self.assertEqual((v1["specs"], v1["differs"], v1["sources"]), ({}, [], []), "V1 states nothing of its own: it inherits the model's values")
        self.assertEqual({k: s["value"] for k, s in v2["specs"].items()}, {"gen.size": 14, "gen.kind": "beta"})
        self.assertEqual(v2["differs"], ["gen.kind", "gen.size"])
        self.assertTrue(all(s["id"] == "s1" for s in v2["sources"]) and v2["sources"])
        self.assertEqual(m["specs"]["gen.size"]["value"], 12, "model keeps its own value; revision values never leak upward")
        d = json.loads((self.api / "widgets" / "products" / "widgetco-w-500-v2.json").read_text())
        self.assertEqual((d["kind"], d["specs"]["gen.size"]["value"], d["relations"][0]["type"], d["relations"][0]["target"]), ("revision", 14, "variant_of", "widgetco-w-500"))
        d1 = json.loads((self.api / "widgets" / "products" / "widgetco-w-500-v1.json").read_text())
        self.assertEqual(d1["specs"]["gen.size"]["inherited_from"], "widgetco-w-500")
        self.assertNotIn("revisions", d)
        # an unlabelled hw_rev revision (monitor style) still lists under its model with the identifier value as label
        m2 = json.loads((self.api / "widgets" / "products" / "widgetco-w-200-b.json").read_text())
        self.assertEqual([r["label"] for r in m2["revisions"]], ["B"])


if __name__ == "__main__":
    unittest.main()
