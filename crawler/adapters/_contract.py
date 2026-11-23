"""THE adapter contract module (ARCHITECTURE.md section 15.5); every adapter and the importer go through it.
_run.py = the discover/fetch/parse CLI for class-style adapters (lenovo_psref, asus, apple); tripplite/cyberpower
keep module-level functions and are exposed through registry.py (FnAdapter shim) so scripts/import.py and any
future runner see ONE interface. Snapshot log + blob store layout are identical for all five (this module owns it).

Adapter contract (ARCHITECTURE.md section 15.5) + shared helpers: dataclasses, append-only snapshot
store, claim builders, and a runner. Network goes only through crawl.Net (robots, per-host delay, breaker).

raw/<source>/snapshots.jsonl   append-only {snapshot, ref, url, final_url, status, fetched_at, etag, last_modified, adapter, blob}
raw/<source>/blobs/<sha256><ext>  content addressed, never overwritten
raw/<source>/parsed/<key>.json    derived ParseResult (rebuildable from blobs; not authoritative)
raw/<source>/discovery.json       latest Discovery (refs + checkpoint)
"""
import gzip, hashlib, json, sys, time
from dataclasses import dataclass, field, asdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "crawler"))
import crawl  # noqa: E402  (shared Net)

NET = crawl.Net()


@dataclass(frozen=True)
class Ref:
    source_id: str
    key: str
    url: str
    hints: dict = field(default_factory=dict)


@dataclass(frozen=True)
class Discovery:
    refs: list
    complete: bool
    stop_reason: str | None
    checkpoint: dict


@dataclass(frozen=True)
class Snapshot:
    snapshot: str
    ref: Ref
    status: int | str
    fetched_at: str
    final_url: str
    headers: dict
    not_modified: bool = False


@dataclass
class ParseResult:
    identifiers: list = field(default_factory=list)
    aliases: list = field(default_factory=list)
    claims: list = field(default_factory=list)
    media: list = field(default_factory=list)
    documents: list = field(default_factory=list)
    absences: list = field(default_factory=list)
    links: list = field(default_factory=list)
    fingerprints: dict = field(default_factory=dict)
    sources: list = field(default_factory=list)   # extension: record-level sources[] that claims' "s1" point at


class BlobStore:
    """Content-addressed, append-only. Doubles as the BlobReader handed to parse()."""
    def __init__(self, source_id):
        self.dir = ROOT / "raw" / source_id
        self.blobs = self.dir / "blobs"
        self.log = self.dir / "snapshots.jsonl"
        self.blobs.mkdir(parents=True, exist_ok=True)

    def put(self, body: bytes, ext: str) -> str:
        h = hashlib.sha256(body).hexdigest()
        p = self.blobs / f"{h}{ext}"
        if not p.exists():
            p.write_bytes(body)
        return f"sha256:{h}"

    def path(self, snapshot: str, ext: str) -> Path:
        return self.blobs / f"{snapshot.split(':', 1)[1]}{ext}"

    def read(self, snapshot: str, ext: str) -> bytes:
        return self.path(snapshot, ext).read_bytes()

    def append(self, snap: Snapshot, adapter: str, ext: str):
        rec = {"snapshot": snap.snapshot, "ref": asdict(snap.ref)["key"], "url": snap.ref.url, "final_url": snap.final_url,
               "status": snap.status, "fetched_at": snap.fetched_at, "etag": snap.headers.get("etag"),
               "last_modified": snap.headers.get("last_modified"), "adapter": adapter, "blob": f"blobs/{snap.snapshot.split(':',1)[1]}{ext}"}
        with self.log.open("a") as f:
            f.write(json.dumps(rec) + "\n")

    def snapshots(self):
        return [json.loads(l) for l in self.log.read_text().splitlines()] if self.log.exists() else []

    def latest(self, status=200):
        """Latest log record per ref with the given status (append-only log: last write wins)."""
        out = {}
        for s in self.snapshots():
            if s["status"] == status:
                out[s["ref"]] = s
        return out

    def read_rec(self, rec) -> bytes:
        """Body of a snapshot-log record (ext is whatever the record's blob path says)."""
        return (self.dir / rec["blob"]).read_bytes()


def http_snapshot(store, ref, url, delay, ext, adapter, headers=None, store_body=True):
    """GET through shared Net; append snapshot record + blob. Non-200 still logged (status), no blob."""
    r = NET.get(url, delay, headers=headers)
    now = time.strftime("%FT%TZ", time.gmtime())
    if r is None or isinstance(r, str):
        snap = Snapshot("sha256:", ref, r or "breaker", now, url, {})
        store.append(snap, adapter, ext)
        return snap, None
    hd = {"etag": r.headers.get("ETag"), "last_modified": r.headers.get("Last-Modified"), "content_type": r.headers.get("Content-Type")}
    if r.status_code != 200:
        snap = Snapshot("sha256:", ref, r.status_code, now, r.url, hd)
        store.append(snap, adapter, ext)
        return snap, None
    sha = store.put(r.content, ext)
    snap = Snapshot(sha, ref, 200, now, r.url, hd)
    store.append(snap, adapter, ext)
    return snap, r.content


def claim(entity, key, value, unit, raw, source, adapter, stage, observed, locator=None, quote=None, conditions=None, status="known"):
    cid = "c_" + hashlib.sha256("|".join(map(str, (entity, key, json.dumps(value), json.dumps(conditions), source, adapter))).encode()).hexdigest()[:16]
    c = {"id": cid, "key": key, "status": status, "kind": "official", "unit": unit, "raw": (raw or "")[:300],
         "source": "s1", "method": {"stage": stage, "extractor": adapter}, "observed_at": observed, "review": {"state": "candidate"}}
    if status == "known":
        c["value"] = value
    if conditions:
        c["conditions"] = conditions
    if locator:
        c["locator"] = locator
    if quote:
        c["quote"] = quote[:300]
    return c
