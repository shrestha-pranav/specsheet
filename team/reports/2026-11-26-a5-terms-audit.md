# A5 r11 terms audit of crawl:agent hosts (2026-11-26). Proposals: team/queue/terms-audit-r11.yaml (policy not edited)
Scope: 48 agent hosts with evidence none/search against policy .9 (12 hosts already handled by A2-chg/A2-bat were skipped). Fetched robots.txt, homepage and terms with the crawler UA at about 1 req/s, robots checked before each page. No workaround and no other fetcher for blocked hosts. WebSearch was used once, only to find the TP-Link terms URL. No Bright Data.
Basis codes: A = automated access/scraping barred; B = site licence limits use to personal non-commercial (se.com/satechi standard); R = robots.txt blocks Claude agents with Disallow: /; X = blocked.
Result: 33 flips to human_only, citing 39,132 published values. 15 hosts stay agent with their evidence upgraded to fetched.

Flips to human_only, with published values citing each host:
- A: www.asus.com 10841, rog.asus.com 3651, www.tp-link.com 3927, us.tcl.com 2088, www.netgear.com 481 (contested, see below), levoit.com 64, byjasco.com 0, austere.com 0
- B: www.sandisk.com 2605, documents.sandisk.com 124, www.vizio.com 1922, www.dell.com 1418, www.dreametech.com 542, www.gl-inet.com 508, us.mova.tech 265, www.irobot.com 119, learn.microsoft.com 18, www.microsoft.com 0, www.razer.com 0
- R: www.winixamerica.com 307 (also B); amazon.com 0; 9to5toys.com 0
- X (evidence: blocked): www.cyberpowersystems.com 4929 (AWS WAF challenge), assets.tripplite.com 4898 (tripplite.com redirects to Eaton, which sends Akamai 403), www.kingston.com 425 (Cloudflare challenge on pages)
- Retail/review, free false, 0 values: slickdeals.net, techradar.com (Future plc terms), the-gadgeteer.com, furper.com (A); bhphotovideo.com, androidauthority.com, gizmochina.com (403), switchchargers.com (timeout) (X)

Stay agent: ww2.arb.ca.gov, techspecs.ui.com, www.benq.com, us.roborock.com, www.teamgroupinc.com, images.teamgroupinc.com, furmanpower.com, smartgadgetkit.com, en.best-batteries.com, plus 6 document_host CDNs (inherit the linking page).

Open questions for the coordinator:
1. Netgear s12 bars "automated tools ... web crawlers" and names NETGEAR websites. That contradicts the 2026-11-25.5 reading (subscription only), under which www.downloads.netgear.com (180 values) and downloads1 stay agent. One ruling should cover all three hosts.
2. These agent hosts have the same terms as a B flip: i.dell.com and www.delltechnologies.com (Dell), download.microsoft.com (Microsoft), static.gl-inet.com (GL.iNet, 7 values).
3. Where does B stop? The .9 decision kept mophie agent on a download/print clause, and I applied the same to furmanpower. The stronger access/use licences are flipped.
4. CARB robots.txt sets Crawl-delay: 5 for all agents, so its fetcher must pace at 5 s or more. Our 1 req/s default breaks it.
5. Roborock's user agreement renders by JS and could not be read. A person should check it.
6. A flip stops new agent fetches only. The roughly 39k stored values follow the parked owner decision (a), as for LG, Samsung and Apple.
Shared files changed: none (2 new files only). Scratch: /tmp/a5audit.
