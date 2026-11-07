import { Refine } from '@refinedev/core';
import { ThemedLayoutV2 } from '@refinedev/antd';
import routerBindings from '@refinedev/react-router-v6';
import { BrowserRouter, Navigate, Outlet, Route, Routes } from 'react-router-dom';
import { KeyOutlined } from '@ant-design/icons';

import { authProvider } from '../authProvider';
import { dataProvider } from '../dataProvider';
import { i18nProvider } from '../i18nProvider';
import { UI_PLUGINS, INSTANCE_TITLE } from '../instance';
import { TokensPage } from '../pages/tokens/TokensPage';

const coreResources = [{ name: 'tokens', list: '/tokenek', meta: { label: 'Gépi tokenek', icon: <KeyOutlined /> } }];

/** The landing screen: the first plugin's list, or the core's own page. */
const HOME = (UI_PLUGINS[0]?.resources[0]?.list as string | undefined) ?? '/tokenek';

/**
 * Menu grouping goes through Refine's `meta.parent`, never hand-inserted
 * `<div>`s between menu items — rc-menu cannot match keys across a raw
 * `<div>`, and then no menu item is ever highlighted. Plugin resources come
 * first, as-is (the menu leads with the domain); a plugin that wants a group
 * sets its own `meta.parent`.
 */
export function AdminApp() {
  const resources = [...UI_PLUGINS.flatMap((p) => p.resources), ...coreResources];
  return (
    <BrowserRouter>
      <Refine
        dataProvider={dataProvider}
        authProvider={authProvider}
        i18nProvider={i18nProvider}
        routerProvider={routerBindings}
        resources={resources}
        options={{ disableTelemetry: true, syncWithLocation: true }}
      >
        <Routes>
          <Route
            element={
              <ThemedLayoutV2 Title={() => <strong>{INSTANCE_TITLE}</strong>}>
                <Outlet />
              </ThemedLayoutV2>
            }
          >
            <Route index element={<Navigate to={HOME} replace />} />
            <Route path="tokenek" element={<TokensPage />} />
            {UI_PLUGINS.flatMap((p) => p.routes).map((r) => (
              <Route key={r.path} path={r.path} element={r.element} />
            ))}
            <Route path="*" element={<Navigate to={HOME} replace />} />
          </Route>
        </Routes>
      </Refine>
    </BrowserRouter>
  );
}
