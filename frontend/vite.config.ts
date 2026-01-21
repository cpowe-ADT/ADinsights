import { fileURLToPath } from 'node:url';

import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

const childProcessShim = fileURLToPath(new URL('./src/shims/child_process.ts', import.meta.url));
const emptyShim = fileURLToPath(new URL('./src/shims/empty.ts', import.meta.url));
const proxyTarget = process.env.VITE_DEV_PROXY_TARGET?.trim() || 'http://localhost:8000';

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
    proxy: {
      '/api': {
        target: proxyTarget,
        changeOrigin: true,
      },
    },
  },
  build: {
    rollupOptions: {
      output: {
        manualChunks(id) {
          if (!id.includes('node_modules')) {
            return undefined;
          }
          if (id.includes('react-router')) {
            return 'react-router';
          }
          if (id.includes('react-dom') || id.includes('react')) {
            return 'react-vendor';
          }
          if (id.includes('leaflet')) {
            return 'leaflet';
          }
          if (id.includes('recharts')) {
            return 'recharts';
          }
          if (id.includes('@tanstack')) {
            return 'tanstack';
          }
          return 'vendor';
        },
      },
    },
  },
  test: {
    globals: true,
    environment: 'jsdom',
    setupFiles: './src/setupTests.ts',
    reporters: ['default', ['json', { outputFile: 'test-results/vitest-report.json' }]],
    coverage: {
      provider: 'v8',
      reportsDirectory: 'coverage',
      reporter: ['text', 'text-summary', 'lcov', 'json-summary'],
      reportOnFailure: true,
    },
  },
});
