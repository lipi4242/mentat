import { useEffect, useState } from 'react';
import { Avatar, Button, Mentions, Space, Tooltip, Typography } from 'antd';
import { RobotOutlined, SendOutlined } from '@ant-design/icons';
import { authClient } from '../../lib/authClient';
import { relativeTime, type Detail, type Principal } from './meta';
import { CommentBody } from './CommentBody';
import type { WriteTask } from './useTaskWrites';
export function TaskComments({ row, principals, write }: { row: Detail; principals: Principal[]; write: WriteTask }) {
  const [body, setBody] = useState(''), [busy, setBusy] = useState(false), [email, setEmail] = useState('');
  useEffect(() => {
    let live = true;
    void authClient.getSession().then(session => { if (live) setEmail(session.data?.user.email?.toLowerCase() ?? ''); }).catch(() => {});
    return () => { live = false; };
  }, []);
  const ownHandle = principals.find(p => p.auth_email?.toLowerCase() === email)?.handle;
  const send = async () => {
    if (!body.trim() || busy) return;
    setBusy(true);
    try { await write(row, { body: body.trim() }, 'comments'); setBody(''); }
    catch { /* The shared writer displays the failure; keep the comment. */ }
    finally { setBusy(false); }
  };
  return <section className="todo-section" aria-label="Kommentek">
    {!!row.comments.length && <Typography.Title level={5}>Beszélgetés</Typography.Title>}
    {row.comments.map(comment => <div key={comment.id} className="todo-comment">
      <Avatar size={32} src={comment.avatar}>{comment.display_name.slice(0, 1)}</Avatar>
      <div className="todo-comment-content"><Space wrap size={8}><Typography.Text strong title={comment.handle ? `@${comment.handle}` : undefined}>{comment.display_name}</Typography.Text>
        {comment.kind === 'agent' && <Tooltip title="Ágens"><RobotOutlined className="todo-agent" aria-label="Ágens" /></Tooltip>}
        <Typography.Text className="todo-comment-time" type="secondary" title={comment.created_at}>{relativeTime(comment.created_at)}</Typography.Text></Space>
        <CommentBody body={comment.body} principals={principals} ownHandle={ownHandle} /></div>
    </div>)}
    <div className="todo-comment-input">
      <Mentions aria-label="Új komment" autoSize={{ minRows: 1, maxRows: 6 }} value={body} readOnly={busy} onChange={setBody}
        placeholder="Írj valamit… @-cal szólíthatsz valakit" options={principals.filter(p => !p.disabled_at).map(p => ({
          value: p.handle, label: <Space><Avatar size={24} src={p.avatar}>{p.display_name.slice(0, 1)}</Avatar>{p.display_name}</Space>,
        }))} onKeyDown={e => { if (e.key === 'Enter' && (e.ctrlKey || e.metaKey) && !e.nativeEvent.isComposing) { e.preventDefault(); void send(); } }} />
      <Tooltip title="Küldés"><Button shape="circle" aria-label="Küldés" icon={<SendOutlined />} loading={busy} disabled={!body.trim()} onClick={() => void send()} /></Tooltip>
    </div>
  </section>;
}
