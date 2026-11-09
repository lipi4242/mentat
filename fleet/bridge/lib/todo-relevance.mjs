// lib/todo-relevance.mjs — melyik todo-esemeny ebreszti az agenst (AC 2). Tiszta fuggvenyek.
//
// Releváns: neki adtak ki valamit / visszakerult hozza / kommentben megemlitettek / az o
// elfogadasara var / komment egy olyan tetelen, ahol nala a labda (ball = assignee, kulonben owner).
// NEM releváns: a sajat irasa, a puszta mezovaltozas, masok egymas kozti forgalma.
// Egy implementacio: a desktop-hook (fleet/plugin/hooks/todo/) ennek a fajlnak bajtra azonos masolatat
// futtatja (test/todo-plugin-copy.test.mjs). Az esetek: test/fixtures/todo-relevance.json.

// Ezekhez kell a tetel aktualis allapota (ball, owner, cim): a hivo egyszer lekeri.
export const NEEDS_TASK = new Set(["created", "updated", "commented", "handback", "item_issue", "item_handback",
  "item_submit", "item_reject", "item_resume"]);

// engine anytime_todo/cli_me.py ACK_MARK — a ket ertek egyutt valtozik.
export const ACK_MARK = "[ack]";

export const diffOf = (ev) => {
  if (ev && typeof ev.diff === "object" && ev.diff) return ev.diff;
  try { const d = JSON.parse(ev?.diff_json ?? "null"); return d && typeof d === "object" ? d : {}; } catch { return {}; }
};

export const ballOf = (task) => (task ? task.assignee_id || task.owner_id || null : null);

// A todo worker mentions.ts mintajaval egyezo @handle-felismeres.
export function mentions(body, handle) {
  if (typeof body !== "string" || !handle) return false;
  const re = /(?:^|[^\p{L}\p{N}_@.+-])@([a-z0-9_]{1,64})(?![\p{L}\p{N}_])/gu;
  for (const m of body.matchAll(re)) if (m[1] === handle) return true;
  return false;
}

export const isOwn = (ev, me) => Boolean(me?.id) && ev?.actor_id === me.id;

// -> null (nem ebreszt) | { verb } ; verb: a sor magyar igeje ("kiadta", "kommentelt" ...)
export function classify(ev, me, task) {
  if (!ev || !me?.id || isOwn(ev, me)) return null;
  const d = diffOf(ev);
  const mine = (id) => id === me.id;
  switch (ev.kind) {
    case "item_issue":
      return mine(d.dev_id) ? { verb: "kiadta" } : null;
    case "created":
      return task && mine(ballOf(task)) ? { verb: "kiadta" } : null;
    case "updated":
      // Csak a gazda-/felelos-csere ebreszt, a tobbi mezo (cim, hatarido, leiras) nem.
      if ("assignee_id" in d && mine(d.assignee_id)) return { verb: "kiadta" };
      if ("owner_id" in d && mine(d.owner_id) && task && mine(ballOf(task))) return { verb: "kiadta" };
      return null;
    case "handback":
    case "item_handback":
      return task && mine(task.owner_id) ? { verb: "visszaadta" } : null;
    case "item_reject":
      return task && !mine(task.owner_id) && mine(ballOf(task)) ? { verb: "visszadobta" } : null;
    case "item_resume":
      return task && mine(task.assignee_id) ? { verb: "folytatásra visszaadta" } : null;
    case "item_submit":
      return task && mine(task.owner_id) ? { verb: "elfogadásra küldte" } : null;
    case "commented":
      // `mentat-todo ack` nyugtaja ("[ack] ..."): senkit nem ebreszt, kulonben az ack pingpongot inditana.
      if (typeof d.body === "string" && d.body.startsWith(ACK_MARK)) return null;
      if (mentions(d.body, me.handle)) return { verb: "megemlített" };
      return task && mine(ballOf(task)) ? { verb: "kommentelt" } : null;
    default:
      return null;
  }
}

// "Tartalom nelkuli" komment (a runaway-fekhez): a megemlitesek, irasjelek es emojik nelkul
// legfeljebb nehany betu, vagy egy tipikus nyugta-szo.
const ACKS = /^(ok(é|e|s|ay)?|köszi|köszönöm|kösz|thanks?|thx|rendben|megvan|értem|igen|nem|jó|done|kész|noted|ack)$/i;
export function contentFree(body) {
  if (typeof body !== "string") return true;
  const t = body.replace(/@[a-z0-9_]{1,64}/gi, " ").replace(/[^\p{L}\p{N}]+/gu, " ").trim();
  return t.length < 12 || ACKS.test(t);
}
