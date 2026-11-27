# smart-home: merchants and blocked sources (US, A2-home 2026-11-26). No retailer scraped this round.
- Retailer data = aliases, prices, availability; never identity. "Works with Matter" / "Works with Alexa" retail badges are aliases, never smart.matter.
- BLOCKED on.dcl.csa-iot.org (CSA Matter DCL REST): robots.txt answers HTTP 501 'Not Implemented'; crawler/robots.py (RFC 9309, r11) treats any 5xx as disallow-all. Not reached through any other fetcher. Ruling needed: RFC 9309 2.3.1.4 allows treating a robots.txt unreachable > 30 days as unavailable (or using a cached copy); r5 fetched it as 'no rules'.
- Bluetooth SIG qualification: robots Disallow /; bluetooth.com Cloudflare; apps.fcc.gov 503: blocked (A5 survey r2). Not contacted.
- Aqara, Apple, Samsung, TP-Link/Tapo: human_only by terms. Not contacted.
- Home Depot / Lowe's / Best Buy / Amazon: not probed; Bright Data not used.
