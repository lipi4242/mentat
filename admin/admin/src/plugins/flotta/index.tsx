// A flotta-ellenőrzés képernyője. A worker fele: worker/src/plugins/flotta/.
import { ClusterOutlined } from '@ant-design/icons';
import type { AdminPluginUI } from '../../core/plugin';
import { neutral } from '../todo';
import { FlottaPage } from './FlottaPage';

export const flottaUI: AdminPluginUI = {
  id: 'flotta', title: 'Flotta', icon: <ClusterOutlined />,
  resources: [{ name: 'flotta/status', list: '/flotta', meta: { label: 'Flotta', icon: <ClusterOutlined /> } }],
  routes: [{ path: 'flotta', element: neutral(<FlottaPage />) }],
};
