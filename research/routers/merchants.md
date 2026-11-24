# Routers: maker-site access (A2 coverage r2, 2026-11-24; one polite GET each, crawler UA)
- eero (eero.com/shop/<model>): 200, robots allows /shop. Not parsed yet.
- Ubiquiti techspecs.ui.com: 200; product pages carry __NEXT_DATA__ with a structured `technicalSpecification` tree (labelled features + values).
  Best structured router source found; the gateway SKUs (UCG/UDR/UX) are the router-category rows. No adapter built yet.
- GL.iNet (www.gl-inet.com, Shopify): 200, robots explicitly allows product HTML. Not parsed yet.
