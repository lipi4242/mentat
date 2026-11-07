import { createAuthClient } from 'better-auth/react';
import { emailOTPClient } from 'better-auth/client/plugins';
import { API_BASE } from '../config';

export const authClient = createAuthClient({
  baseURL: (API_BASE || window.location.origin).replace(/\/+$/, ''),
  plugins: [emailOTPClient()],
  fetchOptions: { credentials: 'include' },
});
