// lib/webhook.mjs — EGY POST a beallitott hostra. node:https: atiranyitast
// alapbol sem kovet; rejectUnauthorized mindig true. A hibaszoveg redact()-on at megy.
// Ket korlat: a socket-idle `timeout`, es egy FALI ORAS setTimeout, ami a
// valasz-olvasast is lefedi (egy csepegtetett valasz az idle-t sosem lovi el).
// A valasz-torzset (legfeljebb MAX_BODY BAJT) JSON-kent visszaadja (`json`),
// ha az; a cel `_REPLY` mezoje ebbol ir a szalba (lib/webhook-chain.mjs).
// Nagyobb valasz: `overflow: true`, nincs parse, a kapcsolat bontva.
import { request } from "node:https";

export const DEFAULT_TIMEOUT_MS = 5000;
const MAX_BODY = 64 * 1024;
const parse = (s) => { try { return JSON.parse(s); } catch { return null; } };

// Hibaszoveg -> napló/sorfajl/notice: a token, es barmely URL userinfo- es
// query-resze `***`. A beallitott URL titkos darabjai (jelszo, felhasznalo,
// query-ertekek) szo szerint is kicserelodnek, ha legalabb 4 karakteresek
// (rovidebbet cserelni a szoveg ertelmet rontana).
const URL_RE = /\b([a-z][a-z0-9+.-]*:\/\/)([^\s/?#@]*@)?([^\s?#]*)(\?[^\s#]*)?/gi;
const esc = (x) => x.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
export function redact(s, { url, token } = {}) {
  let out = String(s ?? "");
  const lits = token ? [token] : [];
  try {
    const u = new URL(url);
    lits.push(u.password, u.username, ...u.searchParams.values());
    lits.push(decodeURIComponent(u.password), decodeURIComponent(u.username)); // dobhat: a fenti marad
  } catch { /* nincs/ervenytelen URL: csak a token es a minta */ }
  for (const x of lits) if (x && (x === token || x.length >= 4)) out = out.replace(new RegExp(esc(x), "g"), "***");
  return out.replace(URL_RE, (_, p, ui, rest, q) => `${p}${ui ? "***@" : ""}${rest}${q ? "?***" : ""}`);
}

export function postWebhook({ url, token, header = "x-bridge-token", body, timeoutMs = DEFAULT_TIMEOUT_MS, ca }) {
  return new Promise((resolve) => {
    let timer, settled = false;
    // settle EGYSZER: a valasz, a req-hiba, a bontas es a fali ora versenyeznek
    const done = (r) => {
      if (settled) return;
      settled = true; clearTimeout(timer);
      resolve(r.error ? { ...r, error: redact(r.error, { url, token }) } : r);
    };
    const data = JSON.stringify(body);
    const req = request(url, {
      method: "POST", ca, rejectUnauthorized: true, timeout: timeoutMs,
      headers: { "content-type": "application/json", "content-length": Buffer.byteLength(data),
        [header.toLowerCase()]: token },
    }, (res) => {
      // torzs kozbeni bontas: se "end", se req-"error" — kulon kell feloldani
      const aborted = () => done({ ok: false, error: "response aborted" });
      res.on("error", aborted);
      res.on("aborted", aborted);
      const s = res.statusCode;
      const result = (extra) => (s >= 200 && s < 300 ? { ok: true, status: s, ...extra }
        : { ok: false, status: s, ...extra, error: s >= 300 && s < 400 ? `atiranyitas (${s}) — nem kovetem` : `HTTP ${s}` });
      const chunks = [];
      let bytes = 0;
      res.on("data", (d) => {
        bytes += d.length; // Buffer: bajt, nem karakter
        if (bytes > MAX_BODY) { done(result({ overflow: true })); res.destroy(); return; }
        chunks.push(d);
      });
      res.on("end", () => {
        const j = parse(Buffer.concat(chunks).toString("utf8"));
        done(result(j && typeof j === "object" ? { json: j } : {})); // nem-JSON valasz: nincs mezo
      });
    });
    const kill = () => req.destroy(Object.assign(new Error("timeout"), { code: "timeout" }));
    // a fali ora MAGA oldja fel (a destroy utan a req mar nem mindig ad "error"-t)
    timer = setTimeout(() => { done({ ok: false, error: "timeout" }); kill(); }, timeoutMs);
    req.on("timeout", kill);
    req.on("error", (e) => done({ ok: false, error: e.code || e.message }));
    req.end(data);
  });
}
