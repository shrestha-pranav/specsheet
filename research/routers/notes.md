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
