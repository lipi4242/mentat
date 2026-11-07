import { defineConfig } from 'vitest/config';

export default defineConfig({
  test: {
    environment: 'jsdom',
    setupFiles: ['./src/test-setup.ts'],
    include: ['src/**/*.test.{ts,tsx}'],
    // The first test in a file that imports AdminApp pays for transforming the
    // whole Refine/antd shell: ~8–11 s on a 2-core box, ~2.7 s once cached. The
    // 5 s default timed out on that cold import, not on the behaviour under test.
    testTimeout: 30_000,
  },
});
