#!/usr/bin/env python3
"""RFC 9309 robots.txt matcher (A3-rob r11). Replaces urllib.robotparser, which ignores the `*` and `$` path wildcards: us.eufy.com
`Disallow: /*.json` was read as a literal prefix and violated twice. No dependencies (scripts/corrections.py imports it too).

  group   the group(s) whose user-agent product token equals ours (case-insensitive; all such groups merged), else the `*` group(s), else
          no rules. A run of consecutive user-agent lines opens one group; Sitemap and unknown lines do not end a group.
  match   a rule matches when its pattern matches the start of path[?query]; `*` = any run of characters, a trailing `$` = end of URL.
          Percent-encoding is normalised on both sides (RFC 9309 2.2.2, review-11): non-ASCII characters are UTF-8 percent-encoded,
          escapes of unreserved characters are decoded, other escapes upper-cased -- so `/%61` == `/a` and `/café` == `/caf%C3%A9`.
          Empty `Disallow:` is no rule.
  verdict the longest matching pattern wins, measured in normalised octets (a %XX escape is one octet; `/%61` and `/a` are both 2);
          on a tie Allow wins; no match = allowed. /robots.txt itself is always allowed.
  delay   `Crawl-delay: N` of the selected group(s) (max) -> .crawl_delay; crawl.Net waits max(its delay, N) between requests to the host.
  fetch   (policy for callers, `from_response`) 2xx -> parse; 4xx -> unavailable = allow all; 5xx / network error -> unreachable = disallow all.

Scope (review-11 item 6): this module and crawl.Net govern *crawling* -- requests to manufacturer / retailer / registry hosts for product data.
These out-of-crawler network calls are deliberately NOT crawling and are exempt from robots.txt (no change; listed so the exemption is explicit):
  scripts/corrections.py fetch_issues   `gh api` GET of our own GitHub repo's issues (authenticated API use under GitHub's API terms)
  scripts/requests_weekly.py            `gh issue list` against our own repo (missing-product requests)
  scripts/backup.sh                     curl push to our own Uptime Kuma heartbeat (monitoring, not a content fetch)
  scripts/corrections.py intake hosts   GitHub issue-attachment downloads (the submitter's own upload; still policy-checked per hop)
Anything that fetches third-party content must go through crawl.Net or this checker with its real UA (corrections.py robots_ok does).
"""
import re
import urllib.parse

AGENT = "specsheet-crawler"          # product token of crawl.UA
MAX_BYTES = 500 * 1024               # RFC 9309 2.5: parse at least 500 KiB


def _norm(s):
    """RFC 9309 2.2.2: UTF-8 percent-encode non-ASCII, decode escapes of unreserved characters and upper-case the rest, so /a%7Eb == /a~b,
    %2f == %2F and /café == /caf%C3%A9."""
    s = "".join(c if c.isascii() else "".join(f"%{b:02X}" for b in c.encode("utf-8", "surrogatepass")) for c in s)

    def fix(m):
        ch = chr(int(m.group(1), 16))
        return ch if (ch.isascii() and (ch.isalnum() or ch in "-._~")) else "%" + m.group(1).upper()
    return re.sub(r"%([0-9A-Fa-f]{2})", fix, s)


def octets(p):
    """Length of a normalised pattern in octets: each %XX escape counts once (the ranking key; RFC 9309 compares octets, not spelling)."""
    return len(re.sub(r"%[0-9A-F]{2}", "%", _norm(p)))


def _pattern(p):
    p = _norm(p)
    end = p.endswith("$")
    body = p[:-1] if end else p
    return re.compile("".join(".*" if c == "*" else re.escape(c) for c in body) + ("$" if end else ""), re.S)


class Robots:
    def __init__(self, text="", agent=AGENT, allow_all=False, disallow_all=False):
        self.agent = agent.lower()
        self.allow_all, self.disallow_all = allow_all, disallow_all
        self.rules = []      # [(length, allow, compiled, raw)]
        self.crawl_delay = None   # seconds, from the selected group(s) (max); not in RFC 9309 but widely used and we honour it
        if text:
            self._parse(text[:MAX_BYTES])

    @classmethod
    def from_response(cls, status, text, agent=AGENT):
        if status is None or status >= 500:
            return cls(agent=agent, disallow_all=True)
        if 400 <= status < 500:
            return cls(agent=agent, allow_all=True)
        return cls(text if 200 <= status < 300 else "", agent=agent)

    def _parse(self, text):
        groups, cur, in_agents = [], None, False
        for line in text.splitlines():
            line = line.split("#", 1)[0].strip()
            if ":" not in line:
                continue
            k, v = (x.strip() for x in line.split(":", 1))
            k = k.lower()
            if k == "user-agent":
                if not in_agents:
                    cur = {"agents": [], "rules": []}
                    groups.append(cur)
                    in_agents = True
                cur["agents"].append(v.lower())
            elif k in ("allow", "disallow"):
                in_agents = False
                if cur is not None and v:
                    cur["rules"].append((k == "allow", v))
            elif k == "crawl-delay":
                in_agents = False
                try:
                    d = float(v)
                except ValueError:
                    continue
                if cur is not None and 0 <= d < 86400:
                    cur["delay"] = max(cur.get("delay") or 0, d)
        def token(a):
            return re.split(r"[/\s]", a, 1)[0]
        mine = [g for g in groups if any(token(a) == self.agent for a in g["agents"])]
        chosen = mine or [g for g in groups if "*" in g["agents"]]
        delays = [g["delay"] for g in chosen if g.get("delay") is not None]
        self.crawl_delay = max(delays) if delays else None
        for g in chosen:
            for allow, raw in g["rules"]:
                self.rules.append((octets(raw), allow, _pattern(raw), raw))

    def verdict(self, url):
        """-> (allowed, rule) where rule is the deciding raw pattern or None."""
        sp = urllib.parse.urlsplit(url)
        path = (sp.path or "/") + ("?" + sp.query if sp.query else "")
        if sp.path == "/robots.txt":
            return True, None
        if self.disallow_all:
            return False, "(robots.txt unreachable)"
        if self.allow_all:
            return True, None
        path = _norm(path)
        best = None
        for length, allow, rx, raw in self.rules:
            if rx.match(path) and (best is None or length > best[0] or (length == best[0] and allow and not best[1])):
                best = (length, allow, raw)
        return (True, None) if best is None else (best[1], best[2])

    def allowed(self, url):
        return self.verdict(url)[0]


if __name__ == "__main__":       # python3 -I crawler/robots.py ROBOTS_FILE URL...
    import sys
    rb = Robots(open(sys.argv[1]).read())
    for u in sys.argv[2:]:
        print(rb.verdict(u), u)
