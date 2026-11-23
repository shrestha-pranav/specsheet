# Laptop merchants (US) - aliases/prices only, never identity

Retailers rename configs; use them to harvest the ID in the MPN/model field and the UPC, then resolve against the manufacturer catalogue (identity.md).
- Best Buy: carries retailer-specific SKU numbers + `Model` (MTM / HP product no. / Apple part no.). Official products API exists (key required); best US coverage.
- Amazon: ASIN + `Item model number`; titles noisy, third-party configs (RAM/SSD swaps) common; scrape-restricted, treat as alias source only.
- Costco / Walmart / Sam's: exclusive configs, often model-code-only in the title (Lenovo `82xx...`, HP `15-fd...`).
- Newegg, B&H, Micro Center: show manufacturer part number prominently (good for exact match).
- Manufacturer stores (Lenovo.com US, HP.com, Dell.com, Apple.com/shop): configurators; prices/configs but Akamai-protected (Lenovo, HP, Dell).
- Not probed this round (budget: no Bright Data); ranked next: Best Buy, Newegg, B&H.
