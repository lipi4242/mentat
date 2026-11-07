// lib/handlers.mjs — egy Telegram-update feldolgozasa: kapu (allowlist,
// mention), kezbesites (szoveg/reakcio: deliver; media: tartos sor), majd a
// bejovo kezbesitesi sor (logInbound) — CSAK sikeres kezbesites/enqueue utan.
// Reply es reakcio eseten egy jelolt a webhook-celoknak (onApprovalCandidate);
// hogy melyik cel kapja, a lib/webhook-match.mjs donti el.
import { sanitize } from "./sanitize.mjs";
import { isMentioned } from "./gating.mjs";
import { pickMedia, attachmentKind } from "./media.mjs";
import { buildTextLine, buildReactionLine } from "./lines.mjs";

function reactionEmojis(arr) {
  if (!Array.isArray(arr)) return [];
  return arr.map((r) => (r?.type === "emoji" ? r.emoji
    : r?.type === "custom_emoji" ? "[custom_emoji]"
      : r?.type === "paid" ? "⭐" : "[?]"));
}

// bot(): { username, id } — a getMe utan ismert, ezert fuggveny.
export function createHandlers({
  groupId, allowIds, requireMention, maxFileBytes, bot,
  deliver, enqueueMedia, logInbound, log = () => {}, onApprovalCandidate = () => {},
}) {
  const allowedChats = new Set([String(groupId)]);
  const allowedUsers = new Set(allowIds.map(String));

  // Csoport-uzenet a sajat csoportbol, vagy DM az allowlistrol. Bot-uzenet SOHA.
  function allowDecision({ chatId, fromId, isBot }) {
    if (isBot) return false;
    return allowedChats.has(String(chatId)) || allowedUsers.has(String(fromId));
  }

  function handleMessage(msg, { edited = false, updateId } = {}) {
    if (!msg) return;
    const chatId = String(msg.chat?.id);
    const fromId = String(msg.from?.id);
    if (!allowDecision({ chatId, fromId, isBot: msg.from?.is_bot === true })) {
      if (msg.from?.is_bot !== true) log(`drop: chat=${chatId} from=${fromId} (not allowed)`);
      return;
    }
    // Kozos csoportban csak @botnev-es uzenet vagy a bot uzenetere adott reply
    // jut be (BRIDGE_REQUIRE_MENTION=false: dedikalt csoport, minden bemegy).
    const isGroupChat = msg.chat?.type === "group" || msg.chat?.type === "supergroup";
    if (requireMention && isGroupChat) {
      const text = msg.text ?? msg.caption ?? "";
      const entities = msg.text != null ? msg.entities : msg.caption_entities;
      const mentioned = isMentioned(text, entities, bot().username);
      const replyToBot = msg.reply_to_message && String(msg.reply_to_message.from?.id) === String(bot().id);
      if (!mentioned && !replyToBot) return;
    }
    const who = msg.from?.first_name || msg.from?.username || fromId;
    const replyTo = msg.reply_to_message?.message_id;
    // Szerkesztett uzenetnel a mediat NEM toltjuk le ujra — szovegkent megy at.
    const media = edited ? null : pickMedia(msg, maxFileBytes);
    if (media) {
      enqueueMedia({ msg, media, updateId }); // SZINKRON fajlba — az offset mar lephet
      // A naplosorba fajl-ut nem kerul, csak a teny es a felirat.
      logInbound({ chat_id: chatId, msg_id: msg.message_id, kind: "media", from: sanitize(who),
        from_id: fromId, reply_to: replyTo, text: `${msg.caption ? sanitize(msg.caption) : ""} [media]` });
      return;
    }
    const kind = msg.text || msg.caption ? null : attachmentKind(msg);
    const raw = msg.text ?? msg.caption ?? (kind
      ? `[${kind} csatolmány érkezett — ezt a híd nem tudja átadni, csak szöveget, képet és hangot]`
      : "[non-text message]");
    const text = sanitize(raw);
    if (!text) return;
    // Jovahagyo webhook (3.1): minden reply, nem szerkesztett uzenet, ami a
    // fenti kapun (allowDecision + mention) atjutott; a jogosultsagot a szerver
    // donti el (tg_from_id), a hid nem szuk ujra. A tartos sor-iras a
    // beinjektalas ELOTT tortenik es DOBHAT: ilyenkor semmi nem injektalodott,
    // az offset nem lep (mint a pending-nel). A visszaadott fuggveny (ha van)
    // inditja a halozati kuldest — a deliver UTAN.
    let kick = null;
    if (!edited && replyTo != null) {
      kick = onApprovalCandidate({ event_id: `${chatId}:${msg.message_id}`, tg_from_id: fromId, tg_chat_id: chatId,
        tg_message_id: msg.message_id, tg_reply_to: replyTo, tg_date: msg.date, text: raw },
      { kind: "message", replyToFromId: msg.reply_to_message?.from?.id, botId: bot().id,
        replyToText: msg.reply_to_message?.text ?? msg.reply_to_message?.caption ?? "" });
    }
    // A NYERS szoveg megy a sorepitonek: o vag 6000-nel, CSONKA-jellel.
    deliver(buildTextLine({ who, fromId, chatId, messageId: msg.message_id, replyTo, text: raw, edited, updateId }));
    if (typeof kick === "function") kick();
    logInbound({ chat_id: chatId, msg_id: msg.message_id, kind: edited ? "edited" : "message",
      from: sanitize(who), from_id: fromId, reply_to: replyTo, text });
  }

  function handleReaction(mr) {
    if (!mr) return;
    const chatId = String(mr.chat?.id);
    const fromId = String(mr.user?.id ?? "");
    if (!allowDecision({ chatId, fromId, isBot: mr.user?.is_bot === true })) return;
    const oldE = reactionEmojis(mr.old_reaction);
    const added = reactionEmojis(mr.new_reaction).filter((e) => !oldE.includes(e));
    if (!added.length) return;
    const who = mr.user?.first_name || mr.user?.username || fromId || "valaki";
    // Reakcio-jelolt (a `reaction`-illesztesu celoknak): sajat message_id nincs,
    // a reagalt uzenet a horgony celja — tg_message_id = tg_reply_to. Mint a
    // reply-nal: a tartos iras a deliver ELOTT (dobhat), a kuldes UTANA.
    const kick = onApprovalCandidate({ event_id: `${chatId}:${mr.message_id}:r${fromId}:${mr.date}`,
      tg_from_id: fromId, tg_chat_id: chatId, tg_message_id: mr.message_id, tg_reply_to: mr.message_id,
      tg_date: mr.date, text: added.join(" ") }, { kind: "reaction" });
    deliver(buildReactionLine({ who, fromId, chatId, messageId: mr.message_id, added }));
    if (typeof kick === "function") kick();
    logInbound({ chat_id: chatId, msg_id: null, target_msg_id: mr.message_id, kind: "reaction",
      from: sanitize(who), from_id: fromId, text: sanitize(added.join(" ")) });
  }

  return { allowDecision, handleMessage, handleReaction };
}
