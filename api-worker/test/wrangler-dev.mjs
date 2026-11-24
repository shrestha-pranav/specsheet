// Start `wrangler dev --local` on a port with --var overrides and a throwaway --persist-to dir. No accounts, no network.
import { spawn } from "node:child_process";
import { mkdtempSync } from "node:fs";
import { tmpdir } from "node:os";
import { join, resolve } from "node:path";
const root = resolve(import.meta.dirname, "..");
export async function startWorker(port, vars = [], { inspectorPort } = {}) {
  const state = mkdtempSync(join(tmpdir(), "specsheet-wd-"));
  const args = ["wrangler", "dev", "--local", "--port", String(port), "--persist-to", state, "--inspector-port", String(inspectorPort ?? port + 1000), ...vars.flatMap((v) => ["--var", v])];
  const p = spawn("npx", args, { cwd: root, stdio: ["ignore", "pipe", "pipe"], detached: true, env: { ...process.env, WRANGLER_SEND_METRICS: "false" } });
  let log = ""; p.stdout.on("data", (d) => (log += d)); p.stderr.on("data", (d) => (log += d));
  const stop = () => { try { process.kill(-p.pid, "SIGKILL"); } catch { /* gone */ } };
  for (let i = 0; i < 120; i++) {
    try { if ((await fetch(`http://127.0.0.1:${port}/health`)).status === 200) return { port, stop, log: () => log }; } catch { /* starting */ }
    await new Promise((r) => setTimeout(r, 500));
  }
  stop();
  throw new Error(`wrangler dev on ${port} did not start:\n${log.slice(-2000)}`);
}
