// Node-only: resolve `cloudflare:workers` to a stub so src/index.ts can be imported by scripts/cpu-bench.mjs (Worker CPU without workerd).
import { register } from "node:module";
register("data:text/javascript," + encodeURIComponent(`
export async function resolve(s, c, n) { if (s === "cloudflare:workers") return { url: "data:text/javascript,export class DurableObject { constructor(c, e) { this.ctx = c; this.env = e; } }", shortCircuit: true }; return n(s, c); }`));
