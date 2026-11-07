// The instance's own data models (worker: plugins/custom/). One menu entry;
// the entities come from GET /api/meta at runtime, so a model the agent
// declares in config/models.json shows up here without screen code.
import { DatabaseOutlined } from '@ant-design/icons';
import type { AdminPluginUI } from '../../core/plugin';
import { DataPage } from './DataPage';

export const customUI: AdminPluginUI = {
  id: 'custom',
  title: 'Saját adatok',
  icon: <DatabaseOutlined />,
  resources: [{ name: 'custom', list: '/adatok', show: '/adatok/:id', meta: { label: 'Saját adatok', icon: <DatabaseOutlined /> } }],
  routes: [
    { path: 'adatok', element: <DataPage /> },
    // :id is the entity's name (ugyfelek), not a row id.
    { path: 'adatok/:id', element: <DataPage /> },
  ],
};
