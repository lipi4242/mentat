// Teszt-segedlet (nem *.test.mjs): onalairt https-stub a webhook-tesztekhez.
// A cert/kulcs tmp konyvtarba kerul; openssl nelkul `null` -> a teszt skippel.
import { spawnSync } from "node:child_process";
import { tempDir } from "./tmp.mjs";
import { mkdtempSync, readFileSync } from "node:fs";
import { createServer as createHttps } from "node:https";
import { createServer as createNet } from "node:net";
import { tmpdir } from "node:os";
import { join } from "node:path";

let cached;
export function makeCert() {
  if (cached !== undefined) return cached;
  const dir = tempDir("wh-cert-");
  const k = join(dir, "key.pem"), c = join(dir, "cert.pem");
  const r = spawnSync("openssl", ["req", "-x509", "-newkey", "rsa:2048", "-nodes", "-keyout", k,
    "-out", c, "-days", "1", "-subj", "/CN=127.0.0.1", "-addext", "subjectAltName=IP:127.0.0.1"],
  { stdio: "ignore" });
  cached = r.status === 0 ? { key: readFileSync(k), cert: readFileSync(c) } : null;
  return cached;
}

// handler(req, res, bodyText) — a stub minden kerest rogzit.
export async function startStub(handler) {
  const pem = makeCert();
  const requests = [];
  const sockets = new Set();
  const server = createHttps({ key: pem.key, cert: pem.cert }, (req, res) => {
    let data = "";
    req.on("data", (d) => { data += d; });
    req.on("end", () => {
      requests.push({ method: req.method, url: req.url, headers: req.headers, body: data });
      handler(req, res, data);
    });
  });
  server.on("connection", (s) => { sockets.add(s); s.on("close", () => sockets.delete(s)); });
  await new Promise((r) => server.listen(0, "127.0.0.1", r));
  const port = server.address().port;
  return {
    url: `https://127.0.0.1:${port}/hook`, port, requests, ca: pem.cert,
    close: () => new Promise((r) => { for (const s of sockets) s.destroy(); server.close(() => r()); }),
  };
}

// Egy biztosan zart port: megnyitjuk, majd bezarjuk.
export async function closedPort() {
  const s = createNet();
  await new Promise((r) => s.listen(0, "127.0.0.1", r));
  const port = s.address().port;
  await new Promise((r) => s.close(r));
  return port;
}
