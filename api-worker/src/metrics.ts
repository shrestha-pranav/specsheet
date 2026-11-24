// Metrics contract (product/measurement-plan.md §1-2, decisions D4): one Analytics Engine point per request (MCP: one per logical tool
// call), dataset specsheet_requests. Never written: IP, full UA, request bodies (except redacted miss text), filter values, referrers.
import type { Env } from "./config.ts";

export type Kind = "api" | "mcp" | "beacon" | "ops";
export type Outcome = "ok_results" | "ok_empty" | "match_fail" | "bad_input" | "quota" | "breaker" | "error" | "ok";
export interface Point {
  kind: Kind; route: string; category: string; status: number; outcome: Outcome; ua: string; mode: string; traffic: string;
  release: string; mcpClient: string; cid: string; detail: string; results: number; bytes: number; wallMs: number; cacheHit: boolean;
}

const BOTS: [RegExp, string][] = [
  [/googlebot|google-inspectiontool|googleother/i, "google"], [/bingbot|bingpreview/i, "bing"], [/gptbot|oai-searchbot|chatgpt-user/i, "openai"],
  [/claudebot|claude-user|claude-searchbot|anthropic-ai/i, "anthropic"], [/perplexitybot|perplexity-user/i, "perplexity"],
  [/applebot/i, "apple"], [/duckduckbot/i, "duckduckgo"], [/yandex/i, "yandex"], [/baiduspider/i, "baidu"], [/ccbot/i, "commoncrawl"],
  [/bytespider/i, "bytedance"], [/amazonbot/i, "amazon"], [/facebookexternalhit|meta-externalagent/i, "meta"], [/ahrefsbot|semrushbot|mj12bot|dotbot/i, "seo"],
  [/bot\b|crawler|spider|uptime|monitor/i, "other"],
];

/** Declared (spoofable) UA family. The full UA string is never written. */
export function uaFamily(ua: string | null | undefined, route = ""): string {
  const s = ua ?? "";
  for (const [re, name] of BOTS) if (re.test(s)) return `bot:${name}`;
  if (route.startsWith("/mcp") || /\bmcp\b|modelcontextprotocol|claude-code|cursor|cline|windsurf/i.test(s)) return "mcp";
  if (/^(curl|wget|httpie|xh)\//i.test(s) || /\b(curl|wget|httpie)\//i.test(s)) return "curl-like";
  if (/python|aiohttp|httpx|requests\//i.test(s)) return "python";
  if (/node|undici|axios|got\b|deno|bun\//i.test(s)) return "node";
  if (/^mozilla\//i.test(s)) return "browser";
  return "other";
}

/** MCP clientInfo.name, normalized to [a-z0-9-]{1,32} or 'other'. */
export function normClientName(n: unknown): string {
  if (typeof n !== "string") return "other";
  const s = n.toLowerCase().trim().replace(/[\s_./]+/g, "-").replace(/[^a-z0-9-]/g, "").replace(/-+/g, "-").replace(/^-|-$/g, "");
  return /^[a-z0-9-]{1,32}$/.test(s) ? s : "other";
}

/** Miss text: lowercase, emails, URLs and phone-like runs (>=7 digits with spaces/dashes/parentheses) -> '·', then at most 80 chars. */
export function redactMiss(text: string): string {
  let s = String(text ?? "").toLowerCase().normalize("NFKC");
  s = s.replace(/[\u0000-\u001f\u007f]/g, " ");
  s = s.replace(/\b[a-z0-9._%+-]+@[a-z0-9.-]+\.[a-z]{2,}\b/g, "·");
  s = s.replace(/\b(?:https?:\/\/|www\.)\S+/g, "·").replace(/\b[a-z0-9-]+(?:\.[a-z0-9-]+)*\.(?:com|net|org|io|co|us|uk|de|ca|info|biz|me|ly|gl|app|dev|xyz)\b(?:\/\S*)?/g, "·");
  s = s.replace(/\+?\(?\d[\d\s().-]{5,}\d/g, (m) => ((m.match(/\d/g)?.length ?? 0) >= 7 && /[\s().-]/.test(m) ? "·" : m));
  s = s.replace(/\d{10,}/g, "·"); // long bare digit runs (account / card / phone without separators)
  s = s.replace(/\s+/g, " ").trim();
  return [...s].slice(0, 80).join("");
}

// retry = same cid + canonical key within 10 s (per isolate, approximate)
const recent = new Map<string, number>();
export function trafficClass(req: Request, ua: string, cid: string, canonical: string, now = Date.now()): string {
  if (req.headers.get("x-specsheet-test") === "1" || /specsheet-smoke/i.test(req.headers.get("user-agent") ?? "")) return "test";
  if (ua.startsWith("bot:")) return "bot";
  if (canonical && cid) {
    const k = `${cid}|${canonical}`, t = recent.get(k);
    recent.set(k, now);
    if (recent.size > 5000) for (const [kk, tt] of recent) { if (now - tt > 10_000) recent.delete(kk); if (recent.size < 4000) break; }
    if (t !== undefined && now - t < 10_000) return "retry";
  }
  return "real";
}

/** Fields in the contract order: index1; blob1..blob11; double1..double4. */
export function toDataPoint(p: Point): AnalyticsEngineDataPoint {
  return {
    indexes: [p.kind],
    blobs: [p.route, p.category, String(p.status), p.outcome, p.ua, p.mode, p.traffic, p.release, p.mcpClient, p.cid, p.detail],
    doubles: [p.results, p.bytes, p.wallMs, p.cacheHit ? 1 : 0],
  };
}

export function writePoint(env: Env, p: Point): AnalyticsEngineDataPoint {
  const dp = toDataPoint(p);
  try { env.METRICS?.writeDataPoint(dp); } catch { /* metrics never fail a request */ }
  return dp;
}
