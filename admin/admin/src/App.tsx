import { useRef } from 'react';
import '@refinedev/antd/dist/reset.css';
import { App as AntApp, ConfigProvider, Spin } from 'antd';
import huHU from 'antd/locale/hu_HU';

import { authClient } from './lib/authClient';
import { Login } from './pages/Login';
import { AdminApp } from './core/AdminApp';

function Shell({ children }: { children: React.ReactNode }) {
  return (
    <ConfigProvider locale={huHU}>
      <AntApp>{children}</AntApp>
    </ConfigProvider>
  );
}

/**
 * Auth gate. The `bootstrapped` ref waits for the FIRST session load only —
 * a later background refetch (e.g. window focus) must not tear down the
 * Login tree mid-OTP-entry. Losing this makes login intermittently fail in
 * a way that is miserable to diagnose.
 */
export default function App() {
  const { data: session, isPending } = authClient.useSession();
  const bootstrapped = useRef(false);
  if (!isPending) bootstrapped.current = true;

  if (isPending && !bootstrapped.current) {
    return (
      <Shell>
        <div style={{ minHeight: '100vh', display: 'grid', placeItems: 'center' }}>
          <Spin size="large" />
        </div>
      </Shell>
    );
  }

  return <Shell>{session ? <AdminApp /> : <Login />}</Shell>;
}
