// A menedzser feladatának és a tulajdonos e-mailjének szövege. Egy helyen,
// hogy a kettő ugyanazt mondja ugyanarról az incidensről.
//
// A FELADAT (cím, leírás, komment) csak szerveroldali, felsorolt értékekből épül:
// a regisztrált box neve, az ágens neve (NAME_RE-vel ellenőrzött azonosító), a zárt
// listás ellenőrzés-kulcs (CHECKS), időbélyeg, számláló és egy rögzített sablon. A
// boxtól jövő szabad szöveg (`detail`) NEM kerül bele: egy ágens olvassa, és egy
// ellopott box-token különben utasítást írhatna neki. A részlet az incidensen marad
// (a UI és az e-mail escape-elve mutatja).
import { ATTEMPT_MIN, CLAIM_WAIT_MIN } from './states';
import { CHECKS, DEADMAN, OVERLOAD, REJECTED, type Fleet, type Row } from './types';

export function what(inc: Row): string {
  if (inc.check_key === OVERLOAD) return 'túl sok flotta-hiba egyszerre (a többi összevonva)';
  if (inc.check_key === REJECTED) return `a ${inc.box_name} box jelentéseit a központ elutasítja`;
  return inc.check_key === DEADMAN
    ? `a ${inc.box_name} box nem jelentett`
    : `${inc.agent}: ${inc.check_key} piros (${inc.box_name})`;
}

export const title = (inc: Row) => `[flotta] ${what(inc)}`;

export function fixHint(inc: Row): string {
  if (inc.check_key === REJECTED) return `A ${inc.box_name} boxon \`fleet doctor\`: a jelentés-sor mutatja a HTTP-kódot. 409: egy ágens másik boxhoz tartozik — áthelyezés az Adminban (POST /api/flotta/v1/agents/<név>/release). 400: a box flotta-verziója és az Admin nem illik össze.`;
  if (inc.check_key === OVERLOAD) return 'Nézd meg az Admin flotta-oldalát: valószínűleg egy box vagy egy beállítás szórja a hibát. A visszatartott feladatok és levelek a keret felszabadulásakor mennek.';
  return inc.check_key === DEADMAN
    ? `Nézd meg, él-e a ${inc.box_name} box és fut-e rajta a reconcile (\`systemctl --user status fleet-reconcile.timer\`), ` +
      `és megvan-e a ~/.config/fleet/flotta.env. Utána \`fleet doctor\` a boxon.`
    : `A ${inc.box_name} boxon: \`fleet doctor ${inc.agent}\`, majd ha kell, \`fleet doctor ${inc.agent} --fix\`.`;
}

/**
 * A menedzser feladata (flotta-menedzser). Csak felsorolt értékekből épül (incidens-azonosító, box- és
 * ágensnév a registry-mintájú NAME_RE szerint, ellenőrzés-kulcs a CHECK_RE szerint): a box
 * szabad szövegű `detail`-je nem kerül bele, mert azt egy ágens olvassa utasításként.
 */
export function instructions(fleet: Fleet, inc: Row): string {
  const t = inc.agent ? `--agent ${inc.agent} ` : '';
  return [
    `Mi bukott: ${what(inc)} — ${CHECKS[inc.check_key] ?? CHECKS.egyeb}.`,
    `Incidens: ${inc.id} · box: ${inc.box_name}${inc.agent ? ` · ágens: ${inc.agent}` : ''} · ellenőrzés: ${inc.check_key} · nyílt: ${inc.opened_at}`,
    'A részletek az Admin flotta-oldalán vannak.',
    '',
    `1. Vedd át ${CLAIM_WAIT_MIN} percen belül: \`fleet incident claim ${inc.id} --as <a te flottaneved>\` (utána ${ATTEMPT_MIN} perced van, meghosszabbítás nincs).`,
    `2. Minden lépés a végrehajtón megy, a ${inc.box_name} boxon: \`fleet repair-exec ${inc.id} doctor ${t}\` (csak olvas), ` +
      `majd ha kell \`fleet repair-exec ${inc.id} doctor-fix ${t}\` vagy \`bridge-install\` / \`unquarantine --cause …\`.`,
    `3. Lezárás csak ellenőrzéssel: \`fleet repair-exec ${inc.id} postcheck ${t}\` — zöld, nonce-os próba zár, kézzel ne zárd.`,
    `Ha nem megy: \`fleet incident release ${inc.id} --as <a te flottaneved>\`, és a lánc következője kapja. Szabad parancsot ne futtass a cél ellen.`,
    `${fleet.escalate_min} perc után, vagy ha a lánc elfogy, a tulajdonos e-mailt kap. (fleet plugin: \`flotta-incidens\` skill)`,
  ].join('\n');
}

/** A záró komment: csak felsorolt értékekből (nem a tárolt resolve_note-ból). */
export function closeNote(inc: Row): string {
  const why = inc.check_key === DEADMAN ? `a ${inc.box_name} box újra jelent` : `zöld jelentés a ${inc.box_name} boxról`;
  return `[flotta-ellenőrzés] Megoldva: ${why} (${inc.resolved_at ?? '?'}). A feladatot a rendszer zárta.`;
}
