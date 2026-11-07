import { Empty, Tag, Timeline, Typography } from 'antd';

export type CaseEvent = {
  id: number;
  at: string;
  actor: 'user' | 'agent' | string;
  actor_token_id: string | null;
  kind: string;
  body: string | null;
};

/**
 * The event trail as `GET /api/cases/:id` returns it (newest first — the
 * worker orders by `id DESC`). The token id is shown alongside an
 * agent event on purpose: "an agent did it" stops being attribution the
 * moment more than one token exists.
 */
export function CaseEvents({ events }: { events: CaseEvent[] }) {
  if (!events.length) {
    return <Empty description="Még nincs esemény" image={Empty.PRESENTED_IMAGE_SIMPLE} />;
  }
  return (
    <Timeline
      items={events.map((e) => ({
        color: e.actor === 'agent' ? 'blue' : 'green',
        children: (
          <div>
            <Typography.Text strong>{e.kind}</Typography.Text>{' '}
            <Tag color={e.actor === 'agent' ? 'blue' : 'default'}>
              {e.actor === 'agent' ? `ágens${e.actor_token_id ? ` · ${e.actor_token_id}` : ''}` : 'ember'}
            </Tag>
            <div>
              <Typography.Text type="secondary">{e.at}</Typography.Text>
            </div>
            {e.body ? <div style={{ whiteSpace: 'pre-wrap' }}>{e.body}</div> : null}
          </div>
        ),
      }))}
    />
  );
}
