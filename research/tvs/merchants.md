# TVs: merchants (US, A2 2026-11-23) - not scraped this round
Role: retailer data = aliases, MPN candidates, prices, availability; never primary identity (team rule). Retailer-exclusive model strings
(Costco/Sam's `QN65S92FAF`-style, Best Buy `65QM85`, LG `A`-channel `OLED65C4AUA`) are separate models unless the maker declares them
identical (research/tvs/identity.md); a retailer saying "same as" is not corroboration.
- Best Buy: public Products API (free key; coordinator): model number + SKU + UPC + spec list; the cheapest bulk MPN/UPC join for the
  Best Buy-exclusive strings (Insignia/Toshiba/TCL QM85 lines). Not used (no key).
- Costco / Sam's Club: channel-exclusive designations (Samsung S92/S93, LG `A`/`G` channel letters); listing pages bot-protected; capture as
  aliases with market + channel tag only when a maker/ES source declares the equivalence.
- Amazon: ASIN + title, unreliable MPN; Fire TV editions (Insignia, Amazon Omni) are maker-branded models; Bright Data not used.
- Walmart: Onn/Vizio/Hisense walmart-only strings; site bot-protected; not probed.
- B&H / Crutchfield: clean MPN + UPC in schema.org JSON-LD, tolerant of plain fetch (verify robots before use); good for Sony (sony.com
  blocked: manufacturers.yaml).
- RTINGS (reviews, not a merchant): panel subtype per size, measured zones/brightness/input lag; JS-rendered, ToS; curated claims only.
- Blocked/unprobed: sony.com (403). No retailer was fetched.
- Round 2 (A2, 2026-11-23): DOE CCMS (regulations.doe.gov certification data, cross-brand TV power, the best source for non-ENERGY-STAR sets) is
  BLOCKED: robots.txt and the certification-data page both return 403 to the crawler UA. Recorded, no workaround. A DOE bulk export downloaded by a
  human, or another DOE-hosted open-data route, would be the way in. Hisense: server HTML has no spec table (client-side AEM API, 504/refused) ->
  not built. Vizio built from its own pages (manufacturers.yaml).
