// Tiny stand-in for https://x402.org/facilitator: accepts any well-formed payment. For offline end-to-end tests only.
import http from "node:http";
export function startMockFacilitator(port) {
  const calls = { verify: 0, settle: 0 };
  const server = http.createServer((req, res) => {
    let body = "";
    req.on("data", (d) => (body += d));
    req.on("end", () => {
      const send = (o) => { res.setHeader("content-type", "application/json"); res.end(JSON.stringify(o)); };
      const url = req.url.split("?")[0];
      if (url.endsWith("/supported")) return send({ kinds: [{ x402Version: 2, scheme: "exact", network: "eip155:84532" }], extensions: [], signers: { "eip155:*": ["0x0000000000000000000000000000000000000001"] } });
      const j = body ? JSON.parse(body) : {};
      const payer = j.paymentPayload?.payload?.authorization?.from ?? "0x0";
      if (url.endsWith("/verify")) { calls.verify++; return send({ isValid: true, payer }); }
      if (url.endsWith("/settle")) { calls.settle++; return send({ success: true, payer, transaction: "0x" + "ab".repeat(32), network: "eip155:84532" }); }
      res.statusCode = 404; send({ error: "nope" });
    });
  });
  return new Promise((r) => server.listen(port, "127.0.0.1", () => r({ server, calls })));
}
