// lib/webhook-chain.mjs — a celok kozti sorrend (_UNLESS) es a szalba irt valasz (_REPLY).
//
// Sorrend: egy _UNLESS-es cel eleme addig var, amig a nevezett (szulo) cel
// ugyanarra az esemenyre adott vegso kimenete meg nincs meg (ok / rejected /
// failed). A dontes a szulo sorfajljaban orzott kimenetbol jon (akkor is, ha a
// fuggo elem csak egy ujrajatszaskor kerult a sorba): ha a valasz-JSON-ban a
// kulcs=ertek all (pl. ok=true: a "mehet" jovahagyas volt), az elem NEM hiv
// (`webhook_skipped`). Halozati kimerules utan fut (a kiesett szerver nem
// jovahagyas); ha a szulo kimenete ismeretlen: fail-closed, nem hiv.
//
// Valasz: a cel _REPLY mezoje a valasz-JSON-bol (2xx vagy vegleges 4xx), ha
// nem nema (_REPLY_SKIP). Ha egy fuggo cel var ugyanarra az esemenyre, a szoveg
// NEM megy ki azonnal: a fuggo cel a sajatjaval EGY uzenetben, sortoressel
// fuzve kuldi (vagy egyedul, ha kimarad). Egy szulonek egy fuggoje lehet (a
// targets-parse elutasitja a masodikat), igy egy _UNLESS-lanc egy esemenyre
// legfeljebb EGY valaszt ir; egymastol fuggetlen _REPLY-os celok kulon-kulon
// valaszolhatnak. A reply a kivalto uzenetre megy (reakcional a reagaltra).
// Ujrakuldes nincs: a duplikalt valasz rosszabb a hianyzonal.
import { pathToFileURL } from "node:url";

export const MAX_REPLY = 4096;

export function replyOf(t, json) {
  if (!t.reply || !json || typeof json !== "object") return null;
  const v = json[t.reply.field];
  if (typeof v !== "string" || !v.trim()) return null;
  if (t.reply.skip.some(([k, val]) => String(json[k]) === val)) return null;
  return v;
}

export function createChain({ targets, queues, sendReply = async () => {}, log = () => {} }) {
  const filters = new Map();
  async function filterOk(t, text) {
    if (!t.nofooter.filter) return true;
    if (!filters.has(t.name)) filters.set(t.name, import(pathToFileURL(t.nofooter.filter).href).then((m) => m.default));
    try { return Boolean((await filters.get(t.name))(text)); } catch (e) {
      log(`webhook ${t.name}: NOFOOTER_FILTER hiba, nema marad: ${e?.message}`);
      return false; // fail-closed: ketes esetben nem szolunk
    }
  }

  async function say(t, item, parts) {
    const text = parts.filter(Boolean).join("\n").slice(0, MAX_REPLY);
    if (!text) return;
    try {
      await sendReply({ chatId: item.body.tg_chat_id, replyTo: item.body.tg_message_id, text, target: t.name });
    } catch (e) { log(`webhook ${t.name}: valasz-kuldes hiba: ${e?.message}`); }
  }

  function hooksFor(t) {
    const h = {
      ready: (item) => !item.after || item.after_done === true || !queues.get(item.after)?.has(item.event_id),
      async onFinal(item, { event, res }) {
        const own = event === "webhook_skipped" ? item.local_reply || null : replyOf(t, res?.json);
        const text = [item.prefix, own].filter(Boolean).join("\n") || null;
        let handed = false;
        for (const d of targets) {
          if (d.unless?.target !== t.name) continue;
          const q = queues.get(d.name), it = q?.find(item.event_id);
          if (!it || it.after !== t.name || it.after_done) continue;
          q.annotate(item.event_id, { after_done: true, prefix: handed ? null : text });
          handed = true;
          q.tick();
        }
        if (!handed) await say(t, item, [text]);
      },
    };
    if (t.unless || t.nofooter) {
      h.before = async (item) => {
        const u = t.unless;
        if (item.after && u) {
          const o = queues.get(u.target)?.outcome(item.event_id);
          if (!o?.known) return { event: "webhook_skipped", detail: `unless ${u.target}: a szulo kimenete ismeretlen` };
          if (o.json && String(o.json[u.key]) === u.value) {
            return { event: "webhook_skipped", detail: `unless ${u.target}:${u.key}=${u.value}` };
          }
        }
        if (item.nofooter) {
          item.local_reply = (await filterOk(t, item.body.text)) ? t.nofooter.text : null;
          return { event: "webhook_skipped", detail: item.local_reply ? "nofooter: visszakerdez" : "nofooter: nema" };
        }
        return null;
      };
    }
    return h;
  }
  return { hooksFor };
}
