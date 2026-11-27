#!/usr/bin/env python3
"""Review-11 fixes (A3-fix r12; reviews/2026-11-26-astra-review-11.md). Zero real requests: fake transports, temp stores, fixtures only.

  P1-1 robots.py RFC 9309 2.2.2 octet normalisation (/%61 == /a, /cafe-acute == /caf%C3%A9, Allow ties); corrections.py matches its own UA,
       policy-checks every robots.txt redirect hop and paces by max(1 s, Crawl-delay)
  P1-2 delisted ref: discover -> delist -> rediscover -> failed fetch keeps it delisted; wrong-identity 200 keeps it delisted + pinned;
       only a fresh 200 with the same identity clears it; published lifecycle is not `current` and carries last_verified
  P1-3 PECRON wrong-model rows (th/th, th/td, td/td) reject the table; approximations with or without whitespace never exact
  coverage_guard fails closed on an unreadable baseline unless --bootstrap; NITECORE contradictory titles; KUXIU AVS text-level
"""
import dataclasses, email.message, gzip, io, json, os, sys, tempfile, unittest, urllib.request, urllib.response
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "crawler" / "adapters"), str(ROOT / "crawler"), str(ROOT / "scripts")]
import robots as R  # noqa: E402
import _contract as C  # noqa: E402
import _run  # noqa: E402
import registry as REG  # noqa: E402
import pecron_stations as PE  # noqa: E402
import nitecore_powerbanks as N  # noqa: E402
import kuxiu_chargers as K  # noqa: E402
import coverage_guard as G  # noqa: E402
import corrections as CR  # noqa: E402
import v1_publish as V  # noqa: E402
import importlib.util  # noqa: E402

_spec = importlib.util.spec_from_file_location("specsheet_import_r11", ROOT / "scripts" / "import.py")
IMP = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(IMP)


# ------------------------------------------------------------------------------------------------------------------------------- P1-1
class RobotsOctets(unittest.TestCase):
    def test_percent_encoded_unreserved_ranks_as_its_octet(self):
        rb = R.Robots("User-agent: *\nDisallow: /%61\nAllow: /a\n")
        self.assertTrue(rb.allowed("https://h.example/a"))              # equal octet length 2: Allow wins the tie (was: /%61 = 4 chars won)
        self.assertTrue(rb.allowed("https://h.example/%61bc"))
        self.assertEqual(R.octets("/%61"), R.octets("/a"))
        rb = R.Robots("User-agent: *\nAllow: /%61\nDisallow: /a\n")
        self.assertTrue(rb.allowed("https://h.example/abc"))

    def test_non_ascii_pattern_and_path(self):
        rb = R.Robots("User-agent: *\nDisallow: /café\n")
        for u in ("https://h.example/caf%C3%A9", "https://h.example/caf%c3%a9/x", "https://h.example/café"):
            self.assertFalse(rb.allowed(u), u)
        self.assertTrue(rb.allowed("https://h.example/cafe"))
        rb = R.Robots("User-agent: *\nDisallow: /caf%C3%A9\n")
        self.assertFalse(rb.allowed("https://h.example/café"))
        self.assertEqual(R.octets("/café"), R.octets("/caf%C3%A9"), "6 octets either way")

    def test_allow_ties_across_spellings(self):
        rb = R.Robots("User-agent: *\nDisallow: /caf%C3%A9\nAllow: /café\n")
        self.assertTrue(rb.allowed("https://h.example/caf%C3%A9"))
        rb = R.Robots("User-agent: *\nDisallow: /caf%C3%A9/\nAllow: /café\n")
        self.assertFalse(rb.allowed("https://h.example/café/x"))       # longer Disallow (7 octets) beats Allow (6)
        rb = R.Robots("User-agent: *\nAllow: /%7Ex\nDisallow: /~x\n")
        self.assertTrue(rb.allowed("https://h.example/~x"))


class FakeNet(urllib.request.BaseHandler):
    handler_order = 100

    def __init__(self, routes):
        self.routes, self.seen = routes, []

    def https_open(self, req):
        self.seen.append((req.full_url, req.get_header("User-agent")))
        code, loc, data = self.routes[req.full_url]
        h = email.message.Message()
        if loc:
            h["Location"] = loc
        r = urllib.response.addinfourl(io.BytesIO(data), h, req.full_url, code)
        r.msg = "OK" if code == 200 else "Found"
        return r


class Pol:
    """Minimal crawl policy: hosts in AGENT are listed crawl: agent, everything else listed human_only."""
    AGENT = {"maker.example", "cdn.maker.example"}

    def entry_for(self, url):
        return {"listed": True}

    def crawl(self, url):
        import urllib.parse
        return "agent" if urllib.parse.urlsplit(url).hostname in self.AGENT else "human_only"


class CorrectionsRobots(unittest.TestCase):
    def setUp(self):
        self.waits, self.clock = [], [1000.0]
        CR._LAST.clear()
        self._s, self._n = CR._sleep, CR._now
        CR._sleep = lambda s: (self.waits.append(round(s, 3)), self.clock.__setitem__(0, self.clock[0] + s))
        CR._now = lambda: self.clock[0]

    def tearDown(self):
        CR._sleep, CR._now = self._s, self._n

    def test_matches_its_own_user_agent(self):
        txt = b"User-agent: specsheet-crawler\nAllow: /\n\nUser-agent: specsheet-corrections\nDisallow: /img/\n\nUser-agent: *\nAllow: /\n"
        net = FakeNet({"https://maker.example/robots.txt": (200, None, txt)})
        self.assertFalse(CR.robots_ok("https://maker.example/img/a.png", Pol(), handlers=(net,)))
        self.assertEqual(CR.AGENT, "specsheet-corrections")
        self.assertTrue(all(ua.startswith("specsheet-corrections/") for _, ua in net.seen))

    def test_robots_redirect_policy_checked(self):
        net = FakeNet({"https://maker.example/robots.txt": (302, "https://other.example/robots.txt", b""),
                       "https://other.example/robots.txt": (200, None, b"User-agent: *\nAllow: /\n")})
        self.assertFalse(CR.robots_ok("https://maker.example/a.png", Pol(), handlers=(net,)), "unfollowable robots redirect = disallow all")
        self.assertEqual([u for u, _ in net.seen], ["https://maker.example/robots.txt"], "the human_only host gets zero requests")
        net = FakeNet({"https://maker.example/robots.txt": (302, "https://cdn.maker.example/robots.txt", b""),
                       "https://cdn.maker.example/robots.txt": (200, None, b"User-agent: *\nDisallow: /a\n")})
        self.assertFalse(CR.robots_ok("https://maker.example/a.png", Pol(), handlers=(net,)))      # agent hop followed and obeyed
        self.assertEqual(len(net.seen), 2)

    def test_crawl_delay_paces_every_request(self):
        img = "https://maker.example/i/a.png"
        net = FakeNet({"https://maker.example/robots.txt": (200, None, b"User-agent: *\nCrawl-delay: 7\n"),
                       img: (302, "https://maker.example/i/b.png", b""), "https://maker.example/i/b.png": (200, None, b"img")})
        CR.hash_image(img, pol=Pol(), handlers=(net,))
        self.assertEqual([u for u, _ in net.seen], ["https://maker.example/robots.txt", img, "https://maker.example/i/b.png"])
        self.assertEqual(self.waits, [7.0, 7.0], "image and redirect hop each wait the robots Crawl-delay after the previous request")
        self.waits.clear()
        CR.hash_image(img, pol=Pol(), handlers=(FakeNet({"https://maker.example/robots.txt": (200, None, b""), img: (200, None, b"x")}),))
        self.assertEqual(self.waits, [1.0, 1.0], "no Crawl-delay: the 1 s floor")


# ------------------------------------------------------------------------------------------------------------------------------- P1-2
class FakeAdapter:
    id, source_id, version = "fake_r11", "fake-r11", 1
    pages = {}        # key -> (status, model)  for the next fetch
    listed = []

    def __init__(self, store):
        self.store, self.adapter = store, f"{self.id}@{self.version}"

    def discover(self, checkpoint, net):
        return C.Discovery([C.Ref(self.source_id, k, f"https://maker.example/{k}", {}) for k in self.listed], True, None, {})

    def fetch(self, ref, prior, net):
        st, model = self.pages[ref.key]
        if st != 200:
            s = C.Snapshot("sha256:", ref, st, "2026-11-26T00:00:00Z", ref.url, {})
        else:
            s = C.Snapshot(self.store.put(json.dumps({"model": model, "n": len(self.store.snapshots())}).encode(), ".json"), ref, 200,
                           f"2026-11-{10 + len(self.store.snapshots()):02d}T00:00:00Z", ref.url, {})
        self.store.append(s, self.adapter, ".json")
        self.fetched.append(ref.key)
        return s

    def parse(self, snap, blobs, profile):
        d = json.loads(blobs.read(snap.snapshot, ".json"))
        pr = C.ParseResult()
        pr.identifiers.append({"scheme": "mfr_model", "value": d["model"], "role": "key"})
        pr.claims.append({"key": "gen.n", "value": d["n"]})
        return pr


class TmpStore(C.BlobStore):
    def __init__(self, d):
        self.dir = Path(d)
        self.blobs = self.dir / "blobs"
        self.log = self.dir / "snapshots.jsonl"
        self.blobs.mkdir(parents=True, exist_ok=True)


class Resurrection(unittest.TestCase):
    def run_cmd(self, ad, cmd):
        argv = sys.argv
        sys.argv = ["x", cmd]
        ad.fetched = []
        try:
            _run.main(ad)
        finally:
            sys.argv = argv

    def hints(self, store, key):
        return next(r["hints"] for r in json.loads((store.dir / "discovery.json").read_text())["refs"] if r["key"] == key)

    def test_discover_delist_rediscover_failed_fetch(self):
        with tempfile.TemporaryDirectory() as td:
            import contextlib
            store = TmpStore(td)
            ad = FakeAdapter(store)
            quiet = contextlib.redirect_stdout(io.StringIO())
            with quiet:
                FakeAdapter.listed, FakeAdapter.pages = ["a", "q7"], {"a": (200, "A1"), "q7": (200, "Q7")}
                self.run_cmd(ad, "discover"); self.run_cmd(ad, "fetch")
                good = store.latest()["q7"]["snapshot"]
                FakeAdapter.listed = ["a"]                                   # delisted
                self.run_cmd(ad, "discover"); self.run_cmd(ad, "fetch")
                self.assertEqual(ad.fetched, [])
                self.assertEqual(self.hints(store, "q7")["listing"], "delisted")
                FakeAdapter.listed = ["a", "q7"]                             # re-listed: discovery alone does not resurrect it
                self.run_cmd(ad, "discover")
                h = self.hints(store, "q7")
                self.assertEqual((h["listing"], bool(h["relisted_at"])), ("delisted", True))
                FakeAdapter.pages["q7"] = (503, None)                        # failed re-fetch: re-fetched (despite an old 200), stays delisted
                self.run_cmd(ad, "fetch")
                self.assertEqual(ad.fetched, ["q7"])
                h = self.hints(store, "q7")
                self.assertEqual((h["listing"], bool(h.get("revalidate_failed_at"))), ("delisted", True))
                self.assertEqual(h["pinned_snapshot"], good)
                self.run_cmd(ad, "discover")                                 # another rediscover keeps the marks
                self.assertEqual(self.hints(store, "q7")["listing"], "delisted")
                FakeAdapter.pages["q7"] = (200, "Q8")                        # fresh 200 naming another product: identity check fails
                self.run_cmd(ad, "fetch")
                h = self.hints(store, "q7")
                self.assertEqual((h["listing"], h["pinned_snapshot"]), ("delisted", good))
                self.assertNotEqual(store.latest()["q7"]["snapshot"], good)
                self.run_cmd(ad, "parse")                                    # parse keeps the pinned, verified snapshot
                cached = json.loads((store.dir / "parsed" / (REG.safe("q7") + ".json")).read_text())
                self.assertEqual(cached["snapshot"], good)
                latest = dict(store.latest())
                REG.apply_pins(latest, store.snapshots(), {"q7": h})            # same pin in the importer's path (registry.iter_observations)
                self.assertEqual(latest["q7"]["snapshot"], good)
                FakeAdapter.pages["q7"] = (200, "Q7")                        # fresh 200, same identity: cleared
                self.run_cmd(ad, "fetch")
                h = self.hints(store, "q7")
                self.assertNotIn("listing", h)
                self.assertNotIn("pinned_snapshot", h)
                self.assertTrue(h["verified_at"])
                self.run_cmd(ad, "fetch")
                self.assertEqual(ad.fetched, [], "a revalidated ref is an ordinary done ref again")

    def test_published_lifecycle_and_dates(self):
        e = IMP.Ent("robot-vacuums", "model", "roborock")
        e.obs = {("store", "q7", "sha:1"), ("store", "q7", "sha:2"), ("csa", "x", "sha:3")}
        w = type("W", (), {"ents": [e]})()
        seen = {("store", "sha:1"): "2026-10-01T05:00:00Z", ("store", "sha:2"): "2026-11-02T05:00:00Z", ("csa", "sha:3"): "2026-11-20T00:00:00Z"}
        IMP.mark_delisted({"rv": w}, {("store", "q7"): "2026-11-26"}, seen)
        self.assertEqual(e.extra["listing"], {"state": "delisted", "since": "2026-11-26", "sources": ["store"], "last_verified": "2026-11-02"})
        lc = V.lifecycle_of("current", json.dumps(e.extra))
        self.assertEqual(lc, {"state": "unknown", "listing": "delisted", "delisted_at": "2026-11-26", "last_verified": "2026-11-02"})
        self.assertEqual(V.lifecycle_of("discontinued", json.dumps(e.extra))["state"], "discontinued")
        self.assertEqual(V.lifecycle_of("current", "{}"), {"state": "current"})
        import jsonschema
        sch = json.loads((ROOT / "schemas" / "record.schema.json").read_text())["properties"]["lifecycle"]
        jsonschema.validate(lc, sch)


# ------------------------------------------------------------------------------------------------------------------------------- P1-3
TABLE = ('<table><tbody><tr><th><span>Model</span></th><th><span>E1000LFP</span></th></tr>'
         '<tr><th>Capacity</th><td>1024Wh</td></tr><tr><th>Weight</th><td>29lbs(13.5Kg)</td></tr>'
         '<tr><th>Battery Type</th><td>LiFePo4</td></tr></tbody></table>')
PROD = {"title": "PECRON E1000LFP Portable Power Station 1800W 1024Wh", "body_html": "", "variants": [{"sku": "E1000LFP", "title": "E1000LFP"}]}


class Blob:
    def __init__(self, body):
        self.b = gzip.compress(body)

    def read(self, snapshot, ext):
        return self.b


def snap(src, key):
    return C.Snapshot("sha256:x", C.Ref(src, key, "https://example.invalid/" + key, {}), 200, "t", "u", {})


def pec(page):
    pr = PE.PecronStations().parse(snap(PE.SOURCE, "pecron-e1000lfp"), Blob(json.dumps({"page": page, "product": PROD}).encode()), None)
    return {c["key"]: c.get("value") for c in pr.claims if c["status"] == "known"}


class PecronModelRows(unittest.TestCase):
    def test_own_table(self):
        self.assertEqual(pec(TABLE)["cap.energy_wh"], 1024)

    def test_wrong_model_rows_any_cell_shape(self):
        for head in ('<tr><th>Model</th><td>E2000LFP</td></tr>', '<tr><td>Model</td><td>E2000LFP</td></tr>', '<tr><td>Model</td><th>E2000LFP</th></tr>',
                     '<tr><th><span>Model:</span></th><th><b>E2000LFP</b></th></tr>', '<tr><th>Model No.</th><td>E1000LFP / E2000LFP</td></tr>'):
            page = TABLE.replace('<tr><th><span>Model</span></th><th><span>E1000LFP</span></th></tr>', head).replace("1024Wh", "1920Wh")
            self.assertEqual(pec(page), {}, head)
        page = TABLE + TABLE.replace("E1000LFP", "E2000LFP").replace("1024Wh", "1920Wh")      # a second table for another model: own one kept
        self.assertEqual(pec(page)["cap.energy_wh"], 1024)

    def test_approximations_never_exact(self):
        for w in ("~28.7kg", "~ 28.7kg", "approx.28.7kg", "Approx. 28.7 kg", "about 28.7kg", "Around28.7kg", "28.7kg+", "28.7 kg about",
                  "28.7 kg (approx.)", "≈28.7kg"):
            self.assertNotIn("phys.weight", pec(TABLE.replace("29lbs(13.5Kg)", w)), w)
        self.assertEqual(pec(TABLE)["phys.weight"], 13.5)
        self.assertFalse(PE.APPROX.search("100V~120V Pure Sine Wave"))


# ------------------------------------------------------------------------------------------------------------------------------- others
class CoverageGuardFailsClosed(unittest.TestCase):
    def test_baselines(self):
        import contextlib
        with tempfile.TemporaryDirectory() as td:
            new = Path(td) / "n.json"; new.write_text(json.dumps({"categories": {}}))
            bad = Path(td) / "b.json"; bad.write_text("{not json")
            err = io.StringIO()
            with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(err):
                self.assertEqual(G.main(["--new", str(new), "--ref", "no-such-ref-r11"]), 2)
                self.assertEqual(G.main(["--new", str(new), "--old", str(Path(td) / "missing.json")]), 2)
                self.assertEqual(G.main(["--new", str(new), "--old", str(bad)]), 2)
                self.assertEqual(G.main(["--new", str(new), "--ref", "no-such-ref-r11", "--bootstrap"]), 0)
            self.assertIn("--bootstrap", err.getvalue())


class NitecoreTitles(unittest.TestCase):
    ROW = ('<div class="spec-key"><span>Output</span></div><div class="spec-value"><span>USB-C: 5V⎓3A (15W MAX)</span></div>'
           '<div class="spec-key"><span>Capacity</span></div><div class="spec-value"><span>10,000mAh 3.85V (38.5Wh)</span></div>')

    def parse(self, head, key="nb10000"):
        return N.NitecorePowerbanks().parse(snap(N.SOURCE, key), Blob((head + self.ROW).encode()), None)

    def test_contradictory_titles_absent(self):
        pr = self.parse('<meta property="og:title" content="NITECORE NB10000 Energy Brick"><h1>NB20000 Gen3</h1>')
        self.assertEqual(pr.identifiers, [])
        self.assertIn("contradictory page titles", pr.absences[0]["reason"])
        pr = self.parse('<title>NITECORE NB20000 Gen3</title><meta property="og:title" content="NITECORE NB10000">')     # title order irrelevant
        self.assertEqual(pr.identifiers, [])

    def test_agreeing_titles(self):
        pr = self.parse('<meta property="og:title" content="NITECORE NB10000 Energy Brick"><h1>NITECORE NB10000</h1><title>NB10000 - Store</title>')
        self.assertEqual([i["value"] for i in pr.identifiers if i["scheme"] == "mfr_model"], ["NB10000"])


class KuxiuAvsTextLevel(unittest.TestCase):
    def test_any_layout(self):
        for h, gone, kept in (("<p>USB-C: PD 3.0, AVS 9V-15V⎓2.67A, PPS 3.3-21V⎓3A</p>", "9V-15V", "PPS 3.3-21V"),
                              ("<table><tr><td>AVS</td><td><span>9-15V⎓3A</span></td></tr><tr><td>PPS</td><td>3.3-21V</td></tr></table>", "9-15V", "3.3-21V"),
                              ("<li>EPR AVS: 15V-28V⎓5A</li><li>PPS: 5-21V</li>", "15V-28V", "5-21V"),
                              ("text AVS:9V–15V⎓2.67A; PPS 3.3-11V", "9V", "PPS 3.3-11V")):
            out = K.drop_avs(h)
            self.assertNotIn(gone, out, h)
            self.assertIn(kept, out, h)
        self.assertEqual(K.drop_avs("Charging Protocol: PD 3.2 / SPR AVS"), "Charging Protocol: PD 3.2 / SPR AVS")   # protocol name, no figure


class Pins(unittest.TestCase):
    def test_reissued_pending_and_pinned(self):
        import yaml
        d = yaml.safe_load((ROOT / "data/decisions/policies.yaml").read_text())
        act = {p["id"]: p for p in d["claim_policies"]}
        ret = {p["id"]: p for p in d["retired_policies"]}
        for new, old, mod in (("claim/mfr-power-stations-pecron@2", "claim/mfr-power-stations-pecron@1", "pecron_stations"),
                              ("claim/mfr-power-banks-nitecore@2", "claim/mfr-power-banks-nitecore@1", "nitecore_powerbanks"),
                              ("claim/mfr-chargers-kuxiu@2", "claim/mfr-chargers-kuxiu@1", "kuxiu_chargers")):
            p = act[new]
            a = p["approval"]
            self.assertIn(a["state"], ("pending", "approved"))
            if a["state"] == "approved":
                self.assertTrue(a.get("by") and a.get("at"))
            self.assertEqual(p["audit"]["parsers"], {f"{mod}@2": REG.parser_fingerprint(mod)})
            self.assertEqual(p["match"]["extractors"], [f"{mod}@2"])
            self.assertEqual(ret[old]["retired"]["superseded_by"], new)
            self.assertNotIn(old, act)
            self.assertEqual({k: v for k, v in p["match"].items() if k != "extractors"}, {k: v for k, v in ret[old]["match"].items() if k != "extractors"})


if __name__ == "__main__":
    unittest.main()
