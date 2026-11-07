// lib/gating.mjs — a csoportos mention-kapu tiszta logikája.
//
// A naiv `text.includes("@" + username)` két irányban is hibás volt:
//   - átengedte a `@BotName_evil` alakot (részszó-egyezés — idegen bot
//     említése a mi kapunkat nyitotta ki),
//   - elbukott a kis/nagybetű eltérésen (a Telegram kliensek a felhasználó
//     által gépelt alakot küldik).
// Elsődlegesen a Telegram `entities` mezőjére támaszkodunk (ez a hitelesen
// felismert említés), és csak ha nincs `mention` entitás, esünk vissza
// szóhatáros, kis/nagybetű-érzéketlen regexre.

export function escapeRegex(s) {
  return String(s).replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
}

// entities: msg.entities vagy msg.caption_entities (offset/length UTF-16
// kódegységben — a JS String.slice ugyanabban számol, így az illesztés pontos).
export function isMentioned(text, entities, username) {
  if (!username) return false;
  const t = String(text || "");
  const want = `@${username}`.toLowerCase();
  const mentions = (Array.isArray(entities) ? entities : []).filter(
    (e) => e?.type === "mention",
  );
  if (mentions.length) {
    return mentions.some(
      (e) => t.slice(e.offset, e.offset + e.length).toLowerCase() === want,
    );
  }
  return new RegExp(`@${escapeRegex(username)}\\b`, "i").test(t);
}
