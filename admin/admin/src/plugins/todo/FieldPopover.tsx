import { useState, type ReactNode } from 'react';
import { Button, Popover, Tooltip } from 'antd';
export function FieldPopover({ label, icon, children, value, onClose }: {
  label: string; icon: ReactNode; children: ReactNode; value?: ReactNode; onClose: () => Promise<unknown>;
}) {
  const [open, setOpen] = useState(false);
  return <Popover trigger="click" open={open} placement="bottomLeft" content={<div className="todo-editor">{children}</div>}
    onOpenChange={next => { setOpen(next); if (!next) void onClose().catch(() => setOpen(true)); }}>
    <Tooltip title={label}><Button type="text" aria-label={label} icon={value ? undefined : icon}>{value}</Button></Tooltip>
  </Popover>;
}
