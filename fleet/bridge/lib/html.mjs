// lib/html.mjs — biztonsagos Telegram-HTML. A send.mjs alapbol parse_mode
// nelkul kuld (nincs formazas-injekcio); a `--html` kapcsolo ezen a szuron
// at enged formazast: CSAK a Telegram altal engedett tagek maradnak tagek,
// minden mas `<` es a nyers `&` escape-elodik. Tiszta fuggveny.
//
// Engedett tagek (https://core.telegram.org/bots/api#html-style):
//   b strong i em u ins s strike del code pre a blockquote tg-spoiler
//   span class="tg-spoiler"   pre-n belul <code class="language-x">
// Az <a> csak http/https/tg href-fel; mas attributumot eldobunk.
// Kiegyensulyozatlan tageket nem javitunk: azt a Bot API 400-zal utasitja el,
// es a send.mjs hangosan bukik — jobb, mint egy csendben mas alaku uzenet.

const SIMPLE = new Set(["b", "strong", "i", "em", "u", "ins", "s", "strike", "del",
  "code", "pre", "blockquote", "tg-spoiler"]);

const TAG_RE = /<(\/?)([a-zA-Z][a-zA-Z0-9-]*)((?:\s+[^<>]*)?)\s*(\/?)>/g;
// Csak a nevesitett es a helyes hosszusagu numerikus entitasok maradnak.
const AMP_RE = /&(?!(?:amp|lt|gt|quot|#[0-9]{1,7}|#x[0-9a-fA-F]{1,6});)/g;

export function escapeText(s) {
  return String(s ?? "").replace(AMP_RE, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
}

function attr(attrs, name, valueRe) {
  const re = new RegExp(`(?:^|\\s)${name}\\s*=\\s*"(${valueRe})"`);
  const m = re.exec(attrs || "");
  return m ? m[1] : null;
}

function renderTag(closing, name, attrs) {
  const n = name.toLowerCase();
  if (SIMPLE.has(n)) {
    if (closing) return `</${n}>`;
    if (n === "code") {
      const cls = attr(attrs, "class", "language-[a-zA-Z0-9_+-]+");
      return cls ? `<code class="${cls}">` : "<code>";
    }
    return `<${n}>`;
  }
  if (n === "span") {
    if (closing) return "</span>";
    return attr(attrs, "class", "tg-spoiler") ? '<span class="tg-spoiler">' : null;
  }
  if (n === "a") {
    if (closing) return "</a>";
    const href = attr(attrs, "href", "(?:https?:|tg:)[^\"<>]*");
    return href ? `<a href="${href.replace(AMP_RE, "&amp;")}">` : null;
  }
  return null;
}

// sanitizeHtml — a szoveg tagjai kozul az engedettek maradnak, minden mas
// szo szerint jelenik meg (escape-elve). A tagek KOZOTTI szoveg escape-elodik.
export function sanitizeHtml(text) {
  const src = String(text ?? "");
  let out = "";
  let last = 0;
  for (const m of src.matchAll(TAG_RE)) {
    out += escapeText(src.slice(last, m.index));
    const rendered = renderTag(m[1] === "/", m[2], m[3]);
    out += rendered ?? escapeText(m[0]);
    last = m.index + m[0].length;
  }
  out += escapeText(src.slice(last));
  return out;
}
