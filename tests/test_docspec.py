#!/usr/bin/env python3
"""docspec@1 (crawler/adapters/_docspec.py) + docspec-attach@1 identity helpers: SSD datasheet rows and monitor spec-sheet rows, affirmative only."""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "crawler" / "adapters"))
sys.path.insert(0, str(ROOT / "scripts"))
import _docspec as X  # noqa: E402
import docspec_attach as DS  # noqa: E402


def doc(*lines, method="text_layer"):
    return {"pages": [{"n": 1, "text": "\n".join(lines), "blocks": [], "method": method}]}


def kv(facts):
    return {f["key"]: f["value"] for f in facts}


def test_ssd():
    # SanDisk portable: USB 3.2 interface -> usb; USB4 / Thunderbolt / connector-only -> nothing (ruling 4)
    assert kv(X.ssd(doc("INTERFACE                     USB 3.2 Gen 2x2 (20Gbps)"))) == {"if.protocol": "usb"}
    assert kv(X.ssd(doc("Interface      USB 3.2 Gen2 x1 (UASP)"))) == {"if.protocol": "usb_uasp"}
    assert X.ssd(doc("INTERFACE                     USB4® (40Gbps)")) == []
    assert X.ssd(doc("Interface (2x) Thunderbolt 3™ (40Gbps) Ports; (1x) USB-C™ (10Gbps) Port")) == []
    assert X.ssd(doc("      Connector                                            USB Type-C")) == []
    assert X.ssd(doc("Interface                                             PCIe 4.0 x4 with NVMe")) == []
    # DRAM rows (ruling 5)
    assert kv(X.ssd(doc("      DRAM                                    Yes"))) == {"hw.dram_type": "dram"}
    assert kv(X.ssd(doc("   DRAM Cache                                 NO"))) == {"hw.dram_type": "dramless"}
    assert kv(X.ssd(doc("   DRAM CACHE         Host Memory Buffer"))) == {"hw.dram_type": "dramless_hmb"}
    assert kv(X.ssd(doc("   Cache Memory       Samsung 2GB LPDDR4 DRAM"))) == {"hw.dram_type": "dram"}
    assert X.ssd(doc("   DRAM Cache          G70 PRO (Yes) / G70 (NO)")) == []                 # two products in one cell
    assert X.ssd(doc("   DRAM         Yes        Yes        No        No")) == []                  # per-capacity columns
    assert X.ssd(doc("   DRAM Cache    NO", "   DRAM Cache    YES")) == []                         # one key, two values: nothing
    # NAND type
    assert kv(X.ssd(doc("      NAND Type        SANDISK® TLC 3D NAND"))) == {"hw.nand_type": "tlc"}
    assert kv(X.ssd(doc("      NAND Flash       Samsung V-NAND 3bit MLC"))) == {"hw.nand_type": "tlc"}
    assert X.ssd(doc("      NAND Flash       3D NAND")) == []
    # controller needs a part-like token
    assert kv(X.ssd(doc("      Controller       Phison E18"))) == {"hw.controller": "Phison E18"}
    assert X.ssd(doc("      Controller       In-House")) == []
    # OCR pages are never read
    assert X.ssd(doc("INTERFACE   USB 3.2 Gen 2", method="ocr")) == []
    # prose is never a row
    assert X.ssd(doc("Beat your competition with a USB 3.2 Gen2x2 interface thanks to a shock-resistant structure")) == []


def test_monitor():
    assert kv(X.monitor(doc("Brightness 300cd (typ) / 240cd (Min)    Flicker Safe   Yes   CABINET"))) == {"flk.pwm": "none"}
    assert kv(X.monitor(doc("Flicker Safe   •"))) == {"flk.pwm": "none"}
    assert X.monitor(doc("Flicker Safe   No")) == []
    assert X.monitor(doc("SUBTITLE FLICKER")) == []
    assert kv(X.monitor(doc("USB Type-C™ with 90W Power Delivery & LAN (RJ-45)"))) == {"usb.usbc_pd_w": 90.0}
    assert X.monitor(doc("USB Type-C™ with 65 Power Delivery")) == []                                 # no W printed
    assert X.monitor(doc("USB Type-C with 15W Power Delivery (downstream)")) == []


def test_identity():
    assert DS.base_sku("SDSSDE83-2T00-G25") == "SDSSDE83"
    assert DS.base_sku("SDSSDE83") is None              # no suffix: the exact rule already covers it
    assert DS.base_sku("34WQ75C-B") == "34WQ75C"
    assert DS.base_sku("T-FORCE") is None


if __name__ == "__main__":
    test_ssd(); test_monitor(); test_identity()
    print("ok")
