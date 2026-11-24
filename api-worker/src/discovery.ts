import { PRICES, paidEnabled, type Env } from "./config.ts";
import { PAID_ROUTES } from "./x402.ts";

export function openapi(env: Env, origin: string) {
  const network = env.X402_NETWORK || "eip155:84532";
  const paid = (key: keyof typeof PAID_ROUTES, price: string) => ({
    "x-x402": { scheme: "exact", price, network, asset: "USDC" },
    "x-payment-info": { price: { mode: "fixed", currency: "USD", amount: price.replace("$", "") }, protocols: [{ x402: {} }] },
    responses: { "402": { description: "Payment required: x402 requirements in the PAYMENT-REQUIRED header and JSON body", content: { "application/json": { schema: { $ref: "#/components/schemas/PaymentRequired" } } } } },
    description: PAID_ROUTES[key].description,
  });
  const ok = (schema: object) => ({ "200": { description: "OK", content: { "application/json": { schema } } } });
  const spec = {
    openapi: "3.1.0",
    info: { title: "specsheet API", version: "0.1.0", description: "Free static spec data plus x402 pay-per-request endpoints. Testnet (Base Sepolia) unless the operator enables mainnet.", "x-guidance": "Call /llms.txt for a summary. Paid endpoints answer 402 with x402 payment requirements; pay in USDC and retry with a PAYMENT-SIGNATURE header." },
    servers: [{ url: origin }],
    paths: {
      "/v1/manifest.json": { get: { summary: "Free: dataset manifest (redirects to static JSON)", responses: { "302": { description: "Redirect to the static dataset" } } } },
      "/v1/{path}": { get: { summary: "Free: any static dataset file (categories.json, <cat>/products/<id>.json, ...); 302 to GH Pages", parameters: [{ name: "path", in: "path", required: true, schema: { type: "string" } }], responses: { "302": { description: "Redirect" } } } },
      "/v1/query": { get: { summary: "Paid: filtered query with provenance", ...paid("GET /v1/query", PRICES.query),
        parameters: [
          { name: "category", in: "query", required: true, schema: { type: "string" } },
          { name: "filters", in: "query", schema: { type: "string" }, description: "Comma list of key<op>value; ops >= <= > < != = ~ . Example: cpu.cores>=8,brand=ASUS" },
          { name: "q", in: "query", schema: { type: "string" }, description: "Free-text match on brand/name/identifiers" },
          { name: "fields", in: "query", schema: { type: "string" }, description: "Comma list of spec keys to return" },
          { name: "limit", in: "query", schema: { type: "integer", default: 25, maximum: 100 } },
          { name: "offset", in: "query", schema: { type: "integer", default: 0 } },
        ], responses: { ...ok({ $ref: "#/components/schemas/QueryResult" }), "400": { description: "Bad filter (not charged)" } } } },
      "/v1/changes": { get: { summary: "Paid: record diff since a release", ...paid("GET /v1/changes", PRICES.changes),
        parameters: [
          { name: "since", in: "query", required: true, schema: { type: "string" }, description: "Release id (see /v1/manifest.json release) or ISO date" },
          { name: "category", in: "query", schema: { type: "string" } },
          { name: "limit", in: "query", schema: { type: "integer", default: 1000, maximum: 5000 } },
        ], responses: { ...ok({ type: "object" }) } } },
      "/v1/match": { get: { summary: "Paid: resolve a listing title to a product id (not yet implemented, returns 501 uncharged)", ...paid("GET /v1/match", PRICES.match),
        parameters: [{ name: "title", in: "query", required: true, schema: { type: "string" } }, { name: "category", in: "query", schema: { type: "string" } }],
        responses: { ...ok({ type: "object" }), "501": { description: "Not implemented yet" } } } },
      "/v1/bulk/{category}.jsonl.gz": { get: { summary: "Paid: full category dump", ...paid("GET /v1/bulk/*", PRICES.bulk),
        parameters: [{ name: "category", in: "path", required: true, schema: { type: "string" } }],
        responses: { "200": { description: "gzip JSON lines", content: { "application/gzip": { schema: { type: "string", format: "binary" } } } }, "402": { description: "Payment required" } } } },
      "/mcp": { post: { summary: "MCP (Streamable HTTP, stateless JSON-RPC): tools query_specs, match_product; payment via _meta[\"x402/payment\"]", responses: { "200": { description: "JSON-RPC response" } } } },
    },
    components: { schemas: {
      PaymentRequired: { type: "object", description: "x402 PaymentRequired (v2)", properties: { x402Version: { type: "integer" }, accepts: { type: "array", items: { type: "object" } }, error: { type: "string" } } },
      QueryResult: { type: "object", properties: { category: { type: "string" }, release: { type: "string" }, total: { type: "integer" }, count: { type: "integer" }, results: { type: "array", items: { type: "object", properties: { id: { type: "string" }, brand: { type: "string" }, name: { type: "string" }, specs: { type: "object", description: "key -> {value, unit, kind, sources[{id,url,label,tier,retrieved_at}]}" }, sources: { type: "array", items: { type: "object" } } } } } } },
    } },
  };
  if (!paidEnabled(env)) { // paid mode off: advertise only the free surface
    for (const k of ["/v1/query", "/v1/changes", "/v1/match", "/v1/bulk/{category}.jsonl.gz", "/mcp"]) delete (spec.paths as Record<string, unknown>)[k];
    spec.info.description += " Paid endpoints are coming soon and not currently offered.";
  }
  return spec;
}

export function llmsTxt(env: Env, origin: string) {
  const network = env.X402_NETWORK || "eip155:84532";
  if (!paidEnabled(env)) return `# specsheet
> Cross-brand product spec sheets with provenance. Free static dataset only; paid API endpoints are coming soon.

- [Dataset manifest](${origin}/v1/manifest.json): categories, counts, release (redirects to the static dataset)
- Any static file under /v1/ redirects to the free dataset.
- [OpenAPI 3.1](${origin}/openapi.json)
`;
  return `# specsheet
> Cross-brand product spec sheets with provenance (laptops, monitors, TVs, SSDs, routers, power strips, chargers and more). Facts are manufacturer/regulator-published values; every value lists its source.

Network: ${network} (${network === "eip155:84532" ? "Base Sepolia TESTNET, no real money" : "mainnet"}). Payments: x402, USDC, no account or API key.

## Free
- [Dataset manifest](${origin}/v1/manifest.json): categories, counts, release (redirects to the static dataset)
- Any static file under /v1/ (categories.json, <category>/products/<id>.json, <category>/facets.json) redirects to the free dataset.

## Paid (HTTP 402 with x402 requirements, then retry with payment)
- GET ${origin}/v1/query?category=laptops&filters=cpu.cores>=8,brand=ASUS&limit=10 : ${PRICES.query} per call, filtered results with per-value sources
- GET ${origin}/v1/match?title=<listing title> : ${PRICES.match} per call, resolve a retail title to a product id (not live yet)
- GET ${origin}/v1/changes?since=<release id or date> : ${PRICES.changes} per call, record diff between releases
- GET ${origin}/v1/bulk/<category>.jsonl.gz : ${PRICES.bulk} per call, full category dump

## Machine interfaces
- [OpenAPI 3.1](${origin}/openapi.json)
- MCP (stateless Streamable HTTP): POST ${origin}/mcp, tools query_specs and match_product
- x402 discovery: unpaid requests to paid routes return the payment requirements

## Notes
- Values with status unknown or conflicted are never returned as facts; absent specs mean not established.
- Some sources are excluded from paid tiers for licensing reasons; the free dataset is unaffected.
`;
}
