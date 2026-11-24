import type { Context, Hono } from "hono";
import { PRICES, paidEnabled, type Env } from "./config.ts";

// Minimal stateless MCP (Streamable HTTP, JSON responses). Paid tools reuse the paid REST routes through an
// internal subrequest, so there is exactly one payment path (the x402 middleware). Payment follows the x402 MCP
// transport shape: the client sends the signed payload in params._meta["x402/payment"]; an unpaid call returns an
// error result whose structuredContent is the x402 PaymentRequired object; success carries the settlement in
// result._meta["x402/payment-response"].
// TODO: swap for Cloudflare agents `McpAgent` + `paidTool` if/when a Durable Object runtime is wanted (needs DO binding).

const TOOLS = [
  { name: "query_specs", description: `Filtered spec query with per-value provenance. Costs ${PRICES.query} USDC (x402).`,
    inputSchema: { type: "object", properties: { category: { type: "string" }, filters: { type: "string", description: "key<op>value comma list, e.g. cpu.cores>=8,brand=ASUS" }, q: { type: "string" }, fields: { type: "string" }, limit: { type: "integer" }, offset: { type: "integer" } }, required: ["category"] },
    route: "/v1/query" },
  { name: "match_product", description: `Resolve a retail listing title to a specsheet product id. Costs ${PRICES.match} USDC (x402). Not yet live.`,
    inputSchema: { type: "object", properties: { title: { type: "string" }, category: { type: "string" } }, required: ["title"] },
    route: "/v1/match" },
];

const rpc = (id: unknown, result: unknown) => ({ jsonrpc: "2.0", id, result });
const rpcErr = (id: unknown, code: number, message: string) => ({ jsonrpc: "2.0", id, error: { code, message } });

export async function handleMcp(c: Context<{ Bindings: Env }>, app: Hono<{ Bindings: Env }>) {
  let msg: any;
  try { msg = await c.req.json(); } catch { return c.json(rpcErr(null, -32700, "parse error"), 400); }
  if (Array.isArray(msg)) return c.json(rpcErr(null, -32600, "batching not supported"), 400);
  const { id, method, params } = msg ?? {};
  if (id !== undefined && !paidEnabled(c.env) && method !== "ping") return c.json(rpcErr(id, -32000, "coming soon: paid tools are not enabled"), 503);
  if (id === undefined) return new Response(null, { status: 202 }); // notification
  switch (method) {
    case "initialize":
      return c.json(rpc(id, { protocolVersion: params?.protocolVersion ?? "2025-06-18", capabilities: { tools: {} }, serverInfo: { name: "specsheet", version: "0.1.0" },
        instructions: "Paid tools use x402 (USDC, Base Sepolia testnet by default). Unpaid calls return the payment requirements; resend with _meta['x402/payment']." }));
    case "ping": return c.json(rpc(id, {}));
    case "tools/list": return c.json(rpc(id, { tools: TOOLS.map(({ route: _r, ...t }) => t) }));
    case "tools/call": {
      const tool = TOOLS.find((t) => t.name === params?.name);
      if (!tool) return c.json(rpcErr(id, -32602, `unknown tool ${params?.name}`));
      const url = new URL(tool.route, c.req.url);
      for (const [k, v] of Object.entries((params?.arguments ?? {}) as Record<string, unknown>)) if (v !== undefined && v !== null) url.searchParams.set(k, String(v));
      const headers = new Headers({ accept: "application/json" });
      const pay = params?._meta?.["x402/payment"];
      if (pay) headers.set("PAYMENT-SIGNATURE", typeof pay === "string" ? pay : btoa(JSON.stringify(pay)));
      const r = await app.fetch(new Request(url, { headers }), c.env, c.executionCtx);
      const text = await r.text();
      let json: unknown; try { json = JSON.parse(text); } catch { json = undefined; }
      if (r.status === 402) {
        const hdr = r.headers.get("PAYMENT-REQUIRED");
        let req: unknown = json; try { if (hdr) req = JSON.parse(atob(hdr)); } catch { /* fall back to body */ }
        return c.json(rpc(id, { isError: true, structuredContent: req, content: [{ type: "text", text: JSON.stringify(req) }], _meta: { "x402/error": { code: 402 } } }));
      }
      const meta: Record<string, unknown> = {};
      const pr = r.headers.get("PAYMENT-RESPONSE");
      if (pr) meta["x402/payment-response"] = pr;
      return c.json(rpc(id, { isError: r.status >= 400, structuredContent: json, content: [{ type: "text", text }], _meta: meta }));
    }
    default: return c.json(rpcErr(id, -32601, `method not found: ${method}`));
  }
}
