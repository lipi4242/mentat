// Refine only renders a Logout item in ThemedLayoutV2's sider when an
// authProvider with `logout` is present — without one the signed-in shell has
// no way out at all except clearing cookies by hand.
//
// The real gate is App.tsx (better-auth's useSession decides Login vs shell),
// so `check` is a formality: if Refine is mounted, the session already exists.
// Signing out clears the session atom, App re-renders, and the user lands on
// Login — no route-level redirect needed.
import type { AuthProvider } from '@refinedev/core';
import { authClient } from './lib/authClient';

export const authProvider: AuthProvider = {
  login: async () => ({ success: false, error: new Error('A bejelentkezés a Login képernyőn történik.') }),
  logout: async () => {
    await authClient.signOut();
    return { success: true };
  },
  check: async () => ({ authenticated: true }),
  onError: async () => ({}),
};
