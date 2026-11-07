import test from "node:test";
import assert from "node:assert/strict";
import { sanitizeHtml, escapeText } from "../lib/html.mjs";
import { buildPayload } from "../send.mjs";

test("engedett tagek maradnak, a szoveg escape-elodik", () => {
  assert.equal(sanitizeHtml("<b>NÁLAD VAN</b> 520 k & <i>ok</i>"), "<b>NÁLAD VAN</b> 520 k &amp; <i>ok</i>");
  assert.equal(sanitizeHtml("<pre>a < b</pre>"), "<pre>a &lt; b</pre>");
});

test("nem engedett tag szo szerint jelenik meg", () => {
  assert.equal(sanitizeHtml("<script>x</script>"), "&lt;script&gt;x&lt;/script&gt;");
  assert.equal(sanitizeHtml("<img src=x onerror=1>"), "&lt;img src=x onerror=1&gt;");
  assert.equal(sanitizeHtml("<b onclick=\"x\">t</b>"), "<b>t</b>");
});

test("a href csak http/https/tg, mas attributum eldobva", () => {
  assert.equal(sanitizeHtml('<a href="https://x.y/?a=1&b=2" target="_blank">l</a>'),
    '<a href="https://x.y/?a=1&amp;b=2">l</a>');
  assert.equal(sanitizeHtml('<a href="javascript:alert(1)">l</a>'), '&lt;a href="javascript:alert(1)"&gt;l</a>');
});

test("spoiler es code class", () => {
  assert.equal(sanitizeHtml('<span class="tg-spoiler">s</span>'), '<span class="tg-spoiler">s</span>');
  assert.equal(sanitizeHtml('<span style="x">s</span>'), '&lt;span style="x"&gt;s</span>');
  assert.equal(sanitizeHtml('<pre><code class="language-py">x</code></pre>'), '<pre><code class="language-py">x</code></pre>');
});

test("ervenyes entitasok nem duplazodnak", () => {
  assert.equal(escapeText("a &amp; b &lt; c &#233; & d"), "a &amp; b &lt; c &#233; &amp; d");
});

test("buildPayload html modban parse_mode-ot ad, plain modban nem", () => {
  assert.equal(buildPayload("1", "x", null).parse_mode, undefined);
  assert.equal(buildPayload("1", "x", null, { html: true }).parse_mode, "HTML");
});

test("data-href nem href; NUL karakter nem ut ki semmit; rossz entitas escape", () => {
  assert.equal(sanitizeHtml('<a data-href="https://x">l</a>'), '&lt;a data-href="https://x"&gt;l</a>');
  assert.equal(sanitizeHtml("a\u0000b & c"), "a\u0000b &amp; c");
  assert.equal(escapeText("&#99999999; &bogus; &#x41;"), "&amp;#99999999; &amp;bogus; &#x41;");
});
