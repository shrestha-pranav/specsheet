"""Adversarial fixtures for reviews/2026-11-23-astra-review-2.md (risks 1-5, next steps 1-3). Fast, no network, no real raw/ needed.

  python3 -m unittest tests.test_adversarial

1 governance   policy meaning frozen per id (lock), explicit allowlists, exact relation rules pinned to parser versions, approval fields,
               parser drift; snapshot identity independent of parser version; parsed-cache invalidation on parser edits / --reparse
2 semantics    assertions = value + qualifier + basis conditions + measurement mode, order independent; "up to" never implies a cache state;
               ENERGY STAR power basis / DisplayHDR CTS version as basis conditions
3 revisions    all-revisions vs unspecified/default revision; contradictory revisions; no upward or sideways leakage
4 identity     level in durable anchors (+ legacy migration keeping ids, ambiguity flagged), same identifier across levels and markets,
               explicit cross-market scope, stem links never transmit trust
5 hygiene      HTML entities decoded at import; release size budget evaluation
"""
import copy, importlib, json, os, subprocess, sys, tempfile, textwrap, unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts")); sys.path.insert(0, str(ROOT / "crawler" / "adapters"))
import identity as I  # noqa: E402
import normalize as N  # noqa: E402
import resolve as R  # noqa: E402
import decisions as D  # noqa: E402
import release_manifest as RM  # noqa: E402
imp = importlib.import_module("import")
import v1_publish as P  # noqa: E402
import yaml  # noqa: E402


def write_policies(d, doc, ledger=""):
    (d / "decisions").mkdir(parents=True, exist_ok=True)
    (d / "decisions" / "policies.yaml").write_text(yaml.safe_dump(doc, sort_keys=False))
    (d / "decisions" / "ledger.jsonl").write_text(ledger)


CLAIM_POL = {"id": "claim/x@1", "since": "2026-11-23", "rationale": "fixture", "audit": {"by": "t", "at": "2026-11-23", "evidence": "e", "parsers": {"xa@1": "sha256:aaa"}},
             "approval": {"state": "approved", "by": "fixture-approver", "at": "2026-11-26"},     # 2026-11-26 gate: only approved policies auto-accept
             "match": {"extractors": ["xa@1"], "source_ids": ["xs"], "kinds": ["official"], "statuses": ["known"], "keys": {"xs": ["gen.a"]}}}
REL_POL = {"id": "rel/x@1", "since": "2026-11-23", "rationale": "fixture", "approval": {"state": "approved", "by": "fixture-approver", "at": "2026-11-26"}, "rules": [{"method": "adapter:xs", "types": ["configuration_of"], "parsers": ["xa@1"]}]}


class Governance(unittest.TestCase):
    def setUp(self):
        self.d = Path(tempfile.mkdtemp())

    def dec(self, claim=CLAIM_POL, rel=REL_POL, retired=()):
        write_policies(self.d, {"format": "specsheet.policies/2", "claim_policies": [claim], "relation_policies": [rel], "retired_policies": list(retired)})
        return D.Decisions(self.d)

    def test_policy_meaning_frozen_per_id(self):
        new, _ = self.dec().check_lock()
        self.assertEqual(sorted(new), ["claim/x@1", "rel/x@1"])
        widened = copy.deepcopy(CLAIM_POL); widened["match"]["keys"]["xs"].append("gen.b")
        with self.assertRaises(SystemExit) as cm:
            self.dec(claim=widened).check_lock()
        self.assertIn("changed under the same id", str(cm.exception))
        approved = copy.deepcopy(CLAIM_POL); approved["approval"] = {"state": "approved", "by": "pranav", "at": "2026-11-24"}
        self.assertEqual(self.dec(claim=approved).check_lock()[0], [], "approving does not change the hash")
        renamed = dict(widened, id="claim/x@2")
        with self.assertRaises(SystemExit) as cm:      # @1 vanished instead of being retired
            self.dec(claim=renamed).check_lock()
        self.assertIn("disappeared", str(cm.exception))
        retired = dict(CLAIM_POL, retired={"at": "2026-11-24", "superseded_by": "claim/x@2"})
        new, _ = self.dec(claim=renamed, retired=[retired]).check_lock()
        self.assertEqual(new, ["claim/x@2"])

    def test_retired_policies_never_apply(self):
        dec = self.dec(claim=dict(CLAIM_POL, id="claim/x@2"), retired=[dict(CLAIM_POL, id="claim/old@1", match=dict(CLAIM_POL["match"], keys={"xs": ["gen.z"]}))])
        ctx = {"source_id": "xs", "extractor": "xa@1", "key": "gen.z", "kind": "official", "status": "known", "normalized": True}
        self.assertEqual(dec.claim_state("c1", ctx), ("candidate", None))

    def test_broad_policies_rejected(self):
        broad = copy.deepcopy(CLAIM_POL); del broad["match"]["keys"]; broad["match"]["spec_types"] = ["number"]
        with self.assertRaises(SystemExit):
            self.dec(claim=broad)
        glob = {"id": "rel/g@1", "since": "x", "rationale": "x", "methods": ["adapter:*"], "types": ["variant_of"]}
        with self.assertRaises(SystemExit):
            self.dec(rel=glob)
        globrule = dict(REL_POL, rules=[{"method": "adapter:*", "types": ["variant_of"], "parsers": ["xa@1"]}])
        with self.assertRaises(SystemExit):
            self.dec(rel=globrule)

    def test_allowlist_is_per_source(self):
        dec = self.dec()
        ctx = {"source_id": "xs", "extractor": "xa@1", "key": "gen.a", "kind": "official", "status": "known", "normalized": True}
        self.assertEqual(dec.claim_state("c1", ctx)[0], "accepted")
        self.assertEqual(dec.claim_state("c1", dict(ctx, key="gen.b"))[0], "candidate", "unlisted key")
        self.assertEqual(dec.claim_state("c1", dict(ctx, extractor="xa@2"))[0], "candidate", "parser bump needs a new policy")
        self.assertEqual(dec.claim_state("c1", dict(ctx, source_id="other"))[0], "candidate")

    def test_relation_rules_pinned_to_method_and_parser(self):
        dec = self.dec()
        self.assertEqual(dec.relation_state("a", "configuration_of", "b", "adapter:xs", "xa@1")[0], "approved")
        self.assertEqual(dec.relation_state("a", "configuration_of", "b", "adapter:xs", "xa@2")[0], "proposed", "new parser version inherits nothing")
        self.assertEqual(dec.relation_state("a", "configuration_of", "b", "adapter:xs-new", "xa@1")[0], "proposed", "new adapter by naming alone")
        self.assertEqual(dec.relation_state("a", "variant_of", "b", "adapter:xs", "xa@1")[0], "proposed", "type not listed")
        stem = dict(REL_POL, rules=[{"method": "stem:lg", "types": ["possible_match"], "parsers": ["xa@1"]}])
        self.assertEqual(self.dec(rel=stem).relation_state("a", "possible_match", "b", "stem:lg", None)[0], "proposed",
                         "stem links carry no parser, so no rule can approve them (and never transmit certification)")

    def test_parser_drift_and_approval_states(self):
        dec = self.dec()
        self.assertEqual(dec.parser_drift({"xa@1": "sha256:aaa"}), [])
        self.assertEqual(dec.parser_drift({"xa@1": "sha256:bbb"}), [("claim/x@1", "xa@1", "sha256:aaa", "sha256:bbb")])
        self.assertEqual(dec.approvals(), {"claim/x@1": "approved", "rel/x@1": "approved"})
        bare = {k: v for k, v in REL_POL.items() if k != "approval"}
        self.assertEqual(self.dec(rel=bare).approvals()["rel/x@1"], "missing")

    def test_repo_policies_pass_their_own_governance(self):
        dec = D.Decisions(ROOT / "data")
        self.assertEqual(dec.check_lock(write=False)[0], [], "every active/retired policy is locked")
        # Retired policies (any version) must be locked (checked above), not also active, and either
        # superseded by a higher active version of the same family or explicitly marked `retired:`.
        # (Was `all retired are @1`, an r4 snapshot; user approved retiring @2+ on 2026-11-23.)
        fam = lambda pid: (pid.rsplit("@", 1)[0], int(pid.rsplit("@", 1)[1]))
        active = [p["id"] for p in dec.claim_policies + dec.relation_policies]
        for p in dec.retired_policies:
            self.assertNotIn(p["id"], active, f"{p['id']} is both active and retired")
            f, v = fam(p["id"])
            newer = [a for a in active if fam(a)[0] == f and fam(a)[1] > v]
            self.assertTrue(newer or p.get("retired"), f"{p['id']} retired without successor or reason")
        self.assertTrue(any(fam(p["id"])[0] == "claim/mfr-routers-structured" and fam(p["id"])[1] >= 2 for p in dec.claim_policies),
                        "edited router policy re-issued (@2 or a later reissue)")
        import registry
        cur = {v["parser"]: v["fingerprint"] for v in (registry.parser_info(s) for s in registry.SOURCES) if v["parser"]}
        self.assertEqual(dec.parser_drift(cur), [], "audited parser fingerprints match the code")


ADAPTER_V1 = '''
import _contract as C
from dataclasses import dataclass, field
class Fx:
    id, version, source_id = "fxp", {ver}, "fx"
    def parse(self, snap, blobs, profile):
        body = blobs.read(snap.snapshot, ".json").decode()
        return C.ParseResult(claims=[{{"key": "gen.a", "value": body.strip() + "{suffix}"}}])
'''


class SnapshotAndCache(unittest.TestCase):
    """Run in a subprocess: _contract.ROOT is read from SPECSHEET_ROOT at import time."""

    def run_py(self, root, code):
        env = dict(os.environ, SPECSHEET_ROOT=str(root))
        p = subprocess.run([sys.executable, "-I", "-c", code], env=env, capture_output=True, text=True)
        self.assertEqual(p.returncode, 0, p.stderr[-2000:])
        return json.loads(p.stdout.splitlines()[-1])

    def test_parser_bump_reparses_existing_snapshots_and_cache_follows_code(self):
        root = Path(tempfile.mkdtemp()); ad = Path(tempfile.mkdtemp())
        (root / "raw" / "fx" / "blobs").mkdir(parents=True)
        (root / "raw" / "fx" / "blobs" / ("a" * 64 + ".json")).write_text("v")
        (root / "raw" / "fx" / "snapshots.jsonl").write_text(json.dumps({"snapshot": "sha256:" + "a" * 64, "ref": "k1", "url": "u", "final_url": "u", "status": 200,
                                                                          "fetched_at": "t", "adapter": "fxp@1", "blob": "blobs/" + "a" * 64 + ".json"}) + "\n")
        (root / "raw" / "fx" / "parsed").mkdir()
        (root / "raw" / "fx" / "parsed" / "k1.json").write_text(json.dumps({"claims": [{"key": "gen.a", "value": "STALE-LEGACY"}]}))   # legacy bare cache
        (root / "sources.extra.json").write_text(json.dumps({"fx": {"brand": "fx", "brand_name": "Fx", "category": "c", "module": "fxmod", "importer": "strip"}}))
        code = textwrap.dedent(f'''
            import sys, json, importlib
            sys.path.insert(0, {str(ad)!r}); sys.path.insert(0, {str(ROOT / "crawler" / "adapters")!r})
            import registry as R
            R.ADAPTERS = __import__("pathlib").Path({str(ad)!r})
            st = {{}}
            out = [(r["adapter"], pr["claims"][0]["value"]) for r, pr, _ in R.iter_observations("fx", reparse={{reparse}}, stats=st)]
            print(json.dumps([out, st, R.parser_info("fx")]))''')
        def run(ver, suffix, reparse=False):
            (ad / "fxmod.py").write_text(ADAPTER_V1.format(ver=ver, suffix=suffix))
            return self.run_py(root, code.replace("{reparse}", str(reparse)))
        out, st, info = run(1, "")
        self.assertEqual(out, [["fxp@1", "v"]], "legacy cache (unknown parser) is a miss, never trusted")
        self.assertEqual(st, {"cache_misses": 1})
        out, st, _ = run(1, "")
        self.assertEqual(st, {"cache_hits": 1})
        out, st, info2 = run(1, "-edited")       # parser edit WITHOUT a version bump (the SSD hazard)
        self.assertEqual((out, st), ([["fxp@1", "v-edited"]], {"cache_misses": 1}))
        self.assertNotEqual(info["fingerprint"], info2["fingerprint"])
        out, st, info3 = run(2, "-v2")          # version bump: the @1 snapshot is re-parsed, not orphaned
        self.assertEqual((out, st, info3["parser"]), ([["fxp@1", "v-v2"]], {"cache_misses": 1}, "fxp@2"))
        out, st, _ = run(2, "-v2", reparse=True)
        self.assertEqual(st, {"cache_misses": 1}, "--reparse re-parses and rewrites the cache")
        cached = json.loads((root / "raw" / "fx" / "parsed" / "k1.json").read_text())
        self.assertEqual((cached["parser"], cached["snapshot"], cached["result"]["claims"][0]["value"]), ("fxp@2", "sha256:" + "a" * 64, "v-v2"))

    def test_compatible_selects_by_fetcher_id_not_version(self):
        import registry
        cls = type("A", (), {"id": "fxp", "version": 3})
        self.assertTrue(registry.compatible(cls, {"adapter": "fxp@1"}))
        self.assertFalse(registry.compatible(cls, {"adapter": "fxp-page@1"}))
        cls.snapshot_formats = ["fxp@2"]
        self.assertFalse(registry.compatible(cls, {"adapter": "fxp@1"}))


# ----------------------------------------------------------------------------------------------- semantics
def C(i, v, q=None, cond=None, mmode=None, kind="official", src="s1", disp=None):
    nx = {k: x for k, x in (("qualifier", q), ("display", disp)) if x}
    return {"id": i, "status": "known", "kind": kind, "cond": cond or {}, "mmode": mmode, "ok": True, "value": v, "raw": str(v), "nx": nx, "source": src}


def both_orders(test, spec, cs):
    a, b = R.resolve_spec(spec, cs, []), R.resolve_spec(spec, list(reversed(cs)), [])
    test.assertEqual(a, b, "resolution depends on claim order")
    return a


class Semantics(unittest.TestCase):
    spec = {"key": "perf.seq_read", "unit": "MB/s"}

    def test_exact_vs_up_to_same_number_is_not_one_value(self):
        r = both_orders(self, self.spec, [C("c1", 100), C("c2", 100, q="up_to", src="s2")])
        self.assertEqual(r["status"], "conflicted")
        self.assertEqual(sorted((a["value"], a.get("qualifier") or "") for a in r["alternatives"]), [(100, ""), (100, "up_to")])
        self.assertTrue(all(a["claims"] and a["sources"] for a in r["alternatives"]), "provenance per branch")

    def test_single_qualified_value_keeps_qualifier_and_display(self):
        r = both_orders(self, self.spec, [C("c1", 7450, q="up_to", disp="7.45 GB/s"), C("c2", 7450, q="up_to", src="s2", disp="7.45 GB/s")])
        self.assertEqual((r["status"], r["value"], r["qualifier"], r["display"], r["claims"], r["sources"]), ("known", 7450, "up_to", "7.45 GB/s", ["c1", "c2"], ["s1", "s2"]))

    def test_conditional_rows_keep_qualifier_and_alternatives_keep_qualifier(self):
        spec = {"key": "pd.out", "unit": "W", "headline_condition": {"ports": "single"}}
        r = both_orders(self, spec, [C("c1", 65, cond={"ports": "single"}), C("c2", 45, q="up_to", cond={"ports": "dual"}),
                                     C("c3", 30, cond={"ports": "triple"}), C("c4", 20, q="approx", cond={"ports": "triple"}, src="s2")])
        rows = {json.dumps(x["conditions"]): x for x in r["conditional"]}
        self.assertEqual((rows['{"ports": "dual"}']["qualifier"], rows['{"ports": "dual"}']["claims"]), ("up_to", ["c2"]))
        tri = rows['{"ports": "triple"}']
        self.assertEqual(tri["status"], "conflicted")
        self.assertIn({"value": 20, "kind": "official", "sources": ["s2"], "claims": ["c4"], "qualifier": "approx"}, tri["alternatives"])

    def test_measured_only_modes_are_not_conflicts(self):
        spec = {"key": "pd.out", "unit": "W"}
        r = both_orders(self, spec, [C("m1", 61, kind="measured", mmode="negotiated"), C("m2", 58, kind="measured", mmode="sustained", src="s2")])
        self.assertEqual((r["status"], r["value"], r["kind"]), ("unknown", None, "measured"))
        self.assertEqual(sorted((a["value"], a["measurement_mode"]) for a in r["alternatives"]), [(58, "sustained"), (61, "negotiated")])
        r = both_orders(self, spec, [C("m1", 61, kind="measured", mmode="negotiated"), C("m3", 63, kind="measured", mmode="negotiated", src="s2")])
        self.assertEqual(r["status"], "conflicted", "same mode, different value = a real disagreement")
        r = R.resolve_spec(spec, [C("m1", 61, kind="measured", mmode="negotiated")], [])
        self.assertEqual((r["status"], r["measurement_mode"]), ("known", "negotiated"), "a measured-only value keeps its mode")

    def test_energy_star_power_basis_and_displayhdr_cts_are_conditions(self):
        es = {"key": "pwr.typical", "unit": "W", "basis_conditions": ["power_basis"]}
        ESB = {"power_basis": "energy_star_on_mode"}
        r = both_orders(self, es, [C("m", 22), C("e", 17.5, cond=ESB, src="s2")])
        self.assertEqual((r["status"], r["value"]), ("unknown", None), "maker typical vs ES on-mode: incomparable bases, no pick, no conflict")
        self.assertEqual({json.dumps(a.get("basis", {})) for a in r["alternatives"]}, {"{}", json.dumps(ESB)})
        self.assertNotIn("conditional", r, "a basis condition does not split the headline")
        r = R.resolve_spec(es, [C("e", 17.5, cond=ESB)], [])
        self.assertEqual((r["status"], r["value"], r["basis"]), ("known", 17.5, ESB), "ES-only value stays the headline, basis visible")
        r = both_orders(self, es, [C("m", 17.5), C("e", 17.5, cond=ESB, src="s2")])
        self.assertEqual((r["status"], r["value"], len(r["alternatives"])), ("known", 17.5, 2))
        dh = {"key": "hdr.vesa_tier", "basis_conditions": ["cts_version"]}
        r = both_orders(self, dh, [C("d1", "DisplayHDR 400", cond={"cts_version": "1.0"}), C("d2", "DisplayHDR 600", cond={"cts_version": "1.1"})])
        self.assertEqual(r["status"], "unknown")
        r = both_orders(self, dh, [C("d1", "DisplayHDR 400", cond={"cts_version": "1.1"}), C("d2", "DisplayHDR 600", cond={"cts_version": "1.1"})])
        self.assertEqual(r["status"], "conflicted", "two tiers under the same CTS version contradict")

    def test_up_to_does_not_imply_cache_state(self):
        import _ssd
        snap = type("S", (), {"fetched_at": "t"})()
        pr = type("PR", (), {"claims": []})()
        _ssd.add(pr, "x@2", snap, "perf.seq_read", 7450, "Up to 7,450 MB/s", "sku", "A", "Sequential Read")
        self.assertNotIn("conditions", pr.claims[-1], "'up to' alone is not cache evidence")
        _ssd.add(pr, "x@2", snap, "perf.seq_write", 530, "Up to 530 MB/s ** Measured with Intelligent TurboWrite technology being activated", "sku", "A", "Sequential Write")
        self.assertEqual(pr.claims[-1]["conditions"], {"cache_state": "in_slc_cache"})
        U = N.units({"specs": []})
        ok, v, x = N.normalise({"key": "perf.seq_read", "type": "number", "unit": "MB/s", "label": "Sequential read (rated)"}, {"status": "known", "value": 7450, "raw": "Sequential Read: Up to 7,450 MB/s"}, U)
        self.assertEqual((ok, v, x.get("qualifier")), (True, 7450, "up_to"), "qualifier recovered from the literal of a pre-parsed number")
        prof = yaml.safe_load((ROOT / "research" / "ssds" / "spec-profile.yaml").read_text())
        seq = {s["key"]: s for s in prof["specs"]}
        for k in ("perf.seq_read", "perf.seq_write"):
            self.assertNotIn("headline_condition", seq[k], "the headline is the stated (up to) figure, not an assumed cache state")
            self.assertEqual(seq[k]["basis_conditions"], ["cache_state"])
        mon = {s["key"]: s for s in yaml.safe_load((ROOT / "research" / "monitors" / "spec-profile.yaml").read_text())["specs"]}
        self.assertEqual((mon["pwr.typical"]["basis_conditions"], mon["hdr.vesa_tier"]["basis_conditions"]), (["power_basis"], ["cts_version"]))


# ----------------------------------------------------------------------------------------------- revisions
class Revisions(unittest.TestCase):
    def test_contradictory_revisions_and_unspecified_model_facts(self):
        ident = {"model_defining": ["wifi.generation"]}
        specdefs = {k: {"key": k, "level": lv, **extra} for k, lv, extra in (
            ("wifi.generation", "model", {}), ("wifi.marketing_class", "model", {"revision_scope": "all"}), ("wifi.rate_5_mbps", "model", {}),
            ("hw.cpu_cores", "revision", {}), ("port.lan_count", "model", {}), ("wifi.streams_5", "model", {}))}
        ents = {"m": {"kind": "model"}, "v1": {"kind": "revision"}, "v2": {"kind": "revision"}}
        cl = lambda i, v, src="s1": [dict(C(i, v, src=src), review="accepted")]
        claims = {"m": {"wifi.generation": cl("g", "wifi6"), "wifi.marketing_class": cl("k", "AX3000"), "wifi.rate_5_mbps": cl("r", 2402)},
                  "v1": {"hw.cpu_cores": cl("a1", 2), "port.lan_count": cl("a2", 4), "wifi.streams_5": cl("a3", 2)},
                  "v2": {"hw.cpu_cores": cl("b1", 4), "port.lan_count": cl("b2", 3), "wifi.streams_5": cl("b3", 4)}}
        absn = {e: {} for e in ents}
        res, cyc = P.view(ents, claims, absn, specdefs, {"v1": "m", "v2": "m"}, {"accepted"}, ident)
        self.assertEqual(cyc, [])
        m, v1, v2 = res["m"], res["v1"], res["v2"]
        for rv in (v1, v2):
            self.assertEqual(rv["wifi.generation"]["inherited_from"], "m"); self.assertEqual(rv["wifi.marketing_class"]["inherited_from"], "m")
            self.assertNotIn("wifi.rate_5_mbps", rv, "an unspecified/default-revision fact is not pushed onto every revision")
        self.assertEqual([v1[k]["value"] for k in ("hw.cpu_cores", "port.lan_count", "wifi.streams_5")], [2, 4, 2])
        self.assertEqual([v2[k]["value"] for k in ("hw.cpu_cores", "port.lan_count", "wifi.streams_5")], [4, 3, 4])
        self.assertTrue(all(k not in m for k in ("hw.cpu_cores", "port.lan_count", "wifi.streams_5")), "revision values never leak up to the model")
        self.assertEqual({k: r["revision_applicability"] for k, r in m.items()},
                         {"wifi.generation": "all", "wifi.marketing_class": "all", "wifi.rate_5_mbps": "unspecified"})
        md = {"specs": m}
        e1 = P.revision_entry({"id": "v1", "name": "V1", "lifecycle": {"state": "current"}, "specs": v1, "sources": [{"id": "s1"}]},
                              {"extra": json.dumps({"revision_label": "V1"}), "name": "V1"}, [], md)
        self.assertEqual(sorted(e1["specs"]), ["hw.cpu_cores", "port.lan_count", "wifi.streams_5"], "summary lists own specs only")
        self.assertEqual(e1["differs"], ["hw.cpu_cores", "port.lan_count", "wifi.streams_5"])

    def test_revision_level_in_inheritance_map(self):
        self.assertIn("revision", R.LEVEL)
        self.assertFalse(R.inheritable({"key": "x", "level": "model"}, "model", "revision"))
        self.assertTrue(R.inheritable({"key": "x", "level": "model"}, "model", "configuration"), "ordinary hierarchy unchanged")


# ----------------------------------------------------------------------------------------------- identity
class Identity(unittest.TestCase):
    def test_same_identifier_across_levels_and_markets(self):
        km = I.key("mfr_model", "RAX54S", "netgear", "US", "model")
        kc = I.key("mfr_model", "RAX54S", "netgear", "US", "configuration")
        ke = I.key("mfr_model", "RAX54S", "netgear", "EU", "model")
        a = {I.anchor("routers", k) for k in (km, kc, ke)}
        self.assertEqual(len(a), 3, "level and market are both in the durable anchor")
        self.assertEqual(I.legacy_anchor(I.anchor("routers", km)), I.legacy_anchor(I.anchor("routers", kc)), "v1 anchors collided across levels")

    def test_legacy_registry_migrates_by_kind_keeps_ids_and_flags_ambiguity(self):
        p = Path(tempfile.mkdtemp()) / "registry.jsonl"
        lines = [{"id": "acme-x1", "anchors": ["c|mfr_model|acme|X1|"], "category": "c", "kind": "model"},
                 {"id": "acme-x1-cfg", "anchors": ["c|mfr_model|acme|X1|"], "category": "c", "kind": "configuration"},
                 {"id": "acme-y", "anchors": ["c|mfr_model|acme|Y|"], "category": "c", "kind": "model"},
                 {"id": "acme-y-2", "anchors": ["c|mfr_model|acme|Y|"], "category": "c", "kind": "model"}]
        p.write_text("".join(json.dumps(x) + "\n" for x in lines))
        r = I.IdRegistry(p)
        A = lambda v, lv: I.anchor("c", I.key("mfr_model", v, "acme", None, lv))
        self.assertEqual((r.lookup([A("X1", "model")]), r.lookup([A("X1", "configuration")])), (["acme-x1"], ["acme-x1-cfg"]),
                         "a model and a configuration with the same value keep their own ids")
        self.assertEqual(r.lookup([A("Y", "model")]), ["acme-y"], "first line wins, as before")
        self.assertEqual([x["ids"] for x in r.ambiguous], [["acme-y", "acme-y-2"]], "same-level legacy collision is flagged")
        r.add("acme-other", [A("Y", "model")], "c", "model")
        self.assertEqual(r.rebinds, [{"anchor": A("Y", "model"), "bound": "acme-y", "attempted": "acme-other"}])
        self.assertEqual(r.lookup([A("Y", "model")]), ["acme-y"], "never rebound")
        self.assertEqual(r.kind_of["acme-x1-cfg"], "configuration")

    def test_repo_registry_migration_keeps_every_public_id(self):
        r = I.IdRegistry(ROOT / "data" / "_ids" / "registry.jsonl", readonly=True)
        self.assertEqual(r.ambiguous, [])
        self.assertEqual(set(r.by_anchor.values()), {i for i in r.ids}, "every registered id still resolves through a v2 anchor")

    def world(self, scope):
        meta = {"identity_scope": scope, "brand_aliases": {}, "brand_names": {}, "skip_rx": None, "package_markets": None}
        return imp.World("monitors", D.Decisions(Path(tempfile.mkdtemp())), [], meta)

    def obs(self, w, model, market, sid, tier="manufacturer"):
        pr = {"identifiers": [{"scheme": "mfr_model", "value": model, "value_raw": model, "issuer": "acme", "market": market, "package_level": "model", "role": "key"}],
              "aliases": [], "claims": [], "absences": [], "fingerprints": {}, "sources": [{"id": "s1", "url": f"https://x/{sid}", "tier": tier}]}
        st = __import__("collections").defaultdict(int); st["labels"] = __import__("collections").Counter(); st["label_example"] = {}
        imp.do_model(w, {"brand": "acme", "brand_name": "Acme"}, sid, {"ref": model + sid, "snapshot": "sha256:" + sid, "url": "u", "fetched_at": "t"}, pr, {}, st)
        return st

    def test_cross_market_exact_merge_is_scoped_explicitly(self):
        w = self.world({"cross_market_brands": "*", "market_scoped_brands": []})
        self.obs(w, "M27", "US", "a"); self.obs(w, "m27", None, "b", tier="certifier")
        self.assertEqual(len(w.ents), 1, "unstated market matches the stated one: one model")
        st = self.obs(w, "M27", "EU", "c")
        self.assertEqual((len(w.ents), st["quarantined_cross_market"], len(w.quarantine)), (1, 1, 1), "two different stated markets never merge automatically")
        w = self.world({"cross_market_brands": "*", "market_scoped_brands": ["acme"]})
        self.obs(w, "M27", "US", "a"); self.obs(w, "M27", "EU", "c")
        self.assertEqual(len(w.ents), 2, "market-scoped brand: market is part of the key")
        with self.assertRaises(SystemExit):
            self.obs(self.world(None), "M27", "US", "a")

    def test_links_record_their_parser(self):
        a, b = imp.Ent("c", "configuration", "x"), imp.Ent("c", "model", "x")
        imp.PARSER["current"] = "xa@1"
        imp.link(a, "configuration_of", b, "adapter:xs"); imp.link(b, "possible_match", a, "stem:x")
        self.assertEqual((a.rels[0][3], b.rels[0][3]), ("xa@1", None))


# ----------------------------------------------------------------------------------------------- hygiene + budget
class Hygiene(unittest.TestCase):
    def test_html_entities_decoded_at_import(self):
        pr = {"aliases": [{"text": "UltraGear&trade; 27&quot; G-SYNC&reg;"}], "identifiers": [{"value": "A&amp;B", "value_raw": "A&amp;B"}],
              "claims": [{"value": "Wi&#8209;Fi 7 &amp; more", "raw": "Caf&eacute;", "quote": None}, {"value": ["a&amp;b", 3]}]}
        n = imp.dehtml(pr)
        self.assertEqual(pr["aliases"][0]["text"], 'UltraGear™ 27" G-SYNC®')
        self.assertEqual((pr["claims"][0]["value"], pr["claims"][0]["raw"], pr["claims"][1]["value"]), ("Wi‑Fi 7 & more", "Café", ["a&b", 3]))
        self.assertEqual((pr["identifiers"][0]["value"], pr["identifiers"][0]["value_raw"]), ("A&amp;B", "A&B"), "identity keys never move")
        self.assertEqual(n, 5)
        self.assertEqual(imp._un("AT&T 5G"), "AT&T 5G", "a bare ampersand is not an entity")

    def test_release_budget(self):
        b = {"api_warn_mib": 100, "api_fail_mib": 150, "repo_pack_warn_mib": 250, "repo_pack_migrate_mib": 500}
        M = RM.MIB
        self.assertEqual(RM.evaluate(80 * M, 10 * M, b)[0], "ok")
        self.assertEqual(RM.evaluate(101 * M, 10 * M, b)[0], "warn")
        self.assertEqual(RM.evaluate(151 * M, 10 * M, b)[0], "fail")
        self.assertEqual(RM.evaluate(80 * M, 300 * M, b)[0], "warn")
        st, msgs = RM.evaluate(80 * M, 600 * M, b)
        self.assertEqual(st, "warn"); self.assertIn("migration trigger", msgs[0])
        self.assertEqual(json.loads((ROOT / "data" / "release-budget.json").read_text())["api_fail_mib"], 150)


if __name__ == "__main__":
    unittest.main()
