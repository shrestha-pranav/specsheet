# Chargers: merchant / evidence-source notes (A2, 2026-11-24)

Retail listings are aliases only (team rule). Nothing below was scraped; deal titles are handled by scripts/match.py, not by crawling.

| source | status | notes |
|---|---|---|
| Amazon / Best Buy / Walmart / Target | not a source | Listing titles are aliases; the matcher maps them to maker model numbers. |
| ChargerLAB | blocked (robots) | robots.txt disallows ClaudeBot/anthropic-ai (power-banks round); measured PDO tests would be the `measured` tier. |
| USB-IF certified products | not probed | would verify PD/EPR certification (TID), the obvious next T0 source. |
| voltme.com | blocked | products.json 403, not retried (no workarounds). |
| cablematters.com | blocked | robots.txt disallow. |
