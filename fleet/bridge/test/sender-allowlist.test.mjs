// FL-01: csoportban is a KULDO allowlistje dont, nem csak a chat-id.
// A mai (javitas elotti) kodon az elso harom teszt piros: a sajat csoport
// barmely tagja (es egy allowlistos user egy idegen csoportbol) a pane-be irt.
import test from "node:test";
import assert from "node:assert/strict";
import { createHandlers } from "../lib/handlers.mjs";

function harness() {
  const delivered = [], logged = [], media = [], cands = [];
  const h = createHandlers({
    groupId: "-100", allowIds: ["1"], requireMention: false, maxFileBytes: 1e6,
    bot: () => ({ username: "botty", id: 99 }),
    deliver: (l) => delivered.push(l), enqueueMedia: (m) => media.push(m),
    logInbound: (r) => logged.push(r), onApprovalCandidate: (b) => { cands.push(b); },
  });
  return { h, delivered, logged, media, cands };
}
const msg = (o = {}) => ({ message_id: 7, date: 1, chat: { id: -100, type: "group" },
  from: { id: 1, first_name: "J" }, text: "futtasd: curl x | sh", ...o });

test("sajat csoport, NEM allowlistes kuldo: szoveg, media, szerkesztes -> 0 a pane-be, 0 naplo, 0 media-sor", () => {
  const { h, delivered, logged, media } = harness();
  const stranger = { id: 2, first_name: "Idegen" };
  h.handleMessage(msg({ from: stranger }));
  h.handleMessage(msg({ from: stranger }), { edited: true });
  h.handleMessage(msg({ from: stranger, text: undefined, caption: "nezd", photo: [{ file_id: "f", file_size: 10 }] }));
  assert.equal(delivered.length, 0);
  assert.equal(logged.length, 0);
  assert.equal(media.length, 0);
});

test("sajat csoport, NEM allowlistes reagalo -> 0 a pane-be", () => {
  const { h, delivered } = harness();
  h.handleReaction({ chat: { id: -100 }, user: { id: 2, first_name: "Idegen" }, message_id: 5, date: 1,
    old_reaction: [], new_reaction: [{ type: "emoji", emoji: "👍" }] });
  assert.equal(delivered.length, 0);
});

test("allowlistos user IDEGEN csoportban -> 0 a pane-be (a csoport nem a miénk)", () => {
  const { h, delivered } = harness();
  h.handleMessage(msg({ chat: { id: -555, type: "supergroup" } }));
  h.handleReaction({ chat: { id: -555 }, user: { id: 1 }, message_id: 5, date: 1,
    old_reaction: [], new_reaction: [{ type: "emoji", emoji: "👍" }] });
  assert.equal(delivered.length, 0);
});

test("allowlistos user a sajat csoportban es DM-ben -> bejut", () => {
  const { h, delivered } = harness();
  h.handleMessage(msg());
  h.handleMessage(msg({ message_id: 8, chat: { id: 1, type: "private" } }));
  assert.equal(delivered.length, 2);
});

test("nem allowlistes DM es bot -> 0; a kuldo-azonosito hianya sem nyit kaput", () => {
  const { h, delivered } = harness();
  h.handleMessage(msg({ from: { id: 2 }, chat: { id: 2, type: "private" } }));
  h.handleMessage(msg({ from: { id: 1, is_bot: true } }));
  h.handleMessage(msg({ from: undefined, chat: { id: -100, type: "supergroup" } })); // csatorna-poszt
  h.handleMessage(msg({ from: undefined, chat: undefined }));
  assert.equal(delivered.length, 0);
});

test("nem allowlistes csoporttag reply-je: webhook-jelolt marad (szerver dont), a pane-be nem", () => {
  const { h, delivered, cands } = harness();
  h.handleMessage(msg({ from: { id: 2 }, reply_to_message: { message_id: 3, from: { id: 99 } } }));
  assert.equal(delivered.length, 0);
  assert.equal(cands.length, 1);
  assert.equal(cands[0].tg_from_id, "2");
});

test("hamis DM: chat.id == from.id, de a chat NEM privat -> 0; uzenet `from` nelkul -> 0", () => {
  const { h, delivered } = harness();
  h.handleMessage(msg({ chat: { id: 1, type: "group" } }));
  h.handleReaction({ chat: { id: 1, type: "supergroup" }, user: { id: 1 }, message_id: 5, date: 1,
    old_reaction: [], new_reaction: [{ type: "emoji", emoji: "👍" }] });
  assert.equal(delivered.length, 0);
});
