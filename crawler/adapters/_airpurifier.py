"""Shared, pure helpers for the air-purifiers adapters (research/air-purifiers/). No network.

- brand_id(): certifier brand strings -> canonical brand id. The alias table is an identity decision (research/air-purifiers/identity.md):
  only spellings of ONE brand owner are folded (Coway / Coway Airmega / AIRMEGA; Honeywell / "Honeywell(TM) by Kaz" = the Kaz licence;
  Dreo / Dreo Home). Relabel brands that share a certification (AROEVE / BREEZOME / KLOUDIC all filing MK01A) are NOT folded: a different
  brand is a different product line even when the hardware is declared identical.
- model_ok(): a model string must contain a digit and a letter-or-digit run of >= 3 (rejects ES 'W' / 'B' slot rows and names like 'Kilo').
- norm(): the importer's mfr_model normalisation (upper, no spaces) used for grouping certifier rows per (brand, model).
- shared_list_snapshot(): certifier adapters (ENERGY STAR, CARB) fetch ONE list per run; each per-model ref then gets its own snapshot
  record pointing at that same content-addressed blob (no second request), so the importer's one-ref-one-observation contract holds.
"""
import html, re, time
import _contract as C

BRAND_ALIASES = {
    "coway airmega": "coway", "airmega": "coway", "coway airmega, coway, coway": "coway", "coway co., ltd.": "coway",
    "honeywell by kaz": "honeywell", "honeywell": "honeywell",
    "dreo home": "dreo", "blueair ab": "blueair", "medify air": "medify", "medify air, llc": "medify", "medifyair": "medify",
    "iqair": "iqair", "levoit": "levoit", "sharkninja operating llc": "shark", "goveelife": "govee", "pure code": "purecode",
    "black + decker": "black_decker", "black+decker": "black_decker", "black & decker": "black_decker",
}
BRAND_NAMES = {"coway": "Coway", "honeywell": "Honeywell", "dreo": "Dreo", "blueair": "Blueair", "medify": "Medify Air", "iqair": "IQAir",
               "levoit": "Levoit", "winix": "Winix", "shark": "Shark", "govee": "Govee", "purecode": "PureCode", "black_decker": "BLACK+DECKER",
               "lg": "LG", "samsung": "Samsung", "dyson": "Dyson", "alen": "Alen", "molekule": "Molekule", "airdoctor": "AirDoctor",
               "germguardian": "GermGuardian", "rabbit air": "Rabbit Air", "sharp": "Sharp", "midea": "Midea", "cuckoo": "CUCKOO"}
NOT_PURIFIER = re.compile(r"hand ?dryer|air ?condition|heat pump|furnace|\bduct|hvac|ceiling|mini.?split|dehumidif|refrigerat|vacuum|"
                          r"\bfan coil|air handler|range hood|\bdryer\b", re.I)


def clean(s):
    return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", str(s or "")))).strip()


def brand_id(raw):
    b = re.sub(r"[™®©]", "", clean(raw)).lower()
    b = re.sub(r"\s+", " ", re.sub(r"[.,\s]+$", "", b)).strip()
    return BRAND_ALIASES.get(b, b)


def norm(model):
    return re.sub(r"\s+", "", str(model or "")).upper()


def model_ok(m):
    m = str(m or "").strip()
    return bool(re.search(r"\d", m) and re.search(r"[A-Za-z0-9]{2,}", m) and len(re.sub(r"\W", "", m)) >= 3 and len(m) <= 40
                and not re.search(r"[*#]", m))


def num(s):
    m = re.search(r"-?\d[\d,]*(?:\.\d+)?", str(s or ""))
    return float(m.group(0).replace(",", "")) if m else None


def intish(x):
    return int(x) if x is not None and float(x).is_integer() else x


def shared_list_snapshot(store, ref, list_key, adapter, ext):
    """Snapshot record for `ref` pointing at the latest stored list blob (taken by discover). No network."""
    rec = store.latest().get(list_key)
    now = time.strftime("%FT%TZ", time.gmtime())
    if rec is None:
        s = C.Snapshot("sha256:", ref, "no_list_snapshot", now, ref.url, {})
        store.append(s, adapter, ext)
        return s
    s = C.Snapshot(rec["snapshot"], ref, 200, rec["fetched_at"], rec["final_url"], {"etag": rec.get("etag"), "last_modified": rec.get("last_modified")})
    store.append(s, adapter, ext)
    return s


def noise_claims(text):
    """'22–52dB' / '22~52 dB(A)' -> [(value, fan_speed)] for range ends; '27 dB' alone -> [] (caller decides the speed from its own label)."""
    t = clean(text).replace("～", "~")
    m = re.fullmatch(r"(?:approx\.?\s*)?(\d{1,2}(?:\.\d)?)\s*(?:dB\s*(?:\(A\))?)?\s*[-–~to]+\s*(\d{2}(?:\.\d)?)\s*dB\s*(\(A\)|A)?", t, re.I)
    if not m:
        return []
    lo, hi = float(m.group(1)), float(m.group(2))
    if not (10 <= lo < hi <= 80):
        return []
    return [(intish(lo), "range_min"), (intish(hi), "range_max")]
