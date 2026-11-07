import { Typography } from 'antd';
import { stageLabel, type ItemDetail } from './meta';
const outcome = { accepted: 'elfogadva', rejected: 'visszaküldve' };
export function ItemDetails({ item }: { item: ItemDetail }) {
  const past = item.reports.filter(r => r.pm_verdict);
  return <>
    {item.description && <section className="todo-section"><Typography.Paragraph style={{ whiteSpace: 'pre-wrap' }}>{item.description}</Typography.Paragraph></section>}
    {item.request_quote && <blockquote className="bl-quote">{item.request_quote}</blockquote>}
    <section className="todo-section" aria-label="Kész, ha">
      <Typography.Title level={5}>Kész, ha</Typography.Title>
      {item.acs.length ? <ol className="bl-acs">{item.acs.map(a => <li key={a.id}>{a.text}</li>)}</ol> : <Typography.Text type="secondary">Még nincs feltétel megadva.</Typography.Text>}
    </section>
    {!!item.links.length && <section className="todo-section"><Typography.Title level={5}>Hivatkozások</Typography.Title>
      {item.links.map(l => <div key={l.id}>{l.url ? <a href={l.url} target="_blank" rel="noreferrer">{l.title || l.url}</a> : l.title}</div>)}</section>}
    {!!past.length && <section className="todo-section"><Typography.Title level={5}>Korábbi körök</Typography.Title>
      {past.map(r => <div key={r.id}>{r.round}. kör — {outcome[r.pm_verdict!]}: {r.summary}</div>)}</section>}
    <Typography.Text type="secondary">Állapot: {stageLabel[item.stage]}</Typography.Text>
  </>;
}
