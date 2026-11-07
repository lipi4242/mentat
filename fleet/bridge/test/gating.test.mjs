import test from "node:test";
import assert from "node:assert/strict";
import { isMentioned, escapeRegex } from "../lib/gating.mjs";

test("exact @mention passes (no entities -> regex fallback)", () => {
  assert.equal(isMentioned("szia @BetaBot mi a helyzet", null, "BetaBot"), true);
  assert.equal(isMentioned("@BetaBot", undefined, "BetaBot"), true);
});

test("prefix-collision bot name does NOT pass", () => {
  // Ez volt a substring-illesztes lyuka: egy IDEGEN bot emlitese nyitotta
  // volna a kaput.
  assert.equal(isMentioned("hello @BetaBot_evil", null, "BetaBot"), false);
  assert.equal(isMentioned("hello @BetaBotXtra", null, "BetaBot"), false);
});

test("mention matching is case-insensitive", () => {
  assert.equal(isMentioned("hé @betabot nézd", null, "BetaBot"), true);
  assert.equal(isMentioned("hé @BETABOT nézd", null, "BetaBot"), true);
});

test("entity-based match: the exact slice decides", () => {
  const text = "@BetaBot csinald meg";
  const ents = [{ type: "mention", offset: 0, length: 8 }];
  assert.equal(isMentioned(text, ents, "BetaBot"), true);
});

test("entity present but for ANOTHER bot -> no fallback rescue", () => {
  const text = "@MasikBot nezd meg @BetaBotEvil";
  const ents = [{ type: "mention", offset: 0, length: 9 }];
  assert.equal(isMentioned(text, ents, "BetaBot"), false);
});

test("non-mention entities fall back to the regex path", () => {
  const ents = [{ type: "bold", offset: 0, length: 4 }];
  assert.equal(isMentioned("bold @BetaBot", ents, "BetaBot"), true);
});

test("empty username never matches (getMe failure would open every gate)", () => {
  assert.equal(isMentioned("@ anything", null, ""), false);
  assert.equal(isMentioned("@undefined", null, undefined), false);
});

test("regex metacharacters in the username are escaped", () => {
  assert.equal(escapeRegex("a.b+c"), "a\\.b\\+c");
  assert.equal(isMentioned("hi @axb", null, "a.b"), false);
  assert.equal(isMentioned("hi @a.b", null, "a.b"), true);
});
