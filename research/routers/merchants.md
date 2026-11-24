# Routers: maker-site access (A2 coverage r2, 2026-11-24; one polite GET each, crawler UA)
- eero (eero.com/shop/<model>): 200, robots allows /shop. Not parsed yet.
- Ubiquiti techspecs.ui.com: 200; product pages carry __NEXT_DATA__ with a structured `technicalSpecification` tree (labelled features + values).
  Best structured router source found; the gateway SKUs (UCG/UDR/UX) are the router-category rows. No adapter built yet.
- GL.iNet (www.gl-inet.com, Shopify): 200, robots explicitly allows product HTML. Not parsed yet.

## A2 coverage r3 (2026-11-24; crawler UA, 1 req/s, robots respected)
- Ubiquiti techspecs.ui.com: no robots.txt served (path returns the app shell) = nothing disallowed. Adapter `ubiquiti_routers@1` (source
  ubiquiti-us-routers): 2 listing pages -> 53 product pages (all cloud gateways + Wi-Fi AP collections; bridges/AirWire/travel router dropped).
  The tree names CPU cores ("Quad-core ARM Cortex-A53"), never the SoC part: SoC stays unknown for Ubiquiti.
- GL.iNet www.gl-inet.com: robots allows product HTML and /products.json (the robots file also carries agent-marketing text: ignored). Adapter
  `glinet_routers@1`: products.json -> 45 router handles, 35 with a Specifications table (10 legacy pages have none). Names SoC vendor, often the part.
  Comparison tables on the same pages are never read.
- eero eero.com/shop/<model>: 200, robots allows (Content-Signal ai-train=no). NOT parsed: the page carries only Wi-Fi generation, an aggregate
  speed and coverage, and no maker model number (identity rule fails). Revisit via eero support/spec pages if they print model numbers.
