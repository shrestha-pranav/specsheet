#!/usr/bin/env python3
"""r7 power-bank PPS rules (A2-pb, 2026-11-26) for INIU and CUKTECH, plus the shared Samsung SFC 2.0 rule (also used by anker_powerbanks@6).

Separate module so shopify_powerbanks.py stays byte-identical: its fingerprint is pinned by the power-bank AND the power-station policies
(shopify_powerstations imports it), and UGREEN keeps ugreen_powerbanks@5. The classes below subclass shopify_powerbanks' INIU / CUKTECH
adapters (discover / fetch / identity unchanged) and add pd.pps claims to the unchanged parse_shop() result, only when it wrote none:

  INIU     iniu_powerbanks@6: the per-port 'Supported Protocol' block ('Supported Protocol Input port : USB-C ...; Output port: USB-C /
           USB-C Cable : UFCS ... / PPS / ...') that parse_shop's label splitter cuts at 'Input'. True only when an 'Output port:' segment
           names USB-C ports only and lists PPS as a protocol item. Never false.
  CUKTECH  cuktech_powerbanks@6: a maker feature bullet listing the bank's fast-charging protocols ('Compatible with a wide range of
           fast-charging protocols, including PD, PPS, QC, FCP, and SCP'): one sentence, affirmative, no input/recharge wording, no question.
  Derived  (both, and anker_powerbanks@6) coordinator ruling r7: Samsung Super Fast Charging 2.0 is PPS by definition. The maker naming
           'Samsung Super Fast Charging 2.0' or '45W (max) (output) for Samsung' for this page -> pd.pps true, kind derived, condition
           basis=derived, quote names the rule. Only when no stated pd.pps claim exists; never a PPS voltage/current range.
           @7 (review-9 P1-2): only an affirmative own-product OUTPUT sentence (see sfc2()); negation, questions, input / recharge /
           adapter context and other-model mentions emit nothing.
"""
import re, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
import _powerbank as P
import shopify_powerbanks as S

VERSION = 7
SFC2 = re.compile(r"Samsung Super Fast Charg\w* 2\.0|\b45\s*W (?:max(?:imum)? )?(?:output )?for Samsung\b", re.I)
NEG = re.compile(r"(?i)\b(?:not|no|doesn.t|does not|without|unsupported|except)\b|\?")
RULE_QUOTE = ("rule r7-sfc2: maker names Samsung Super Fast Charging 2.0 / 45W for Samsung; SFC 2.0 requires USB PD PPS. "
              "No PPS range implied.")


def protocol_output(blk):
    """-> (True, literal) when an 'Output port:' segment of the per-port Supported Protocol block names USB-C ports only and lists PPS."""
    m = re.search(r"Supported Protocols?\s*(Input port\s*:.*?)(?=Product with feature|Cable Spec|Included Accessories|Compatib|$)", blk, re.S)
    if not m:
        return None
    for seg in re.split(r";\s*", m[1]):
        o = re.match(r"\s*Output port\s*:\s*(.+)", seg)
        if not o:
            continue
        ports, _, prot = o[1].partition(" : ") if " : " in o[1] else o[1].partition(": ")
        if re.search(r"USB-C", ports) and not re.search(r"USB-A|wireless", ports, re.I) and re.search(r"(?:^|/)\s*PPS\s*(?:/|$)", prot):
            return True, ("Output port: " + o[1]).strip()[:300]
    return None


def prose_protocols(text):
    """-> the feature sentence listing the bank's fast-charging protocols with PPS, or None."""
    for m in re.finditer(r"(?:[^.!?]|\.(?=\d))*\bprotocols?\b,?\s*(?:including|such as)\s+(?:[^.!?]|\.(?=\d))*\bPPS\b(?:[^.!?]|\.(?=\d))*", text, re.I):
        sent = m[0].strip()
        if text[m.end():m.end() + 1] == "?":
            continue
        if re.search(r"(?i)compatib|support", sent) and not NEG.search(sent) and not re.search(r"(?i)\binput\b|recharg", sent):
            return sent
    return None


SENT_END = re.compile(r"[!?\n]|\.(?!\d)")
QUESTION = re.compile(r"(?i)^\W*(?:Q\s*[:.]|(?:does|do|is|are|can|will|would|could|should|which|what|how|why|when|where|who)\b)")
INPUT_CTX = re.compile(r"(?i)\b(?:input|recharg\w*|refill\w*|adapters?|chargers?|wall\s+(?:plug|outlet|socket|brick)|charging\s+(?:the|this|your)\s+"
                       r"(?:power\s*bank|bank|battery|unit))\b|\bcharg\w*\s+(?:it|this|the\s+(?:power\s*bank|bank|battery))\b")
OTHER_CTX = re.compile(r"(?i)\b(?:other|another|previous|older|newer|sibling|predecessor|successor|unlike|compared|versus|vs)\b")
AFFIRM = re.compile(r"(?i)\b(?:supports?|supported|delivers?|outputs?|provides?|offers?|enables?|compatible|fast[- ]charges?)\b")
MODEL_TOK = re.compile(r"\b[A-Z]{1,4}-?\d{2,5}[A-Z0-9-]*\b")


def _sentence(text, m):
    a = max([x.end() for x in SENT_END.finditer(text, 0, m.start())] or [0])
    z = SENT_END.search(text, m.end())
    return text[a:z.start() if z else len(text)], (text[z.start()] if z else "")


def _norm(v):
    return re.sub(r"[^A-Z0-9]", "", (v or "").upper())


def sfc2(text, model=None):
    """-> the maker sentence naming Samsung SFC 2.0 / '45W for Samsung' as THIS product's output, or None.

    @7 (A3-fix, Codex review-9 P1-2): the whole sentence must be an affirmative own-product output statement. Nothing when the sentence
    is negated anywhere ('... is not supported'), is a question ('Does it support ...?', FAQ 'Q:'), is about input / recharging / an adapter
    ('Recharge using a Samsung SFC 2.0 adapter'), refers to another product ('Our other model P99 supports ...') or names a model token
    that is not this page's model, or has no output verb (support / deliver / output / provide / compatible ...)."""
    text = text or ""
    own = _norm(model)
    for m in SFC2.finditer(text):
        sent, end = _sentence(text, m)
        if end == "?" or QUESTION.search(sent) or NEG.search(sent) or INPUT_CTX.search(sent) or OTHER_CTX.search(sent):
            continue
        devices = re.sub(r"(?i)\b(?:Galaxy|iPhone|iPad|Pixel|Note|Tab)\s+(?:[A-Z]{0,3}\d{1,3}\w*\s*)+", " ", sent)   # target phones, not products
        if any(_norm(t) != own and not (own and (_norm(t) in own or own in _norm(t))) for t in MODEL_TOK.findall(devices)):
            continue
        if not AFFIRM.search(sent):
            continue
        return sent.strip(" .")[:200]
    return None


def add_derived(pr, adapter, snap, model, sent):
    P.emit(pr, adapter, snap, "pd.pps", True, sent, "derived: Samsung Super Fast Charging 2.0 / 45W for Samsung", model,
           {"basis": "derived"}, RULE_QUOTE)
    pr.claims[-1]["kind"] = "derived"


class _R7:
    version = VERSION

    def parse(self, snap, blobs, profile):
        pr = super().parse(snap, blobs, profile)
        model = next((i["value"] for i in pr.identifiers if i.get("scheme") == "mfr_model"), None)
        if not model or any(c["key"] == "pd.pps" for c in pr.claims):
            return pr
        import gzip, json
        d = json.loads(gzip.decompress(blobs.read(snap.snapshot, ".json.gz")))
        text = S.page_text(d["page"])
        rows, blk = S.spec_rows(self, text)
        hit = self.stated(text, blk)
        if hit:
            P.emit(pr, self.adapter, snap, "pd.pps", True, hit[0], hit[1], model, None, hit[2])
        elif (sf := sfc2(text, model)):
            add_derived(pr, self.adapter, snap, model, sf)
        return pr


class IniuPowerbanksR7(_R7, S.IniuPowerbanks):
    def stated(self, text, blk):
        po = protocol_output(blk)
        return (po[1], "Supported Protocol (Output port)", None) if po else None


class CuktechPowerbanksR7(_R7, S.CuktechPowerbanks):
    def stated(self, text, blk):
        ps = prose_protocols(text)
        return (ps, "feature bullet (protocol list)", ps[:125]) if ps else None
