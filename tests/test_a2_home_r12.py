"""A2-home r12: smart-home category from Zigbee2MQTT device definitions (crawler/adapters/zigbee2mqtt_devices.py). Pure fixtures, no network.

  python3 -m unittest tests.test_a2_home_r12
"""
import json, sys, unittest
from pathlib import Path

CODE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(CODE / "crawler" / "adapters"))
import _contract as C  # noqa: E402
import zigbee2mqtt_devices as Z  # noqa: E402
import yaml  # noqa: E402

FILE = '''
import * as m from "../lib/modernExtend";
// model: "COMMENTED" vendor: "X"   (a comment never makes a definition)
export const definitions: DefinitionWithExtend[] = [
    {
        zigbeeModel: ["TRADFRI motion sensor"],
        model: "E1525/E1745",
        vendor: "IKEA",
        description: "TRADFRI motion sensor",
        fromZigbee: [fz.battery, fz.ikea_occupancy],
        exposes: [e.battery(), e.occupancy(), e.binary("illuminance_above_threshold", ea.STATE, true, false)],
        whiteLabel: [{model: "E1745B", vendor: "IKEA", description: "rebadge"}],
    },
    {
        zigbeeModel: ["lumi.sensor_motion.aq2"],
        model: "RTCGQ11LM",
        vendor: "Aqara",
        description: "Motion sensor",
        extend: [m.battery(), m.occupancy(), m.illuminance()],
    },
    {
        zigbeeModel: ["TS011F"],
        model: "TS011F_plug_1",
        vendor: "Tuya",
        description: "Smart plug (with power monitoring)",
        extend: [tuya.modernExtend.tuyaOnOff({electricalMeasurements: true})],
        whiteLabel: [tuya.whitelabel("Lidl", "HG08673", "Plug", ["_TZ3000_x"])],
    },
    {
        zigbeeModel: ["SP 120"],
        model: "SP 120",
        vendor: "Innr",
        description: "Smart plug",
        extend: [m.onOff(), m.electricityMeter()],
    },
    {
        model: "3RSP02028BZ",
        vendor: "Third Reality",
        description: "Smart plug gen2",
        fingerprint: [{modelID: "3RSP02028BZ"}],
        extend: [m.onOff(), thirdRealityExtend.powerReport()],
        exposes: (device, options) => [e.power()],
    },
];
'''


def snap(h):
    return C.Snapshot("sha256:" + "0" * 64, C.Ref(Z.SOURCE, f"{h['brand']}|{Z.norm(h['model'])}", Z.REPO + "x.ts", h), 200,
                      "2026-11-26T00:00:00Z", Z.REPO + "x.ts", {})


def parse(model, brand):
    h = {"brand": brand, "model": model, "file": "x", "vendor": brand}
    defs = [d for d in Z.definitions(FILE) if Z.norm(Z.lit(Z.top_keys(d)["model"])) == Z.norm(model)]
    return Z.parse_defs(snap(h), h, defs)


def claims(pr):
    return {c["key"]: c for c in pr.claims}


class Adapter(unittest.TestCase):
    def test_definitions_cut_from_text(self):
        models = [Z.lit(Z.top_keys(d)["model"]) for d in Z.definitions(FILE)]
        self.assertEqual(models, ["E1525/E1745", "RTCGQ11LM", "TS011F_plug_1", "SP 120", "3RSP02028BZ"], "comments and whiteLabel entries are not definitions")

    def test_generic_tuya_ids_mint_nothing(self):
        self.assertTrue(Z.generic_reason("Tuya", "TS011F_plug_1"))
        self.assertTrue(Z.generic_reason("Tuya", "TS0601_thermostat"))
        self.assertTrue(Z.generic_reason("Philips", "Hue Bridge"), "a name without a digit is not a model")
        self.assertIsNone(Z.generic_reason("IKEA", "E1743"))
        self.assertIsNone(Z.generic_reason("Aqara", "RTCGQ11LM"))

    def test_slash_list_is_one_key_with_variant_aliases(self):
        pr = parse("E1525/E1745", "ikea")
        keys = [i for i in pr.identifiers if i["role"] == "key"]
        self.assertEqual([(k["scheme"], k["value"], k["issuer"]) for k in keys], [("mfr_model", "E1525/E1745", "ikea")])
        al = {(a["text"], a["kind"]) for a in pr.aliases}
        self.assertTrue({("E1525", "model_variant"), ("E1745", "model_variant"), ("TRADFRI motion sensor", "device_reported_model"),
                         ("IKEA E1745B", "white_label")} <= al)

    def test_complete_enumeration_writes_false_lux_flag_is_not_lux(self):
        c = claims(parse("E1525/E1745", "ikea"))
        self.assertIs(c["sensor.occupancy"]["value"], True)
        self.assertIs(c["sensor.illuminance"]["value"], False, "illuminance_above_threshold is a day/night flag, not lux")
        self.assertIs(c["power.metering"]["value"], False)
        self.assertEqual(c["gen.device_type"]["value"], "motion_sensor")
        self.assertEqual(c["power.source"]["value"], "battery")
        self.assertEqual(c["conn.protocols"]["value"], ["zigbee"])
        self.assertTrue(all(x["kind"] == "reported" for x in c.values()), "community database: claim kind reported, never official")
        self.assertEqual(parse("E1525/E1745", "ikea").sources[0]["tier"], "other")

    def test_modern_extend_static_list_is_complete(self):
        c = claims(parse("RTCGQ11LM", "aqara"))
        self.assertIs(c["sensor.illuminance"]["value"], True)
        self.assertIs(c["ctl.light"]["value"], False)
        c = claims(parse("SP 120", "innr"))
        self.assertEqual(c["gen.device_type"]["value"], "plug_or_switch")
        self.assertIs(c["power.metering"]["value"], True)
        self.assertNotIn("power.source", c, "Z2M never states mains")

    def test_code_or_vendor_helper_means_true_only(self):
        c = claims(parse("3RSP02028BZ", "third_reality"))
        self.assertIs(c["ctl.on_off"]["value"], True)
        self.assertFalse(any(x.get("value") is False for x in c.values()), "an arrow-function exposes list is not a complete enumeration")


class Wiring(unittest.TestCase):
    def test_registry_and_category_files(self):
        import registry
        self.assertEqual(registry.SOURCES["zigbee2mqtt-devices"]["category"], "smart-home")
        for f in ("spec-profile.yaml", "category.yaml", "identity.md", "manufacturers.yaml", "merchants.md"):
            self.assertTrue((CODE / "research" / "smart-home" / f).exists(), f)

    def test_profile_validates_and_covers_emitted_keys(self):
        import jsonschema
        prof = yaml.safe_load((CODE / "research" / "smart-home" / "spec-profile.yaml").read_text())
        schema = json.loads((CODE / "schemas" / "category-profile.schema.json").read_text())
        self.assertEqual(list(jsonschema.Draft202012Validator(schema).iter_errors(prof)), [])
        keys = {s["key"] for s in prof["specs"]}
        emitted = {c["key"] for m, b in (("E1525/E1745", "ikea"), ("RTCGQ11LM", "aqara"), ("SP 120", "innr")) for c in parse(m, b).claims}
        self.assertEqual(emitted - keys, set())
        self.assertTrue(set(Z.CAP_KEYS) <= keys)

    def test_claims_validate_against_record_schema(self):
        import jsonschema
        s = json.loads((CODE / "schemas" / "record.schema.json").read_text())
        v = jsonschema.Draft202012Validator({"$schema": s.get("$schema"), "$defs": s["$defs"], "$ref": "#/$defs/claim"})
        pr = parse("RTCGQ11LM", "aqara")
        self.assertEqual([e.message for c in pr.claims for e in v.iter_errors(c)], [])
        self.assertTrue(pr.sources[0]["url"].startswith("https://raw.githubusercontent.com/Koenkk/zigbee-herdsman-converters/"))

    def test_policy_allowlist_and_approval_invariant(self):
        pol = [p for p in yaml.safe_load((CODE / "data" / "decisions" / "policies.yaml").read_text())["claim_policies"]
               if "zigbee2mqtt-devices" in (p.get("match") or {}).get("source_ids", [])]
        self.assertEqual(len(pol), 1)
        p = pol[0]
        self.assertEqual(p["match"]["kinds"], ["reported"])
        self.assertEqual(p["match"]["extractors"], [Z.ADAPTER])
        a = p.get("approval") or {}
        self.assertTrue(a.get("state") == "pending" or (a.get("state") == "approved" and a.get("by") and a.get("at")))

    def test_source_policy_entry(self):
        sp = yaml.safe_load((CODE / "data" / "source-policy.yaml").read_text())
        e = [s for s in sp["sources"] if s["domain"] == "raw.githubusercontent.com" and s.get("path") == "/Koenkk/zigbee-herdsman-converters/"]
        self.assertEqual(len(e), 1)
        self.assertEqual((e[0]["kind"], e[0]["crawl"], e[0]["paid"], e[0]["licence_grant"]), ("measurement", "agent", False, False))


if __name__ == "__main__":
    unittest.main()
