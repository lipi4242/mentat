import { useRef, useState } from 'react';
import { App as AntApp, Button, Card, Form, Input, Typography } from 'antd';
import { authClient } from '../lib/authClient';
import { INSTANCE_TITLE } from '../instance';

const { Title, Text } = Typography;
const OTP_LENGTH = 6;

export function Login() {
  const { message } = AntApp.useApp();
  const [phase, setPhase] = useState<'email' | 'code'>('email');
  const [email, setEmail] = useState('');
  const [loading, setLoading] = useState(false);
  // antd's `loading` button only swallows its OWN onClick — pressing Enter in
  // the input still fires a native form submit. Without this ref-guard a
  // double Enter sends two OTPs, and better-auth invalidates the first, so
  // the code in the user's inbox no longer works. `loading` state is too late
  // to guard with: React batches it, both handlers see the old value.
  const inFlight = useRef(false);

  const sendOtp = async (values: { email: string }) => {
    if (inFlight.current) return;
    inFlight.current = true;
    setLoading(true);
    try {
      const { error } = await authClient.emailOtp.sendVerificationOtp({
        email: values.email,
        type: 'sign-in',
      });
      if (error) {
        message.error(error.message ?? 'A kód elküldése sikertelen.');
        return;
      }
      setEmail(values.email);
      setPhase('code');
      message.success('Ha a cím jogosult, elküldtük a kódot.');
    } catch (e) {
      message.error(e instanceof Error ? e.message : 'Ismeretlen hiba.');
    } finally {
      inFlight.current = false;
      setLoading(false);
    }
  };

  const verifyOtp = async (values: { otp: string }) => {
    if (inFlight.current) return;
    inFlight.current = true;
    setLoading(true);
    try {
      const { error } = await authClient.signIn.emailOtp({ email, otp: values.otp.trim() });
      if (error) {
        message.error(error.message ?? 'Érvénytelen vagy lejárt kód.');
        return;
      }
      // A 200 még nem session — cross-site süti csendben elveszhet.
      const { data: session } = await authClient.getSession();
      if (!session) {
        message.error(
          'A kód helyes volt, de a munkamenet nem jött létre — a böngésző nem tartotta meg a session-sütit. Ellenőrizd, hogy a megfelelő admin-domainen vagy-e.',
        );
        return;
      }
    } catch (e) {
      message.error(e instanceof Error ? e.message : 'Ismeretlen hiba.');
    } finally {
      inFlight.current = false;
      setLoading(false);
    }
  };

  return (
    <div style={{ minHeight: '100vh', display: 'grid', placeItems: 'center', padding: 24 }}>
      <Card style={{ width: 380, maxWidth: '100%' }}>
        <Title level={3} style={{ marginTop: 0 }}>
          {INSTANCE_TITLE}
        </Title>
        {phase === 'email' ? (
          <>
            <Text type="secondary">Add meg az e-mail-címed a bejelentkezéshez.</Text>
            <Form layout="vertical" onFinish={sendOtp} initialValues={{ email }} style={{ marginTop: 16 }}>
              <Form.Item
                label="E-mail"
                name="email"
                rules={[{ required: true, type: 'email', message: 'Érvényes e-mail szükséges.' }]}
              >
                <Input placeholder="name@example.com" autoFocus autoComplete="email" />
              </Form.Item>
              <Button type="primary" htmlType="submit" block loading={loading}>
                Kód küldése
              </Button>
            </Form>
          </>
        ) : (
          <>
            <Text type="secondary">
              Add meg a(z) <strong>{email}</strong> címre küldött {OTP_LENGTH} jegyű kódot.
            </Text>
            <Form layout="vertical" onFinish={verifyOtp} style={{ marginTop: 16 }}>
              <Form.Item
                label="Kód"
                name="otp"
                rules={[
                  { required: true, message: `${OTP_LENGTH} jegyű kód szükséges.` },
                  { pattern: new RegExp(`^\\d{${OTP_LENGTH}}$`), message: `${OTP_LENGTH} számjegy szükséges.` },
                ]}
              >
                <Input placeholder={'1'.repeat(OTP_LENGTH)} autoFocus inputMode="numeric" maxLength={OTP_LENGTH} />
              </Form.Item>
              <Button type="primary" htmlType="submit" block loading={loading}>
                Bejelentkezés
              </Button>
              <Button type="link" block disabled={loading} onClick={() => setPhase('email')} style={{ marginTop: 8 }}>
                Másik e-mail-cím
              </Button>
            </Form>
          </>
        )}
      </Card>
    </div>
  );
}
