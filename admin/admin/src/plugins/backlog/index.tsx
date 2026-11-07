import './backlog.css';
import { InboxOutlined, ProjectOutlined } from '@ant-design/icons';
import type { AdminPluginUI } from '../../core/plugin';
import { neutral } from '../todo';
import { BallPage } from './BallPage';
import { ItemPage } from './ItemPage';
import { ProjectPage } from './ProjectPage';
import { ProjectsPage } from './ProjectsPage';
export const backlogUI: AdminPluginUI = {
  id: 'backlog', title: 'Backlog', icon: <ProjectOutlined />,
  resources: [
    { name: 'backlog/ball', list: '/labda', meta: { label: 'Kinél a labda', icon: <InboxOutlined /> } },
    { name: 'backlog/projects', list: '/projektek', meta: { label: 'Projektek', icon: <ProjectOutlined /> } },
  ],
  routes: [
    { path: 'labda', element: neutral(<BallPage />) },
    { path: 'projektek', element: neutral(<ProjectsPage />) },
    { path: 'projekt/:id', element: neutral(<ProjectPage />) },
    { path: 'tetel/:id', element: neutral(<ItemPage />) },
  ],
};
