import './todo.css';
import { CheckSquareOutlined, TagsOutlined, TeamOutlined } from '@ant-design/icons';
import { ConfigProvider } from 'antd';
import type { ReactNode } from 'react';
import type { AdminPluginUI } from '../../core/plugin';
import { TasksPage } from './TasksPage';
import { TaskPage } from './TaskPage';
import { LabelsPage } from './LabelsPage';
import { PrincipalsPage } from './PrincipalsPage';
export const neutral = (page: ReactNode) => <ConfigProvider theme={{ token: { colorPrimary: '#59656b', colorLink: '#46545c',
  colorText: '#2b3338', colorTextSecondary: '#66727a', colorSuccess: '#4f8a83', colorBgLayout: '#f7f8f8',
  colorError: '#59656b', colorWarning: '#59656b', colorInfo: '#59656b',
  fontSize: 15, borderRadius: 6, controlInteractiveSize: 20 } }}><div className="todo-surface">{page}</div></ConfigProvider>;
export const todoUI: AdminPluginUI = {
  id: 'todo', title: 'Feladatok', icon: <CheckSquareOutlined />,
  resources: [
    { name: 'todo/tasks', list: '/feladatok', show: '/feladatok/:id', meta: { label: 'Feladatok', icon: <CheckSquareOutlined /> } },
    { name: 'todo/labels', list: '/feladat-cimkek', meta: { label: 'Címkék', icon: <TagsOutlined /> } },
    { name: 'todo/principals', list: '/resztvevok', meta: { label: 'Résztvevők', icon: <TeamOutlined /> } },
  ],
  routes: [
    { path: 'feladatok', element: neutral(<TasksPage />) },
    { path: 'feladatok/:id', element: neutral(<TaskPage />) },
    { path: 'feladat-cimkek', element: neutral(<LabelsPage />) },
    { path: 'resztvevok', element: neutral(<PrincipalsPage />) },
  ],
};
