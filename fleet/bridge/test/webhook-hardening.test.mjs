// Codex-review (3.1 utan): a hibaszoveg redakcioja (token, URL query/userinfo)
// es a torzs kozben bonto szerver.
import test from "node:test";
import { tempDir } from "./tmp.mjs";
import assert from "node:assert/strict";
import { mkdtempSync, readFileSync, existsSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { createWebhookQueue, RETRY_DELAYS_MS } from "../lib/webhook-queue.mjs";
import { postWebhook, redact } from "../lib/webhook.mjs";
import { makeCert, startStub } from "./https-stub.mjs";

const TOKEN = "TITKOS-webhook-token-123";
const URL_ = "https://usr:PWSECRET@h.example:8443/hook?k=QSECRET&x=1";
const CFG = { url: URL_, token: TOKEN };
const SECRETS = [TOKEN, "QSECRET", "PWSECRET", "usr:"];
const body = { event_id: "-100:7", tg_from_id: "1", tg_chat_id: "-100", tg_message_id: 7,
  tg_reply_to: 3, tg_date: 1700000000, text: "ok" };
const today = () => new Date().toISOString().slice(0, 10);
const noSsl = () => (makeCert() ? false : "openssl nincs");
const clean = (s, what) => { for (const x of SECRETS) assert.ok(!s.includes(x), `${what}: ${x} benne`); };

test("redact: token, userinfo es query -> ***, a host megmarad", () => {
  const out = redact(`fail ${TOKEN} at ${URL_} (k=QSECRET)`, CFG);
  clean(out, "redact");
  assert.match(out, /h\.example:8443\/hook\?\*\*\*/);
  assert.match(out, /https:\/\/\*\*\*@/);
  assert.equal(redact("ECONNREFUSED", CFG), "ECONNREFUSED");
});

for (const kind of ["visszaadott", "dobott"]) {
  test(`webhook-sor: a ${kind} tokenes hiba sem a sorfajlba, sem a notice-ba, sem a logba nem kerul`, async () => {
    const dir = tempDir("whh-");
    const file = join(dir, "q.json"), logDir = join(dir, "inbox");
    const logs = [];
    const clock = { t: 1_000_000 };
    const msg = `bukott: Bearer ${TOKEN} -> ${URL_}`;
    const post = async () => { if (kind === "dobott") throw new Error(msg); return { ok: false, error: msg }; };
    const q = createWebhookQueue({ file, cfg: CFG, post, logDir, log: (...a) => logs.push(a.join(" ")),
      now: () => clock.t });
    await q.enqueue(body);
    clean(readFileSync(file, "utf8"), "sorfajl (1. proba)");
    for (const d of RETRY_DELAYS_MS) { clock.t += d; await q.tick(); }
    assert.equal(q.depth(), 0);
    const notice = join(logDir, `delivery-${today()}.jsonl`);
    assert.ok(existsSync(notice));
    clean(readFileSync(notice, "utf8"), "notice");
    assert.match(readFileSync(notice, "utf8"), /webhook_failed/);
    clean(readFileSync(file, "utf8"), "sorfajl");
    assert.ok(logs.length >= 4);
    clean(logs.join("\n"), "log");
  });
}

test("postWebhook: a szerver a torzs kozben bont -> gyorsan {ok:false}", { skip: noSsl() }, async () => {
  const stub = await startStub((req, res) => {
    res.writeHead(200, { "content-length": "1000" });
    res.write("reszleges");
    setTimeout(() => res.socket.destroy(), 50);
  });
  try {
    const timeoutMs = 400;
    const t0 = Date.now();
    let guard;
    const r = await Promise.race([
      postWebhook({ url: stub.url, token: TOKEN, body, ca: stub.ca, timeoutMs }),
      new Promise((res) => { guard = setTimeout(() => res({ ok: "LOG", error: "sosem teljesult" }), 3000); }),
    ]);
    clearTimeout(guard);
    assert.equal(r.ok, false, r.error);
    assert.ok(Date.now() - t0 <= timeoutMs + 200, `${Date.now() - t0} ms`);
  } finally { await stub.close(); }
});
