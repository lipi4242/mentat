// lib/webhook-targets.mjs — tobb nevesitett webhook-cel env-szerzodese.
//
//   SUBETHA_WEBHOOKS=draft,ugy            (a sorrend a kiertekeles sorrendje)
//   SUBETHA_WEBHOOK_<NEV>_URL / _TOKEN    (kotelezo; csak https)
//   _TOKEN_HEADER   a token fejlece (alap X-Bridge-Token)
//   _MATCH          reply | reaction | footer, vesszovel (alap reply)
//   _FROM           csak ezektol a kuldoktol (vesszos id-lista; zajszuro, nem jogosultsag)
//   _FOOTER         regex EGY capture-csoporttal a valaszolt BOT-uzenet utolso nem-ures sorara
//   _FOOTER_ALL     regex: a valaszolt szoveg MINDEN talalata ugyanarra az id-re mutasson
//   _FOOTER_FIELD   a torzs-mezo neve a kinyert id-nek (alap ref)
//   _FOOTER_EXCLUDE vesszos lista: ezek a (dekodolt) id-k nem kotnek (pl. listaoldal)
//   _REPLY          a valasz-JSON mezoje, ami a szalba kimegy
//   _REPLY_SKIP     kulcs=ertek[,..]: ha a valasz-JSON-ban igy all, a szal nema
//   _UNLESS         <cel>:kulcs=ertek — megvarja egy KORABBI cel valaszat ugyanarra
//                   az esemenyre, es ha abban igy all, ez a cel nem hiv
//   _NOFOOTER_REPLY egysoros valasz, ha a bot-uzenetre adott valaszban nincs lablec
//   _NOFOOTER_FILTER .mjs ut; default exportja (text) => boolean donti, kell-e
//   _TIMEOUT_MS     keresenkenti idokorlat (alap 5000)
//   _EVENT_ID       on | off — off: a kuldott torzsbol kimarad az event_id (a sor kulcsa marad)
//   _TEXT           raw | oneline:<N> — oneline: egy sorba vonva, vezerlo/zero-width le, N-nel vagva
//   _REPLY_TO       on | off (alap off) — on: a footer-torzs is viszi a tg_reply_to-t
//                   (a szerver ebbol keresi ki a horgonyt, pl. zart opcios valasznal)
// Hibas cel: KI, okkal (a reason-ben se token, se URL); a tobbi cel fut.
import { checkEndpoint, parseWebhookConfig } from "./webhook-config.mjs";
import { DEFAULT_TIMEOUT_MS } from "./webhook.mjs";

const NAME = /^[a-z][a-z0-9_]{0,31}$/i;
const HEADER = /^[A-Za-z0-9-]{1,64}$/;
const MATCHES = new Set(["reply", "reaction", "footer"]);
const list = (v) => String(v ?? "").split(",").map((s) => s.trim()).filter(Boolean);
const pairs = (v) => list(v).map((p) => { const i = p.indexOf("="); return i > 0 ? [p.slice(0, i), p.slice(i + 1)] : null; });

function regex(src, flags, what) {
  try { return new RegExp(src, flags); } catch { throw new Error(`${what} nem ervenyes regex`); }
}

function parseOne(env, name, seen, parents) {
  const P = `SUBETHA_WEBHOOK_${name.toUpperCase()}_`;
  const g = (k) => env[P + k];
  if (!g("URL")) return { name, enabled: false, reason: `${P}URL hianyzik` };
  const base = { name, ...checkEndpoint(g("URL"), g("TOKEN"), { urlName: `${P}URL`, tokenName: `${P}TOKEN` }) };
  if (!base.enabled) return base;
  const header = g("TOKEN_HEADER") || "X-Bridge-Token";
  if (!HEADER.test(header)) return { name, enabled: false, reason: `${P}TOKEN_HEADER ervenytelen` };
  const m = list(g("MATCH") || "reply");
  const bad = m.find((x) => !MATCHES.has(x));
  if (bad) return { name, enabled: false, reason: `${P}MATCH ismeretlen: ${bad}` };
  const match = Object.fromEntries(m.map((x) => [x, true]));
  const ev = (g("EVENT_ID") || "on").toLowerCase(), tx = /^(raw|oneline:([1-9]\d{0,5}))$/.exec(g("TEXT") || "raw");
  if (ev !== "on" && ev !== "off") return { name, enabled: false, reason: `${P}EVENT_ID csak on|off` };
  if (!tx) return { name, enabled: false, reason: `${P}TEXT csak raw|oneline:<N>` };
  const rt = (g("REPLY_TO") || "off").toLowerCase();
  if (rt !== "on" && rt !== "off") return { name, enabled: false, reason: `${P}REPLY_TO csak on|off` };
  const t = { ...base, header, match, timeoutMs: Number(g("TIMEOUT_MS")) > 0 ? Number(g("TIMEOUT_MS")) : DEFAULT_TIMEOUT_MS,
    from: g("FROM") ? new Set(list(g("FROM"))) : null, field: g("FOOTER_FIELD") || "ref",
    eventId: ev === "on", replyTo: rt === "on", exclude: g("FOOTER_EXCLUDE") ? new Set(list(g("FOOTER_EXCLUDE"))) : null, oneline: tx[2] ? Number(tx[2]) : 0,
    footer: null, footerAll: null, reply: null, unless: null, nofooter: null };
  try {
    if (match.footer) {
      if (!g("FOOTER")) return { name, enabled: false, reason: `${P}FOOTER kell a footer-illeszteshez` };
      t.footer = regex(g("FOOTER"), "u", `${P}FOOTER`);
      if (g("FOOTER_ALL")) t.footerAll = regex(g("FOOTER_ALL"), "gu", `${P}FOOTER_ALL`);
    }
  } catch (e) { return { name, enabled: false, reason: e.message }; }
  if (g("REPLY")) {
    const skip = pairs(g("REPLY_SKIP"));
    if (skip.includes(null)) return { name, enabled: false, reason: `${P}REPLY_SKIP alakja kulcs=ertek` };
    t.reply = { field: g("REPLY"), skip };
  }
  if (g("UNLESS")) {
    const u = /^([a-z][a-z0-9_]*):([^=]+)=(.*)$/i.exec(g("UNLESS"));
    if (!u) return { name, enabled: false, reason: `${P}UNLESS alakja <cel>:kulcs=ertek` };
    if (!seen.has(u[1].toLowerCase())) return { name, enabled: false, reason: `${P}UNLESS: ${u[1]} nem korabbi, bekapcsolt cel` };
    // Egy szulonek egy fuggoje: egy lanc = legfeljebb egy szal-valasz (lib/webhook-chain.mjs).
    if (parents.has(u[1].toLowerCase())) return { name, enabled: false, reason: `${P}UNLESS: a(z) ${u[1]} celnak mar van fuggoje` };
    t.unless = { target: u[1].toLowerCase(), key: u[2], value: u[3], raw: g("UNLESS") };
  }
  if (g("NOFOOTER_REPLY") && match.footer) t.nofooter = { text: g("NOFOOTER_REPLY"), filter: g("NOFOOTER_FILTER") || null };
  return t;
}

// Visszater: celok listaja (a KI-allapotuak is, `reason`-nel — a wire figyelmeztet).
export function parseWebhookTargets(env) {
  const out = [];
  const legacy = parseWebhookConfig(env);
  if (legacy.enabled || legacy.reason) {
    out.push({ ...legacy, name: "default", legacy: true, header: "X-Bridge-Token", match: { reply: true },
      timeoutMs: DEFAULT_TIMEOUT_MS, from: null, reply: null, unless: null, nofooter: null });
  }
  const seen = new Set(), names = new Set(), parents = new Set();
  for (const raw of list(env.SUBETHA_WEBHOOKS)) {
    const name = raw.toLowerCase();
    if (!NAME.test(name)) { out.push({ name: "?", enabled: false, reason: "SUBETHA_WEBHOOKS: ervenytelen celnev" }); continue; }
    if (names.has(name) || name === "default") {
      out.push({ name, enabled: false, reason: `SUBETHA_WEBHOOKS: a(z) ${name} nev foglalt` });
      continue;
    }
    names.add(name);
    const t = parseOne(env, name, seen, parents);
    if (t.enabled) { seen.add(name); if (t.unless) parents.add(t.unless.target); }
    out.push(t);
  }
  return out;
}
