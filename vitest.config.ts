/// <reference types="vitest" />
import { defineConfig } from 'vitest/config';

export default defineConfig({
  test: {
    environment: 'jsdom',
    setupFiles: ['src/test/setup.ts'],
    globals: true,
    css: true,
    deps: {
      inline: ['recharts'],
    },
    include: ['frontend/src/{lib,pages,routes,state}/**/*.{test,spec}.{js,ts,jsx,tsx}'],
    exclude: ['qa/**/*', 'integrations/**/*', 'node_modules/**/*'],
    environmentOptions: {
      jsdom: { url: 'http://localhost' },
    },
  },
});
