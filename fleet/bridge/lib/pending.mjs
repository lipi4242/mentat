// lib/pending.mjs — a pending-sor sapkaja. Pure: a hivo dont a riasztasrol.
// A sapka nelkul egy orakig nem fogado tmux korlatlan fajlt hizlalna (3.8G box).
export function capPending(items, entry, max) {
  const out = [...items, entry];
  const dropped = Math.max(0, out.length - max);
  return { items: out.slice(dropped), dropped };
}
