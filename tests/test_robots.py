#!/usr/bin/env python3
"""crawler/robots.py RFC 9309 matcher + crawl.Net wiring (A3-rob r11). Zero real requests: Net gets a fake transport adapter.
Regression: us.eufy.com `Disallow: /*.json` was ignored by urllib.robotparser (no wildcard support) and violated twice."""
import sys, unittest
from pathlib import Path

import requests
from requests.adapters import BaseAdapter

CRAWLER = Path(__file__).resolve().parent.parent / "crawler"
sys.path.insert(0, str(CRAWLER))
import robots as R  # noqa: E402
import crawl  # noqa: E402

EUFY = """User-agent: *
Disallow: /admin
Disallow: /cart
Disallow: /*.json
Disallow: /*.atom
Disallow: /*?*variant=
Sitemap: https://us.eufy.com/sitemap.xml
"""


class Matcher(unittest.TestCase):
    def test_eufy_wildcard(self):
        rb = R.Robots(EUFY)
        for u in ("https://us.eufy.com/products.json", "https://us.eufy.com/products.json?limit=250&page=1",
                  "https://us.eufy.com/products/t2351.json", "https://us.eufy.com/collections/all/products.json",
                  "https://us.eufy.com/products/x?variant=123", "https://us.eufy.com/admin/login"):
            self.assertFalse(rb.allowed(u), u)
        for u in ("https://us.eufy.com/products/t2351", "https://us.eufy.com/sitemap.xml", "https://us.eufy.com/robots.txt",
                  "https://us.eufy.com/products/t2351?view=specs"):
            self.assertTrue(rb.allowed(u), u)
        import urllib.robotparser                      # the old parser got this wrong: keep the regression visible
        old = urllib.robotparser.RobotFileParser(); old.parse(EUFY.splitlines())
        self.assertTrue(old.can_fetch("*", "https://us.eufy.com/products.json"))

    def test_dollar_anchor(self):
        rb = R.Robots("User-agent: *\nDisallow: /*.pdf$\nDisallow: /exact$\n")
        self.assertFalse(rb.allowed("https://h.example/manuals/a.pdf"))
        self.assertTrue(rb.allowed("https://h.example/manuals/a.pdf?dl=1"))      # $ = end of the URL path+query
        self.assertTrue(rb.allowed("https://h.example/manuals/a.pdfx"))
        self.assertFalse(rb.allowed("https://h.example/exact"))
        self.assertTrue(rb.allowed("https://h.example/exactly"))

    def test_allow_overrides_disallow(self):
        rb = R.Robots("User-agent: *\nDisallow: /support/\nAllow: /support/manuals/\nAllow: /p\nDisallow: /p$\nAllow: /tie\nDisallow: /tie\n")
        self.assertFalse(rb.allowed("https://h.example/support/faq"))
        self.assertTrue(rb.allowed("https://h.example/support/manuals/x.pdf"))  # longer Allow wins
        self.assertFalse(rb.allowed("https://h.example/p"))                     # longer Disallow ('/p$', 3) beats Allow '/p' (2)
        self.assertTrue(rb.allowed("https://h.example/page"))
        self.assertTrue(rb.allowed("https://h.example/tie"))                    # equal length: Allow wins

    def test_group_selection(self):
        txt = ("User-agent: *\nDisallow: /\n\nUser-agent: Googlebot\nAllow: /\n\n"
               "User-agent: specsheet-crawler\nUser-agent: otherbot\nDisallow: /private\nSitemap: /s.xml\nDisallow: /tmp\n")
        rb = R.Robots(txt)
        self.assertTrue(rb.allowed("https://h.example/products/a"))             # our group replaces '*', not merged with it
        self.assertFalse(rb.allowed("https://h.example/private/a"))
        self.assertFalse(rb.allowed("https://h.example/tmp/a"))                 # Sitemap does not end the group
        other = R.Robots(txt, agent="somebot")
        self.assertFalse(other.allowed("https://h.example/products/a"))         # fallback to '*'
        self.assertTrue(R.Robots("User-agent: SpecSheet-Crawler/0.1\nDisallow:\n").allowed("https://h.example/x"))   # empty Disallow
        self.assertTrue(R.Robots("User-agent: Googlebot\nDisallow: /\n").allowed("https://h.example/x"))            # no group for us

    def test_percent_encoding_and_status(self):
        rb = R.Robots("User-agent: *\nDisallow: /a%7eb\nDisallow: /%E4\n")
        self.assertFalse(rb.allowed("https://h.example/a~b/c"))
        self.assertFalse(rb.allowed("https://h.example/%e4x"))
        self.assertTrue(R.Robots.from_response(404, "").allowed("https://h.example/anything"))
        self.assertFalse(R.Robots.from_response(503, "").allowed("https://h.example/anything"))
        self.assertFalse(R.Robots.from_response(None, "").allowed("https://h.example/anything"))
        self.assertTrue(R.Robots.from_response(503, "").allowed("https://h.example/robots.txt"))


class Fake(BaseAdapter):
    """routes: url -> (status, body, headers). Records every request that reached the 'network'."""
    def __init__(self, routes):
        super().__init__()
        self.routes, self.seen = routes, []

    def send(self, request, **kw):
        self.seen.append(request.url)
        status, body, headers = self.routes.get(request.url, (404, "", {}))
        r = requests.Response()
        r.status_code, r._content, r.url, r.request = status, body.encode(), request.url, request
        r.headers.update(headers)
        r.encoding = "utf-8"
        return r

    def close(self):
        pass


class NetWiring(unittest.TestCase):
    def setUp(self):
        self.mode = crawl.crawl_mode
        crawl.crawl_mode = lambda url: "agent"
        self.net = crawl.Net()
        self.fake = Fake({
            "https://us.eufy.com/robots.txt": (200, EUFY, {}),
            "https://us.eufy.com/products/t2351": (200, "<html>ok</html>", {}),
            "https://us.eufy.com/go": (301, "", {"Location": "/products.json"}),
            "https://us.eufy.com/old": (301, "", {"Location": "https://other.example/new"}),
            "https://other.example/robots.txt": (200, "User-agent: *\nDisallow: /new\n", {}),
        })
        self.net.s.mount("https://", self.fake)

    def tearDown(self):
        crawl.crawl_mode = self.mode

    def test_disallowed_url_never_requested(self):
        self.assertEqual(self.net.get("https://us.eufy.com/products.json?limit=250&page=1", 0), "robots")
        self.assertNotIn("https://us.eufy.com/products.json?limit=250&page=1", self.fake.seen)
        self.assertEqual(self.net.get("https://us.eufy.com/products/t2351", 0).status_code, 200)

    def test_redirect_hops_checked(self):
        self.assertEqual(self.net.get("https://us.eufy.com/go", 0), "robots")         # same-host hop into a wildcard Disallow
        self.assertNotIn("https://us.eufy.com/products.json", self.fake.seen)
        self.assertEqual(self.net.get("https://us.eufy.com/old", 0), "robots")        # cross-host hop: the target host's robots.txt
        self.assertIn("https://other.example/robots.txt", self.fake.seen)
        self.assertNotIn("https://other.example/new", self.fake.seen)

    def test_robots_redirect_followed(self):
        self.fake.routes["https://r.example/robots.txt"] = (301, "", {"Location": "/robots-us.txt"})
        self.fake.routes["https://r.example/robots-us.txt"] = (200, "User-agent: *\nDisallow: /*.json$\n", {})
        self.assertFalse(self.net.allowed("https://r.example/a.json"))
        self.assertTrue(self.net.allowed("https://r.example/a.json?x=1"))

    def test_crawl_delay_group_and_effective_delay(self):
        txt = "User-agent: *\nCrawl-delay: 5\nDisallow: /x\n\nUser-agent: specsheet-crawler\nCrawl-delay: 2\nDisallow: /y\n"
        self.assertEqual(R.Robots(txt).crawl_delay, 2)                      # our group's value
        self.assertEqual(R.Robots(txt, agent="otherbot").crawl_delay, 5)    # '*' fallback
        self.assertIsNone(R.Robots("User-agent: *\nDisallow: /x\n").crawl_delay)
        self.fake.routes["https://ww2.arb.ca.gov/robots.txt"] = (200, "User-agent: *\nCrawl-delay: 5\n", {})
        self.assertEqual(self.net.crawl_delay("https://ww2.arb.ca.gov/a", 1), 5)        # max(robots, ours)
        self.assertEqual(self.net.crawl_delay("https://us.eufy.com/a", 1), 1)
        sleeps = []
        real = crawl.time.sleep
        crawl.time.sleep = lambda s: sleeps.append(s)
        try:
            self.fake.routes["https://ww2.arb.ca.gov/a"] = (200, "a", {})
            self.fake.routes["https://ww2.arb.ca.gov/b"] = (200, "b", {})
            self.net.get("https://ww2.arb.ca.gov/a", 1)
            self.net.get("https://ww2.arb.ca.gov/b", 1)                 # through Net.get: waits ~5 s, not 1
            self.assertTrue(sleeps and max(sleeps) > 4, sleeps)
            sleeps.clear()
            self.net.s.get("https://ww2.arb.ca.gov/a")                  # adapter calling the session directly: same floor
            self.assertTrue(sleeps and max(sleeps) > 4, sleeps)
        finally:
            crawl.time.sleep = real

    def test_low_level_helper_refused(self):
        """Adapters that bypass Net.get (NET.s.get / NET.s.post, e.g. lenovo_psref's token POST) still hit policy and robots."""
        crawl.crawl_mode = lambda url: "human_only" if "asus.com" in url else "agent"
        for call in (lambda: self.net.s.get("https://www.asus.com/us/p"), lambda: self.net.s.post("https://www.asus.com/api", json={}),
                     lambda: self.net.s.get("https://www.asus.com/robots.txt")):
            with self.assertRaises(crawl.Refused) as cm:
                call()
            self.assertEqual(cm.exception.why, "policy")
            self.assertIsInstance(cm.exception, requests.RequestException)
        self.assertEqual(self.net.get("https://www.asus.com/us/p", 0), "policy")
        self.assertFalse([u for u in self.fake.seen if "asus.com" in u], "a human_only host is never contacted, not even robots.txt")
        with self.assertRaises(crawl.Refused) as cm:
            self.net.s.get("https://us.eufy.com/products.json")
        self.assertEqual(cm.exception.why, "robots")
        self.assertNotIn("https://us.eufy.com/products.json", self.fake.seen)

    def test_live_policy_human_only(self):
        """The real data/source-policy.yaml: every exact-match crawl: human_only host is refused by the shared transport, and nothing reaches it."""
        import yaml
        crawl.crawl_mode = self.mode
        doc = yaml.safe_load((CRAWLER.parent / "data" / "source-policy.yaml").read_text())
        hosts = [e["domain"] for e in doc["sources"] if e.get("crawl") == "human_only" and e.get("match", "exact") == "exact" and "/" not in e["domain"]]
        if not hosts:
            self.skipTest("no human_only host in this policy version")
        for h in hosts:
            url = f"https://{h}/some/page"
            self.assertEqual(crawl.crawl_mode(url), "human_only", url)
            with self.assertRaises(crawl.Refused):
                self.net.s.get(url)
            self.assertEqual(self.net.get(url, 0), "policy")
        self.assertFalse([u for u in self.fake.seen if any(h in u for h in hosts)])

    def test_curl_transport_hops(self):
        """crawl.Net.curl_get (surface.py's Microsoft Store transport): curl never follows redirects itself; every hop is checked + paced."""
        import subprocess, types
        routes = {"https://us.eufy.com/products/t2351": (301, b"", "https://us.eufy.com/products/t2351.json"),
                  "https://us.eufy.com/a": (302, b"", "/products/t2351"), "https://us.eufy.com/products/t2351?x": (200, b"<html>ok</html>", "")}
        routes["https://us.eufy.com/products/t2351"] = (200, b"<html>ok</html>", "")
        routes["https://us.eufy.com/b"] = (301, b"", "https://us.eufy.com/products/t2351.json")
        calls = []
        def fake_run(cmd, capture_output=True):
            self.assertNotIn("-L", cmd)
            url = cmd[-1]; calls.append(url)
            code, body, loc = routes.get(url, (404, b"", ""))
            return types.SimpleNamespace(stdout=body + f"\n{code}\n{loc}".encode(), returncode=0)
        real = subprocess.run
        subprocess.run = fake_run
        try:
            self.assertEqual(self.net.curl_get("https://us.eufy.com/a", 0), (200, b"<html>ok</html>"))
            self.assertEqual(calls, ["https://us.eufy.com/a", "https://us.eufy.com/products/t2351"])
            calls.clear()
            self.assertEqual(self.net.curl_get("https://us.eufy.com/b", 0), (0, b""))          # hop into Disallow: /*.json refused
            self.assertEqual(calls, ["https://us.eufy.com/b"])
            calls.clear()
            crawl.crawl_mode = lambda url: "human_only" if "asus" in url else "agent"
            self.assertEqual(self.net.curl_get("https://www.asus.com/x", 0), (0, b""))
            self.assertEqual(calls, [])
        finally:
            subprocess.run = real

    def test_redirect_hop_policy(self):
        crawl.crawl_mode = lambda url: "human_only" if "other.example" in url else "agent"
        self.assertEqual(self.net.get("https://us.eufy.com/old", 0), "policy")
        self.assertNotIn("https://other.example/new", self.fake.seen)


if __name__ == "__main__":
    unittest.main()
