import { Progress, Typography } from 'antd';
import type { Task } from './meta';
export function TaskProgress({ progress, variant = 'bar' }: { progress: Task['progress']; variant?: 'ring' | 'bar' }) {
  if (!progress) return null;
  const { done, total, percent } = progress;
  return <div className={`todo-progress todo-progress-${variant}`} role="progressbar" aria-label="Részfeladatok haladása"
    aria-valuemin={0} aria-valuemax={100} aria-valuenow={percent} aria-valuetext={`${percent}% (${done}/${total})`}>
    <Progress percent={percent} type={variant === 'ring' ? 'circle' : 'line'} size={variant === 'ring' ? 20 : 'small'} showInfo={false}
      status="normal" strokeColor={percent === 100 ? '#4f8a83' : '#8b969c'} trailColor="#edf0f2" />
    <Typography.Text type="secondary" style={{ fontSize: 12, whiteSpace: 'nowrap' }}>{variant === 'bar' ? `${percent}% · ` : ''}{done}/{total}</Typography.Text>
  </div>;
}
