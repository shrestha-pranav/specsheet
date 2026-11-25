// OpenAPI and llms.txt list only routes that return data in the current mode (D3.5, D4 discovery). Match appears only once ported.
import { BOUNDS, PRICES, QUOTA, type Env, type Mode } from "./config.ts";

export interface Surface { mode: Mode; match: boolean; release: string; categories: string[]; site: string }

const NOTE = "Free preview: quotas may change, paid tier not enabled.";
const NAT = `Quota is per client network (IPv4 address or IPv6 /64), so users behind one NAT or proxy share it: ${QUOTA.daily} data calls per UTC day shared by REST and MCP tool calls (an MCP batch of N tool calls counts N), plus ${QUOTA.perMinute}/minute. 429 responses carry Retry-After in seconds.`;
const bulkHint = (site: string) => `For volume or full copies, use the free static dataset on GitHub Pages (${site}/api/v1/manifest.json, per-category index and product files) instead of this API.`;

export function openapi(env: Env, origin: string, s: Surface) {
  const paid = s.mode === "on";
  const price = (k: keyof typeof PRICES) => (paid ? { "x-price": { amount: PRICES[k].replace("$", ""), currency: "USD", provisional: true } } : {});
  const errs = {
    "400": { description: "Invalid input (never charged; counts once against quota)" }, "414": { description: "URL longer than 2048" },
    "429": { description: "Over quota; Retry-After seconds" }, "503": { description: "preview_paused / preview_capacity; Retry-After seconds" },
    ...(paid ? { "402": { description: "Payment required (x402); free allowance spent" } } : {}),
  };
  const ok = (schema: object) => ({ "200": { description: "OK", content: { "application/json": { schema } } } });
  const paths: Record<string, unknown> = {
    "/": { get: { summary: "Same as /health", responses: ok({ type: "object" }) } },
    "/health": { get: { summary: "Release, policy version, modes, breaker state", responses: ok({ type: "object" }) } },
    "/openapi.json": { get: { summary: "This document", responses: ok({ type: "object" }) } },
    "/llms.txt": { get: { summary: "Plain-text summary for agents", responses: { "200": { description: "text" } } } },
  };
  if (s.mode !== "on-bad") {
    paths["/v1/query"] = { get: { summary: "Filtered spec query with per-value provenance", ...price("query"),
      parameters: [
        { name: "category", in: "query", required: true, schema: { type: "string", enum: s.categories } },
        { name: "filters", in: "query", schema: { type: "string", maxLength: BOUNDS.filtersChars }, description: `Comma list of key<op>value (ops >= <= > < != = ~), at most ${BOUNDS.filterClauses} clauses, keys from the category schema, values <= ${BOUNDS.filterValue} chars. Example: cpu.cores>=8,brand=ASUS. Unknown values never match, but rows that might match (unknown, conflicted, disagreeing sources) are counted in \`maybe\` and listed with include=maybe.` },
        { name: "q", in: "query", schema: { type: "string", maxLength: BOUNDS.q }, description: "Substring match on brand/name/variant/identifiers" },
        { name: "fields", in: "query", schema: { type: "string" }, description: `Comma list of at most ${BOUNDS.fields} spec keys to return` },
        { name: "include", in: "query", schema: { type: "string", enum: ["matches", "maybe"], default: "matches" }, description: "maybe = also list rows that might match, after the matches (each result carries status and filter_status)" },
        { name: "limit", in: "query", schema: { type: "integer", default: BOUNDS.limitDefault, minimum: 1, maximum: BOUNDS.limitMax } },
        { name: "offset", in: "query", schema: { type: "integer", default: 0, minimum: 0, maximum: BOUNDS.offsetMax }, description: "Deeper reads: use the static files" },
      ], responses: { ...ok({ $ref: "#/components/schemas/QueryResult" }), ...errs } } };
    paths["/v1/changes"] = { get: { summary: "Record diff since a release", ...price("changes"),
      parameters: [
        { name: "since", in: "query", required: true, schema: { type: "string" }, description: `A retained release id (see /health) or an ISO date within ${BOUNDS.changesDays} days` },
        { name: "category", in: "query", schema: { type: "string", enum: s.categories } },
        { name: "limit", in: "query", schema: { type: "integer", default: BOUNDS.changesLimitDefault, maximum: BOUNDS.changesLimitMax } },
      ], responses: { ...ok({ type: "object" }), ...errs } } };
    paths["/v1/presets"] = { get: { summary: "Curated killer queries as /v1/query filter strings, with fill gate and counts (same payload as MCP list_presets; unpriced, one budget unit)",
      parameters: [{ name: "category", in: "query", schema: { type: "string", enum: s.categories } }], responses: { ...ok({ type: "object" }), ...errs } } };
    if (s.match) paths["/v1/match"] = { get: { summary: "Resolve a retail listing title to a product id (precision first: no answer beats a wrong one)", ...price("match"),
      parameters: [{ name: "title", in: "query", required: true, schema: { type: "string", maxLength: BOUNDS.title } }, { name: "category", in: "query", schema: { type: "string", enum: s.categories } }],
      responses: { ...ok({ type: "object" }), ...errs } } };
    if (paid) {
      paths["/v1/bulk/{category}.jsonl.gz"] = { get: { summary: "Full category dump (gzip JSON lines)", ...price("bulk_category"), parameters: [{ name: "category", in: "path", required: true, schema: { type: "string", enum: s.categories } }], responses: { "200": { description: "application/gzip" }, ...errs } } };
      paths["/v1/bulk/all.jsonl.gz"] = { get: { summary: "All categories (gzip JSON lines)", ...price("bulk_all"), responses: { "200": { description: "application/gzip" }, ...errs } } };
    }
    paths["/mcp"] = { post: { summary: `MCP (stateless Streamable HTTP, JSON-RPC, batch <= ${BOUNDS.mcpBatch}, body <= 16 KB). Tools: ${tools(s).join(", ")}`, responses: { "200": { description: "JSON-RPC response" }, "413": { description: "Body too large" }, "429": { description: "Over quota" } } } };
  }
  return {
    openapi: "3.1.0",
    info: { title: "specsheet API", version: "0.2.0", description: `${paid ? "Paid mode (provisional prices, x402)." : NOTE} ${NAT} ${bulkHint(s.site)}` },
    servers: [{ url: origin }], "x-release": s.release, paths,
    components: { schemas: { QueryResult: { type: "object", properties: {
      release: { type: "string" }, category: { type: "string" }, include: { type: "string" }, total: { type: "integer", description: "rows matching every filter" },
      maybe: { type: "object", description: "{total, unknown, conflicted, disagree}: rows that might match (always reported)" }, offset: { type: "integer" }, count: { type: "integer" },
      results: { type: "array", items: { type: "object", properties: { id: { type: "string" }, brand: { type: "string" }, name: { type: "string" },
        status: { type: "string", enum: ["match", "maybe"] },
        filter_status: { type: "object", description: "spec filter key -> match | unknown | conflicted | disagree" },
        unknown_core: { type: "object", description: "core spec key -> status (unknown, not_published, conflicted, not_applicable) for core keys with no published value" },
        specs: { type: "object", description: "key -> {value, unit, kind, sources: [source id]}" }, sources: { type: "array", description: "{id, url, label, tier, retrieved_at, ...} for the ids used in specs", items: { type: "object" } } } } } } } } },
  };
}

export const tools = (s: Surface) => (s.mode === "on-bad" ? [] : ["query_specs", ...(s.match ? ["match_product"] : []), "list_categories_keys", "list_presets"]);

export function llmsTxt(origin: string, s: Surface) {
  if (s.mode === "on-bad") return `# specsheet API\n> Release ${s.release}. Paid routes are unavailable (payments not configured). ${bulkHint(s.site)}\n- [Health](${origin}/health), [OpenAPI](${origin}/openapi.json), ${origin}/llms.txt\n`;
  const paid = s.mode === "on";
  const p = (k: keyof typeof PRICES) => (paid ? ` (${PRICES[k]} per call after the free allowance; provisional)` : "");
  return `# specsheet API
> Cross-brand product spec sheets with provenance: every value lists the published source it came from. Release ${s.release}.
> ${paid ? "Paid mode with provisional prices (x402)." : NOTE}

## Routes
- GET ${origin}/v1/query?category=laptops&filters=cpu.cores>=8,mem.size>=16&limit=10 : filtered results with per-value sources${p("query")}. Categories: ${s.categories.join(", ")}
- GET ${origin}/v1/changes?since=<release id or ISO date within ${BOUNDS.changesDays} days> : record diff between releases${p("changes")}
${s.match ? `- GET ${origin}/v1/match?title=<retail listing title> : resolve a listing title to a product id, or no candidates when unsure${p("match")}\n` : ""}${paid ? `- GET ${origin}/v1/bulk/<category>.jsonl.gz${p("bulk_category")}, /v1/bulk/all.jsonl.gz${p("bulk_all")}\n` : ""}- MCP: POST ${origin}/mcp (stateless JSON-RPC), tools: ${tools(s).join(", ")}
- [OpenAPI 3.1](${origin}/openapi.json), [health](${origin}/health), this file: ${origin}/llms.txt

## Limits
- ${NAT}
- Inputs are bounded: q <= ${BOUNDS.q} chars, filters <= ${BOUNDS.filterClauses} clauses, fields <= ${BOUNDS.fields}, limit <= ${BOUNDS.limitMax}, offset <= ${BOUNDS.offsetMax}; unknown parameters are rejected.
- ${bulkHint(s.site)}

## Notes
- Values with status unknown or conflicted are never returned as facts; an absent spec means not established.
- Explicit unknown: /v1/query reports \`maybe\` counts (unknown / conflicted / disagree) for every query; include=maybe lists those rows with per-filter \`filter_status\`; every result lists \`unknown_core\` keys.
- GET ${origin}/v1/presets[?category=] : the same curated queries as MCP list_presets (free, one budget unit)
- MCP list_categories_keys (keys, types, units, facet, fill) and list_presets (curated queries as query_specs filter strings) are metadata tools.
`;
}
