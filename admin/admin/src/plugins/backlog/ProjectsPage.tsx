import { Link } from 'react-router-dom';
import { Alert, Skeleton, Typography } from 'antd';
import { useApi } from '../../lib/useApi';
import { API, type Project } from './meta';
export function ProjectsPage() {
  const projects = useApi<Project[]>(`${API}/projects`);
  return <main className="todo-page bl-page">
    <header className="todo-heading"><Typography.Title level={4}>Projektek</Typography.Title><Link to="/labda">Kinél a labda</Link></header>
    {projects.error && <Alert type="info" message={projects.error.message} />}
    {projects.loading && !projects.data ? <Skeleton active /> : (projects.data ?? []).map(p =>
      <div key={p.id} className="todo-row"><Link className="todo-row-title" to={`/projekt/${p.prefix}`}><b>{p.prefix}</b> {p.name}</Link></div>)}
  </main>;
}
