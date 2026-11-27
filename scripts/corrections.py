#!/usr/bin/env python3
"""Evidence-backed corrections (PM D9.2/D10; team/briefs/pm-2026-11-25-corrections-flow.md). GitHub issue form -> claim file in git ->
human ledger decision. We run no accounts and keep no personal data: a claim file never holds a handle, name or email (the issue URL is
the pointer) and evidence images are hashed, never copied.

  python3 -I scripts/corrections.py sync  [--repo OWNER/NAME] [--dry-run] [--issues-json FILE] [--no-images] [--ack-burst]
  python3 -I scripts/corrections.py check [FILE ...]          exit 1 when a claim file fails (prints one line per problem)
  python3 -I scripts/corrections.py queue [--out team/queue/corrections.md]

sync   READ-ONLY against GitHub: `gh api` GET of issues labelled `field-correction` (open and closed). It never comments, labels or closes.
       Writes data/corrections/<issue>.yaml (only when the content changed). --dry-run writes nothing and prints what it would write.
       Abuse limits (brief section 5): at most MAX_OPEN_PER_ACCOUNT open corrections per GitHub account are synced (counted in memory from
       the API, the handle is never stored); the rest are listed with the `gh issue edit N --add-label needs-triage-later` command for a
       maintainer to run. More than BURST_PER_DAY new corrections in 24 h pauses the sync (exit 3) until a human re-runs it with --ack-burst.
check  Per file: entity + key exist, the value normalises under the category profile, the evidence fits its type (E1/E4: hashed photos;
       E2: a `kind: maker` domain; E3: a `kind: measurement` domain), the cited domain has a D9 disposition with free: true (unlisted,
       free: false and path-excluded URLs fail), terms acknowledged, COI only as E2, family scope lists its configs explicitly, the D10
       revision guard (a family-wide measured claim needs two samples or a maker single-design statement), and agent proposals cite only
       `crawl: agent` domains with E2/E3.
queue  team/queue/corrections.md for the reviewer (scripts/review_corrections.py writes the ledger lines). No LLM decides anything.

Claim kind follows the evidence: E1/E2 -> official, E3/E4 -> measured (measurement.mode from the form). Source: E1/E4 -> tier crowd, url =
the issue; E2 -> tier manufacturer, url = the maker page, evidence = the issue; E3 -> tier measurement, url = the cited page, evidence = the
issue. Extractor correction@1, claim id c_corr_<ref>_<n> (n = 1.. over `applies_to`, else 1). No auto-accept policy may name correction@1
(decisions.py enforces it): every correction needs a human ledger line. import.py calls apply() after entity ids exist.

Hardening (Codex review-7, 2026-11-25):
  - Approval is bound to content. claim_digest() = sha256 of the canonical claim content (claim id, entity + target, applies_to in order,
    key, value, kind, measurement, conditions, evidence type/urls/image hashes + transcriptions, source, terms/coi/submitter). The reviewer CLI
    writes it into each accept line; decisions.py treats an accept whose digest is missing or differs from the current claim file as
    withheld (candidate, pending) until a fresh decision. A reject stays a reject whatever the content.
  - Privacy before persistence. Every string is decoded (percent / HTML entities, repeatedly) and checked before anything is written:
    handles and emails (literal, encoded, "(at)/(dot)") are removed from free text, payload ids must match the id pattern, and evidence
    URLs lose userinfo, fragments and identifying/tokenised query parameters; a URL whose path still identifies a person is dropped.
    sanitize_doc() is the last pass before data/corrections is written (dry-run prints the same sanitized text).
  - Crawl policy on every hop. Every fetch here goes through policy_open(): the first URL and each redirect target must be either
    the GitHub issue-attachment INTAKE exception or a listed `crawl: agent` source; human_only, none and unlisted hosts get zero requests.
    INTAKE exception (documented, narrow): attachment hashing of images a contributor uploaded to a field-correction issue may fetch
    github.com/user-attachments/assets/*, (private-)user-images.githubusercontent.com and the GitHub asset CDN those redirect to, even
    though github.com issue pages are `crawl: human_only`: the contributor submitted the file to us for exactly this check, and the
    bytes are hashed in memory, never stored. Issue text itself is read only through `gh api` (api.github.com, the same intake).
"""
import argparse, datetime as dt, hashlib, html, json, os, re, subprocess, sys, urllib.error, urllib.parse, urllib.request
from collections import Counter, defaultdict
from pathlib import Path

import yaml

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import catmeta  # noqa: E402
import normalize as N  # noqa: E402
import source_policy as SP  # noqa: E402

CODE = Path(__file__).resolve().parent.parent
ROOT = catmeta.ROOT
EXTRACTOR = "correction@1"
SOURCE_ID = "corrections"
LABEL = "field-correction"
TRIAGE_LABEL = "needs-triage-later"
MAX_OPEN_PER_ACCOUNT = 10
BURST_PER_DAY = 20
MAX_TRANSCRIPTION = 125
TYPES = {"E1": "official", "E2": "official", "E3": "measured", "E4": "measured"}
TIER = {"E1": "crowd", "E2": "manufacturer", "E3": "measurement", "E4": "crowd"}
MODES = {"inspection", "optical", "advertised_by_device", "negotiated", "sustained", "peak"}
FAST_REJECT = {"no_evidence": "No evidence: text alone is not evidence (photo of the label, a maker page or a measurement link is needed).",
               "identity_not_visible": "Identity not visible: the model number is not readable in the evidence, or does not match this product.",
               "fact_not_visible": "Fact not visible: the evidence does not show the proposed value.",
               "domain_not_allowed": "Domain not allowed: the cited site has no free disposition in our source policy (D9).",
               "duplicate": "Duplicate of an earlier correction or of the value already published."}
# Section labels of .github/ISSUE_TEMPLATE/field-correction.yml (the form renders `### <label>` headings in the issue body).
FORM = {"payload": "Catalogue field", "claimed_value": "Proposed value", "evidence_type": "Evidence type", "evidence_url": "Evidence URL",
        "extra_urls": "More evidence (second sample)", "single_design_url": "Maker statement that the line has one design",
        "applies_to": "Applies to (configurations)", "attachments": "Photos", "measurement_mode": "Measurement method",
        "conditions": "Conditions", "terms": "Contributor terms", "coi": "Conflict of interest"}
TERMS_VERSION = "2026-11-25"           # owner-approved 2026-11-25 (no relicensing clause); bump with the checkbox wording in the issue form
IMG = re.compile(r"https://(?:github\.com/user-attachments/assets/[0-9a-f-]+|(?:private-)?user-images\.githubusercontent\.com/[^\s)\"'>]+)")
MENTION = re.compile(r"(?<![\w.])@[A-Za-z0-9](?:[A-Za-z0-9-]{0,38})")
EMAIL = re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+")
URL = re.compile(r"https?://[^\s<>()\"']+")
OBF_EMAIL = re.compile(r"[\w.+-]+\s*[\[({]\s*at\s*[\])}]\s*[\w-]+(?:\s*(?:[\[({]\s*dot\s*[\])}]|\.)\s*[\w-]+)+", re.I)
ID = re.compile(r"[a-z0-9][a-z0-9._-]{0,95}")
TOKEN_KEYS = re.compile(r"^(?:utm_.*|token|access_token|auth|authorization|key|api_?key|sig|signature|x-amz-.*|session|sid|jwt|code|state|"
                        r"email|e-?mail|mail|user|username|login|uid|u|ref|referrer|fbclid|gclid|mc_eid|mc_cid|_hs.*|hsa_.*)$", re.I)
TOKENISH = re.compile(r"(?=.*\d)(?=.*[A-Za-z])[A-Za-z0-9_\-.=+/]{20,}")
MAINTAINERS = "maintainers.yaml"


def decoded(text, rounds=3):
    """Undo percent- and HTML-entity encoding (repeatedly: %2540, &amp;#64;) so encoded PII is seen."""
    t = str(text or "")
    for _ in range(rounds):
        n = urllib.parse.unquote_plus(html.unescape(t))
        if n == t:
            break
        t = n
    return t


def has_pii(text):
    """An email address or @handle, literal or encoded (percent, HTML entity, '(at)/(dot)')."""
    for t in (str(text or ""), decoded(text)):
        if EMAIL.search(t) or OBF_EMAIL.search(t) or MENTION.search(t.replace("://", " ")):
            return True
    return False


def clean_url(u):
    """-> the URL without userinfo, fragment or identifying/tokenised query parameters; None when it cannot be made safe (not http(s), or
    the host/path itself carries an email or @handle after decoding)."""
    try:
        sp = urllib.parse.urlsplit(str(u or "").strip())
    except ValueError:
        return None
    if sp.scheme not in ("http", "https") or not sp.hostname or "@" in sp.netloc or has_pii(sp.netloc) or has_pii(sp.path):
        return None
    q = [(k, v) for k, v in urllib.parse.parse_qsl(sp.query, keep_blank_values=True)
         if not TOKEN_KEYS.match(decoded(k)) and not has_pii(k) and not has_pii(v) and not TOKENISH.fullmatch(decoded(v))]
    return urllib.parse.urlunsplit((sp.scheme, sp.netloc.lower(), sp.path, urllib.parse.urlencode(q), ""))


def clean_id(x):
    x = str(x or "").strip()
    return x if ID.fullmatch(x) and not has_pii(x) else None


def sanitize_doc(doc):
    """Last pass before a claim file is written: every string (any depth) is checked after decoding. URL-looking strings go through
    clean_url (dropped from lists / set to None when unsafe); any other string with PII is scrubbed. -> a new doc."""
    def walk(v):
        if isinstance(v, dict):
            return {k: walk(x) for k, x in v.items()}
        if isinstance(v, list):
            out = [walk(x) for x in v]
            return [x for x in out if x is not None or not v]
        if isinstance(v, str):
            if re.match(r"https?://", v):
                return clean_url(v)
            return scrub(v, 10_000) if has_pii(v) else v
        return v
    return walk(doc)


def maintainers(data_dir=None):
    """data/decisions/maintainers.yaml: the reviewer handles allowed on a correction decision line. Documented exception to "no personal
    data": these are public maintainer handles of the repo owner/maintainers (they decide in public), never contributors'."""
    p = Path(data_dir or ROOT / "data") / "decisions" / MAINTAINERS
    if not p.exists():
        return set()
    doc = yaml.safe_load(p.read_text()) or {}
    return {str(h) for h in (doc.get("maintainers") if isinstance(doc, dict) else doc) or []}


def claim_digest(doc, cid, eid):
    """sha256 of the canonical content one ledger accept approves. Any change to value, evidence, scope or target order changes it."""
    ev = doc.get("evidence") or {}
    body = {"claim": cid, "entity": doc.get("entity"), "target": eid, "applies_to": list(doc.get("applies_to") or []), "key": doc.get("key"),
            "value": doc.get("value"), "kind": doc.get("kind"), "measurement": doc.get("measurement") or None,
            "conditions": doc.get("conditions") or {}, "conditions_text": doc.get("conditions_text") or None,
            "evidence": {"type": ev.get("type"), "url": ev.get("url"), "extra_urls": list(ev.get("extra_urls") or []),
                         "single_design_url": ev.get("single_design_url"),
                         "images": [[i.get("sha256"), i.get("transcription")] for i in ev.get("images") or []]},
            "source": doc.get("source") or {}, "terms_ack": doc.get("terms_ack"), "coi": doc.get("coi"), "submitted_by": doc.get("submitted_by")}
    return "sha256:" + hashlib.sha256(json.dumps(body, sort_keys=True, ensure_ascii=False, separators=(",", ":"), default=str).encode()).hexdigest()


def current_digests(data_dir=None):
    """{claim id: digest} over data/corrections. A file that still carries PII yields no digest (so no accept can match it)."""
    out = {}
    for _, doc in load(data_dir):
        if doc.get("issue") is None and doc.get("proposal") is None:
            continue
        if has_pii(json.dumps(doc, default=str, ensure_ascii=False)):
            continue
        for cid, eid in claim_ids(doc):
            out[cid] = claim_digest(doc, cid, eid)
    return out


def corrections_dir(data_dir=None):
    return Path(data_dir or ROOT / "data") / "corrections"


def scrub(text, limit=300):
    """Free text from an issue: no handles, no emails, bounded. Mentions and addresses become placeholders."""
    t = str(text or "")
    if has_pii(t):
        t = decoded(t)              # encoded addresses/handles are decoded first so the placeholders catch them
    t = EMAIL.sub("[email removed]", t)
    t = OBF_EMAIL.sub("[email removed]", t)
    t = MENTION.sub("[handle removed]", t)
    t = re.sub(r"\s+", " ", t).strip()
    return t[:limit]


def ref_of(doc):
    return str(doc["issue"]) if doc.get("issue") is not None else f"a{doc['proposal']}"


def order(doc):
    return (doc.get("issue") is None, int(doc.get("issue") if doc.get("issue") is not None else doc.get("proposal") or 0))


def claim_ids(doc):
    targets = doc.get("applies_to") or [doc.get("entity")]
    return [(f"c_corr_{ref_of(doc)}_{n}", eid) for n, eid in enumerate(targets, 1)]


def pointer(doc, repo=None):
    """Where the evidence lives: the issue URL (crowd/maintainer), or the proposal file in git (agent proposals)."""
    if doc.get("url"):
        return doc["url"]
    repo = repo or site_repo()
    return f"https://github.com/{repo}/blob/main/data/corrections/{ref_of(doc)}.yaml"


def site_repo():
    try:
        return json.loads((CODE / "docs" / "site.json").read_text())["repo"]
    except (OSError, KeyError, ValueError):
        return "shrestha-pranav/specsheet"


def source_of(doc, pol=None):
    """-> {url, tier, label, evidence} of the claim's source (the evidence decides it, not the channel)."""
    ev = doc.get("evidence") or {}
    t = ev.get("type")
    ref = ref_of(doc)
    if t in ("E1", "E4"):
        return {"url": pointer(doc), "tier": "crowd", "label": f"{'Contributor photo of the product label' if t == 'E1' else 'Contributor measurement'} (correction {ref})",
                "evidence": None}
    url = ev.get("url")
    credit = None
    if pol is not None and url:
        credit = (pol.entry_for(url) or {}).get("credit")
    label = f"{credit or SP.host_of(url) or 'cited page'} (cited in correction {ref})"
    return {"url": url, "tier": TIER.get(t, "other"), "label": label, "evidence": pointer(doc)}


def load(data_dir=None):
    """-> [(path, doc)] of every claim file, sorted by path."""
    d = corrections_dir(data_dir)
    out = []
    if d.exists():
        for p in sorted(d.glob("*.yaml")):
            out.append((p, yaml.safe_load(p.read_text()) or {}))
    return out


# ---------------------------------------------------------------------------------------------------------------- entity lookup
class Catalogue:
    """Entity ids from the id registry (category + kind), family membership from the working store when it exists."""
    def __init__(self, data_dir=None, db=None):
        self.cat, self.kind, self.family = {}, {}, {}
        rp = Path(data_dir or ROOT / "data") / "_ids" / "registry.jsonl"
        if rp.exists():
            for ln in rp.read_text().splitlines():
                if ln.strip():
                    r = json.loads(ln)
                    self.cat.setdefault(r["id"], r.get("category")); self.kind.setdefault(r["id"], r.get("kind"))
        self.db = Path(db) if db else ROOT / "state" / "specsheet.sqlite"
        if self.db.exists():
            import sqlite3
            con = sqlite3.connect(self.db)
            for eid, cat, kind, fam, par in con.execute("SELECT id, category, kind, family_id, parent_id FROM entities"):
                self.cat[eid] = cat; self.kind[eid] = kind
                self.family[eid] = fam or par       # family membership (family_id; the parent when the store has no family link)
            con.close()

    def members(self, fam):
        return {e for e, f in self.family.items() if f == fam}


_PROFILES = {}


def spec_of(cat, key):
    if cat not in _PROFILES:
        try:
            prof = catmeta.load(cat)["profile"]
        except (OSError, TypeError):
            prof = {"specs": []}
        _PROFILES[cat] = (prof, {s["key"]: s for s in prof.get("specs") or []}, N.units(prof))
    prof, specs, U = _PROFILES[cat]
    return specs.get(key), U


def normalised(cat, key, value):
    sp, U = spec_of(cat, key)
    if sp is None:
        return False, None
    ok, nv, _ = N.normalise(sp, {"status": "known", "value": value, "raw": str(value)}, U)
    return ok, nv


# ---------------------------------------------------------------------------------------------------------------- check
def check(doc, pol, cat_lookup, others=()):
    """-> [(code, message)]. Empty = the file may go to a reviewer. `others` = the other claim docs (duplicate detection)."""
    bad = []
    add = lambda code, msg: bad.append((code, msg))
    if doc.get("issue") is None and doc.get("proposal") is None:
        add("format", "needs issue: N (or proposal: N for an agent proposal)")
        return bad
    sub = str(doc.get("submitted_by") or "")
    agent = sub.startswith("agent:")
    if sub not in ("crowd", "maintainer") and not agent:
        add("format", "submitted_by must be crowd, maintainer or agent:<role>")
    if doc.get("issue") is not None and not re.fullmatch(r"https://github\.com/[\w.-]+/[\w.-]+/issues/\d+", str(doc.get("url") or "")):
        add("format", "url must be the issue URL")
    for f in ("author", "user", "login", "handle", "email", "name"):
        if f in doc:
            add("pii", f"claim files never carry {f!r} (no personal data, D9.2)")
    blob = json.dumps(doc, default=str, ensure_ascii=False)
    if has_pii(blob):
        add("pii", "an email address or @handle appears in the claim file")
    if doc.get("triage") == TRIAGE_LABEL:
        add("abuse", "over the per-account open limit: triage later")
    if doc.get("terms_ack") is not True:
        add("terms", "contributor terms not acknowledged")
    eid, key = doc.get("entity"), doc.get("key")
    cat = cat_lookup.cat.get(eid)
    if not cat:
        add("identity", f"entity {eid!r} is not a catalogue id")
    sp = spec_of(cat, key)[0] if cat else None
    if cat and sp is None:
        add("key", f"{key!r} is not a {cat} spec key")
    if doc.get("value") in (None, ""):
        add("no_evidence", "no proposed value")
    elif sp is not None and not normalised(cat, key, doc["value"])[0]:
        add("value", f"value {doc['value']!r} does not normalise as {sp['type']}{' ' + sp['unit'] if sp.get('unit') else ''}"
                     f"{' (one of ' + ', '.join(map(str, sp['enum'])) + ')' if sp.get('enum') else ''}")
    ev = doc.get("evidence") or {}
    t = ev.get("type")
    if t not in TYPES:
        add("no_evidence", "evidence.type must be E1..E4")
        return bad
    if doc.get("kind") != TYPES[t]:
        add("kind", f"kind must follow the evidence: {t} -> {TYPES[t]}")
    want_src = source_of(doc, pol)
    if (doc.get("source") or {}).get("tier") != want_src["tier"] or (doc.get("source") or {}).get("url") != want_src["url"]:
        add("source", f"source must be {want_src['tier']} {want_src['url']}")
    imgs = ev.get("images") or []
    if t in ("E1", "E4"):
        if agent:
            add("agent", "agents file E2/E3 only (they cannot photograph a product)")
        if not imgs:
            add("no_evidence", f"{t} needs at least one photo (attachments)")
        if any(not re.fullmatch(r"sha256:[0-9a-f]{64}", str(i.get("sha256") or "")) for i in imgs):
            add("no_evidence", "a photo could not be hashed (re-sync)")
        if any(len(str(i.get("transcription") or "")) > MAX_TRANSCRIPTION for i in imgs):
            add("format", f"transcriptions are at most {MAX_TRANSCRIPTION} characters")
    urls = [u for u in [ev.get("url")] + list(ev.get("extra_urls") or []) if u]
    if t in ("E2", "E3") and not ev.get("url"):
        add("no_evidence", f"{t} needs an evidence URL")
    if doc.get("coi") and t != "E2":
        add("coi", "a submitter who works for or is paid by the maker is accepted only with a maker URL (E2)")
    if t in ("E3", "E4"):
        if (doc.get("measurement") or {}).get("mode") not in MODES:
            add("measurement", f"measured claims need measurement.mode in {sorted(MODES)}")
    elif doc.get("measurement"):
        add("measurement", "only E3/E4 claims are measured")
    want_kind = {"E2": "maker", "E3": "measurement"}
    for u in urls + ([ev["single_design_url"]] if ev.get("single_design_url") else []):
        d = pol.disposition(u)
        e = pol.entry_for(u)
        if not d["listed"] or not d["free"]:
            add("domain_not_allowed", f"{d['host'] or u}: {'not in the source policy' if not d['listed'] else 'free: false'} (D9)")
            continue
        need = "maker" if u == ev.get("single_design_url") else want_kind.get(t)
        if need and (e or {}).get("kind") != need:      # review-7: a single-design statement is a maker page for every evidence type (E4 too)
            add("domain_not_allowed", f"{d['host']}: {t} needs a `kind: {need}` domain, this one is {(e or {}).get('kind')}")
        if agent and pol.crawl(u) != "agent":
            add("agent", f"{d['host']}: crawl {pol.crawl(u)}; an agent may cite only crawl: agent domains")
    if t in ("E1", "E4") and urls:
        pass       # an extra link beside a photo is context for the reviewer, not the source
    # family scope (SSD seed): the configs are listed, never implied
    targets = doc.get("applies_to")
    if cat and cat_lookup.kind.get(eid) == "family":
        if not targets:
            add("scope", "a family-scoped claim lists applies_to: [config ids] explicitly (a config is never implied)")
        mem = cat_lookup.members(eid)
        for x in targets or []:
            if x not in cat_lookup.cat:
                add("scope", f"applies_to {x!r} is not a catalogue id")
            elif mem and x not in mem:
                add("scope", f"applies_to {x!r} is not a member of {eid}")
    elif targets:
        for x in targets:
            if x not in cat_lookup.cat:
                add("scope", f"applies_to {x!r} is not a catalogue id")
    if doc.get("kind") == "measured" and (cat_lookup.kind.get(eid) == "family" or len(targets or []) > 1):
        samples = independent_samples(urls, imgs if t == "E4" else [])
        if samples < 2 and not ev.get("single_design_url"):
            add("revision_guard", "a family-wide measured claim needs two independent samples or a maker single-design statement (D10)")
    for o in others:
        if o is doc or o.get("entity") != eid or o.get("key") != key:
            continue
        if str(o.get("value")).strip().lower() == str(doc.get("value")).strip().lower() and order(o) < order(doc) and o.get("state") != "closed":
            add("duplicate", f"same entity, key and value as correction {ref_of(o)}")
            break
    return bad


def _sample_key(u):
    """Coarse identity of a cited sample: the registrable-ish host (www. dropped). Two URLs on one site (pages of one review, URL
    variants, query/fragment tricks) are one sample; review-7: distinct URLs are not independent samples."""
    return re.sub(r"^www\.", "", SP.host_of(u))


def independent_samples(urls, imgs=()):
    """URL samples count once per site; photos once per distinct hash (a duplicated photo is one sample)."""
    return len({_sample_key(u) for u in urls if _sample_key(u)}) + len({i.get("sha256") for i in imgs if i.get("sha256")})


def check_all(data_dir=None, pol=None, paths=None, db=None):
    pol = pol or SP.load()
    cl = Catalogue(data_dir, db)
    docs = load(data_dir)
    if paths:
        want = {Path(p).resolve() for p in paths}
        sel = [(p, d) for p, d in docs if p.resolve() in want] + [(Path(p), yaml.safe_load(Path(p).read_text()) or {}) for p in paths
                                                                  if Path(p).resolve() not in {q.resolve() for q, _ in docs}]
    else:
        sel = docs
    allds = [d for _, d in docs]
    return [(p, d, check(d, pol, cl, allds)) for p, d in sel]


# ---------------------------------------------------------------------------------------------------------------- import (scripts/import.py)
def apply(worlds, events, data_dir, pol=None):
    """Attach every claim file's claim(s) to its entities (ids must exist). Claims start as candidates: only a ledger line accepts one.
    A file failing a structural check (unknown entity/key) is skipped and counted, never half-applied. -> stats dict."""
    st = Counter()
    docs = load(data_dir)
    st["files"] = len(docs)
    if not docs:
        return dict(st)
    pol = pol or SP.load()
    by_id = {}
    for cat, w in worlds.items():
        for e in w.ents:
            if e.id:
                by_id[e.id] = (cat, e)
    h = hashlib.sha256()
    for p, doc in docs:
        h.update(p.name.encode() + b"\0" + p.read_bytes() + b"\0")
        ids = claim_ids(doc) if (doc.get("issue") is not None or doc.get("proposal") is not None) else []
        ev = doc.get("evidence") or {}
        if not ids or ev.get("type") not in TYPES or any(eid not in by_id for _, eid in ids) or doc.get("triage") == TRIAGE_LABEL \
                or doc.get("terms_ack") is not True or not doc.get("key") or not doc.get("entity") or doc.get("value") in (None, "") \
                or has_pii(json.dumps(doc, default=str, ensure_ascii=False)):
            st["skipped"] += 1
            print(f"corrections: {p.name} skipped (unknown entity/key, no value, evidence type, terms, triage or PII; run scripts/corrections.py check)", file=sys.stderr)
            continue
        src = source_of(doc, pol)
        if not src["url"]:
            st["skipped"] += 1
            continue
        snap = "sha256:" + hashlib.sha256(f"correction|{ref_of(doc)}|{src['url']}".encode()).hexdigest()
        trans = "; ".join(str(i.get("transcription")) for i in ev.get("images") or [] if i.get("transcription"))
        for cid, eid in ids:
            cat, e = by_id[eid]
            e.srcs.setdefault(snap, {"url": src["url"], "tier": src["tier"], "label": src["label"], "snapshot": snap,
                                     "retrieved_at": doc.get("submitted_at"), "evidence": src["evidence"]})
            c = {"_cid": cid, "key": doc["key"], "status": "known", "value": doc["value"], "raw": str(doc["value"])[:300], "kind": TYPES[ev["type"]],
                 "method": {"stage": "crowd" if doc.get("submitted_by") != "maintainer" else "manual", "extractor": EXTRACTOR},
                 "observed_at": doc.get("submitted_at") or "1970-01-01T00:00:00Z",
                 "locator": {"correction": ref_of(doc), "evidence_type": ev["type"], **({"image_sha256": [i["sha256"] for i in ev.get("images") or []]} if ev.get("images") else {})}}
            if doc.get("conditions"):
                c["conditions"] = doc["conditions"]
            if trans:
                c["quote"] = trans[:200]
            if c["kind"] == "measured":
                m = {"mode": (doc.get("measurement") or {}).get("mode")}
                if (doc.get("measurement") or {}).get("instrument"):
                    m["instrument"] = str(doc["measurement"]["instrument"])[:120]
                notes = (doc.get("measurement") or {}).get("notes") or doc.get("conditions_text")
                if notes:
                    m["notes"] = str(notes)[:200]
                c["measurement"] = m
            e.claims.append((c, (SOURCE_ID, ref_of(doc), snap)))
            st["claims"] += 1
            st[f"claims_{ev['type']}"] += 1
    st["digest"] = "sha256:" + h.hexdigest()
    return dict(st)


# ---------------------------------------------------------------------------------------------------------------- sync (GitHub, read-only)
def sections(body):
    out, cur = {}, None
    for ln in (body or "").splitlines():
        m = re.match(r"^###\s+(.+?)\s*$", ln)
        if m:
            cur = m.group(1); out[cur] = []
        elif cur is not None:
            out[cur].append(ln)
    return {k: ("\n".join(v).strip() if "\n".join(v).strip() != "_No response_" else "") for k, v in out.items()}


def parse_payload(text):
    m = re.search(r"\{.*\}", text or "", re.S)
    if not m:
        return {}
    try:
        p = json.loads(m.group(0))
    except ValueError:
        return {}
    return p if isinstance(p, dict) else {}


def checked(text):
    return bool(re.search(r"^\s*-\s*\[[xX]\]", text or "", re.M))


def fetch_issues(repo):
    """Read-only GET via gh. The login is used only in memory for the per-account limit, never returned to disk."""
    q = f"repos/{repo}/issues?labels={LABEL}&state=all&per_page=100&sort=created&direction=asc"
    jq = ".[] | select(.pull_request == null) | {number, body, state, state_reason, created_at, closed_at, html_url, login: .user.login}"
    r = subprocess.run(["gh", "api", "--method", "GET", "--paginate", q, "--jq", jq], capture_output=True, text=True)
    if r.returncode != 0:
        raise SystemExit(f"gh api failed: {r.stderr.strip()[:300]}")
    return [json.loads(ln) for ln in r.stdout.splitlines() if ln.strip()]


INTAKE = (("github.com", "/user-attachments/assets/"), ("user-images.githubusercontent.com", "/"), ("private-user-images.githubusercontent.com", "/"),
          ("objects.githubusercontent.com", "/"), ("github-production-user-asset-6210df.s3.amazonaws.com", "/"))


class BlockedFetch(Exception):
    """A URL (first request or a redirect hop) the crawl policy does not allow this script to request."""


def fetch_allowed(url, pol):
    """-> 'intake' | 'agent' | None. https only. The GitHub issue-attachment intake exception (module docstring), else a listed source with
    crawl: agent. human_only, none and unlisted (the policy's unlisted default is 'agent' for the crawler; here it is refused) -> None."""
    try:
        sp = urllib.parse.urlsplit(str(url))
    except ValueError:
        return None
    if sp.scheme != "https" or not sp.hostname or "@" in sp.netloc:
        return None
    h = sp.hostname.lower().rstrip(".")
    if any(h == ih and sp.path.startswith(ip) for ih, ip in INTAKE):
        return "intake"
    if pol is not None and pol.entry_for(url) is not None and pol.crawl(url) == "agent":
        return "agent"
    return None


UA = "specsheet-corrections/0.1 (+https://github.com/shrestha-pranav/specsheet)"
_ROBOTS = {}


def robots_ok(url, handlers=(), timeout=30):
    """RFC 9309 robots.txt check (crawler/robots.py, A3-rob r11) for a crawl: agent source; the GitHub intake (the submitter's own upload,
    not a crawl) is exempt. Fetched once per origin (cached only on the real transport); 4xx = allow, 5xx / unreachable = refuse."""
    sys.path.insert(0, str(CODE / "crawler"))
    import robots as RB
    sp = urllib.parse.urlsplit(url)
    origin = f"{sp.scheme}://{sp.netloc.lower()}"
    rb = _ROBOTS.get(origin) if not handlers else None
    if rb is None:
        req = urllib.request.Request(origin + "/robots.txt", headers={"User-Agent": UA})
        try:
            with urllib.request.build_opener(*handlers).open(req, timeout=timeout) as resp:
                rb = RB.Robots.from_response(resp.getcode() or 200, resp.read(RB.MAX_BYTES).decode("utf-8", "replace"))
        except urllib.error.HTTPError as e:
            rb = RB.Robots.from_response(e.code, "")
        except Exception:
            rb = RB.Robots.from_response(None, "")
        if not handlers:
            _ROBOTS[origin] = rb
    return rb.allowed(url)


def _allowed_hop(url, pol, handlers=(), timeout=30):
    mode = fetch_allowed(url, pol)
    return mode == "intake" or (mode == "agent" and robots_ok(url, handlers, timeout))


class PolicyRedirect(urllib.request.HTTPRedirectHandler):
    """Re-checks every redirect hop before the next request is built: a refused hop raises, so no request reaches it."""
    def __init__(self, pol, handlers=()):
        self.pol, self.handlers = pol, handlers

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        newurl = urllib.parse.urljoin(req.full_url, newurl)
        if not _allowed_hop(newurl, self.pol, self.handlers):
            raise BlockedFetch(f"redirect to {SP.host_of(newurl) or newurl} refused by the crawl policy or robots.txt")
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def policy_open(url, pol, timeout=30, handlers=()):
    """The only network opener in this module. `handlers` lets tests inject a fake transport (zero real requests)."""
    if not _allowed_hop(url, pol, handlers, timeout):
        raise BlockedFetch(f"{SP.host_of(url) or url} refused by the crawl policy or robots.txt")
    opener = urllib.request.build_opener(PolicyRedirect(pol, handlers), *handlers)
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    return opener.open(req, timeout=timeout)


def hash_image(url, timeout=30, limit=25_000_000, pol=None, handlers=()):
    """sha256 of an attachment, streamed in memory; nothing is written. Honest UA, no retries around a block, policy on every hop."""
    pol = pol if pol is not None else SP.load()
    h, n = hashlib.sha256(), 0
    with policy_open(url, pol, timeout, handlers) as resp:
        while True:
            b = resp.read(65536)
            if not b:
                break
            n += len(b)
            if n > limit:
                raise ValueError("attachment too large")
            h.update(b)
    return "sha256:" + h.hexdigest()


def doc_from_issue(it, cat_lookup, pol, old=None, hasher=hash_image, now=None):
    """Issue (gh JSON) -> claim doc. Never copies the handle; free text is scrubbed of handles and emails."""
    s = sections(it.get("body"))
    get = lambda f: s.get(FORM[f], "")
    pay = parse_payload(get("payload"))
    et = (re.match(r"\s*(E[1-4])\b", get("evidence_type")) or [None, None])[1]
    safe = lambda xs: [c for c in (clean_url(u.rstrip(".,;")) for u in xs) if c]      # review-7: sanitized before anything persists
    urls = safe(URL.findall(get("evidence_url")))
    extra = safe(URL.findall(get("extra_urls")))
    sdu = (safe(URL.findall(get("single_design_url"))) or [None])[0]
    applies = [x for x in re.split(r"[\s,;]+", get("applies_to")) if re.fullmatch(r"[a-z0-9][a-z0-9-]{1,95}", x) and not has_pii(x)]
    old_tr = {i.get("sha256"): i.get("transcription") for i in ((old or {}).get("evidence") or {}).get("images") or []}
    images = []
    for u in dict.fromkeys(IMG.findall(it.get("body") or "")):
        try:
            sha = hasher(u) if hasher else None
        except Exception as ex:  # noqa: BLE001  a failed fetch leaves the image unhashed (check fails it); never retried around a block
            print(f"corrections: #{it['number']}: an attachment could not be hashed ({type(ex).__name__})", file=sys.stderr)
            sha = None
        images.append({"sha256": sha, "transcription": old_tr.get(sha)})
    mm = get("measurement_mode")
    mode = next((m for m in MODES if re.search(rf"\b{m}\b", mm)), None)
    ev = {"type": et}
    if urls:
        ev["url"] = urls[0]
    if urls[1:] + extra:
        ev["extra_urls"] = list(dict.fromkeys(urls[1:] + extra))
    if sdu:
        ev["single_design_url"] = sdu.rstrip(".,;")
    ev["images"] = images
    iurl = str(it.get("html_url") or "")
    doc = {"issue": int(it["number"]), "url": iurl if re.fullmatch(r"https://github\.com/[\w.-]+/[\w.-]+/issues/\d+", iurl) else None,
           "state": it.get("state") if it.get("state") in ("open", "closed") else None,
           "entity": clean_id(pay.get("entity_id") or pay.get("entity")), "key": clean_id(pay.get("key")),
           "shown_value": scrub(pay.get("shown_value"), 200) if pay.get("shown_value") is not None else None,
           "release": clean_id(pay.get("build") or pay.get("release")),
           "value": scrub(get("claimed_value"), 200), "evidence": ev}
    if applies:
        doc["applies_to"] = applies
    doc["kind"] = TYPES.get(et)
    if TYPES.get(et) == "measured":
        doc["measurement"] = {"mode": mode}
    doc["conditions"] = (old or {}).get("conditions") or {}
    ct = scrub(get("conditions"), 200)
    if ct:
        doc["conditions_text"] = ct
    doc["terms_ack"] = checked(get("terms"))
    doc["terms_version"] = TERMS_VERSION
    doc["coi"] = checked(get("coi"))
    doc["submitted_by"] = (old or {}).get("submitted_by") or "crowd"
    doc["submitted_at"] = it.get("created_at")
    src = source_of(doc, pol)
    doc["source"] = {"url": src["url"], "tier": src["tier"], **({"via": src["evidence"]} if src["evidence"] else {})}
    doc["synced_at"] = now or dt.datetime.now(dt.timezone.utc).strftime("%FT%TZ")
    return sanitize_doc(doc)


def _dump(doc):
    return yaml.safe_dump(doc, sort_keys=False, allow_unicode=True, width=140)


def sync(repo, data_dir=None, dry_run=False, issues=None, hasher=hash_image, ack_burst=False, now=None, out=sys.stdout, pol=None):
    """-> {written, unchanged, over_limit: [issue numbers], paused: bool}. Posts nothing."""
    pol = pol or SP.load()
    if hasher is hash_image:
        hasher = lambda u: hash_image(u, pol=pol)       # noqa: E731  the policy-checked opener with this run's policy
    cl = Catalogue(data_dir)
    issues = fetch_issues(repo) if issues is None else issues
    now_t = dt.datetime.strptime(now, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=dt.timezone.utc) if now else dt.datetime.now(dt.timezone.utc)
    recent = [it for it in issues if (now_t - dt.datetime.strptime(it["created_at"], "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=dt.timezone.utc)).total_seconds() < 86400]
    res = {"issues": len(issues), "written": [], "unchanged": 0, "over_limit": [], "paused": False}
    if len(recent) > BURST_PER_DAY and not ack_burst:
        res["paused"] = True
        print(f"corrections sync PAUSED: {len(recent)} corrections in the last 24 h (> {BURST_PER_DAY}). A human looks first, then re-runs with --ack-burst.", file=out)
        return res
    per = Counter()
    keep = []
    for it in sorted(issues, key=lambda x: (x["created_at"], x["number"])):
        login = it.get("login") or ""
        if it.get("state") == "open":
            per[login] += 1
            if per[login] > MAX_OPEN_PER_ACCOUNT:
                res["over_limit"].append(it["number"])
                continue
        keep.append(it)
    d = corrections_dir(data_dir)
    for it in keep:
        p = d / f"{it['number']}.yaml"
        old = yaml.safe_load(p.read_text()) if p.exists() else None
        doc = doc_from_issue(it, cl, pol, old, hasher, now)
        if old is not None and {k: v for k, v in old.items() if k != "synced_at"} == {k: v for k, v in doc.items() if k != "synced_at"}:
            res["unchanged"] += 1
            continue
        res["written"].append(p.name)
        if dry_run:
            print(f"[dry-run] would write {p.relative_to(d.parent.parent) if d.parent.parent in p.parents else p}:\n" + _dump(doc), file=out)
        else:
            d.mkdir(parents=True, exist_ok=True)
            p.write_text(_dump(doc))
    for n in res["over_limit"]:
        print(f"over the {MAX_OPEN_PER_ACCOUNT}-open limit (not synced; a maintainer runs): gh issue edit {n} --repo {repo} --add-label {TRIAGE_LABEL}", file=out)
    print(f"corrections sync{' (dry run, nothing written)' if dry_run else ''}: {res['issues']} issues, {len(res['written'])} "
          f"{'to write' if dry_run else 'written'}, {res['unchanged']} unchanged, {len(res['over_limit'])} over the per-account limit", file=out)
    return res


# ---------------------------------------------------------------------------------------------------------------- queue
def ledger_claims(data_dir=None):
    lp = Path(data_dir or ROOT / "data") / "decisions" / "ledger.jsonl"
    out = {}
    if lp.exists():
        for ln in lp.read_text().splitlines():
            if ln.strip() and not ln.lstrip().startswith("#"):
                d = json.loads(ln)
                if d.get("action") in ("accept_claim", "reject_claim"):
                    out[d["claim"]] = d
    return out


def current_value(cat, eid, key, api=None):
    api = Path(api or ROOT / "docs" / "api" / "v1")
    p = api / str(cat) / "products" / f"{eid}.json"
    if not p.exists():
        return "not published", None
    sp = (json.loads(p.read_text()).get("specs") or {}).get(key)
    if not sp:
        return "unknown", None
    return sp.get("status"), sp.get("value")


def queue(data_dir=None, out_path=None, pol=None, api=None, now=None):
    pol = pol or SP.load()
    res = check_all(data_dir, pol)
    led = ledger_claims(data_dir)
    digests = current_digests(data_dir)
    cl = Catalogue(data_dir)
    now_t = dt.datetime.strptime(now, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=dt.timezone.utc) if now else dt.datetime.now(dt.timezone.utc)
    lines = ["# Corrections review queue", "",
             f"Generated by `scripts/corrections.py queue`. Decide with `scripts/review_corrections.py` (a human handle writes every ledger line; "
             f"no LLM decides). Fast reject reasons: {', '.join(FAST_REJECT)}.", "",
             "| claim | entity | key | current | proposed | evidence | kind | check | age | decision |", "|--|--|--|--|--|--|--|--|--|--|"]
    close = []
    for p, doc, bad in res:
        age = ""
        if doc.get("submitted_at"):
            try:
                age = f"{(now_t - dt.datetime.strptime(doc['submitted_at'], '%Y-%m-%dT%H:%M:%SZ').replace(tzinfo=dt.timezone.utc)).days} d"
            except ValueError:
                pass
        for cid, eid in claim_ids(doc):
            st, val = current_value(cl.cat.get(eid), eid, doc.get("key"), api)
            dec = led.get(cid)
            stale = dec and dec["action"] == "accept_claim" and dec.get("digest") != digests.get(cid)
            decision = "pending (changed since accept: withheld)" if stale else f"{dec['action'].split('_')[0]} by {dec['by']}" if dec else "pending"
            dec = None if stale else dec
            chk = "ok" if not bad else "; ".join(sorted({c for c, _ in bad}))
            lines.append(f"| {cid} | {eid} | {doc.get('key')} | {st}{'' if val is None else ' ' + json.dumps(val)[:40]} | {str(doc.get('value'))[:40]} | "
                         f"{(doc.get('evidence') or {}).get('type')} | {doc.get('kind')} | {chk} | {age} | {decision} |")
            if dec and doc.get("state") == "open" and doc.get("issue") is not None:
                close.append(doc["issue"])
    if close:
        rel = "the next release"
        ip = CODE / "releases" / "index.jsonl"
        if ip.exists():
            last = [json.loads(x) for x in ip.read_text().splitlines() if x.strip()]
            rel = f"release {last[-1]['release']}" if last else rel
        lines += ["", "## Close-out drafts (never posted by a script; run after the release that publishes the decision)", ""]
        for n in sorted(set(close)):
            lines.append(f"- `gh issue close {n} --comment \"Decided and published in {rel}: see /v1/changes. Thank you.\"`")
    probs = [(p, b) for p, _, b in res if b]
    if probs:
        lines += ["", "## Check problems", ""] + [f"- {p.name}: " + "; ".join(f"{c}: {m}" for c, m in b) for p, b in probs]
    text = "\n".join(lines) + "\n"
    out_path = Path(out_path or CODE / "team" / "queue" / "corrections.md")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(text)
    return text


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("sync")
    s.add_argument("--repo", default=site_repo())
    s.add_argument("--dry-run", action="store_true")
    s.add_argument("--issues-json", help="saved `gh api` issue list (testing/offline) instead of calling gh")
    s.add_argument("--no-images", action="store_true", help="do not fetch attachments (images stay unhashed and fail check)")
    s.add_argument("--ack-burst", action="store_true")
    s.add_argument("--data", default=None)
    c = sub.add_parser("check")
    c.add_argument("files", nargs="*")
    c.add_argument("--data", default=None)
    q = sub.add_parser("queue")
    q.add_argument("--out", default=None)
    q.add_argument("--data", default=None)
    a = ap.parse_args()
    if a.cmd == "sync":
        issues = json.loads(Path(a.issues_json).read_text()) if a.issues_json else None
        r = sync(a.repo, a.data, a.dry_run, issues, None if a.no_images else hash_image, a.ack_burst)
        sys.exit(3 if r["paused"] else 0)
    if a.cmd == "check":
        res = check_all(a.data, paths=a.files or None)
        nbad = 0
        for p, _, bad in res:
            for code, msg in bad:
                print(f"{p.name}: {code}: {msg}")
            nbad += bool(bad)
        print(f"corrections check: {len(res)} files, {nbad} failing", file=sys.stderr)
        sys.exit(1 if nbad else 0)
    if a.cmd == "queue":
        queue(a.data, a.out)
        print(f"wrote {a.out or 'team/queue/corrections.md'}", file=sys.stderr)


if __name__ == "__main__":
    main()
