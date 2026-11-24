// Shared request cases for scripts/load-test.mjs (workerd) and scripts/cpu-bench.mjs (Node V8). Laptops = the largest category.
const keys = ["cpu.cores>=", "mem.size>=", "stor.size>=", "pwr.battery_wh>=", "disp.size>=", "cpu.threads>=", "phys.weight<=", "cpu.boost_clock>=", "disp.nits_sdr>=", "mem.max>=", "stor.slots>=", "brand!="];
const vals = [2, 4, 128, 20, 11, 2, 5, 1, 100, 4, 1, "Nobrand"];
export const CASES = {
  "baseline GET /robots.txt (no DO, no data)": () => "/robots.txt",
  "chargers limit 1 (DO spend, tiny data)": (i) => `/v1/query?category=chargers&limit=1&offset=${i % 100}`,
  "laptops max (12 filters, limit 100)": (i) => `/v1/query?category=laptops&limit=100&filters=${encodeURIComponent(keys.map((k, j) => k + (j === 11 ? vals[j] + i : vals[j])).join(","))}`,
  "laptops max + q + offset": (i) => `/v1/query?category=laptops&limit=100&offset=${(i * 7) % 900}&q=${encodeURIComponent(["intel", "amd", "ultra", "core", "ryzen"][i % 5])}&filters=${encodeURIComponent(`mem.size>=${4 + (i % 4) * 4},brand!=x${i}`)}`,
  "laptops typical (2 filters, limit 50)": (i) => `/v1/query?category=laptops&limit=50&offset=${i % 40}&filters=${encodeURIComponent(`cpu.cores>=${4 + (i % 8)},mem.size>=16`)}`,
  "monitors limit 100": (i) => `/v1/query?category=monitors&limit=100&offset=${(i * 13) % 1900}`,
  "match title": (i) => `/v1/match?title=${encodeURIComponent(["Anker 735 Charger (Nano II 65W) GaN 3-port", "Samsung T7 Shield 2TB (MU-PE2T0S/AM)", "UGREEN Nexode 300W 8-Port Desktop Charger", "Lenovo ThinkPad X1 Carbon Gen 12 21KC0001US laptop"][i % 4] + " #" + i)}`,
  "MCP batch 10 x query_specs laptops limit 100": (i) => ({ body: JSON.stringify(Array.from({ length: 10 }, (_, j) => ({ jsonrpc: "2.0", id: j, method: "tools/call", params: { name: "query_specs", arguments: { category: "laptops", limit: 100, offset: (i * 10 + j) % 2000, filters: `cpu.cores>=${2 + j}` } } }))) }),
};

