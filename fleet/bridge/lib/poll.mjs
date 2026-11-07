// lib/poll.mjs — a getUpdates-ciklus es az offset-szemantika.
//
// OFFSET-SZEMANTIKA (a "tranzakcionalitas nem hazudhat" pont): az offset
// UPDATE-enkent lep, es CSAK azutan, hogy az adott update feldolgozasa
// HIBATLANUL lefutott (tartos naplo + tartos enqueue/pending-iras). Ha barmelyik
// dob, a koteg megszakad, az offset azon az update-en ALL MEG, igy a kovetkezo
// getUpdates ugyanattol az update_id-tol hozza le ujra: at-least-once.
import { saveJson, loadJsonQuarantine } from "./jsonfile.mjs";
import { writeHealth } from "./health.mjs";

const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

export async function initOffset({ tg, offsetFile, onCorrupt, log }) {
  const o = loadJsonQuarantine(offsetFile, null, onCorrupt);
  if (o && Number.isInteger(o.offset)) {
    log("resuming from stored offset", o.offset);
    return o.offset;
  }
  // Elso indulas: a backlogot atugorjuk.
  let offset = 0;
  try {
    const { body } = await tg("getUpdates", { offset: -1, timeout: 0 });
    if (body.ok && body.result.length) {
      offset = body.result[body.result.length - 1].update_id + 1;
      log(`first run: skipping backlog, starting at offset ${offset}`);
    }
  } catch (e) {
    log("first run offset probe failed, starting at 0:", e.message);
  }
  saveJson(offsetFile, { offset });
  return offset;
}

// processUpdate(upd) DOBHAT — akkor az offset nem lep fole.
export async function pollForever({ tg, offset, offsetFile, healthFile, conflictAlertMs,
  processUpdate, depths, alert, log }) {
  let savedOffset = offset;
  let conflictSince = null;
  let conflictAlerted = false;
  let processFailAlerted = false; // egy incidensre EGY riasztas
  for (;;) {
    try {
      // A hosszu-poll timeout 50 s; az AbortSignal (65 s) ENNEK FOLOTT van.
      // Az allowed_updates LECSERELI az alapertelmezett halmazt: a reakciot es a
      // szerkesztett uzenetet kulon kell kerni.
      const { status, body } = await tg("getUpdates", {
        offset, timeout: 50, allowed_updates: ["message", "edited_message", "message_reaction"],
      }, 65_000);
      if (status === 409) {
        conflictSince = conflictSince || Date.now();
        writeHealth(healthFile, { last_409: Date.now() });
        if (!conflictAlerted && Date.now() - conflictSince > conflictAlertMs) {
          conflictAlerted = true;
          await alert("15 perce 409-et kapok a getUpdates-re — valami más poller fogja a bot-tokent. " +
            "Amíg ez áll, nem érnek be az üzenetek. (Fut valahol a telegram-plugin?)");
        }
        log("409 Conflict — another poller holds this token. Backing off 20s.");
        await sleep(20_000);
        continue;
      }
      conflictSince = null;
      conflictAlerted = false;
      if (!body.ok) {
        log("getUpdates not ok:", JSON.stringify(body).slice(0, 300));
        await sleep(5000);
        continue;
      }
      writeHealth(healthFile, { last_poll_ok: Date.now(), ...depths() });
      let batchFailed = false;
      for (const upd of body.result) {
        try {
          processUpdate(upd);
        } catch (e) {
          batchFailed = true;
          log(`update ${upd.update_id} feldolgozása HIBA (az offset nem lép fölé):`, e.message);
          if (!processFailAlerted) {
            processFailAlerted = true;
            await alert(`nem tudom tartósan rögzíteni a beérkező üzenetet (${e.message}) — ` +
              "amíg ez áll, nem lépek tovább, az üzenetek újra le fognak jönni. " +
              "Nézzetek rá a lemezre/állapotkönyvtárra.");
          }
          break;
        }
        offset = upd.update_id + 1;
        writeHealth(healthFile, { last_update_seen: Date.now() });
      }
      if (offset !== savedOffset) {
        saveJson(offsetFile, { offset });
        savedOffset = offset;
      }
      if (batchFailed) await sleep(5000); // ne porogjunk ugyanazon az updaten
      else processFailAlerted = false;
    } catch (e) {
      log("loop error:", e.message);
      await sleep(5000);
    }
  }
}
