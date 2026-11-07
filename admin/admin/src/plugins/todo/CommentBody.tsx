import { Typography } from 'antd';
import type { Principal } from './meta';
export function CommentBody({ body, principals, ownHandle }: { body: string; principals: Principal[]; ownHandle?: string }) {
  const known = new Set(principals.map(p => p.handle));
  return <Typography.Paragraph className="todo-comment-body" ellipsis={{ rows: 4, expandable: true, symbol: 'tovább' }}>
    {body.split(/((?<![\p{L}\p{N}_@.+-])@[a-z0-9_]{1,64}(?![\p{L}\p{N}_]))/gu).map((part, i) => part.startsWith('@') && known.has(part.slice(1))
      ? <span key={i} className={`todo-mention${part.slice(1) === ownHandle ? ' todo-mention-own' : ''}`}>{part}</span> : part)}
  </Typography.Paragraph>;
}
