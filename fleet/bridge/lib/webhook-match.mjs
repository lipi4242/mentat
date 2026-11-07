// lib/webhook-match.mjs — melyik webhook-cel kapja az esemenyt, milyen torzzsel.
// Tiszta fuggveny: nem ir, nem hiv halozatot. A kapu (allowlist, mention,
// bot soha, szerkesztett soha) a handlers.mjs dolga — ide mar csak atjutott
// reply/reakcio er.
//
//   reply    — minden reply; a torzs a 3.1-es (event_id, tg_*, tg_reply_to, text)
//   reaction — uj emoji egy uzeneten; tg_message_id = tg_reply_to = a reagalt uzenet
//   footer   — reply a BOT sajat uzenetere, aminek utolso nem-ures sora a _FOOTER
//              mintara illeszkedik (es _FOOTER_ALL mellett minden link ugyanarra
//              mutat); a torzs: tg_* (tg_reply_to csak _REPLY_TO=on mellett) + <_FOOTER_FIELD>: id.
//              Lablec nelkul, _NOFOOTER_REPLY mellett: halozat nelkuli elem, ami
//              csak a szalba valaszol (nofooter: true).
// Kétes esetben (nem a bot uzenete, tobb kulonbozo id, dekodolhatatlan id) nincs kotes.

// A Partner-fork sanitize-anak tukre (_TEXT=oneline:<N>): vezerlo -> szokoz,
// bidi/zero-width le, whitespace osszevonva, trim, N UTF-16 egysegnel vagva.
export const oneline = (s, n) => String(s).replace(/[\x00-\x1f\x7f]+/g, " ")
  .replace(/[\u200b-\u200f\u202a-\u202e\u2066-\u2069\ufeff]/g, "").replace(/\s+/g, " ").trim().slice(0, n);

const dec = (s) => { try { return decodeURIComponent(s); } catch { return null; } };

export function footerId(t, text) {
  const lines = String(text || "").split(/\r?\n/).map((x) => x.trim()).filter(Boolean);
  if (!lines.length) return null;
  const m = t.footer.exec(lines[lines.length - 1]);
  // _FOOTER_EXCLUDE a DEKODOLT id-re (a fork: `tipu%73` is listaoldal, nem ugy)
  const ok = (d) => (d && !t.exclude?.has(d) ? d : null);
  const id = m && m[1] != null ? ok(dec(m[1])) : null;
  if (!id) return null;
  if (t.footerAll) {
    const all = new Set();
    for (const x of String(text).matchAll(t.footerAll)) { const d = x[1] != null ? ok(dec(x[1])) : null; if (d) all.add(d); }
    if (all.size !== 1 || !all.has(id)) return null;
  }
  return id;
}

function footerItem(t, b, ctx) {
  if (ctx.botId == null || ctx.replyToFromId == null || String(ctx.replyToFromId) !== String(ctx.botId)) return null;
  const { event_id, tg_from_id, tg_chat_id, tg_message_id, tg_reply_to, tg_date, text } = b;
  const id = footerId(t, ctx.replyToText);
  // Kulcssorrend a forke: ..., tg_date, <mezo>, text (a nyers torzs bajtra egyezzen).
  // _REPLY_TO=on: a horgony (tg_reply_to) a tg_message_id utan; off mellett a torzs bajtra a regi.
  const rt = t.replyTo ? { tg_reply_to } : {};
  if (id) return { body: { event_id, tg_from_id, tg_chat_id, tg_message_id, ...rt, tg_date, [t.field]: id, text }, extra: {} };
  return t.nofooter ? { body: { event_id, tg_from_id, tg_chat_id, tg_message_id, tg_date, text }, extra: { nofooter: true } } : null;
}

// body: a handlers.mjs jeloltje; ctx: { kind: "message"|"reaction", replyToFromId, botId, replyToText }
// Visszater: [{ target, body, extra }] a celok sorrendjeben. Az `extra.after` a
// _UNLESS-ben nevezett cel neve, ha az is kapta ezt az esemenyt (arra var).
export function matchTargets(targets, body, ctx = {}) {
  const out = [];
  const got = new Set();
  for (const t of targets) {
    if (!t.enabled) continue;
    if (t.from && !t.from.has(String(body.tg_from_id))) continue;
    let hit = null;
    if (ctx.kind === "reaction") hit = t.match.reaction ? { body, extra: {} } : null;
    else if (t.match.reply) hit = { body, extra: {} };
    else if (t.match.footer) hit = footerItem(t, body, ctx);
    if (!hit) continue;
    if (t.oneline) hit.body = { ...hit.body, text: oneline(hit.body.text, t.oneline) };
    if (t.unless && got.has(t.unless.target)) hit.extra.after = t.unless.target;
    got.add(t.name);
    out.push({ target: t, ...hit });
  }
  return out;
}
