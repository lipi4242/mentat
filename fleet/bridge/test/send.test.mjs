import test from "node:test";
import assert from "node:assert/strict";
import {
  buildPayload,
  buildReactionPayload,
  parseArgs,
  USAGE,
} from "../send.mjs";

test("payload: plain text, preview off, 4096 cut", () => {
  const p = buildPayload("42", "x".repeat(5000));
  assert.equal(p.chat_id, "42");
  assert.equal(p.text.length, 4096);
  assert.equal(p.disable_web_page_preview, true);
  assert.ok(!("parse_mode" in p));
  assert.ok(!("reply_to_message_id" in p));
});

test("payload: reply targeting when given", () => {
  assert.equal(buildPayload("42", "hi", 7).reply_to_message_id, 7);
});

test("argv parsing", () => {
  const a = parseArgs(["--chat", "42", "--reply-to", "7", "hello", "world"]);
  assert.deepEqual(a, {
    chat: "42",
    replyTo: 7,
    react: null,
    messageId: null,
    textStdin: false,
    why: null,
    html: false,
    text: "hello world",
  });
});

test("--why atmegy a parseArgs-on, es szo szerint marad", () => {
  const a = parseArgs(["--chat", "42", "--why", "a kert teljes spec-reszlet", "hosszu"]);
  assert.equal(a.why, "a kert teljes spec-reszlet");
  assert.equal(a.text, "hosszu", "az indok NEM szivarog bele az uzenetbe");
});

test("--why ertek nelkul hangos hiba, nem lenyelt argumentum", () => {
  assert.throws(() => parseArgs(["--chat", "42", "--why"]), /--why requires a value/);
});

test("`--` terminator: everything after it is verbatim text", () => {
  const a = parseArgs(["--chat", "42", "--", "--chat", "is", "just", "text"]);
  assert.equal(a.chat, "42");
  assert.equal(a.text, "--chat is just text");
  assert.equal(a.replyTo, null);
});

test("`--` with no options before it still yields text", () => {
  assert.equal(parseArgs(["--", "--reply-to"]).text, "--reply-to");
});

test("missing option value at the end is a usage error, not a swallowed arg", () => {
  assert.throws(() => parseArgs(["--chat"]), /--chat requires a value/);
  assert.throws(() => parseArgs(["--chat", "42", "--reply-to"]), /--reply-to requires a value/);
});

test("non-numeric --reply-to is rejected loudly (was: silent NaN -> no reply)", () => {
  assert.throws(() => parseArgs(["--chat", "42", "--reply-to", "nope", "hi"]),
    /--reply-to must be a positive integer/);
  assert.throws(() => parseArgs(["--chat", "42", "--reply-to", "7abc", "hi"]),
    /--reply-to must be a positive integer/);
});

test("text containing option-looking tokens after `--` reaches the payload", () => {
  const a = parseArgs(["--chat", "42", "--", "vigyazz: --reply-to 9 nem opcio"]);
  assert.equal(buildPayload(a.chat, a.text, a.replyTo).text, "vigyazz: --reply-to 9 nem opcio");
});

test("reaction payload: emoji reaction on a message", () => {
  const p = buildReactionPayload("42", 7, "👍");
  assert.equal(p.chat_id, "42");
  assert.equal(p.message_id, 7);
  assert.deepEqual(p.reaction, [{ type: "emoji", emoji: "👍" }]);
});

test("argv: react mode", () => {
  const a = parseArgs(["--chat", "42", "--react", "👍", "--message", "7"]);
  assert.equal(a.react, "👍");
  assert.equal(a.messageId, 7);
});

test("argv: --text-stdin flag parsing (no positional text)", () => {
  const a = parseArgs(["--chat", "42", "--text-stdin"]);
  assert.equal(a.textStdin, true);
  assert.equal(a.text, "");
});

test("argv: --text-stdin + positional text is a usage error", () => {
  assert.throws(() => parseArgs(["--chat", "42", "--text-stdin", "hello"]),
    /--text-stdin cannot be combined with positional text/);
  assert.throws(() => parseArgs(["--chat", "42", "--text-stdin", "--", "hello"]),
    /--text-stdin cannot be combined with positional text/);
});

test("argv: --text-stdin combined with --reply-to", () => {
  const a = parseArgs(["--chat", "42", "--text-stdin", "--reply-to", "9"]);
  assert.equal(a.textStdin, true);
  assert.equal(a.replyTo, 9);
});

test("argv: --instance mar nem opcio (2.0) — szovegkent marad, nem nyel el semmit", () => {
  assert.equal(parseArgs(["--chat", "42", "--", "--instance", "box1"]).text, "--instance box1");
});

test("USAGE: a kimenet-kodok (3 vak naplo, 5 unknown) dokumentalva", () => {
  assert.match(USAGE, /\b3\b[^\n]*delivery log/i);
  assert.match(USAGE, /\b5 unknown\b/);
});
