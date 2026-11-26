"""Maker spec images -> entities (A3 document pipeline, 2026-11-25). Transform `imgattach@1`, extractor `specimg@1` (+ `specimg-review@1`, never
in an auto-accept policy). Called by scripts/import.py right after docattach (same worlds, same event types). Fingerprint = this file +
crawler/adapters/_docparse.py + the page parsers it reuses + scripts/docattach.py (identity helpers) + crawler/specimages.py (OCR recipe).

Inputs (derived from raw/, nothing from the network): raw/_specimages/discovery.json (image -> the registered pages it was found on, each with
the page's own variant SKUs) and raw/_specimages/ocr/<sha>.json (grayscale + 2x upscale tesseract, word confidences).

Identity (brief coord-2026-11-25-ocr-mophie-a3 + review-6 rules). An image is considered only for an entity observed on a page it was found
on (edge verified exactly like docattach: the discovery page URL is the URL of the entity's own observation). It is bound to that entity by
  (a) INHERITANCE: the linking page is single-SKU (exactly one non-bundle variant SKU, and it is one of the entity's own SKUs), the image's
      file-name model tokens are all own identifiers, and the OCR text names no other model -> identity 'page', variant 'exact'; or
  (b) OCR IDENTITY: the image text names an own mfr_model / mfr_sku with every word of the mention at token confidence >= 60 (docattach.hits)
      and no sibling model (docattach.identity). Variant 'exact' only when the mention is an own SKU and no other SKU of the base model, no
      foreign region token and no shared identifier is in play; otherwise 'model_only' -> specimg-review@1.
  A file-name token naming another model, or ANY variant / foreign-region / shared-identifier evidence (OCR text or file name: A2667113 on an
  A2667111-only page, even with empty file_models) vetoes (a) and every 'exact' (review-8): then only (b) binds, as model_only. Nothing else binds; an unbound image is an `image_proposal` event (reason recorded), never a claim.
Value trust (on top of docparse@2's per-row lowest digit-word confidence >= 60): a line is read only when the MEAN confidence of its
digit-bearing words is >= 70 and none of its value tokens is ambiguous (a digit group split by a space inside a number or range,
'3.3-1 1V'; a letter OCR often confuses with a digit next to a digit, '1JOOW', '2O.0V'; a dangling decimal point '3. 25A'). A rejected line is
replaced by a prose line (it closes any open port row, so it can never merge two rows): fail closed.
Claims: exactly docattach.claims_for (same grammar, same port attribution onto the linking observation's out.ports, same keys per category),
document_kind 'spec_image', ocr true, ocr_conf = the row's lowest token confidence, identity conditions {identity: ocr | page,
identity_scope: image, identity_variant}. Source = the image URL, tier manufacturer, linked_from = the linking page (one source entry per
image x linking page). The source policy's document_host rule (cdn.shopify.com) inherits the linking page's disposition along that edge.
"""
import hashlib, json, re, sys
from collections import Counter
from pathlib import Path

CODE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(CODE / "scripts"))
sys.path.insert(0, str(CODE / "crawler" / "adapters"))
sys.path.insert(0, str(CODE / "crawler"))
import _contract as C  # noqa: E402
import _docparse as X  # noqa: E402
import docattach as DA  # noqa: E402

TRANSFORM = "imgattach@1"
NAME, VERSION = "specimg", 1
EXTRACTOR, EXTRACTOR_REVIEW = f"{NAME}@{VERSION}", f"{NAME}-review@{VERSION}"
SOURCE_ID = DA.SOURCE_ID
MIN_VALUE_MEAN = 70.0
IMG_DIR = C.ROOT / "raw" / "_specimages"
AMBIGUOUS = [re.compile(r"\d[-–~.]\s*\d+\s+\d+(?:\.\d+)?\s*[VAW]\b"),         # '3.3-1 1V', '3.3- 1 1V'
             re.compile(r"\d\s+\.\s*\d|\d\.\s+\d"),                          # '3. 25A', '3 .25A'
             re.compile(r"(?<![A-Za-z])(?=[0-9OoIlJ|]*\d)(?=[0-9OoIlJ|.]*[OoIlJ|])[0-9OoIlJ|.]{2,}\s*[VAW]\b")]   # '1JOOW', '2O.0V', '1l.5A'


VALUE_LINE = re.compile(r"\d\s*[VAW]\b|\d\s*[VAW]\s*[⎓=/]|PPS", re.I)


def fingerprint():
    h = hashlib.sha256()
    for p in (Path(__file__), CODE / "crawler/adapters/_docparse.py", CODE / "crawler/adapters/_powerbank.py", CODE / "crawler/adapters/_charger.py",
              CODE / "scripts/docattach.py", CODE / "crawler/specimages.py"):
        h.update(p.name.encode() + b"\0" + p.read_bytes() + b"\0")
    return "sha256:" + h.hexdigest()[:20]


def ambiguous(line):
    return any(rx.search(line) for rx in AMBIGUOUS)


def value_mean(words):
    dig = [c for w, c in words if re.search(r"\d", w)]
    return sum(dig) / len(dig) if dig else None


def gated_doc(ocr):
    """OCR sidecar -> a one-page docparse document whose value lines all passed the value gate (rejected lines -> prose placeholder)."""
    lines, toks, st = [], [], Counter()
    for ws in ocr.get("lines") or []:
        text = " ".join(w for w, _ in ws)
        if VALUE_LINE.search(text):                    # electrical value lines only; identity lines are judged by docattach.hits (>= 60 per word)
            m = value_mean(ws)
            if ambiguous(text):
                st["lines_ambiguous"] += 1
                text, ws = "unreadable value line", [["unreadable", 0.0], ["value", 0.0], ["line", 0.0]]
            elif m is not None and m < MIN_VALUE_MEAN:
                st["lines_low_conf"] += 1
                text, ws = "unreadable value line", [["unreadable", 0.0], ["value", 0.0], ["line", 0.0]]
        lines.append(text); toks.append([[w, c] for w, c in ws])
    page = {"n": 1, "method": "ocr", "text": "\n".join(lines), "blocks": [], "ocr_conf": ocr.get("mean_conf"), "tokens": toks}
    return {"pages": [page]}, st


def parse(ocr):
    doc, st = gated_doc(ocr)
    return {"power": X.power_output(doc), "text": X.full_text(doc), "id_pages": DA._id_pages(doc), "pages": 1, "ocr_pages": 1}, st


def binding(e, w, res, img, f):
    """-> (identity conditions | None, reason)."""
    own = {v.upper() for v in DA.ident_values(e)}
    skus = DA.sku_values(e)
    idn = DA.identity(e, w, res, img["url"])
    if idn["siblings"]:
        return None, "names_other_model"
    fm = set(img.get("file_models") or [])
    page_skus = f.get("page_skus") or []
    single = len(page_skus) == 1 and page_skus[0].upper() in skus
    # review-8 P1: conflicting-identity vetoes come BEFORE either binding branch. Another SKU of an own base model (OCR text or file name),
    # a foreign region token or an identifier another entity shares means the image may describe another configuration: never 'exact'.
    conflict = bool(idn["variants"] or idn["region"] or idn["shared"]) or not fm <= own
    if single and not conflict:
        return {"identity": "page", "identity_scope": "image", "identity_variant": "exact"}, "single_sku_page"
    if idn["mine"]:
        exact = any(v.upper() in skus for v in idn["mine"]) and not conflict
        return {"identity": "ocr", "identity_scope": "image", "identity_variant": "exact" if exact else "model_only"}, "ocr_model_number"
    if idn["low"]:
        return None, "identity_low_confidence"
    if not single:
        return None, "multi_sku_page_no_ocr_model"
    if not fm <= own:
        return None, "file_name_names_other_sku"
    return None, "conflicting_variant_region_shared"


def image_source(e, img, linked_from):
    h = hashlib.sha256(f"{img['url']}\0{linked_from}".encode()).hexdigest()[:12]
    snap = f"{img['sha']}#image#edge={h}"
    e.srcs.setdefault(snap, {"url": img["url"], "tier": "manufacturer", "label": "spec image (OCR)", "snapshot": snap,
                             "retrieved_at": img.get("retrieved_at"), "linked_from": linked_from})
    return snap


def claims_for(cat, res, url, pports, idc, disagree=False):
    cs, unattr = DA.claims_for(cat, res, "spec_image", url, pports, lambda page, btxt: idc, disagree)
    for c in cs:
        c["conditions"]["identity_scope"] = "image"
        c["method"] = {"stage": "ocr", "extractor": EXTRACTOR if idc["identity_variant"] == "exact" else EXTRACTOR_REVIEW}
        c["locator"] = {"image": url}
    return cs, unattr


def apply(worlds, events, stats, root=None):
    d = Path(root or IMG_DIR)
    if not (d / "discovery.json").exists():
        return Counter()
    imgs = json.loads((d / "discovery.json").read_text())["images"]
    by_obs = {}
    for cat, w in worlds.items():
        if cat not in DA.CATEGORIES:
            continue
        DA._compute_lineage(w.ents)
        for e in w.ents:
            for ob in e.obs:
                by_obs.setdefault((cat, ob[0], ob[1]), []).append(e)
    st = Counter()
    for img in imgs:
        op = d / "ocr" / f"{img['sha'].split(':', 1)[-1]}.json"
        if not op.exists():
            st["images_not_ocred"] += 1
            continue
        res, gst = parse(json.loads(op.read_text()))
        st.update({f"images_{k}": v for k, v in gst.items()})
        st["images_parsed"] += 1
        for f in img["found_on"]:
            cat = f["category"]
            if cat not in worlds or cat not in DA.CATEGORIES:
                continue
            for e in by_obs.get((cat, f["source_id"], f["ref"]), []):
                w = worlds[cat]
                if not DA.edge_verified(e, f):
                    st["image_edges_unverified"] += 1
                    continue
                idc, why = binding(e, w, res, img, f)
                ob = (SOURCE_ID, img["url"], img["sha"])
                if idc is None:
                    st[f"image_unbound:{why}"] += 1
                    if res["power"]["device"] or res["power"]["ports"] or res["power"]["pps_named"]:
                        events.append(("image_proposal", cat, e, w.anchors(e.keys), ob, {"reason": why, "url": img["url"], "page": f["page_url"]}))
                    continue
                st[f"image_bound:{why}"] += 1
                pp, disagree = DA.page_ports(e, (f["source_id"], f["ref"]))
                cs, unattr = claims_for(cat, res, img["url"], pp, idc, disagree)
                st["image_port_rows_unattributable"] += unattr
                if not cs:
                    continue
                for c in cs:
                    snap = image_source(e, img, f["page_url"])
                    c["locator"]["linked_from"] = f["page_url"]
                    c["observed_at"] = f.get("retrieved_at") or "1970-01-01T00:00:00Z"
                    e.claims.append((c, (SOURCE_ID, img["url"], snap)))
                    st[f"image_claims:{cat}:{c['key']}"] += 1
                    st[f"image_claims_by_extractor:{c['method']['extractor']}"] += 1
                e.obs.add(ob)
                events.append(("image_attach", cat, e, w.anchors(e.keys), ob, {"url": img["url"], "binding": why, "claims": len(cs),
                                                                              "identity_variant": idc["identity_variant"]}))
                st["image_attached"] += 1
    for k, v in st.items():
        stats[k] = stats.get(k, 0) + v
    return st
