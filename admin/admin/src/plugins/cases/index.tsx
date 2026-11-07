// The cases plugin's screens. The worker half is worker/src/plugins/cases/;
// both are listed in their plugin registries (admin/src/instance.ts,
// config/plugins.ts). Copy this pair to build the next plugin.
import { FolderOpenOutlined } from '@ant-design/icons';
import type { AdminPluginUI } from '../../core/plugin';
import { CaseListPage } from './CaseListPage';
import { CaseShowPage } from './CaseShowPage';

export const casesUI: AdminPluginUI = {
  id: 'cases',
  title: 'Ügyek',
  icon: <FolderOpenOutlined />,
  resources: [{ name: 'cases', list: '/ugyek', show: '/ugyek/:id', meta: { label: 'Ügyek', icon: <FolderOpenOutlined /> } }],
  routes: [
    { path: 'ugyek', element: <CaseListPage /> },
    { path: 'ugyek/:id', element: <CaseShowPage /> },
  ],
};
