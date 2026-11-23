# Air purifiers: merchants and blocked sources (US, A2 2026-11-23) - no retailer scraped this round
Role: retailer data = aliases, prices, availability; never identity. A retailer "compatible filter" list is not a filter pairing.
- **AHAM Verifide directory: BLOCKED for us.** ahamverifide.org (robots allows) links to www.ahamdir.com/room-air-cleaners/, an Angular app whose
  data comes from an undocumented POST API on gbs.trutesta.io (Intertek). The one attempt to call it was refused by the tool policy; recorded,
  not retried, no workaround. Way in: a human-downloaded export (the directory UI offers xlsx), or AHAM permission for the API.
- Amazon / Walmart / Target / Home Depot: bot-protected listing pages, not probed; Bright Data not used.
- Best Buy Products API (free key, coordinator): MPN + UPC join for Insignia / retailer-exclusive strings.
- Costco: club-exclusive Coway/Levoit/Winix strings (Winix AT41, C909 vs C545-type siblings). Separate models unless the maker declares identity.
- Filter prices: only the maker's own store pairing (Winix Replacement Filter tab) is used; dated, list vs sale kept apart.
