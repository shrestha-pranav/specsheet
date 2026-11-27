#!/usr/bin/env python3
"""Zigbee2MQTT device-definition adapter v1 (contract ARCHITECTURE 15.5) for category smart-home. A2-home r12.

Source   : Koenkk/zigbee-herdsman-converters (MIT), the device database Zigbee2MQTT ships: src/devices/index.ts imports one module per
           vendor file (src/devices/<vendor>.ts); each file exports `definitions`, a list of object literals with model (the maker's model id,
           IKEA E1743, Aqara RTCGQ11LM), vendor, description, zigbeeModel (the model id string the device itself reports), whiteLabel
           (rebadged siblings) and exposes / extend (what Zigbee2MQTT exposes for the paired device).
           Host raw.githubusercontent.com (data/source-policy.yaml path /Koenkk/zigbee-herdsman-converters/: kind measurement, crawl agent;
           robots.txt 404 = no rules; GitHub ToS D.8 public repository contents; MIT). Every GET goes through crawl.Net (robots + Crawl-delay
           on every hop), DELAY 1.5 s on top.
discover : GET index.ts (ref '_index'), then every imported vendor file (ref '_file_<name>'), one stored snapshot each (raw TypeScript as
           served). Definitions are cut out of the file text by a brace scanner (no TS evaluation). One ref per (brand, normalised model).
fetch    : no network; a snapshot record per ref pointing at its vendor-file blob.
parse    : pure; re-cuts the definition from the stored file. Rules (research/smart-home/spec-profile.yaml):
  - identity: mfr_model = Z2M `model` as written, issuer = brand slug of `vendor`. A slash list ('E1524/E1810') stays ONE key (Z2M says
    the strings are one device); each token is a model_variant alias (preview), never a second key. zigbeeModel strings = alias
    kind device_reported_model. whiteLabel entries = alias kind white_label (other brand's rebadge), never an entity of their own here.
  - generic chip ids are not maker models: vendor Tuya with a TS0xxx / TS1xxx / TS0601_* model, and any model without a digit, mint nothing.
  - conn.protocols = [zigbee] (the definition exists because the device speaks Zigbee). compat.zigbee2mqtt = true.
  - exposes -> capability booleans (sensor.occupancy, sensor.illuminance, sensor.temperature, sensor.humidity, sensor.contact,
    sensor.water_leak, sensor.smoke, sensor.vibration, power.metering, power.battery, ctl.light, ctl.color, ctl.color_temp, ctl.on_off,
    ctl.cover, ctl.lock, ctl.thermostat, ctl.action) and gen.device_type (rule table DEVICE_TYPE, first match). A definition whose exposes
    are fully static (no arrow/function, no spread of a variable, no unknown helper) is a COMPLETE enumeration: a capability it does not
    list is false (basis complete_enumeration, raw = the token list). Otherwise only true is written (absent = unknown).
  - power.source: battery when the definition exposes battery / battery_low / voltage-of-battery; never 'mains' (Z2M does not state it).
Usage    : python3 -I crawler/adapters/zigbee2mqtt_devices.py discover|fetch|parse|run
"""
import json, re, sys, time, unicodedata
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
import _contract as C
from _contract import Ref, Discovery, ParseResult, claim  # noqa
import _run

ID, VERSION, SOURCE = "zigbee2mqtt_devices", 1, "zigbee2mqtt-devices"
ADAPTER = f"{ID}@{VERSION}"
BASE = "https://raw.githubusercontent.com/Koenkk/zigbee-herdsman-converters/master/src/devices/"
REPO = BASE          # refs and cited sources are the raw file URL: the host source-policy lists (github.com/blob is unlisted)
DELAY = 1.5
STAGE = "adapter"


# ---------------------------------------------------------------- text scanning (pure)
def _skip_str(t, i):
    q = t[i]
    i += 1
    while i < len(t):
        c = t[i]
        if c == "\\":
            i += 2; continue
        if c == q:
            return i + 1
        i += 1
    return i


def strip_comments(t):
    """Blank out // and /* */ comments (strings kept), so braces and keys inside comments never count. Length preserved."""
    out, i, n = list(t), 0, len(t)
    while i < n:
        c = t[i]
        if c in "\"'`":
            i = _skip_str(t, i); continue
        if t.startswith("//", i):
            j = t.find("\n", i)
            j = n if j < 0 else j
            out[i:j] = " " * (j - i); i = j; continue
        if t.startswith("/*", i):
            j = t.find("*/", i + 2)
            j = n if j < 0 else j + 2
            out[i:j] = [ch if ch == "\n" else " " for ch in t[i:j]]; i = j; continue
        i += 1
    return "".join(out)


def _match(t, i):
    """index just past the bracket closing the one at t[i]."""
    pairs = {"{": "}", "[": "]", "(": ")"}
    stack, n = [], len(t)
    while i < n:
        c = t[i]
        if c in "\"'`":
            i = _skip_str(t, i); continue
        if c in pairs:
            stack.append(pairs[c])
        elif c in ")]}":
            if not stack or stack.pop() != c:
                return -1
            if not stack:
                return i + 1
        i += 1
    return -1


MODEL_KEY = re.compile(r"(?<![\w.])model\s*:\s*([\"'])((?:\\.|(?!\1).)*)\1")


def top_keys(obj):
    """{key: value text} for the top-level properties of an object literal '{...}'."""
    out, i, n, depth, start, key = {}, 1, len(obj) - 1, 0, 1, None
    seg = []
    while i < n:
        c = obj[i]
        if c in "\"'`":
            i = _skip_str(obj, i); continue
        if c in "{[(":
            depth += 1
        elif c in "}])":
            depth -= 1
        elif c == "<" and i and (obj[i - 1].isalnum() or obj[i - 1] == "_"):     # TS generic m.numeric<"cluster", Attrs>(...)
            j = obj.find(">", i)
            if j > 0 and "(" not in obj[i:j] and ";" not in obj[i:j]:
                i = j + 1; continue
        elif c == "," and depth == 0:
            seg.append(obj[start:i]); start = i + 1
        i += 1
    seg.append(obj[start:n])
    for s in seg:
        m = re.match(r"\s*([A-Za-z_$][\w$]*)\s*:\s*(.*)\Z", s, re.S)
        if m:
            out[m.group(1)] = m.group(2).strip()
        elif re.match(r"\s*\.\.\.", s):
            out.setdefault("__spread__", []).append(s.strip())
        if not m:
            out.setdefault("__items__", []).append(s.strip())
    return out


def definitions(text):
    """-> [object-literal text] for every definition in a vendor file: the innermost object containing a top-level `model: "..."`
    together with `vendor:` (a whiteLabel entry also has model + vendor, so it is excluded by requiring it is not inside another one)."""
    t = strip_comments(text)
    objs, seen = [], set()
    for m in MODEL_KEY.finditer(t):
        # walk back to the opening brace of the enclosing object
        depth, j = 0, m.start() - 1
        while j >= 0:
            c = t[j]
            if c in "}])":
                depth += 1
            elif c in "{[(":
                if depth == 0:
                    break
                depth -= 1
            j -= 1
        if j < 0 or t[j] != "{":
            continue
        end = _match(t, j)
        if end < 0 or j in seen:
            continue
        seen.add(j)
        objs.append((j, end, t[j:end]))
    # drop objects nested inside another definition object (whiteLabel entries, nested helpers)
    out = []
    for j, end, o in objs:
        if any(a < j and end <= b for a, b, _ in objs):
            continue
        k = top_keys(o)
        if "model" in k and "vendor" in k:
            out.append(o)
    return out


def lit(v):
    m = re.fullmatch(r"\s*([\"'])((?:\\.|(?!\1).)*)\1\s*", v or "", re.S)
    return re.sub(r"\\(.)", r"\1", m.group(2)) if m else None


def lit_list(v):
    if not v or not v.strip().startswith("["):
        return None
    return [re.sub(r"\\(.)", r"\1", m.group(2)) for m in re.finditer(r"([\"'])((?:\\.|(?!\1).)*)\1", v)]


def clean(s):
    return re.sub(r"\s+", " ", str(s or "")).strip()


def brand_id(raw):
    b = unicodedata.normalize("NFKD", re.sub(r"[™®©]", "", clean(raw))).encode("ascii", "ignore").decode().lower().strip(" .,")
    return re.sub(r"[^a-z0-9]+", "_", b).strip("_")


def norm(m):
    return re.sub(r"\s+", "", str(m or "")).upper()


GENERIC = re.compile(r"^(TS\d{3,4}[A-Z]?(_.*)?|TS0601.*)$", re.I)


def generic_reason(vendor, model):
    if not re.search(r"\d", model or ""):
        return "model has no digit (a name, not a model number)"
    if GENERIC.match(model or ""):         # TS0xxx is a Tuya module id whichever vendor files it
        return "Tuya chip/module id (TS0xxx), not a maker model"
    if len(model) > 60:
        return "model string too long"
    return None


# ---------------------------------------------------------------- capability rules
# Over the exposes / extend text: every called helper name (last dotted segment, e.g. m.electricityMeter -> electricitymeter) and every quoted
# expose name (e.binary("water_leak") -> water_leak). 'e.' = zigbee-herdsman exposes presets, 'm.' = modernExtend helpers; vendor helpers
# (adurosmart.extend.motionSensor, colorLight) are matched by name. Device chip temperature (deviceTemperature) is not a room sensor.
CAPS = [
    ("sensor.occupancy", r"^(occupancy|presence|motionsensor|occupancysensor|presencesensor|pir.*|motion)$"),
    ("sensor.illuminance", r"^(illuminance|illuminance_lux|illuminancesensor|lux)$"),
    ("sensor.temperature", r"^(temperature|local_temperature_sensor|temperaturesensor|temperaturehumidity.*)$"),
    ("sensor.humidity", r"^(humidity|humiditysensor|temperaturehumidity.*)$"),
    ("sensor.contact", r"^(contact|doorwindowcontact.*|contactsensor|doorsensor)$"),
    ("sensor.water_leak", r"^(water_leak|waterleak.*|leaksensor)$"),
    ("sensor.smoke", r"^(smoke|smokealarm.*|smokesensor|smoke_detector)$"),
    ("sensor.vibration", r"^(vibration|vibrationsensor)$"),
    ("power.metering", r"^(electricitymeter|power|energy|current|powermeasuringdevice|metering|produced_energy)$"),
    ("power.battery", r"^(battery|battery_low|batterypercentage.*|batteryvoltage|batterywith.*)$"),
    ("ctl.light", r"^(light|light_onoff.*|light_brightness.*|\w*light|ledcontroller.*)$"),
    ("ctl.color", r"^(light_brightness_colorxy|light_brightness_colortemp_colorxy|light_brightness_colortemp_colorhs|light_brightness_colorhs|colorlight|color_xy|color_hs)$"),
    ("ctl.color_temp", r"^(light_brightness_colortemp.*|tunablewhitelight|color_temp|colortemp)$"),
    ("ctl.on_off", r"^(\w*onoff|switch|light|light_onoff.*|light_brightness.*|onoffdevice|powermeasuringdevice|relay|plug|socket|\w*light)$"),
    ("ctl.cover", r"^(cover|cover_?position.*|windowcovering|shade|blind.*|curtain.*|\w*cover)$"),
    ("ctl.lock", r"^(lock|doorlock|lockcontrol)$"),
    ("ctl.thermostat", r"^(climate|thermostat|trv|radiator.*)$"),
    ("ctl.action", r"^(action|commandsonoff|commandslevelctrl|commandsscenes|commandscolorctrl|actionenumlookup|dimmerremote|sceneremote|remote|button.*)$"),
    ("x.siren", r"^(warning|iaswarning|\w*siren\w*|squawk|alarm)$"),
    ("x.air_quality", r"^(co2|pm25|voc|formaldehyd|formaldehyde|air_quality|eco2|pm10)$"),
]
CAPS = [(k, re.compile(rx)) for k, rx in CAPS]
CAP_KEYS = [k for k, _ in CAPS if not k.startswith("x.")]
# gen.device_type: first rule whose capability set matches (order = specificity)
DEVICE_TYPE = [
    ("lock", {"ctl.lock"}), ("thermostat", {"ctl.thermostat"}), ("cover", {"ctl.cover"}),
    ("smoke_sensor", {"sensor.smoke"}), ("water_leak_sensor", {"sensor.water_leak"}),
    ("light", {"ctl.light"}), ("motion_sensor", {"sensor.occupancy"}), ("contact_sensor", {"sensor.contact"}),
    ("vibration_sensor", {"sensor.vibration"}), ("siren", {"x.siren"}), ("air_quality_sensor", {"x.air_quality"}), ("plug_or_switch", {"ctl.on_off"}), ("energy_meter", {"power.metering"}),
    ("climate_sensor", {"sensor.temperature"}), ("climate_sensor", {"sensor.humidity"}), ("remote_or_button", {"ctl.action"}),
]
# a complete (static) enumeration: every top-level item of exposes / extend is a call (method chains .withX(...) allowed) of either an
# e.* / m.* / exposes.* preset or a vendor helper NAMED for what it exposes (ikeaLight, lumiElectricityMeter: its name matches a CAPS rule)
# or for plumbing that exposes no capability (OTA, custom cluster, identify, reset guard). Anything else (tuya.modernExtend.tuyaBase datapoint
# tables, unnamed helpers, variables, spreads, arrow functions, control flow) = not complete: it may add exposes we cannot see.
CALL = re.compile(r"^((?:[A-Za-z_]\w*\s*\.\s*)*)([A-Za-z_]\w*)\s*(?:<[^()]*>)?\s*\((.*)\)((?:\s*\.\s*with\w+\s*\(.*\))*)$", re.S)
PLUMBING = re.compile(r"^(\w*ota|add\w*cluster|\w*cluster|identify|\w*preventreset|\w*configure\w*|\w*reporting|deviceendpoints|"
                      r"\w*powersource|\w*readprimaryversions|readgenbasic\w*|\w*quirk\w*|handle\w*|\w*powercfg\w*|\w*poweronbehavior|"
                      r"\w*backlight\w*|\w*countdown|\w*childlock|\w*switchtype|\w*indicator\w*|\w*led\w*mode)$")


def item_ok(x):
    m = CALL.match(x.strip())
    if not m:
        return False
    prefix, name = re.sub(r"\s+", "", m.group(1)), m.group(2).lower()
    if prefix in ("e.", "m.", "exposes.", "ea."):
        return True
    if name in ("tuyabase", "tuyamagicpacket") or not prefix and name in ("numeric", "binary", "enumlookup"):
        return name not in ("tuyabase", "tuyamagicpacket")
    return any(cap_hit(k, rx, name) for k, rx in CAPS) or bool(PLUMBING.match(name))


def _items(arr):
    arr = (arr or "").strip()
    if not (arr.startswith("[") and arr.endswith("]")):
        return None
    return [x for x in (v.strip() for v in top_keys("{" + arr[1:-1] + "}").get("__items__", [])) if x]


def names_of(txt):
    out = {m.group(1).lower() for m in re.finditer(r"([A-Za-z_]\w*)\s*\(", txt or "")}
    out |= {m.group(2).lower() for m in re.finditer(r"\b(?:e\.(?:binary|numeric|enum|text|list|composite)|binary|numeric|enumLookup|iasZoneAlarm)\s*\(\s*(?:\{\s*name:\s*)?([\"'])(\w+)\2", txt or "")}
    for z in re.findall(r"zoneType\s*:\s*[\"'](\w+)[\"']", txt or ""):
        out.add(z.lower())
    for z in re.findall(r"zoneAttributes\s*:\s*\[([^\]]*)\]", txt or ""):
        out |= {w.lower() for w in re.findall(r"[\"'](\w+)[\"']", z)}
    if re.search(r"\bcolorTemp\s*:", txt or ""):
        out.add("colortemp")
    if re.search(r"\bcolor\s*:\s*(?:true|\{)", txt or ""):
        out.add("color_xy")
    if re.search(r"electricalMeasurements\s*:\s*true", txt or ""):
        out.add("electricitymeter")
    out.discard("devicetemperature")
    out -= {n for n in out if re.match(r"^(light(delay|duration|indicator|sensitivity)|backlight|indicatorlight|nightlight|ledindicator)$", n)}
    return out


def cap_hit(key, rx, n):
    """A helper name hits a capability when the name, or the name minus a vendor prefix (tradfriOccupancy, ikeaBattery, lumiElectricityMeter),
    matches its rule. commandsOnOff / commandsLevelCtrl are what a REMOTE sends: they count as actions only, never as on/off control."""
    if n.startswith("commands"):
        return key == "ctl.action" and bool(rx.match(n))
    m = VENDOR_PREFIX.match(n)
    return bool(rx.match(n) or (m and rx.match(n[m.end():])))


VENDOR_PREFIX = re.compile(r"^(lumi|ikea|tradfri|ewelink|sonoff|philips|tuya|dp|heiman|develco|sengled|ledvance|gledopto|innr|legrand|bosch|"
                           r"sunricher|rm|ra|namron|schneider|inovelli|thirdreality|third|aqara|xiaomi)(?=[a-z])")


def caps_of(d):
    """-> (set of true capability keys incl. x.* helpers, complete?, token text)."""
    k = top_keys(d)
    txt = " ".join(x for x in (k.get("exposes"), k.get("extend")) if x)
    names = names_of(txt)
    found = {key for key, rx in CAPS for n in names if cap_hit(key, rx, n)}
    lists = [k.get(f) for f in ("exposes", "extend") if f in k]
    items = [_items(v) for v in lists]
    complete = bool(lists) and all(i is not None for i in items) and all(item_ok(x) for i in items for x in i) and "__spread__" not in k
    return found, complete, txt


# Fallback when the exposes match no rule (vendor helpers, Tuya datapoint tables): the definition's own description, first match.
DESC_TYPE = [
    ("hub_or_bridge", r"\b(router|bridge|gateway|hub|coordinator|repeater|range extender)\b"), ("lock", r"\block\b"),
    ("thermostat", r"\b(thermostat|trv|radiator|heating)\b"), ("cover", r"\b(curtain|blind|shade|shutter|roller|cover)\b"),
    ("smoke_sensor", r"\b(smoke|twinguard)\b"), ("gas_co_sensor", r"\b(gas (sensor|detector|leakage)|gas and co|co sensor|carbon monoxide|combustible gas|lpg)\b"),
    ("energy_meter", r"\b(energy|power|electricity|clamp|phase) (meter|monitor\w*|consumption)|\bpower-meter|\bclamp meter|\benergy meter\b"),
    ("valve", r"\b(valve|watering timer|irrigation)\b"), ("vibration_sensor", r"\bvibration\b"), ("water_leak_sensor", r"\b(water leak\w*|leak\w*|flood)\b"), ("siren", r"\b(siren|alarm sounder|alarm)$|^alarm\b"),
    ("motion_sensor", r"\b(motion|pir|presence|occupancy)\b"), ("contact_sensor", r"\b(door|window|contact) sensor\b"),
    ("air_quality_sensor", r"\b(air quality|co2|pm2\.5|voc)\b"), ("climate_sensor", r"\b(temperature|humidity)\b"), ("light_sensor", r"\billuminance sensor\b"),
    ("light", r"\b(bulb|lamp|lights?|led strip|led controller|downlight|spot|luminaire|dimmer)\b"),
    ("plug_or_switch", r"\b(plug|socket|outlet|relay|switch|power strip)\b"), ("remote_or_button", r"\b(remote|button|scene controller|keypad)\b"),
]
DESC_TYPE = [(k, re.compile(rx, re.I)) for k, rx in DESC_TYPE]


def desc_type(desc):
    return next((k for k, rx in DESC_TYPE if rx.search(desc or "")), None)


class Zigbee2mqttDevices:
    id, version, source_id, categories = ID, VERSION, SOURCE, {"smart-home"}

    def __init__(self):
        self.store = C.BlobStore(SOURCE)

    def discover(self, checkpoint, net):
        snap, body = C.http_snapshot(self.store, Ref(SOURCE, "_index", BASE + "index.ts", {}), BASE + "index.ts", DELAY, ".ts", ADAPTER)
        if body is None:
            return Discovery([], False, f"index.ts: {snap.status}", checkpoint or {})
        names = sorted(set(re.findall(r"from\s+[\"']\./([\w-]+)[\"']", body.decode("utf-8", "replace"))))
        groups, files, stats = {}, [], {"files": len(names), "definitions": 0, "generic": {}, "white_label": 0, "failed_files": []}
        for name in names:
            url = BASE + name + ".ts"
            s, b = C.http_snapshot(self.store, Ref(SOURCE, f"_file_{name}", url, {}), url, DELAY, ".ts", ADAPTER)
            if b is None:
                stats["failed_files"].append([name, s.status])
                continue
            files.append({"name": name, "snapshot": s.snapshot})
            for d in definitions(b.decode("utf-8", "replace")):
                k = top_keys(d)
                model, vendor = lit(k.get("model")), lit(k.get("vendor"))
                if not model or not vendor:
                    continue
                stats["definitions"] += 1
                stats["white_label"] += len(re.findall(r"\bmodel\s*:", k.get("whiteLabel") or ""))
                why = generic_reason(vendor, model)
                if why:
                    stats["generic"][why] = stats["generic"].get(why, 0) + 1
                    continue
                key = f"{brand_id(vendor)}|{norm(model)}"
                g = groups.setdefault(key, {"brand": brand_id(vendor), "vendor": vendor, "model": model, "file": name, "snapshot": s.snapshot, "n": 0})
                g["n"] += 1
        if stats["failed_files"]:
            return Discovery([], False, f"{len(stats['failed_files'])} vendor files failed", {"files": files})
        refs = [Ref(SOURCE, k, REPO + g["file"] + ".ts", g) for k, g in sorted(groups.items())]
        stats.update(refs=len(refs), duplicate_keys=sum(1 for g in groups.values() if g["n"] > 1))
        return Discovery(refs, True, None, dict(stats, files=files))

    def fetch(self, ref, prior, net):
        now = time.strftime("%FT%TZ", time.gmtime())
        sha = (ref.hints or {}).get("snapshot")
        recs = {r["snapshot"]: r for r in self.store.snapshots() if r.get("status") == 200 and str(r.get("ref", "")).startswith("_file_")}
        rec = recs.get(sha)
        if rec is None:
            s = C.Snapshot("sha256:", ref, "no_file_snapshot", now, ref.url, {})
        else:
            s = C.Snapshot(rec["snapshot"], ref, 200, rec["fetched_at"], ref.url, {"etag": rec.get("etag"), "last_modified": rec.get("last_modified")})
        self.store.append(s, ADAPTER, ".ts")
        return s

    def parse(self, snap, blobs, profile):
        pr = ParseResult()
        h = snap.ref.hints or {}
        if snap.ref.key.startswith("_") or not h.get("model"):
            pr.absences.append({"key": "*", "reason": "index / vendor-file snapshot (per-model refs carry the claims)", "source": "s1"})
            return pr
        idx = _DEFS.get(snap.snapshot)
        if idx is None:                  # one vendor file holds hundreds of refs (tuya.ts): cut it once per snapshot
            idx = {}
            for d in definitions(blobs.read(snap.snapshot, ".ts").decode("utf-8", "replace")):
                k = top_keys(d)
                idx.setdefault((brand_id(lit(k.get("vendor"))), norm(lit(k.get("model")))), []).append(d)
            if len(_DEFS) >= 32:
                _DEFS.pop(next(iter(_DEFS)))
            _DEFS[snap.snapshot] = idx
        return parse_defs(snap, h, idx.get((h["brand"], norm(h["model"]))) or [])


_DEFS = {}


def parse_defs(snap, h, defs):
    pr, obs = ParseResult(), snap.fetched_at
    pr.sources = [{"id": "s1", "url": BASE + f"{h.get('file')}.ts" if h.get("file") else snap.ref.url, "label": f"Zigbee2MQTT device definition ({h.get('file')}.ts, zigbee-herdsman-converters, MIT)",
                   "source_id": SOURCE, "tier": "other", "retrieved_at": obs, "snapshot": snap.snapshot}]
    if not defs:
        pr.absences.append({"key": "*", "reason": "definition not found in the stored vendor file", "source": "s1"})
        return pr
    model, brand = h["model"], h["brand"]
    why = generic_reason(h.get("vendor") or brand, model)
    if why:                              # re-checked on the stored row (discovery ran an earlier rule set)
        pr.absences.append({"key": "*", "reason": why, "source": "s1"})
        return pr
    pr.identifiers.append({"scheme": "mfr_model", "value": model, "value_raw": model, "issuer": brand, "market": None, "package_level": "model",
                           "role": "key", "sources": ["s1"]})
    seen = {norm(model)}

    def alias(text, kind):
        if text and norm(text) not in seen:
            seen.add(norm(text))
            pr.aliases.append({"text": clean(text)[:80], "kind": kind, "source": "s1", "observed_at": obs})

    if "/" in model:
        for tok in model.split("/"):
            if re.search(r"\d", tok):
                alias(tok.strip(), "model_variant")
    descs, caps_all, complete_all, toks = [], [], True, []
    for d in defs:
        k = top_keys(d)
        for z in lit_list(k.get("zigbeeModel")) or []:
            alias(z, "device_reported_model")
        for wl in re.findall(r"model\s*:\s*[\"']([^\"']+)[\"'][^}]*?vendor\s*:\s*[\"']([^\"']+)[\"']", k.get("whiteLabel") or ""):
            alias(f"{wl[1]} {wl[0]}", "white_label")
        for wl in re.findall(r"whitelabel\(\s*[\"']([^\"']+)[\"']\s*,\s*[\"']([^\"']+)[\"']", k.get("whiteLabel") or ""):
            alias(f"{wl[0]} {wl[1]}", "white_label")
        if lit(k.get("description")):
            descs.append(lit(k.get("description")))
        found, complete, txt = caps_of(d)
        caps_all.append(found); complete_all = complete_all and complete; toks.append(txt)
    loc = {"file": f"src/devices/{h.get('file')}.ts", "model": model}
    raw = clean(" ".join(toks))[:280]

    def emit(key, value, unit, r, status="known"):
        c = claim(model, key, value, unit, r, "s1", ADAPTER, STAGE, obs, dict(loc), r, status=status)
        c["kind"] = "reported"        # a third-party integration database, not the maker (schema: reported = third-party assertion)
        pr.claims.append(c)

    if descs:
        alias(descs[0], "certifier_listing")
        emit("gen.description", descs[0][:120], None, f"description: {descs[0]}")
    emit("conn.protocols", ["zigbee"], None, "Zigbee2MQTT device definition (zigbee-herdsman-converters)")
    emit("compat.zigbee2mqtt", True, None, f"Zigbee2MQTT supports {h.get('vendor')} {model}")
    if len(defs) > 1 and len({frozenset(c) for c in caps_all}) > 1:
        complete_all = False         # two definitions of one model disagree: no negatives
    caps = set.intersection(*caps_all) if complete_all else set.union(*caps_all)
    for key in CAP_KEYS:
        if key in caps:
            emit(key, True, None, raw)
        elif complete_all:
            emit(key, False, None, "complete exposes list, no " + key.split(".")[1] + ": " + raw)
    dt = next((t for t, need in DEVICE_TYPE if need <= caps), None)
    if dt:
        emit("gen.device_type", dt, None, f"exposes -> {dt}: {raw[:200]}")
    elif descs and (dt := desc_type(descs[0])):
        emit("gen.device_type", dt, None, f"description -> {dt}: {descs[0]}")
    elif complete_all or descs:
        emit("gen.device_type", "other", None, f"no device-type rule matches the exposes or the description: {(descs or [''])[0]} {raw[:150]}")
    if "power.battery" in caps:
        emit("power.source", "battery", None, raw)
    pr.fingerprints = {"raw": snap.snapshot, "model": model, "definitions": len(defs), "complete_exposes": complete_all,
                       "caps": sorted(caps)}
    return pr


if __name__ == "__main__":
    _run.main(Zigbee2mqttDevices())
