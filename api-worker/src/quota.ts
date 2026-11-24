// D3.7 quota and breaker.
// Layer 1: Workers Rate Limiting binding, 60/min per client key (approximate, per location).
// Layer 2: `Budget` Durable Objects (SQLite backend), 16 shards. Each shard keeps today's counts in memory, writes them to SQLite at most
// every 60 s (alarm as the backstop for idle shards), and syncs with the single `Breaker` DO at most every 30 s (or sooner when its
// unreported count nears the threshold): it reports its data-route delta and receives { salt, tripped }.
// Privacy (product/measurement-plan.md §1): the client key (IPv4 /32, IPv6 /64) is passed to the shard in memory and never stored. Counters
// are keyed by HMAC(daily salt, client key), so they cannot be linked to an IP once the salt is deleted (01:00 UTC next day, Breaker alarm).
// cid = first 16 hex of HMAC(daily salt, client key | UA family). Routing to a shard uses an unsalted HMAC with a fixed label: 16 buckets
// identify nobody, and routing must work before the salt is known.
import { DurableObject } from "cloudflare:workers";
import { QUOTA } from "./config.ts";

import { DAY_MS, hmac, nextOneAm, utcDay } from "./keys.ts";
export { DAY_MS, clientKey, secondsToReset, shardName, utcDay } from "./keys.ts";

export interface Bucket { kind: string; n: number; limit: number; data?: boolean } // data: counts toward the breaker total
export interface SpendResult { cid: string; ok: boolean[]; counts: number[]; tripped: boolean; total: number }

export class Budget extends DurableObject {
  private day = "";
  private salt: Uint8Array | null = null;
  private counts = new Map<string, number>(); // `${kind}|${hmac}` -> n, today only
  private dirty = new Set<string>();
  private lastFlush = Date.now();
  private lastSync = 0;
  private pending = 0;
  private tripped = false;
  private total = 0;
  private threshold: number = QUOTA.breakerDaily;

  constructor(ctx: DurableObjectState, env: unknown) {
    super(ctx, env as never);
    ctx.blockConcurrencyWhile(async () => {
      this.ctx.storage.sql.exec("CREATE TABLE IF NOT EXISTS counts (day TEXT, k TEXT, n INTEGER, PRIMARY KEY (day, k))");
      this.rollDay(utcDay());
    });
  }

  private rollDay(day: string) {
    if (day === this.day) return;
    this.flush();
    this.day = day; this.salt = null; this.counts.clear(); this.dirty.clear(); this.pending = 0; this.tripped = false; this.total = 0;
    this.ctx.storage.sql.exec("DELETE FROM counts WHERE day < ?", day); // counters are deleted at the day reset
    for (const r of this.ctx.storage.sql.exec<{ k: string; n: number }>("SELECT k, n FROM counts WHERE day = ?", day)) this.counts.set(r.k, r.n);
  }

  private flush() {
    if (!this.dirty.size) return;
    for (const k of this.dirty) this.ctx.storage.sql.exec("INSERT OR REPLACE INTO counts (day, k, n) VALUES (?, ?, ?)", this.day, k, this.counts.get(k) ?? 0);
    this.dirty.clear();
    this.lastFlush = Date.now();
  }

  private async sync(threshold: number) {
    const ns = (this.env as { BREAKER: DurableObjectNamespace<Breaker> }).BREAKER;
    const stub = ns.get(ns.idFromName("global"));
    const r = await stub.sync(this.day, this.pending, threshold);
    this.pending = 0; this.lastSync = Date.now(); this.tripped = r.tripped; this.total = r.total;
    this.salt = new Uint8Array(r.salt);
  }

  async spend(key: string, ua: string, buckets: Bucket[], threshold: number): Promise<SpendResult> {
    this.rollDay(utcDay());
    this.threshold = threshold;
    const data = buckets.filter((b) => b.data).reduce((n, b) => n + b.n, 0);
    this.pending += data;
    const now = Date.now();
    if (!this.salt || now - this.lastSync >= 30_000 || this.pending >= Math.max(1, Math.floor(threshold / 160))) {
      try { await this.sync(threshold); } catch (e) { if (!this.salt) throw e; } // stale breaker state beats failing every request
    }
    const salt = this.salt!;
    const kh = (await hmac(salt, key)).slice(0, 32);
    const cid = (await hmac(salt, `${key}|${ua}`)).slice(0, 16);
    const ok: boolean[] = [], counts: number[] = [];
    for (const b of buckets) {
      const k = `${b.kind}|${kh}`;
      const n = this.counts.get(k) ?? 0;
      const fits = n + b.n <= b.limit;
      if (fits) { this.counts.set(k, n + b.n); this.dirty.add(k); }
      ok.push(fits); counts.push(fits ? n + b.n : n);
    }
    if (now - this.lastFlush >= 60_000) this.flush();
    if (this.dirty.size || this.pending) {
      const at = await this.ctx.storage.getAlarm();
      if (at === null) await this.ctx.storage.setAlarm(now + 60_000);
    }
    return { cid, ok, counts, tripped: this.tripped, total: this.total };
  }

  async alarm() {
    this.rollDay(utcDay());
    this.flush();
    if (this.pending) { try { await this.sync(this.threshold); } catch { await this.ctx.storage.setAlarm(Date.now() + 60_000); } }
  }
}

/** Global daily data-route total and the daily salt. One instance ("global"). */
export class Breaker extends DurableObject {
  constructor(ctx: DurableObjectState, env: unknown) {
    super(ctx, env as never);
    ctx.blockConcurrencyWhile(async () => {
      this.ctx.storage.sql.exec("CREATE TABLE IF NOT EXISTS totals (day TEXT PRIMARY KEY, n INTEGER)");
      this.ctx.storage.sql.exec("CREATE TABLE IF NOT EXISTS salts (day TEXT PRIMARY KEY, salt BLOB)");
    });
  }

  private saltFor(day: string): ArrayBuffer {
    const row = this.ctx.storage.sql.exec<{ salt: ArrayBuffer }>("SELECT salt FROM salts WHERE day = ?", day).toArray()[0];
    if (row) return row.salt;
    const salt = crypto.getRandomValues(new Uint8Array(32));
    this.ctx.storage.sql.exec("INSERT INTO salts (day, salt) VALUES (?, ?)", day, salt.buffer);
    return salt.buffer;
  }

  async sync(day: string, n: number, threshold: number): Promise<{ salt: ArrayBuffer; tripped: boolean; total: number }> {
    if (day !== utcDay()) day = utcDay();
    const salt = this.saltFor(day);
    const cur = this.ctx.storage.sql.exec<{ n: number }>("SELECT n FROM totals WHERE day = ?", day).toArray()[0]?.n ?? 0;
    const total = cur + n;
    if (n) this.ctx.storage.sql.exec("INSERT OR REPLACE INTO totals (day, n) VALUES (?, ?)", day, total);
    if ((await this.ctx.storage.getAlarm()) === null) await this.ctx.storage.setAlarm(nextOneAm());
    return { salt, tripped: total >= threshold, total };
  }

  async status(threshold: number) {
    const day = utcDay();
    const total = this.ctx.storage.sql.exec<{ n: number }>("SELECT n FROM totals WHERE day = ?", day).toArray()[0]?.n ?? 0;
    return { day, total, tripped: total >= threshold };
  }

  /** 01:00 UTC: delete yesterday's salt (no cid can be recomputed after this) and old totals. */
  async alarm() {
    const today = utcDay();
    this.ctx.storage.sql.exec("DELETE FROM salts WHERE day < ?", today);
    this.ctx.storage.sql.exec("DELETE FROM totals WHERE day < ?", utcDay(Date.now() - 7 * DAY_MS));
    await this.ctx.storage.setAlarm(nextOneAm());
  }
}

