import type { Env } from "./config.ts";
import { HttpError } from "./data.ts";

// TODO(match.py): scripts/match.py (chargers agent, in progress) is the reference implementation. When it lands:
//   1. read its normalisation + scoring rules, 2. port them to TS here (identifier extraction -> exact id/alias lookup
//   -> fuzzy fallback with a confidence), 3. have build_r2.py also emit `match/<cat>.json` (alias -> id table) so the
//   Worker needs no network call, 4. delete the 501 below. The route, price and OpenAPI/MCP wiring already exist.
export async function matchTitle(_env: Env, title: string, _category?: string): Promise<never> {
  throw new HttpError(501, "match is not implemented yet (waiting for scripts/match.py to be ported)", { title, todo: "port scripts/match.py" });
}
