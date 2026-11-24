import { Hono } from "hono";
import type { Env } from "./config.ts";
import { paidEnabled, resolveX402 } from "./config.ts";
import { bulkObject, getManifest, HttpError, runChanges, runQuery } from "./data.ts";
import { llmsTxt, openapi } from "./discovery.ts";
import { matchTitle } from "./match.ts";
import { handleMcp } from "./mcp.ts";
import { getPaymentMiddleware } from "./x402.ts";

const app = new Hono<{ Bindings: Env }>();
const PAID = ["/v1/query", "/v1/changes", "/v1/match", "/v1/bulk/*"];
const origin = (u: string) => new URL(u).origin;

// Payment gate. Fails closed (503) when PAY_TO / mainnet config is not valid; never serves paid data unpaid.
for (const path of PAID) {
  app.use(path, async (c, next) => {
    if (!paidEnabled(c.env)) return c.json({ error: "coming_soon", detail: "paid endpoints are not enabled yet" }, 503);
    const s = resolveX402(c.env);
    if (!s.ok) return c.json({ error: "payments_not_configured", detail: s.reason }, 503);
    return getPaymentMiddleware(c.env, s)(c, next);
  });
}

app.onError((e, c) => {
  if (e instanceof HttpError) return c.json({ error: e.message, ...e.extra }, e.status as 400);
  console.error(e);
  return c.json({ error: "internal_error" }, 500);
});

const int = (v: string | undefined, d: number, max: number) => Math.min(Math.max(Number.parseInt(v ?? "", 10) || d, 0), max);

app.get("/", async (c) => {
  const s = resolveX402(c.env);
  return c.json({
    name: "specsheet-api", docs: { openapi: "/openapi.json", llms: "/llms.txt", mcp: "/mcp" },
    free: "/v1/* (redirects to static dataset)", paid: ["/v1/query", "/v1/changes", "/v1/match", "/v1/bulk/<category>.jsonl.gz"],
    payments: !paidEnabled(c.env) ? { enabled: false, status: "coming soon" } : s.ok ? { network: s.network, testnet: s.testnet } : { configured: false },
  });
});
app.get("/openapi.json", (c) => c.json(openapi(c.env, origin(c.req.url))));
app.get("/llms.txt", (c) => c.text(llmsTxt(c.env, origin(c.req.url))));

export const queryParams = (url: URL) => ({
  category: url.searchParams.get("category") ?? "",
  filters: [...url.searchParams.getAll("filters"), ...url.searchParams.getAll("filter")],
  q: url.searchParams.get("q") ?? undefined,
  fields: url.searchParams.get("fields")?.split(",").filter(Boolean),
  limit: int(url.searchParams.get("limit") ?? undefined, 25, 100) || 25,
  offset: int(url.searchParams.get("offset") ?? undefined, 0, 1_000_000),
});

app.get("/v1/query", async (c) => {
  const p = queryParams(new URL(c.req.url));
  if (!p.category) throw new HttpError(400, "category is required", { categories: (await getManifest(c.env)).categories.map((x) => x.id) });
  return c.json(await runQuery(c.env, p));
});

app.get("/v1/changes", async (c) => {
  const since = c.req.query("since");
  if (!since) throw new HttpError(400, "since is required (release id or ISO date)");
  return c.json(await runChanges(c.env, { since, category: c.req.query("category"), limit: int(c.req.query("limit"), 1000, 5000) || 1000 }));
});

app.get("/v1/match", async (c) => {
  const title = c.req.query("title");
  if (!title) throw new HttpError(400, "title is required");
  return c.json(await matchTitle(c.env, title, c.req.query("category")));
});

app.get("/v1/bulk/:file", async (c) => {
  const { body, release, size } = await bulkObject(c.env, c.req.param("file"));
  return new Response(body, { headers: { "content-type": "application/gzip", "content-length": String(size), "content-disposition": `attachment; filename="${c.req.param("file")}"`, "x-specsheet-release": release } });
});

app.post("/mcp", (c) => handleMcp(c, app));
app.get("/mcp", (c) => c.json({ error: "Use POST (stateless Streamable HTTP, JSON responses only)" }, 405));

// Free path: everything else under /v1/ is the static dataset on GH Pages.
app.get("/v1/*", (c) => {
  const rest = new URL(c.req.url).pathname.slice("/v1/".length);
  if (rest.split("/").includes("..") || rest.startsWith("preview/")) return c.json({ error: "not found" }, 404);
  return c.redirect(`${c.env.STATIC_ORIGIN.replace(/\/$/, "")}/api/v1/${rest}`, 302);
});

export default app;
