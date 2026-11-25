"""Corrections flow (PM D9.2 + D10; team/briefs/pm-2026-11-25-corrections-flow.md), acceptance fixtures end to end:
GitHub issue JSON -> scripts/corrections.py sync (read-only, fake image hasher) -> data/corrections/<n>.yaml -> check -> ledger lines written by
scripts/review_corrections.py's writer -> the real scripts/import.py + v1_publish.publish() on a throwaway data root (SPECSHEET_ROOT).

  E1 accepted -> official value from a crowd source fills an unknown   E3 ChargerLAB -> measured alternative, ChargerLAB credit, no grant
  E3 RTINGS -> rejected by check                                       family claim with one sample -> rejected (D10 revision guard)
  reject_claim after accept -> value gone next build                   correction vs maker value -> conflicted, both shown
  trusted files never show a pending correction (preview: notice only) no handle/email anywhere under data/ or team/
Also: sync dry-run writes nothing, per-account limit and burst pause, form labels == the parser's, decisions.py refuses a policy naming
correction@1 and an agent `by`, path_prefix source policy, presets' kind breakdown + sources-disagree, /v1/changes crowd marks.
  python3 -I tests/test_corrections.py
"""
import email.message, hashlib, io, json, os, shutil, subprocess, sys, tempfile, unittest, urllib.request, urllib.response
from pathlib import Path

import yaml

CODE = Path(__file__).resolve().parent.parent
TMP = Path(tempfile.mkdtemp(prefix="specsheet-corrections-"))
os.environ["SPECSHEET_ROOT"] = str(TMP)          # before importing the scripts: catmeta.ROOT / source policy default = the fixture root
sys.path.insert(0, str(CODE / "scripts"))
import corrections as CR  # noqa: E402
import decisions as D  # noqa: E402
import presets as PR  # noqa: E402
import review_corrections as RC  # noqa: E402
import source_policy as SP  # noqa: E402
import build_r2 as B2  # noqa: E402

REPO = "shrestha-pranav/specsheet"
REVIEWER = "shrestha-pranav"        # data/decisions/maintainers.yaml (fixture copy)
PROFILE = """
profile_format: specsheet.category-profile/1
category: widgets
version: 0.1.0
label: Widgets
identity: {levels: [family, model, package], primary_key: manufacturer model number}
groups: [{id: general, label: General}]
specs:
  - {key: gen.size, label: Size, group: general, type: number, unit: in, tier: core, level: model, facet: {kind: range, bins: [10, 20]}, sources: [spec page]}
  - {key: gen.kind, label: Kind, group: general, type: enum, enum: [alpha, beta], tier: core, level: model, facet: true, sources: [spec page]}
  - {key: gen.flag, label: Flag, group: general, type: bool, tier: core, level: model, facet: true, sources: [label]}
"""
CATEGORY = "name: Widgets\ndescription: Fixture category.\ncolumns: [gen.size, gen.kind, gen.flag]\nmarket_filter: {markets: [US]}\nidentity_scope: {cross_market_brands: \"*\", market_scoped_brands: []}\n"
POLICIES = """
format: specsheet.policies/1
claim_policies:
  - id: claim/widgetco-spec@1
    since: "2026-11-25"
    rationale: fixture
    match: {extractors: [widgetco@1], source_ids: [widgetco-us], kinds: [official], tiers: [manufacturer], statuses: [known], keys: [gen.size, gen.kind, gen.flag]}
relation_policies: []
"""
SOURCE_POLICY = {
    "policy_version": "2026-11-25.9", "changelog": [], "defaults": {"unlisted": {"free": True, "paid": False, "licence_grant": False}, "fail_release_on_unlisted": True},
    "record_rules": {"drop_record_fields": ["media"], "exclude_demo_records": True, "exclude_categories": [], "withheld_status": "not_published"},
    "sources": [
        {"domain": "example.invalid", "match": "exact", "kind": "maker", "credit": "WidgetCo", "free": True, "paid": False, "licence_grant": False, "evidence": {"level": "none"}},
        {"domain": "github.com", "match": "path_prefix", "path": f"/{REPO}/issues", "kind": "crowd", "credit": "Contributor evidence", "free": True, "paid": False,
         "licence_grant": True, "crawl": "human_only", "evidence": {"level": "fetched", "refs": [".github/ISSUE_TEMPLATE/field-correction.yml"]}},
        {"domain": "chargerlab.com", "match": "subdomains", "kind": "measurement", "credit": "ChargerLAB (measured)", "free": True, "paid": False, "licence_grant": False,
         "crawl": "human_only", "evidence": {"level": "fetched", "refs": ["robots"]}},
        {"domain": "notebookcheck.net", "match": "subdomains", "kind": "measurement", "credit": "Notebookcheck", "free": True, "paid": False, "licence_grant": False,
         "crawl": "agent", "evidence": {"level": "fetched", "refs": ["imprint"]}},
        {"domain": "rtings.com", "match": "subdomains", "kind": "measurement", "free": False, "paid": False, "licence_grant": False, "crawl": "none", "evidence": {"level": "search"}},
        {"domain": "techpowerup.com", "match": "subdomains", "kind": "measurement", "free": True, "paid": False, "licence_grant": False, "crawl": "human_only", "evidence": {"level": "fetched", "refs": ["r"]}},
        {"domain": "techpowerup.com", "match": "path_prefix", "path": "/ssd-specs", "kind": "retail_or_review", "free": False, "paid": False, "licence_grant": False,
         "crawl": "none", "evidence": {"level": "fetched", "refs": ["r"]}},
    ]}
LOGIN = "zz-handle-fixture"
EMAIL = "zz.fixture@mail.example"
TERMS = "- [X] I license this contribution under ODbL 1.0 (database) and DbCL 1.0 (contents)."


def body(entity, key, value, etype, url="", photos=0, mode="", conditions="", applies="", extra="", coi=False):
    imgs = "\n".join(f"![IMG_{n}](https://github.com/user-attachments/assets/00000000-0000-0000-0000-{entity[-3:]}{key[-3:].encode().hex()}{n:02d})" for n in range(photos))
    sec = [("Catalogue field", json.dumps({"entity_id": entity, "key": key, "shown_value": "Unknown", "build": "b1"})), ("Proposed value", value),
           ("Evidence type", {"E1": "E1: photo of the product's own label", "E2": "E2: maker page or document URL", "E3": "E3: independent measurement URL",
                              "E4": "E4: my own measurement"}[etype]),
           ("Evidence URL", url or "_No response_"), ("Photos", imgs or "_No response_"), ("Measurement method", mode or "_No response_"),
           ("Conditions", conditions or "_No response_"), ("Applies to (configurations)", applies or "_No response_"),
           ("More evidence (second sample)", extra or "_No response_"), ("Maker statement that the line has one design", "_No response_"),
           ("Contributor terms", TERMS), ("Conflict of interest", "- [X] I work for the maker" if coi else "- [ ] I work for the maker")]
    return "\n\n".join(f"### {k}\n\n{v}" for k, v in sec)


def issue(n, b, login=LOGIN, state="open", at="2026-11-20T10:00:00Z"):
    return {"number": n, "body": b, "state": state, "state_reason": None, "created_at": at, "closed_at": None, "html_url": f"https://github.com/{REPO}/issues/{n}", "login": login}


ISSUES = [
    issue(1, body("widgetco-w-100", "gen.flag", "yes", "E1", photos=1, conditions=f"label on the base; ask @{LOGIN} or {EMAIL}")),
    issue(2, body("widgetco-w-100", "gen.size", "13 in", "E3", url="https://www.chargerlab.com/review-w-100/", mode="sustained: power meter under sustained load")),
    issue(3, body("widgetco-w-200", "gen.kind", "alpha", "E2", url="https://example.invalid/W-200-datasheet")),
    issue(4, body("widgetco-w-200", "gen.size", "25 in", "E1", photos=1)),
    issue(5, body("widgetco-w-100", "gen.kind", "beta", "E3", url="https://www.rtings.com/widget/w-100", mode="optical: photodiode")),
    issue(6, body("widgetco-w-200", "gen.flag", "no", "E1", photos=1, coi=True)),
]
# review-7 P1: PII injected literally and encoded across every field and URL component. #7 is otherwise valid (and accepted), #8 carries
# PII in the identity fields themselves (entity, key, value, applies_to) and must never apply.
TOKEN = "tok9SECRET8abcdefghijklmnop"  # gitleaks:allow  synthetic PII-sanitiser fixture, not a credential
PII_FORMS = [LOGIN, EMAIL, "zz.fixture%40mail.example", "zz.fixture%2540mail.example", "zz.fixture&#64;mail.example", "zz.fixture (at) mail (dot) example",
             "zz.fixture@mail", TOKEN]
_b7 = body("widgetco-w-100", "gen.kind", "alpha", "E2", url=f"https://example.invalid/W-100?email=zz.fixture%40mail.example&token={TOKEN}&model=W-100#{LOGIN}",
           extra=f"https://example.invalid/%40{LOGIN}/profile https://{LOGIN}:pw@example.invalid/x",
           conditions=f"seen by zz.fixture%40mail.example, zz.fixture&#64;mail.example and zz.fixture (at) mail (dot) example; cc %40{LOGIN}")
_b7 = _b7.replace('"shown_value": "Unknown"', f'"shown_value": "ask @{LOGIN}"').replace('"build": "b1"', f'"build": "{EMAIL}"')
_b7 = _b7.replace("### Maker statement that the line has one design\n\n_No response_",
                  f"### Maker statement that the line has one design\n\nhttps://example.invalid/one-design?utm_source=x&mail=zz.fixture%2540mail.example")
_b8 = body(EMAIL, f"@{LOGIN}", f"beta zz.fixture%40mail.example", "E2", url="https://example.invalid/W-200", applies=f"widgetco-w-200 {EMAIL}")
ISSUES += [issue(7, _b7), issue(8, _b8)]
fake_hash = lambda url: "sha256:" + hashlib.sha256(url.encode()).hexdigest()


def parsed(model, claims):
    return {"identifiers": [{"scheme": "mfr_model", "value": model, "value_raw": model, "issuer": "widgetco", "market": "US", "package_level": "model", "role": "key", "sources": ["s1"]}],
            "aliases": [], "media": [], "documents": [], "absences": [], "links": [], "fingerprints": {},
            "claims": [{"id": f"c_{k}_{v}", "key": k, "status": "known", "kind": "official", "unit": u, "raw": f"{k}={v}", "source": "s1",
                        "method": {"stage": "table", "extractor": "widgetco@1"}, "observed_at": "2026-11-23T00:00:00Z", "value": v, "locator": {}} for k, v, u in claims],
            "sources": [{"id": "s1", "url": f"https://example.invalid/{model}", "label": "page", "tier": "manufacturer"}]}


def run_build(t):
    env = dict(os.environ, SPECSHEET_ROOT=str(t))
    r = subprocess.run([sys.executable, "-I", str(CODE / "scripts" / "import.py"), "--data", str(t / "data")], env=env, capture_output=True, text=True)
    assert r.returncode == 0, r.stderr[-3000:]
    imp = json.loads(r.stdout[r.stdout.index("{"):])
    api = t / "api"
    shutil.rmtree(api, ignore_errors=True)
    code = "import sys, json; sys.path.insert(0, %r); import v1_publish as P; from pathlib import Path; P.publish(Path(%r), {})" % (str(CODE / "scripts"), str(api))
    r = subprocess.run([sys.executable, "-I", "-c", code], env=env, capture_output=True, text=True)
    assert r.returncode == 0, r.stderr[-3000:]
    return imp


def detail(t, eid, preview=False):
    p = t / "api" / ("preview/widgets" if preview else "widgets") / "products" / f"{eid}.json"
    return json.loads(p.read_text()) if p.exists() else None


class Flow(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        t = TMP
        os.symlink(CODE / "schemas", t / "schemas")
        (t / "research" / "widgets").mkdir(parents=True)
        (t / "research" / "widgets" / "spec-profile.yaml").write_text(PROFILE)
        (t / "research" / "widgets" / "category.yaml").write_text(CATEGORY)
        (t / "data" / "decisions").mkdir(parents=True)
        (t / "data" / "decisions" / "policies.yaml").write_text(POLICIES)
        (t / "data" / "decisions" / "ledger.jsonl").write_text("")
        (t / "data" / "decisions" / "maintainers.yaml").write_text(f"maintainers: [{REVIEWER}]\n")
        (t / "data" / "source-policy.yaml").write_text(yaml.safe_dump(SOURCE_POLICY, sort_keys=False))
        (t / "sources.extra.json").write_text(json.dumps({"widgetco-us": {"brand": "widgetco", "brand_name": "WidgetCo", "category": "widgets", "module": "none",
                                                                          "importer": "model", "parser": "widgetco@1"}}))
        d = t / "raw" / "widgetco-us"
        (d / "parsed").mkdir(parents=True)
        log = []
        for n, pr in enumerate([parsed("W-100", [("gen.size", 12, "in"), ("gen.kind", "alpha", None)]), parsed("W-200", [("gen.size", 24, "in"), ("gen.kind", "beta", None)])]):
            (d / "parsed" / f"r{n}.json").write_text(json.dumps(pr))
            log.append({"snapshot": f"sha256:{n:064x}", "ref": f"r{n}", "url": pr["sources"][0]["url"], "final_url": pr["sources"][0]["url"], "status": 200,
                        "fetched_at": "2026-11-23T00:00:00Z", "etag": None, "last_modified": None, "adapter": "fixture@1", "blob": f"blobs/{n:064x}.json"})
        (d / "snapshots.jsonl").write_text("".join(json.dumps(x) + "\n" for x in log))
        cls.pol = SP.load(t / "data" / "source-policy.yaml")
        cls.data = t / "data"
        # dry run first: prints, writes nothing
        buf = io.StringIO()
        r = CR.sync(REPO, cls.data, dry_run=True, issues=ISSUES, hasher=fake_hash, now="2026-11-25T12:00:00Z", out=buf, pol=cls.pol)
        cls.dry_written, cls.dry_out = r["written"], buf.getvalue()
        cls.dry_dir_exists = (cls.data / "corrections").exists()
        CR.sync(REPO, cls.data, issues=ISSUES, hasher=fake_hash, now="2026-11-25T12:00:00Z", out=io.StringIO(), pol=cls.pol)
        cls.imp0 = run_build(t)        # ids exist now (registry), no decisions yet
        cls.checks = {p.name: bad for p, _, bad in CR.check_all(cls.data, cls.pol)}
        cls.pre = {e: detail(t, e) for e in ("widgetco-w-100", "widgetco-w-200")}
        cls.pre_prev = detail(t, "widgetco-w-200", preview=True)
        lines = [RC.decision_line(cid, "accept_claim", REVIEWER, r, f"https://github.com/{REPO}/issues/{n}", at="2026-11-25T12:30:00Z", data_dir=cls.data)
                 for cid, n, r in (("c_corr_1_1", 1, "E1 label photo, model visible"), ("c_corr_2_1", 2, "E3 ChargerLAB review"), ("c_corr_3_1", 3, "E2 maker datasheet"),
                                   ("c_corr_7_1", 7, f"E2 maker page; thanks @{LOGIN} ({EMAIL})"))]
        RC.append(lines, cls.data)
        cls.imp1 = run_build(t)
        cls.b1 = {e: detail(t, e) for e in ("widgetco-w-100", "widgetco-w-200")}
        cls.b1_prev = detail(t, "widgetco-w-200", preview=True)
        cls.rows1 = {r["id"]: r for r in json.loads((t / "api" / "widgets" / "index.json").read_text())}
        cls.trusted_text = "".join(p.read_text() for p in (t / "api" / "widgets").rglob("*.json"))
        RC.append([RC.decision_line("c_corr_1_1", "reject_claim", REVIEWER, "photo shows a different revision", "https://github.com/x/y/issues/1",
                                    at="2026-11-25T13:00:00Z", data_dir=cls.data)], cls.data)
        run_build(t)
        cls.b2 = detail(t, "widgetco-w-100")
        # review-7 P0: issue #3 is edited after its accept (alpha -> beta): sync rewrites the file, the old approval no longer binds
        ed = [dict(it, body=it["body"].replace("### Proposed value\n\nalpha", "### Proposed value\n\nbeta")) if it["number"] == 3 else it for it in ISSUES]
        assert ed != ISSUES
        CR.sync(REPO, cls.data, issues=ed, hasher=fake_hash, now="2026-11-25T14:00:00Z", out=io.StringIO(), pol=cls.pol)
        cls.imp3 = run_build(t)
        cls.b3, cls.b3_prev = detail(t, "widgetco-w-200"), detail(t, "widgetco-w-200", preview=True)
        cls.api_text = "".join(p.read_text(errors="ignore") for p in (t / "api").rglob("*") if p.is_file())

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(TMP, ignore_errors=True)

    # ---- sync
    def test_dry_run_writes_nothing(self):
        self.assertFalse(self.dry_dir_exists)
        self.assertEqual(len(self.dry_written), 8)
        self.assertIn("[dry-run] would write", self.dry_out)

    def test_claim_file_shape(self):
        d = yaml.safe_load((self.data / "corrections" / "1.yaml").read_text())
        self.assertEqual((d["issue"], d["entity"], d["key"], d["value"], d["kind"], d["evidence"]["type"]), (1, "widgetco-w-100", "gen.flag", "yes", "official", "E1"))
        self.assertEqual(d["source"], {"url": f"https://github.com/{REPO}/issues/1", "tier": "crowd"})
        self.assertRegex(d["evidence"]["images"][0]["sha256"], r"^sha256:[0-9a-f]{64}$")
        self.assertNotIn("user-attachments", json.dumps(d), "images are hashed, never copied or linked")
        self.assertTrue(d["terms_ack"]); self.assertFalse(d["coi"]); self.assertEqual(d["submitted_by"], "crowd")
        d2 = yaml.safe_load((self.data / "corrections" / "2.yaml").read_text())
        self.assertEqual((d2["kind"], d2["measurement"]["mode"], d2["source"]["tier"], d2["source"]["via"]), ("measured", "sustained", "measurement", f"https://github.com/{REPO}/issues/2"))
        d3 = yaml.safe_load((self.data / "corrections" / "3.yaml").read_text())
        self.assertEqual((d3["kind"], d3["source"]["tier"], d3["source"]["url"]), ("official", "manufacturer", "https://example.invalid/W-200-datasheet"))

    def test_no_handle_or_email_under_data_or_team(self):
        for root in (self.data, CODE / "data", CODE / "team"):
            for p in root.rglob("*"):
                if p.is_file() and p.suffix in (".yaml", ".yml", ".json", ".jsonl", ".md"):
                    txt = p.read_text(errors="ignore")
                    self.assertNotIn(LOGIN, txt, p); self.assertNotIn(EMAIL, txt, p)
        self.assertIn("[handle removed]", (self.data / "corrections" / "1.yaml").read_text())

    def test_per_account_limit_and_burst(self):
        many = [issue(100 + n, body("widgetco-w-100", "gen.flag", "yes", "E1", photos=1), at=f"2026-11-0{1 + n // 10}T0{n % 10}:00:00Z") for n in range(12)]
        many += [issue(200, body("widgetco-w-100", "gen.flag", "yes", "E1", photos=1), login="someone-else", at="2026-11-09T00:00:00Z")]
        out = io.StringIO()
        r = CR.sync(REPO, TMP / "limit-data", dry_run=True, issues=many, hasher=fake_hash, now="2026-11-25T12:00:00Z", out=out, pol=self.pol)
        self.assertEqual(r["over_limit"], [110, 111]); self.assertEqual(len(r["written"]), 11)
        self.assertIn(f"gh issue edit 110 --repo {REPO} --add-label needs-triage-later", out.getvalue())
        self.assertNotIn(LOGIN, out.getvalue(), "the handle is never printed either")
        burst = [issue(300 + n, "", at="2026-11-25T08:00:00Z", login=f"u{n}") for n in range(21)]
        r = CR.sync(REPO, TMP / "burst-data", issues=burst, hasher=fake_hash, now="2026-11-25T12:00:00Z", out=io.StringIO(), pol=self.pol)
        self.assertTrue(r["paused"]); self.assertFalse((TMP / "burst-data").exists())

    def test_form_labels_match_parser(self):
        form = yaml.safe_load((CODE / ".github" / "ISSUE_TEMPLATE" / "field-correction.yml").read_text())
        labels = {b["id"]: b["attributes"]["label"] for b in form["body"] if b.get("id")}
        self.assertEqual(labels, CR.FORM)
        self.assertEqual(form["labels"], [CR.LABEL])
        intro = form["body"][0]["attributes"]["value"]
        self.assertIn("Text alone is not evidence. Photos stay on GitHub; we publish the value and a link to this issue.", intro)
        terms = next(b for b in form["body"] if b.get("id") == "terms")
        self.assertNotIn("DRAFT", terms["attributes"]["description"], "owner approved the wording 2026-11-25")
        self.assertTrue(terms["attributes"]["options"][0]["label"].startswith("I license this contribution under ODbL 1.0 (database) and DbCL 1.0 (contents)."))
        self.assertEqual([o.split(":")[0] for o in next(b for b in form["body"] if b.get("id") == "evidence_type")["attributes"]["options"]], ["E1", "E2", "E3", "E4"])

    # ---- check
    def test_check(self):
        self.assertEqual(self.checks["1.yaml"], []); self.assertEqual(self.checks["2.yaml"], []); self.assertEqual(self.checks["3.yaml"], [])
        self.assertIn("domain_not_allowed", {c for c, _ in self.checks["5.yaml"]}, "E3 from RTINGS is rejected by check")
        self.assertIn("coi", {c for c, _ in self.checks["6.yaml"]}, "an E1 photo from a COI-ticked submitter is not enough")

    def test_check_family_scope_and_paths(self):
        class Cat:
            cat = {"fam": "widgets", "c1": "widgets", "c2": "widgets"}
            kind = {"fam": "family", "c1": "model", "c2": "model"}
            members = staticmethod(lambda f: {"c1", "c2"})
        base = {"issue": 9, "url": f"https://github.com/{REPO}/issues/9", "entity": "fam", "applies_to": ["c1", "c2"], "key": "gen.kind", "value": "alpha",
                "kind": "measured", "measurement": {"mode": "inspection"}, "terms_ack": True, "coi": False, "submitted_by": "crowd",
                "evidence": {"type": "E3", "url": "https://www.chargerlab.com/a/", "images": []}}
        base["source"] = {"url": base["evidence"]["url"], "tier": "measurement", "via": base["url"]}
        codes = lambda d: {c for c, _ in CR.check(d, self.pol, Cat())}
        self.assertIn("revision_guard", codes(base), "family claim with one sample -> rejected")
        two = dict(base, evidence=dict(base["evidence"], extra_urls=["https://www.notebookcheck.net/b.html"]))
        self.assertEqual(codes(two), set())
        self.assertIn("scope", codes(dict(base, applies_to=None)), "a config is never implied")
        self.assertIn("scope", codes(dict(two, applies_to=["c1", "zz"])))
        tpu = dict(two, evidence=dict(two["evidence"], url="https://www.techpowerup.com/ssd-specs/x.d1"), source=dict(base["source"], url="https://www.techpowerup.com/ssd-specs/x.d1"))
        self.assertIn("domain_not_allowed", codes(tpu), "TechPowerUp's SSD database is excluded by path")
        review = dict(tpu, evidence=dict(tpu["evidence"], url="https://www.techpowerup.com/review/x/"), source=dict(base["source"], url="https://www.techpowerup.com/review/x/"))
        self.assertEqual(codes(review), set(), "TechPowerUp reviews stay citable by a person")
        agent = dict(review, submitted_by="agent:a2")
        self.assertIn("agent", codes(agent), "agents cite crawl: agent domains only")
        e1 = dict(base, evidence={"type": "E1", "images": []}, kind="official", measurement=None, source={"url": base["url"], "tier": "crowd"}, applies_to=None, entity="c1")
        self.assertIn("no_evidence", codes(e1), "text alone is not evidence")

    # ---- publish
    def test_pending_never_published(self):
        w200 = self.pre["widgetco-w-200"]
        self.assertEqual(w200["specs"]["gen.size"]["value"], 24)
        self.assertNotIn("corrections_pending", w200)
        self.assertNotIn("github.com", json.dumps(self.pre), "an undecided correction's source is never listed")
        self.assertEqual(self.pre_prev["corrections_pending"], [{"key": "gen.flag", "ref": "6"}, {"key": "gen.kind", "ref": "3"}, {"key": "gen.size", "ref": "4"}])
        self.assertNotIn("gen.size", self.pre_prev["specs"], "preview shows the notice, never the proposed value")
        self.assertEqual(self.b1_prev["corrections_pending"], [{"key": "gen.flag", "ref": "6"}, {"key": "gen.size", "ref": "4"}])
        self.assertNotIn("corrections_pending", self.trusted_text)
        self.assertNotIn("25", json.dumps(self.b1["widgetco-w-200"]["specs"]["gen.size"]))
        self.assertEqual(self.imp1["claims_review"]["widgets"].get("accepted"), 4 + 4)

    def test_e1_fills_unknown_official_crowd(self):
        self.assertNotIn("gen.flag", self.pre["widgetco-w-100"]["specs"])
        sp = self.b1["widgetco-w-100"]["specs"]["gen.flag"]
        self.assertEqual((sp["status"], sp["value"], sp["kind"]), ("known", True, "official"))
        src = {s["id"]: s for s in self.b1["widgetco-w-100"]["sources"]}[sp["sources"][0]]
        self.assertEqual((src["tier"], src["url"], src["relicense"], src["licence_grant"]), ("crowd", f"https://github.com/{REPO}/issues/1", False, True))
        self.assertEqual(self.rows1["widgetco-w-100"]["x"]["gen.flag"]["k"], "label", "index row: maker label (contributor photo)")

    def test_e3_measured_alternative_with_credit_no_grant(self):
        sp = self.b1["widgetco-w-100"]["specs"]["gen.size"]
        self.assertEqual((sp["value"], sp["kind"]), (12, "official"), "a measurement never replaces the maker value")
        alt = next(a for a in sp["alternatives"] if a["kind"] == "measured")
        self.assertEqual((alt["value"], alt["measurement_mode"]), (13, "sustained"))
        src = {s["id"]: s for s in self.b1["widgetco-w-100"]["sources"]}[alt["sources"][0]]
        self.assertEqual((src["tier"], src["url"], src["evidence"], src["licence_grant"]), ("measurement", "https://www.chargerlab.com/review-w-100/", f"https://github.com/{REPO}/issues/2", False))
        self.assertTrue(src["label"].startswith("ChargerLAB (measured)"))
        self.assertEqual(self.rows1["widgetco-w-100"]["x"]["gen.size"]["alt"], [{"v": 13, "k": "measured"}])

    def test_correction_vs_maker_is_conflicted_both_shown(self):
        sp = self.b1["widgetco-w-200"]["specs"]["gen.kind"]
        self.assertEqual(sp["status"], "conflicted")
        self.assertEqual(sorted(a["value"] for a in sp["alternatives"]), ["alpha", "beta"], "the maker value is never deleted")

    def test_reject_after_accept_removes_value(self):
        self.assertNotIn("gen.flag", self.b2["specs"])
        self.assertNotIn(f"issues/1\"", json.dumps(self.b2["sources"]))
        self.assertEqual(self.b2["specs"]["gen.size"]["value"], 12)

    # ---- governance
    def test_ledger_writer_and_governance(self):
        led = [json.loads(x) for x in (self.data / "decisions" / "ledger.jsonl").read_text().splitlines()]
        self.assertEqual([x["id"] for x in led], ["d_corr_1_1", "d_corr_2_1", "d_corr_3_1", "d_corr_7_1", "d_corr_1_1_2"])
        self.assertTrue(all(x["digest"].startswith("sha256:") for x in led if x["action"] == "accept_claim"))
        with self.assertRaises(SystemExit):
            RC.decision_line("c_corr_1_1", "accept_claim", "someone-else", "x", None, data_dir=self.data)     # not in maintainers.yaml
        t0 = Path(tempfile.mkdtemp(dir=TMP)) / "data"
        (t0 / "decisions").mkdir(parents=True)
        (t0 / "decisions" / "ledger.jsonl").write_text(json.dumps({"id": "d1", "by": "someone-else", "action": "reject_claim", "claim": "c_corr_1_1"}) + "\n")
        with self.assertRaises(SystemExit):
            D.Decisions(t0)
        self.assertEqual(led[0]["evidence"], f"https://github.com/{REPO}/issues/1")
        with self.assertRaises(SystemExit):
            RC.decision_line("c_corr_1_1", "accept_claim", "agent:a3", "x", None, data_dir=self.data)
        with self.assertRaises(SystemExit):
            RC.decision_line("c_corr_1_1", "accept_claim", "claude", "x", None, data_dir=self.data)
        t = Path(tempfile.mkdtemp(dir=TMP)) / "data"
        (t / "decisions").mkdir(parents=True)
        (t / "decisions" / "ledger.jsonl").write_text(json.dumps({"id": "d1", "by": "agent:a2", "action": "accept_claim", "claim": "c_corr_1_1"}) + "\n")
        with self.assertRaises(SystemExit):
            D.Decisions(t)
        (t / "decisions" / "ledger.jsonl").write_text("")
        (t / "decisions" / "policies.yaml").write_text(yaml.safe_dump({"claim_policies": [{"id": "claim/x@1", "match": {"keys": ["a"], "source_ids": ["corrections"], "extractors": ["correction@1"]}}]}))
        with self.assertRaises(SystemExit):
            D.Decisions(t)
        real = yaml.safe_load((CODE / "data" / "decisions" / "policies.yaml").read_text())
        self.assertFalse([p["id"] for p in real.get("claim_policies") or [] if "correction@1" in json.dumps(p)], "no auto-accept policy names correction@1")

    def test_interactive_review(self):
        import builtins, contextlib
        d2 = TMP / "review-data"
        shutil.copytree(self.data, d2)
        answers = iter(["a", "y", "y", "y", "W-200 label: 25 in", "", "r", "4"])     # #4: accept with a transcription; #5 (RTINGS): reject, fast reason 4
        orig, builtins.input = builtins.input, lambda prompt="": next(answers)
        try:
            with contextlib.redirect_stdout(io.StringIO()) as out:
                RC.review({"4", "5"}, REVIEWER, d2)
        finally:
            builtins.input = orig
        led = [json.loads(x) for x in (d2 / "decisions" / "ledger.jsonl").read_text().splitlines()]
        self.assertEqual([(x["claim"], x["action"], x["by"]) for x in led[-2:]], [("c_corr_4_1", "accept_claim", REVIEWER), ("c_corr_5_1", "reject_claim", REVIEWER)])
        self.assertEqual(led[-2]["reason"], "E1 label photo, model visible")
        self.assertTrue(led[-1]["reason"].startswith("Domain not allowed"))
        self.assertEqual(yaml.safe_load((d2 / "corrections" / "4.yaml").read_text())["evidence"]["images"][0]["transcription"], "W-200 label: 25 in")
        self.assertIn("PROPOSED: '25 in' -> 25", out.getvalue())

    def test_queue(self):
        out = TMP / "queue.md"
        text = CR.queue(self.data, out, self.pol, api=TMP / "api", now="2026-11-25T12:00:00Z")
        self.assertIn("| c_corr_2_1 | widgetco-w-100 | gen.size |", text)
        self.assertIn("accept by " + REVIEWER + "", text); self.assertIn("pending", text)
        self.assertIn("gh issue close 2 --comment", text)
        self.assertIn("5.yaml: domain_not_allowed", text)

    def test_real_policy_and_files(self):
        pol = SP.load(CODE / "data" / "source-policy.yaml")
        self.assertEqual(pol.entry_for(f"https://github.com/{REPO}/issues/5")["kind"], "crowd")
        self.assertIsNone(pol.entry_for("https://github.com/someone/else/issues/5"))
        self.assertFalse(pol.disposition("https://www.techpowerup.com/ssd-specs/a")["free"])
        self.assertTrue(pol.disposition("https://www.techpowerup.com/review/a")["free"])
        self.assertFalse(pol.disposition("https://www.rtings.com/a")["free"])
        self.assertTrue(pol.disposition(f"https://github.com/{REPO}/issues/5")["licence_grant"], "owner approved the contributor terms 2026-11-25")
        self.assertEqual(CR.TERMS_VERSION, "2026-11-25")
        real = CODE / "data" / "corrections"
        if real.exists():
            for p in real.glob("*.yaml"):
                d = yaml.safe_load(p.read_text())
                for f in ("author", "user", "login", "email"):
                    self.assertNotIn(f, d, p)


class Hardening:
    """Codex review-7: content-bound approval, privacy before persistence, crawl policy on every redirect hop, measurement scope."""
    def test_edit_after_accept_is_withheld(self):
        self.assertEqual(self.b1["widgetco-w-200"]["specs"]["gen.kind"]["status"], "conflicted")
        sp = self.b3["specs"]["gen.kind"]
        self.assertEqual((sp["status"], sp["value"]), ("known", "beta"), "the edited correction is withheld: only the maker value is left")
        self.assertNotIn("alternatives", sp)
        self.assertIn({"key": "gen.kind", "ref": "3"}, self.b3_prev["corrections_pending"], "withheld = pending again")
        self.assertEqual(self.imp3["claims_review"]["widgets"].get("accepted"), 4 + 2, "#1 rejected, #3 withheld; #2 and #7 still bound")

    def test_digest_binds_content(self):
        doc = yaml.safe_load((self.data / "corrections" / "2.yaml").read_text())
        base = CR.claim_digest(doc, "c_corr_2_1", "widgetco-w-100")
        for mut in (dict(doc, value="14 in"), dict(doc, applies_to=["b", "a"]), dict(doc, evidence=dict(doc["evidence"], url="https://www.chargerlab.com/other/")),
                    dict(doc, conditions={"x": 1})):
            self.assertNotEqual(CR.claim_digest(mut, "c_corr_2_1", "widgetco-w-100"), base)
        self.assertNotEqual(CR.claim_digest(dict(doc, applies_to=["a", "b"]), "c_corr_2_1", "a"), CR.claim_digest(dict(doc, applies_to=["b", "a"]), "c_corr_2_1", "a"))
        self.assertEqual(CR.claim_digest(dict(doc, synced_at="later", state="closed"), "c_corr_2_1", "widgetco-w-100"), base, "sync time / issue state do not void a decision")
        d = D.Decisions(self.data)
        ctx = {"source_id": "corrections", "extractor": "correction@1", "key": "gen.size", "kind": "measured", "tier": "measurement", "status": "known", "normalized": True}
        self.assertEqual(d.claim_state("c_corr_2_1", ctx)[0], "accepted")
        self.assertEqual(d.claim_state("c_corr_3_1", ctx), ("candidate", None))
        d.claims["c_corr_2_1"] = {k: v for k, v in d.claims["c_corr_2_1"].items() if k != "digest"}
        self.assertEqual(d.claim_state("c_corr_2_1", ctx), ("candidate", None), "an accept line without a digest never publishes")
        real = CODE / "data" / "decisions" / "ledger.jsonl"
        self.assertFalse([ln for ln in real.read_text().splitlines() if '"c_corr_' in ln], "no correction has been accepted in the real ledger yet")
        self.assertIn("pending (changed since accept: withheld)", CR.queue(self.data, TMP / "q2.md", self.pol, api=TMP / "api", now="2026-11-25T15:00:00Z"))

    def test_pii_never_persisted_or_published(self):
        for root in (self.data, TMP / "api"):
            for p in root.rglob("*"):
                if p.is_file():
                    txt = p.read_text(errors="ignore")
                    for f in PII_FORMS:
                        self.assertNotIn(f, txt, f"{p}: {f}")
                    self.assertFalse(CR.has_pii(txt) and p.suffix == ".yaml", p)
        d7 = yaml.safe_load((self.data / "corrections" / "7.yaml").read_text())
        self.assertEqual(d7["evidence"]["url"], "https://example.invalid/W-100?model=W-100", "identifying query params and fragment dropped, the rest kept")
        self.assertNotIn("extra_urls", d7["evidence"], "a URL whose path names a person, or with userinfo, is dropped")
        self.assertEqual(d7["evidence"]["single_design_url"], "https://example.invalid/one-design")
        self.assertIsNone(d7["release"]); self.assertEqual(d7["shown_value"], "ask [handle removed]")
        d8 = yaml.safe_load((self.data / "corrections" / "8.yaml").read_text())
        self.assertEqual((d8["entity"], d8["key"], d8.get("applies_to")), (None, None, ["widgetco-w-200"]))
        led = [json.loads(x) for x in (self.data / "decisions" / "ledger.jsonl").read_text().splitlines()]
        self.assertEqual(next(x for x in led if x["claim"] == "c_corr_7_1")["reason"], "E2 maker page; thanks [handle removed] ([email removed])")
        self.assertEqual(self.b1["widgetco-w-100"]["specs"]["gen.kind"]["value"], "alpha", "#7 published after sanitizing")
        for f in PII_FORMS:
            self.assertNotIn(f, self.api_text)

    def test_redirects_rechecked_zero_requests(self):
        class FakeNet(urllib.request.BaseHandler):
            handler_order = 100
            def __init__(self, routes):
                self.routes, self.seen = routes, []
            def https_open(self, req):
                self.seen.append(req.full_url)
                code, loc, data = self.routes[req.full_url]
                h = email.message.Message()
                if loc:
                    h["Location"] = loc
                r = urllib.response.addinfourl(io.BytesIO(data), h, req.full_url, code)
                r.msg = "OK" if code == 200 else "Found"
                return r
        att = "https://github.com/user-attachments/assets/00000000-0000-0000-0000-000000000001"
        cdn = "https://objects.githubusercontent.com/x/1.png"
        for dest in ("https://www.chargerlab.com/x.png", "https://www.rtings.com/x.png", "https://unlisted.invalid/x.png", f"https://github.com/{REPO}/issues/1",
                     "http://objects.githubusercontent.com/x/1.png"):
            net = FakeNet({att: (302, dest, b""), dest: (200, None, b"pwned")})
            with self.assertRaises(CR.BlockedFetch):
                CR.hash_image(att, pol=self.pol, handlers=(net,))
            self.assertEqual(net.seen, [att], f"no request reaches {dest}")
        net = FakeNet({att: (302, cdn, b""), cdn: (200, None, b"img")})
        self.assertEqual(CR.hash_image(att, pol=self.pol, handlers=(net,)), "sha256:" + hashlib.sha256(b"img").hexdigest())
        self.assertEqual(net.seen, [att, cdn])
        for first in ("https://www.chargerlab.com/a.png", "https://www.rtings.com/a.png", "https://unlisted.invalid/a.png"):
            net = FakeNet({first: (200, None, b"x")})
            with self.assertRaises(CR.BlockedFetch):
                CR.hash_image(first, pol=self.pol, handlers=(net,))
            self.assertEqual(net.seen, [])
        net = FakeNet({"https://www.notebookcheck.net/a.png": (302, "https://www.chargerlab.com/a.png", b"")})
        with self.assertRaises(CR.BlockedFetch):
            CR.hash_image("https://www.notebookcheck.net/a.png", pol=self.pol, handlers=(net,))
        self.assertEqual(net.seen, ["https://www.notebookcheck.net/a.png"], "a crawl: agent source may not bounce us to a human_only one")

    def test_measurement_scope(self):
        class Cat:
            cat = {"fam": "widgets", "c1": "widgets", "c2": "widgets"}
            kind = {"fam": "family", "c1": "model", "c2": "model"}
            members = staticmethod(lambda f: {"c1", "c2"})
        base = {"issue": 9, "url": f"https://github.com/{REPO}/issues/9", "entity": "fam", "applies_to": ["c1", "c2"], "key": "gen.kind", "value": "alpha",
                "kind": "measured", "measurement": {"mode": "inspection"}, "terms_ack": True, "coi": False, "submitted_by": "crowd",
                "evidence": {"type": "E3", "url": "https://www.chargerlab.com/a/", "extra_urls": ["https://chargerlab.com/a/?page=2", "https://www.chargerlab.com/b/"], "images": []}}
        base["source"] = {"url": base["evidence"]["url"], "tier": "measurement", "via": base["url"]}
        codes = lambda d: {c for c, _ in CR.check(d, self.pol, Cat())}
        self.assertIn("revision_guard", codes(base), "three URLs on one site are one sample")
        img = {"sha256": "sha256:" + "a" * 64, "transcription": "W label"}
        e4 = dict(base, evidence={"type": "E4", "images": [img, dict(img)]}, source={"url": base["url"], "tier": "crowd"})
        self.assertIn("revision_guard", codes(e4), "the same photo twice is one sample")
        self.assertNotIn("revision_guard", codes(dict(e4, evidence={"type": "E4", "images": [img, dict(img, sha256="sha256:" + "b" * 64)]})))
        e4sd = dict(e4, evidence={"type": "E4", "images": [img], "single_design_url": "https://www.chargerlab.com/one-design/"})
        self.assertIn("domain_not_allowed", codes(e4sd), "an E4 single-design statement must be a maker page")
        self.assertNotIn("domain_not_allowed", codes(dict(e4sd, evidence=dict(e4sd["evidence"], single_design_url="https://example.invalid/one-design"))))



for _n, _f in list(vars(Hardening).items()):      # run on Flow's one fixture build (setUpClass), not a second copy
    if _n.startswith("test_"):
        setattr(Flow, _n, _f)


class Presets(unittest.TestCase):
    SCHEMA = {"fields": [{"key": "b", "label": "B", "type": "bool", "facet": True}]}

    def test_kind_breakdown_disagree_and_non_maker(self):
        rows = [{"id": "1", "brand": "A", "v": {"b": False}, "t": ["manufacturer"]},
                {"id": "2", "brand": "A", "v": {"b": False}, "x": {"b": {"alt": [{"v": True, "k": "measured"}]}}, "t": ["manufacturer"]},
                {"id": "3", "brand": "B", "v": {"b": False}, "x": {"b": {"k": "measured"}}, "t": ["manufacturer"]},
                {"id": "4", "brand": "B", "v": {"b": True}, "x": {"b": {"alt": [{"v": False, "k": "measured"}]}}, "t": ["manufacturer"]},
                {"id": "5", "brand": "C", "v": {}, "t": ["manufacturer"]}]
        gate, count = PR.measure({"id": "p", "filters": {"f_b_value": "no"}}, {"id": "c"}, self.SCHEMA, rows, 0.5)
        self.assertEqual(count, {"matches": 2, "maybe": 3, "unknown": 1, "disagree": 2, "ruled_out": 0, "total": 5, "out_of_scope": 0})
        self.assertEqual(gate["keys"][0]["by_kind"], {"measured": 1, "official": 3})
        self.assertEqual(gate["non_maker_brands"], [])
        self.assertEqual(count["matches"] + count["unknown"] + count["disagree"] + count["ruled_out"], count["total"], "disjoint buckets")
        self.assertEqual(sum(gate["keys"][0]["by_kind"].values()), gate["keys"][0]["known"])
        rows[3]["x"]["b"]["k"] = "measured"
        gate, _ = PR.measure({"id": "p", "filters": {"f_b_value": "no"}}, {"id": "c"}, self.SCHEMA, rows, 0.5)
        self.assertEqual(gate["non_maker_brands"], [{"brand": "B", "key": "b", "kinds": ["measured"]}])


    def test_conflict_state_preserved(self):
        num = {"fields": [{"key": "n", "label": "N", "type": "number", "facet": True}]}
        rows = [{"id": "1", "brand": "A", "v": {"n": 10}, "x": {"n": {"alt": [{"v": 12, "k": "measured"}]}}},      # same side (>= 5): still disagree (D10)
                {"id": "2", "brand": "A", "v": {}, "s": {"n": "conflicted"}},                                     # conflict, no headline: explicit
                {"id": "3", "brand": "B", "v": {}, "x": {"n": {"alt": [{"v": 1, "k": "measured"}, {"v": 2, "k": "derived"}]}}},   # every value fails
                {"id": "4", "brand": "B", "v": {}, "x": {"n": {"alt": [{"v": 1, "k": "measured"}, {"v": 9, "k": "derived"}]}}},
                {"id": "5", "brand": "B", "v": {"n": 7}},
                {"id": "6", "brand": "C", "v": {}}]
        _, c = PR.measure({"id": "p", "filters": {"f_n_min": "5"}}, {"id": "c"}, num, rows, 0.1)
        self.assertEqual(c, {"matches": 1, "maybe": 4, "unknown": 1, "disagree": 3, "ruled_out": 1, "total": 6, "out_of_scope": 0})


class Changes(unittest.TestCase):
    def test_crowd_marked(self):
        rec = {"specs": {"a": {"status": "known", "value": 1, "kind": "measured", "sources": ["s2"]}, "b": {"status": "known", "value": 2, "sources": ["s1"]}},
               "sources": [{"id": "s1", "tier": "manufacturer"}, {"id": "s2", "tier": "measurement", "evidence": "https://github.com/x/y/issues/2"}]}
        crowd = {"r": B2.crowd_keys(rec)}
        self.assertEqual(crowd["r"], {"a": {"kind": "measured", "tier": "crowd", "source_tier": "measurement"}})
        d = B2.diff_rows({"r": {"a": 0, "b": 2}}, {"r": {"a": 1, "b": 3}}, {}, crowd)
        self.assertEqual(d["changed"][0]["crowd"], {"a": {"kind": "measured", "tier": "crowd", "source_tier": "measurement"}})


if __name__ == "__main__":
    unittest.main()
