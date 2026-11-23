# Power strips: identity rules (A2, 2026-11-22)

Levels: **family** (Tripp Lite Protect It!/Isobar, APC Essential/Performance SurgeArrest, CyberPower Essential/Professional) >
**model** (the manufacturer model number; this is the primary key) > **configuration** (same model, color/cord suffix) > **package** (multi-pack).
Retail titles and ASINs are aliases only. Amazon "Item model number" is usually the real model; the ASIN (B0...) is never the model.

## Per-brand model schemes
| Brand | Scheme | Decode |
|---|---|---|
| Tripp Lite | TLP1008TEL, TLP1208TELTV, ISOBAR6ULTRA, IBAR6ULTRAUSBB, SPS406HGULTRA, PS-/SK-/DRS- | TLP + outlets(2 digits) + cord ft(2 digits, "08"=8ft) + feature suffix (TEL=phone, TV=coax, USB, B=black, W=white, HG=hospital grade, RA=right angle, OEM=bulk). ISOBAR + outlets + tier (ULTRA/ULTRAUSB). Waber industrial: 3SP, 6NX6. Datasheet states "MODEL NUMBER". |
| APC | P11VNT3, P8GT, PH6U4, PE6U3, P7BT | P + outlets (+ letters) ; V=video, T=tel, N=network/coax, 3 = 3 protected line types; trailing digit/letters: color/cord/USB. Regional suffix -> US sku has no suffix; EU adds -GR/-FR, so filter NEMA only. |
| CyberPower | CSB7012, CSP1208U, CSHB06U, P1208U, B1208P | CSB/CSP/CSHB = strip/surge families; digits: outlets then cord ft ("7012" ~ 7 outlets, 12 ft); trailing U=USB, W=white, P=plug-in. |
| Belkin | BSV804TT, BE112230-08, SRA005 | BSV/BE prefix; "-08" suffix = 8 ft cord; BE11xxxx-nn = series + cord length. |
| Anker | A9131, A9123 | A + 4 digits; color encoded by last digit-letter variants (A9131111 white vs black). |
| Jasco GE / Philips | GE 5-digit (85780, 87434); Philips SPS3413G/37 | GE: each color/cord a separate 5-digit; Philips: SPS#### + "/37" market suffix (37 = US). |
| Furman / Panamax | M-8x2, PST-2+6, MR4300 | Series letters + outlet counts. |
| Austere | 3S-PS4-US2 | series(3S/5S)-product-region+rev. |
| Kasa | HS300, KP303, KP200 | Fixed model; hardware version (v1/v2) matters, region (US) suffix. |

## Variant grouping rules
1. Group key = brand + model number with *cosmetic* suffix stripped only if the brand documents it as cosmetic (Tripp Lite B/W color,
   Belkin -08 cord). When the suffix changes a spec (cord length, outlet count, joules, USB), it is a different **model**, not a variant.
2. Cord length: if brand encodes it in the number (TLP1008=8ft, Belkin -08), treat each as its own model but share a **family** row
   so the UI can show "also available in 4/6/12 ft". Never merge across cord lengths when comparing joules per dollar.
3. Color / finish: variants of one model (same electrical spec). Keep as `configuration` with color field.
4. Multi-pack ("2-pack"): `package` level; per-unit specs identical to the single. CyberPower Multi-Pack Surge, Amazon Basics 2-pack, Anker bundles.
5. Hospital-grade (HG), right-angle (RA), OEM bulk: distinct models (HG changes the plug/receptacle rating); OEM is a packaging alias.
6. Revisions: UL file stays same but joules/clamping may change between revisions (UL 1449 3rd -> 4th ed.): record `revision` when brand states it (Kasa v2).

## Mapping Amazon-style titles to model numbers
- Pull regex candidates from the title with the brand's id_regex (manufacturers.yaml), then confirm against the catalogue index (exact
  SKU hit beats fuzzy). Ignore ASINs. Titles like "Tripp Lite 10 Outlet Surge Protector 8ft Cord 2395 Joules" => fuzzy-match on
  (brand, outlets, cord, joules) triple against the official records; accept only a unique hit, else queue for review.
- Brand-only generic listings (Amazon Basics, UGREEN no model in title) -> use "Item model number" / manufacturer part number field.
- Marketing traps: "surge protector" that is actually a UL 1363 relocatable power tap with no surge suppression (no joules, no
  UL 1449 let-through rating); "8 outlets" counting USB ports; "4000J" for multi-pack sums; "1875W" is 15A x 125V and is the same for every 15A strip.

## Certification as cross-brand key
UL file number (E-xxxxxx) + model is the authoritative check on UL 1449 (surge) / UL 1363 (taps) listing; see merchants.md for access.

## Learned from the full crawls (round 2, 2026-11-22; 249 Tripp Lite datasheets, 293 CyberPower products)
Evidence: `raw/tripplite/parsed/*.json`, `raw/cyberpower/parsed/*.json` (claims keyed to spec-profile.yaml).
1. **Outlet count and cord length are model-defining, not variants.** TLP1008TEL (10 outlets, 8 ft, 2395 J, 120 kA) vs TLP1208TEL
   (12 outlets, 8 ft, 2160 J, 144 kA): the number is `TLP` + outlets + cord ft + features, and *joules moved the wrong way* with more
   outlets. So never infer specs of a sibling from a model-number pattern; each model number is its own record, grouped only into a family.
2. **Cord length**: encoded in the number on Tripp Lite (TLP606 = 6 outlets / 6 ft; ISOBAR6ULTRA = 6 outlets, 6 ft implied; TLP825 = 8 outlets / 25 ft),
   in the CyberPower B-series (B604 = 4 ft cord, B608 = 8, B615 = 15, B625 = 25, B6012 = 12 ft/6 outlets) and the Belkin suffix (-08). Rule: cord length is
   a **configuration axis only when joules, outlets, breaker and standard are identical** (CyberPower B602RC1 / B603RC1 / B604 differ in joules 500/600/600 and
   surge current, so they are separate models). The profile's `cord.length_ft` is therefore a per-record spec, and the family page shows a "cord lengths" strip.
3. **Color / cosmetic suffix** (CyberPower BK, GY, DBL, HPK, PK, TL; Tripp Lite B/W/CW/S; Waber "SK"): same electrical spec, **but listing text can differ per
   color page** (CyberPower B602RC1 states UL 1449 3rd Ed, B602RC1BK only UL 1363, B602RC1GY both). Keep each color its own *configuration*
   with its own claims; a resolver may inherit from the model only when no per-configuration claim exists, and must surface the disagreement as `conflicted`.
4. **Pack count**: CyberPower multipack SKUs (suffix `...2PK`, `...MP2`, category Multi-Pack Surge 38 products) are `package` level;
   per-unit specs copy from the single-unit model. Never multiply joules by pack count (a pack's "2 x 600 J" is not 1200 J).
5. **Hyphen and spacing aliases are the same model**: CyberPower lists both `CPS1215RMS` and `CPS-1215RMS` (one has no data), Tripp Lite `PS-606-HG` and
   `PS606HG`, CyberPower `6050 Black` / `6050 Silver` (legacy numeric models whose *joules differ by color*: 1500 vs 900 J, so those are two models).
   Normalise identifiers case/space/hyphen-insensitively for matching, but keep `value_raw`.
6. **Suffix meanings that change the electrical product** (separate model): HG hospital grade (Tripp Lite PS-6xx-HG), RA right-angle plug, OEM bulk packaging
   (alias, same spec), RMS rack mount, T/TEL telephone line, USB/UAM/CUBE USB ports, GF/SA series names. Treat OEM as packaging alias only.
7. **Discontinued** is prominent: 166 of 293 CyberPower items sit in the Discontinued category (and carry the sparsest data). Keep a `status` per record;
   the UI should default to current models. Tripp Lite datasheets do not state lifecycle.
8. **Joule gap = category signal**: 159 of 249 Tripp Lite datasheets and 235 of 293 CyberPower pages state joules; the rest are plain UL 1363 strips, so a missing
   `surge.joules` is usually `not_published`/plain strip, not unknown. Use `type.kind` from UL 1449 vs UL 1363 listing text, not the product title.
9. **Model number is not always printed in the title**: Tripp Lite titles lead with "Protect It! 10-Outlet..." and put `MODEL NUMBER:` on the datasheet; CyberPower uses
   `acf.model` (which can contain spaces: "6050 Black"). UPC (`gtin`) is Tripp Lite-only in the datasheet table; CyberPower REST item does not carry it.

## Round 3 (2026-11-22): crawl.py brands + colour grouping (crawler/adapters/crawlpy_strips.py)
- Belkin: model = sku with a trailing colour code stripped (BE106000-04-BLK -> BE106000-04, BSV300ttCW -> BSV300tt); cord/rotating/commercial suffixes (-06R, -06-CM) stay separate
  models (joules differ). A colour page keeps its own claims on the *configuration* (BLK page says 700 J, base page 720 J -> `conflicted`); a model with no page of its own inherits
  its colour page's claims. `PK` is a pack suffix (5PK), not pink. Anker: model = A#### from the URL, `A9183123` sku = configuration. Shopify brands: first variant SKU = model, other variants = configurations.
- Scope gate: multi-outlet "extension cords" without surge/strip in the title, smart plugs, lighting, power banks, USB-only chargers and 230 V Furman units are excluded (reasons counted by `python3 -I crawler/adapters/crawlpy_strips.py`).
