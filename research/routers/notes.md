# Routers: who publishes what (US, probed 2026-11-23)

Evidence: 106 TP-Link + 60 NETGEAR + 82 ASUS pages fetched and parsed; FCC lookups sampled (3). Profile: spec-profile.yaml (76 specs, 10 groups).

## Publishers and opacity
- **ASUS (V)**: the most honest table: per-band rate, per-band streams (5GHz 4x4 / 2.4GHz 3x3), flash + RAM, VPN incl. WireGuard, AiMesh. Still no SoC vendor/model.
- **NETGEAR (V on routers, thin on Orbi Wi-Fi 7)**: per-band rate+streams+width+QAM and CPU cores/GHz in one 'WiFi Technology' cell on classic Nighthawk pages; newer pages
  expose 6 JSON-LD headline properties only.
- **TP-Link (V)**: class + per-band rate + ports + VPN; never streams (only '4 Streams' total), never RAM/flash/SoC; the only maker with a US hardware-version list and
  firmware history with dates (a support-length signal: derive 'latest release', never 'supported until').
- **Not tested**: eero, Google Nest, Linksys, Ubiquiti, Synology, GL.iNet: see manufacturers.yaml. GL.iNet (Shopify products.json) is the cheapest next adapter.
- **FCC**: fccid.io device pages fetchable (honest UA, robots allow) and list exhibits; fcc.gov EAS and fcc.report are blocked (403/Cloudflare). Chipset is in photo/PDF exhibits, not text.

## Opacity (tier=core in the profile)
Spatial streams vs 'AX5400', per-band PHY, 160/320 MHz, which port is 2.5G/10G and whether it is the WAN, backhaul type (tri-band != dedicated backhaul),
SoC vendor+model, RAM, flash, hardware version, firmware support window. Official pages never state the last four except ASUS RAM/flash.

## Policy results (data/decisions/policies.yaml, claim/mfr-routers-structured@1 and claim/mfr-routers-class@1)
247 trusted model rows (TP-Link 106, NETGEAR 60, ASUS 81; 1 ASUS page had no model identifier), 166 preview rows (fetch-time price, firmware date, free-text keys stay candidates).
Per-band rates, streams (explicit NxN only), 160/320 widths (320 only with a 6 GHz radio) are accepted; SoC/RAM/FCC remain unknown except ASUS RAM/flash.

## Deferred / needs a human
- Per-hardware-version specs for TP-Link (needs a browser/XHR probe of the version switcher; not plain HTTP).
- FCC internal photos / test reports to name the chipset (image reading; terms of fccid.io unverified).
- OpenWrt Table of Hardware dump for hw.soc_model/ram/flash per revision (licence decision).
- A published 'support until' per brand (eero/Google publish one; others only a firmware history).

## Coordinator ruling 1 (2026-11-24): `wifi.has_6ghz` false from a complete band list (A2 preset fill)
- **Rule.** False is written only when the maker's own structured spec section enumerates every band and 6 GHz is not among them. The
  claim carries the condition `basis: complete_enumeration` (profile `conditions` + has_6ghz `basis_conditions`) and keeps the list as raw.
  Prose, marketing bullets, partial tables, "up to" phrasing, "Tri-band" alone or a missing row never give false; True needs only a 6 GHz
  band named in a spec row. Shared check: `_router.band_enum` (every GHz figure in the cell is a band token, both 2.4 and 5 GHz present,
  no up to / or / optional hedge, a stated Dual/Tri/Quad-Band count equals the radios listed).
- **Lists used.** NETGEAR two-cell spec table 'WiFi Bands' / 'Simultaneous Dual-Band WiFi ...' (every band row of the page must be such a
  list; the Orbi 870 MLO row and beamforming bullets only ever say True); ASUS 'Operating Frequency'; TP-Link 'Frequency', or 'WiFi Speeds'
  when its per-band rates sum to the class number within 3 % (BE3600 = 2882 + 688); Ubiquiti per-radio groups (MIMO, Max. Data Rate, TX
  power, antenna gain) naming the same radios; GL.iNet 'Wi-Fi Speed' when the rates sum to the title's class number (GL-MT3600BE: no class, unknown).
- **NETGEAR rates.** Per-band rate/streams from the 'WiFi Bands' row, else the page's own product-attribute record `c_wifiBands` (nearest
  `c_modelNumber` = page model). Orbi 37x/77x/97x pages print only the class (BE5000), so their per-band rates stay unknown.
- Still unknown: Wi-Fi-less gateways (Ubiquiti UDM/UCG/EFG, GL.iNet Brume/Puli/Collie) sit in the router preset denominator with unknown
  generation; no maker row says "no Wi-Fi", so nothing is written (needs a not_applicable ruling, not a parser).
