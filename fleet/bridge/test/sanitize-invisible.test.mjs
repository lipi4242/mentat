// FL-11: lathatatlan Unicode a pane fele — a mai (javitas elotti)
// sanitizer a tag-savot, a U+2060/U+00AD/U+180E-t es a C1-kontrollt atengedte.
// Minden bejovo ut (szoveg, felirat, nev, reakcio) ES a vegso pane-kapu
// (deliverer -> paneSafe) ugyanazt a szurot hasznalja.
import test from "node:test";
import assert from "node:assert/strict";
import { join } from "node:path";
import { sanitize, sanitizeBody, stripInvisible, paneSafe } from "../lib/sanitize.mjs";
import { buildTextLine, buildMediaLine, buildReactionLine } from "../lib/lines.mjs";
import { createDeliverer } from "../lib/deliverer.mjs";
import { tempDir } from "./tmp.mjs";

// "rm -rf ~" a tag-savban: kepernyon lathatatlan, a modell tokenkent olvassa.
const TAGS = [..."rm -rf ~"].map((c) => String.fromCodePoint(0xe0000 + c.codePointAt(0))).join("");
const BAD = {
  "U+E0001 language tag": "\u{E0001}", "U+E0041 tag A": "\u{E0041}", "U+E007F cancel tag": "\u{E007F}",
  "U+2060 word joiner": "⁠", "U+00AD soft hyphen": "­", "U+180E mongolian vs": "᠎",
  "U+2061 function application": "⁡", "U+2064 invisible plus": "⁤", "U+061C arabic letter mark": "؜",
  "U+200D ZWJ": "‍", "U+202E RLO": "‮", "U+2066 LRI": "⁦", "U+FEFF BOM": "﻿",
  "U+E000 private use": "", "U+F0000 sup. private use": "\u{F0000}", "U+3164 hangul filler": "ㅤ",
  "U+115F hangul choseong filler": "ᅟ", "U+034F CGJ": "͏", "U+FE0F VS16": "️",
  "U+E0100 VS17": "\u{E0100}", "U+E01EF VS256": "\u{E01EF}", "U+D800 lone surrogate": "\uD800",
  "U+2800 braille blank": "\u2800", "U+1D159 null notehead": "\u{1D159}",
};

test("sanitize: minden felsorolt lathatatlan/formazo karakter eltunik", () => {
  for (const [name, ch] of Object.entries(BAD)) {
    assert.equal(sanitize(`a${ch}b`), "ab", name);
    assert.equal(sanitizeBody(`a${ch}b`), "ab", name);
  }
});

test("sanitize: a tag-savban kodolt utasitas nyom nelkul eltunik", () => {
  assert.equal(sanitize(`szia${TAGS}`), "szia");
  assert.equal(/[\u{E0000}-\u{E007F}]/u.test(sanitize(TAGS.repeat(50))), false);
});

test("sanitize: C1-kontroll (U+0085 NEL, U+009B CSI) es U+2028/2029 -> szokoz", () => {
  for (const ch of ["\u0085", "\u009B", " ", " ", "\u0080", "\u009F"]) {
    assert.equal(sanitize(`a${ch}b`), "a b", ch.codePointAt(0).toString(16));
  }
});

test("sanitize: NFKC — teljes szelessegu fejlec-utanzat ASCII lesz, a magyar szoveg es az emoji marad", () => {
  assert.equal(sanitize("［Telegram inbound］"), "[Telegram inbound]");
  assert.equal(sanitize("árvíztűrő ŐŰ 👍🔥"), "árvíztűrő ŐŰ 👍🔥");
  // NFD-ben erkezo ekezet NFC-re all ossze, nem vesz el
  assert.equal(sanitize("árvíz"), "árvíz");
});

test("stripInvisible: nem egysorosit es nem vag, csak szur", () => {
  assert.equal(stripInvisible(`x⁠  y${TAGS}`), "x  y");
});

test("sorepitok: nev, szoveg, felirat, reakcio — egyikben sincs lathatatlan karakter", () => {
  const all = Object.values(BAD).join("") + TAGS;
  const lines = [
    buildTextLine({ who: `J${all}`, fromId: "1", chatId: "-100", messageId: 1, text: `t${all}`, env: {} }),
    buildMediaLine({ who: `J${all}`, fromId: "1", chatId: "-100", messageId: 1, paths: ["/x/a.jpg"],
      caption: `c${all}`, failures: [], kinds: ["photo"], env: {} }),
    buildReactionLine({ who: `J${all}`, fromId: "1", chatId: "-100", messageId: 1, added: [`👍${all}`] }),
  ];
  for (const l of lines) assert.equal(paneSafe(l), l, l);
});

test("deliverer: a pane-be meno sor a vegso kapun at szurve — kozvetlen es pending-ut is", async () => {
  const d = tempDir("inv-");
  const sent = [];
  let up = false;
  const del = createDeliverer({ session: "s", pendingFile: join(d, "p.json"), maxPending: 10,
    pendingAlertMs: 1e9, healthFile: join(d, "h.json"), label: "x",
    inject: (s, line) => { if (!up) return { ok: false, error: "down" }; sent.push(line); return { ok: true }; } });
  del.deliver(`[nyers sor]${TAGS}⁠ vege`); // pl. regi verziobol a pending-sorban maradt
  up = true;
  await del.retryPending();
  del.deliver(`masik­${TAGS}`);
  assert.deepEqual(sent, ["[nyers sor] vege", "masik"]);
});

test("halmozott kombinalo jel 3-ra vagva", () => {
  assert.equal(sanitize("a" + "\u0301".repeat(40) + "b"), "\u00e1\u0301\u0301\u0301b");
  assert.equal(paneSafe("x" + "\u0308".repeat(10)), "x\u0308\u0308\u0308");
});

test("vagas kodpont-hataron: a surrogate par nem torik, a hianyzo szam pontos", () => {
  assert.equal(sanitize("ab😀", 3), "ab […csonkítva: +2 karakter, a teljes szöveg az events logban]");
});

test("paneSafe: a hid sajat utvonalat (pl. ① a konyvtarnevben) NEM irja at, csak szur", () => {
  assert.equal(paneSafe(`/srv/①/a.jpg\u2060${TAGS}`), "/srv/①/a.jpg");
});
