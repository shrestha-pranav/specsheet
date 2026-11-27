# Chargers: merchant / evidence-source notes (A2, 2026-11-24)

Retail listings are aliases only (team rule). Nothing below was scraped; deal titles are handled by scripts/match.py, not by crawling.

| source | status | notes |
|---|---|---|
| Amazon / Best Buy / Walmart / Target | not a source | Listing titles are aliases; the matcher maps them to maker model numbers. |
| ChargerLAB | blocked (robots) | robots.txt disallows ClaudeBot/anthropic-ai (power-banks round); measured PDO tests would be the `measured` tier. |
| USB-IF certified products | not probed | would verify PD/EPR certification (TID), the obvious next T0 source. |
| voltme.com | blocked | products.json 403, not retried (no workarounds). |
| cablematters.com | blocked | robots.txt disallow. |

## r11 (A2-chg, 2026-11-26): maker-site terms audit, new stores, regulators

Provisional dispositions are in data/source-policy.yaml 2026-11-26.9 (`note: provisional r11, licensing review later`).

| host | crawl | why |
|---|---|---|
| www.belkin.com, s3.belkin.com | human_only | terms-of-use.html bars data mining, robots and similar data-gathering tools |
| www.choetech.com, www.hypershop.com, www.aukey.com, plugable.com, www.nekteck.com | human_only | Shopify-template terms bar spiders/crawlers/scrapers |
| satechi.net | human_only | Permitted Use is personal and non-commercial only |
| www.baseus.com | human_only | systematic or automated data collection barred (also affects A2-bat) |
| www.otterbox.com, www.esrtech.com, gonimble.com, www.lention.com | human_only | personal/non-commercial use only, or a no-automation clause |
| kuxiu.com | agent | robots allow /products; terms have no automated-access clause. New adapter kuxiu_chargers (4 models) |
| www.nativeunion.com, www.mophie.com | agent | reproduction clauses only, no automated-access clause |
| www.spigen.com | agent, no adapter | 2 car chargers with prose-only specs; robots.txt prompt text ignored |
| regulations.doe.gov (DOE CCMS) | human_only (blocked) | robots.txt returned 403; not retried, no other fetcher used |
| cacertappliances.energy.ca.gov (CEC MAEDBS) | not a source | terms allow public use with credit, but its battery-charger and UPS tables contain no EPS (external power supply) data |

Anker, INIU, UGREEN, CUKTECH and SHARGE were already human_only (A2-bat, 2026-11-26.7). Values already stored from human_only hosts are still
published under claim/mfr-chargers-structured@4 and are not refetched. That needs a coordinator/owner ruling. AUKEY, Plugable and Nekteck
pages carry specs in images or prose only. Torras and LISEN identify products by Amazon ASIN/FNSKU, which is not a maker model; not built.
Zendure, Scosche, ZAGG and Twelve South have no plain wall chargers. EcoFlow RAPID chargers sit on a human_only host.
