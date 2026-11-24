# Monitors: who publishes what (US, 2026-11-22)

Evidence base this round: DisplayHDR performance-criteria page (fetched), Dell U3224KB datasheet PDF
(fetched, pdftotext), LG US/UK/CA 27GR95QE-B (search snippets; lg.com/us spec URLs 404 or JS-rendered),
RTINGS pages (fetch returns nav only; JS-rendered), RTINGS TV panel-lottery article (via search). Samsung and
Dell product pages were not fetchable with plain HTTP. Treat per-brand claims below as V (verified) or U.

## Publishers and format
- **Dell (V)**: datasheet PDF per model, clean two-column spec table (panel type, brightness *typical*, color
  gamut %, response "5 ms GtG in Fast mode", per-port version, PD W, tilt/swivel/height degrees, VESA,
  power, weight panel-only and with stand). Warranty section names "Premium Panel Exchange" (replacement even for
  one bright pixel). Model = U3224KB; orderable SKU = 210-xxxx; hardware revision only on rear label.
- **LG (V, partial)**: US page has marketing copy plus a spec accordion (JS). UK/CA mirrors list
  panel type, DCI-P3 "98.5% typ", "0.03 ms GtG", brightness (200 SDR / 1000 peak HDR10), ports, sync.
  Model suffix -B is the US edition; same family has no-suffix/regional variants.
- **Samsung (U)**: US pages use LS model codes plus "XZA" region tail; spec table is detailed but
  JS-rendered; "Odyssey OLED G6 G60SF" name is a family handle, not a model.
- **ASUS/MSI/Gigabyte/BenQ/ViewSonic/AOC/Acer/HP/Lenovo (U, not fetched)**: all publish HTML spec tables;
  MSI and Acer encode generation in suffix (E2, V5); HP uses #ABA US suffix; Lenovo uses MTM.
- **DisplayHDR (V)**: displayhdr.org/performance-criteria lists tiers (400/500/600/1000/1400, True Black 400-1400);
  the Certified Products list is searchable by company+model, so it is the one structured official source.
  Any "HDR400"/"HDR10" without the DisplayHDR logo is uncertified. DisplayHDR 400 requires only 250 nit and no
  local dimming; tiers 1000+ need 2D local dimming.
- **RTINGS / TFTCentral / PCMonitors.info (U)**: the only source for measured GtG, input lag, PWM, HDR window
  peaks, zone counts, panel vendor, subpixel layout. RTINGS review pages are JS-heavy; plan on their
  results-table tool or hand-curated per-model records, not scraping. ToS likely forbids bulk copy: store
  facts with citation only.
- **Aggregators (DisplaySpecifications, PCPartPicker, Pangoly)**: useful for panel part numbers and size
  rounding (27" marketed = 26.5" viewable); lower trust, tag as secondary.
- **FCC / rear label / EDID**: only handles on revision, FCC ID photos show label REV; EDID product ID differs
  between revisions often. Energy Star product finder keyed by model gives power.

## Hidden / gamed specs (needs tier=core)
Panel vendor/part (never printed), native vs OC refresh, response basis (GtG vs MPRT vs fast-mode),
DisplayHDR certified vs claimed, zone counts, gamut basis (area vs volume, typ vs min), bit depth with FRC,
which input port does full refresh, DSC, USB-C PD real wattage, dead-pixel/OLED burn-in warranty.

## Revision handling
- Identity levels: family > model > **revision** > package. Model number plus region suffix is the primary key;
  revision is optional and added only when evidence (rear label REV, EDID id, panel part, review note) shows
  difference. Never merge two revisions' specs silently: keep claims tagged with the revision they came from.
- Specs hinted at revision-level: panel.vendor, panel.part_number, panel.generation, sup.firmware_current,
  gen.hw_revision, sup.fcc_id.
- Panel lottery evidence: RTINGS found one Samsung TV model with 3 sizes from 3 panel makers (AUO/Samsung/Sharp)
  identified by version code, modest differences; blogs claim larger variance on monitors (unverified).
- Region: US wants model + suffix (-B, XZA, #ABA); EU/UK SKUs differ in warranty and sometimes panel.

## Open questions
1. How to ingest RTINGS-style measured data without scraping (manual curated, or API)?
2. VESA certified list: confirm whether a JSON/CSV endpoint exists behind the page.
3. Should motion.gtg_measured etc. be claim-kind "measured" with a `source_class` in the record format (A3)?
4. TVs sold as monitors (Samsung Odyssey/LG OLED) overlap with the TV category.

## Zero-fill audit (A2, 2026-11-24)
- `flk.pwm`: ASUS techspec ("Flicker-free: Yes"), LG ("Flicker Safe: Yes") and Lenovo PSREF (certification cell "TÜV Rheinland Flicker
  Free") print explicit flicker-free statements; the adapters left them unmapped. Now mapped by research/monitors/label-mapping.yaml to
  flk.pwm = none as an official maker declaration (claim/monitor-flicker-label-map@1). No source publishes a PWM frequency.
  Dell, BenQ and MSI have no monitor adapter yet (P1 brand work), so their flicker-free claims are not ingested.
- `usb.usbc_pd_w`: dropped where the maker prints it. ASUS "USB-C Power Delivery: N W" was read only on pages with bare I/O lines (fixed
  via label-mapping); Lenovo PSREF writes "up to 90W PD" (number before "PD") which lenovo_monitors@1 misses (~60 models). That needs an
  adapter fix + re-issuing claim/mfr-monitor-structured@2 and rel/source-stated-hierarchy@2 (lenovo_monitors@1 is pinned in both): not done.

## Preset fill (A2, 2026-11-24): coordinator rulings 1 and 3
- **Ruling 1 (complete-enumeration negatives).** `usb.usbc_inputs` = 0 only when the maker's own structured port section is the full
  list (ASUS techspec I/O Ports lines, Lenovo PSREF Rear/Side/Left/Right/Front/Top/Bottom Ports, BenQ Connectivity rows with counts, LG
  Input/Output group), it names a video input, and no USB-C/Thunderbolt port on it takes video. The claim carries
  `{basis: complete_enumeration}` and the list as raw. Any other USB-C mention on the page (accessory cable, "DP/Type-C" in a signal
  frequency row, a stray "USB-C:" row) voids the zero: ASUS XG32UQWMS lists DP + HDMI only but its frequency row names Type-C.
  Positive counts need video evidence (Alt Mode / DisplayPort / Thunderbolt; LG: DP Alternate Mode, a USB-C PD or max-resolution row);
  a USB-C line of unknown role, "Thunderbolt 4 x 2 (Daisy Chain)" and "one upstream, one downstream" write nothing.
  LG "USB Up-stream: Yes (via USB-C)" without video evidence (25G590B-B) stays unknown: a data upstream port is not a video input.
- **Ruling 3 (size class).** A printed class is taken as stated; otherwise the class is derived from the printed diagonal, round half up
  (profile `gen.size_class` note; `_monports.DERIVATION`). BenQ fractional "Screen Size" values (23.8") used to be published as the class
  itself; they are now the derived whole-inch class.
- `flk.pwm` Lenovo: already mapped by label-mapping (TÜV Rheinland Flicker Free in Other/Ergonomic Certifications, 67 of 195 PSREF pages).
  The other "flicker" hits are the MPRT note ("you may notice a negligible flicker"), which is not a flicker-free statement. Nothing added.
