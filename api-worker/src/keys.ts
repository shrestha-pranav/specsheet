// Client key, day boundary and shard routing: pure helpers (no Workers runtime imports, so unit tests run them in Node).
import { QUOTA } from "./config.ts";

export const DAY_MS = 86400_000;
export const utcDay = (t = Date.now()) => new Date(t).toISOString().slice(0, 10);
export const secondsToReset = (t = Date.now()) => Math.max(1, Math.ceil((Math.floor(t / DAY_MS) * DAY_MS + DAY_MS - t) / 1000));

/** IPv4 -> /32, IPv6 -> /64 (first four hextets of the expanded address). Rotating inside a /64 earns nothing. */
export function clientKey(ip: string | null | undefined): string {
  const s = (ip ?? "").trim();
  if (!s) return "none";
  if (!s.includes(":")) return /^\d{1,3}(\.\d{1,3}){3}$/.test(s) ? s : "invalid";
  const m4 = /^::ffff:(\d{1,3}(?:\.\d{1,3}){3})$/i.exec(s);
  if (m4) return m4[1];
  const [head, tail = ""] = s.split("::");
  const h = head ? head.split(":") : [];
  const t = s.includes("::") ? (tail ? tail.split(":") : []) : [];
  const full = s.includes("::") ? [...h, ...Array(Math.max(0, 8 - h.length - t.length)).fill("0"), ...t] : h;
  if (full.length !== 8 || !full.every((x) => /^[0-9a-f]{1,4}$/i.test(x))) return "invalid";
  return full.slice(0, 4).map((x) => x.toLowerCase().replace(/^0+(?=.)/, "")).join(":") + "::/64";
}

const enc = new TextEncoder();
const hex = (b: ArrayBuffer) => [...new Uint8Array(b)].map((x) => x.toString(16).padStart(2, "0")).join("");
export async function hmac(key: Uint8Array, msg: string): Promise<string> {
  const k = await crypto.subtle.importKey("raw", key, { name: "HMAC", hash: "SHA-256" }, false, ["sign"]);
  return hex(await crypto.subtle.sign("HMAC", k, enc.encode(msg)));
}
export async function shardName(key: string): Promise<string> {
  return `shard-${parseInt((await hmac(enc.encode("specsheet-shard-routing"), key)).slice(0, 2), 16) % QUOTA.shards}`;
}


/** 01:00 UTC after t: when the Breaker deletes the previous day's salt. */
export function nextOneAm(t = Date.now()) {
  const d0 = Math.floor(t / DAY_MS) * DAY_MS + 3600_000;
  return d0 > t ? d0 : d0 + DAY_MS;
}
