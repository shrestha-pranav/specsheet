"""Monitor port-list helpers shared by lg_us / asus_monitors / lenovo_monitors / benq_monitors (preset fill 2026-11-24).

usb.usbc_inputs = USB-C / Thunderbolt / USB4 ports that take a video signal from the computer (research/monitors/spec-profile.yaml).
  A line counts when it names a USB-C-class port, says nothing that makes it downstream/out/data-only, and names video
  (Alt Mode, DisplayPort/DP, Thunderbolt, USB4). A USB-C line that is neither clearly an input nor clearly downstream makes the
  whole list ambiguous: nothing is written (never a guess).
  0 only under coordinator ruling 1 (2026-11-24, complete enumeration): the maker's own structured port section lists every port,
  it names at least one video input, and no USB-C-class port on it is a video input. That claim carries the basis condition
  {basis: complete_enumeration} and the list as raw. Prose, partial tables and pages without a port section never give 0.

gen.size_class: coordinator ruling 3 (2026-11-24). Where the maker prints a size class it is taken as stated; where it prints only the
  panel / screen diagonal the class is derived by one deterministic rule, round half up to the whole inch (23.8 -> 24, 31.5 -> 32,
  26.5 -> 27, 21.45 -> 21). The claim is kind=derived with locator.derivation = DERIVATION and the stated diagonal as raw.
"""
import math
import re

DERIVATION = "size_class_round_half_up@1"
CPORT = re.compile(r"USB[- ]?C\b|USB[- ]?C®|Type[- ]?C|Thunderbolt|USB ?4", re.I)
DOWN = re.compile(r"down-?stream|\bout\b|data (?:transfer )?only|not support (?:DP|DisplayPort|video)", re.I)
POWER_IN = re.compile(r"\bDC[- ]?in\b|power input", re.I)
VIDEO = re.compile(r"alt\.? ?mode|DisplayPort|\bDP\b|Thunderbolt|USB ?4|video", re.I)
VIDEO_IN = re.compile(r"^\s*(?:\d+\s*x\s*)?(?:HDMI|Display ?Port|DP\b|Mini ?Display ?Port|VGA|D-?Sub|DVI|USB[- ]?C|Thunderbolt)", re.I)


def size_class(d):
    """Round half up to the whole inch (ruling 3)."""
    return int(math.floor(float(d) + 0.5))


def classify(line):
    """-> 'input' | 'other' (not a USB-C video input) | 'ambiguous' for one port line."""
    if not CPORT.search(line):
        return "other"
    if DOWN.search(line) and not re.search(r"\bupstream\b", line, re.I):
        return "other"
    if re.search(r"\bupstream\b", line, re.I) and re.search(r"data (?:transfer )?only", line, re.I):
        return "other"
    if VIDEO.search(line):
        return "input"
    if POWER_IN.search(line):
        return "other"              # a power-only USB-C inlet (portable monitors)
    return "ambiguous"


def lead_count(line):
    """'2x ...' / '... x 2' / '... x2' -> count; default 1. 'USB-C x 2 (DP Alt Mode x1 + DC In x1)' -> the Alt Mode count."""
    if POWER_IN.search(line) and (m := re.search(r"alt\.? ?mode[^+)]*?x\s*(\d+)", line, re.I)):
        return int(m[1])
    m = re.match(r"\s*(\d+)\s*x\b", line, re.I) or re.search(r"\bx\s*(\d+)\b", line, re.I)
    return int(m[1]) if m else 1


def count_inputs(lines, count=lead_count):
    """lines = the maker's full port list (one port type per entry). -> (n, complete_zero) or (None, False) when ambiguous.
    complete_zero is True when n == 0 (the caller attaches basis: complete_enumeration)."""
    if not lines:
        return None, False
    n = 0
    for l in lines:
        c = classify(l)
        if c == "ambiguous":
            return None, False
        if c == "input":
            k = count(l)
            if k > 1 and re.search(r"daisy|down-?stream|\bout\b", l, re.I):   # '2x Thunderbolt 4 (one USB upstream, one USB downstream)' too
                return None, False      # 'Thunderbolt 4 x 2 (Daisy Chain)': one of them is the chain-out port, which one is not stated
            n += k
    if n == 0 and not any(VIDEO_IN.search(l) for l in lines):
        return None, False          # a list naming no video input at all is not an input list
    return n, n == 0
