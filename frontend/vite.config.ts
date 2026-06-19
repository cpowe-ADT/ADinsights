import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';

import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

const childProcessShim = fileURLToPath(new URL('./src/shims/child_process.ts', import.meta.url));
const emptyShim = fileURLToPath(new URL('./src/shims/empty.ts', import.meta.url));
const proxyTarget = process.env.VITE_DEV_PROXY_TARGET?.trim() || 'http://localhost:8000';
const devHttpsEnabled = ['1', 'true', 'yes'].includes(
  (process.env.VITE_DEV_HTTPS ?? '').trim().toLowerCase(),
);
const devHttpsKey = process.env.VITE_DEV_HTTPS_KEY?.trim();
const devHttpsCert = process.env.VITE_DEV_HTTPS_CERT?.trim();
const devHttps =
  devHttpsEnabled && devHttpsKey && devHttpsCert
    ? {
        key: readFileSync(devHttpsKey),
        cert: readFileSync(devHttpsCert),
      }
    : undefined;

export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: {
      child_process: childProcessShim,
      fs: emptyShim,
      module: emptyShim,
    },
  },
  define: {
    'process.env': {},
    global: 'globalThis',
  },
  server: {
    port: 5173,
    host: '0.0.0.0',
    ...(devHttps ? { https: devHttps } : {}),
    proxy: {
      '/api': {
        target: proxyTarget,
        changeOrigin: true,
      },
    },
  },
  test: {
    globals: true,
    environment: 'jsdom',
    setupFiles: './src/setupTests.ts',
    reporters: ['default', ['json', { outputFile: 'test-results/vitest-report.json' }]],
    // `forks` pool is more reliable than the default `threads` when the full
    // suite runs alongside other dev processes (Vite dev server, Storybook,
    // parallel builds). Threads pool was intermittently timing out a handful
    // of heavy test files (App.integration, useDashboardStore, MetaPagePosts,
    // DashboardLibrary/Create, GoogleAdsWorkspacePage) under load; the same
    // tests pass deterministically on `forks`. Revisit if vitest improves
    // threads-pool stability.
    pool: 'forks',
    coverage: {
      provider: 'v8',
      reportsDirectory: 'coverage',
      reporter: ['text', 'text-summary', 'lcov', 'json-summary'],
      reportOnFailure: true,
    },
  },
});
