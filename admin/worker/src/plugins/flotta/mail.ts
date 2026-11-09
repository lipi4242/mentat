// Az eszkaláció levele. A részlet a boxtól jön (gépi bemenet): a HTML-be csak
// escape-elve kerül, mert a sablon *Html mezői nyersen illesztődnek be.
import { renderTransactionalEmail } from '../../lib/email-template';
import type { Mail } from '../../lib/email';
import type { Brand } from '../../types';
import { fixHint, what } from './task-text';
import type { Row } from './types';

export type MailKind = 'first' | 'repeat' | 'resolved';

const esc = (s: string) => s.replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' })[c]!);

const HEAD: Record<MailKind, string> = { first: 'Flotta-hiba', repeat: 'Még mindig fennáll', resolved: 'Megoldva' };

export function incidentMail(kind: MailKind, inc: Row, why: string, b: Brand, repeatMin: number, attempts: string[] = []): Mail {
  const subject = `${kind === 'resolved' ? 'Megoldva' : 'Flotta-hiba'}: ${what(inc)}`;
  const lines = kind === 'resolved'
    ? [`Megoldódott: ${what(inc)}.`, inc.resolve_note ? `(${inc.resolve_note})` : '']
    : [`${what(inc)}.`, inc.detail ? `Részlet: ${inc.detail}` : '', `Nyílt: ${inc.opened_at} · miért most: ${why}`,
      inc.todo_task_id ? 'Egy felelős ágens feladatot kapott rá.' : 'Nincs illetékes, ép felelős ágens: senki nem kapott rá feladatot.',
      ...(attempts.length ? ['Kísérletek:', ...attempts.map(a => `· ${a}`)] : ['Kísérlet még nem volt.']),
      `Javítás: ${fixHint(inc)}`,
      `Amíg nyitva van, ${Math.round(repeatMin / 6) / 10} óránként újra szólunk.`];
  const body = lines.filter(Boolean);
  return {
    subject,
    text: [HEAD[kind], '', ...body, '', b.name].join('\r\n'),
    html: renderTransactionalEmail({ heading: HEAD[kind], bodyHtml: body.map(l => `<p style="margin:0 0 10px;">${esc(l)}</p>`).join('') }, b),
  };
}
