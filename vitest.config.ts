/// <reference types="vitest" />
import { defineConfig } from 'vitest/config';

export default defineConfig({
  test: {
    environment: 'jsdom',
    setupFiles: ['src/test/setup.ts'],
    globals: true,
    css: true,
    include: ['frontend/src/**/*.{test,spec}.{js,ts,jsx,tsx}'],
    exclude: ['qa/**/*', 'integrations/**/*', 'node_modules/**/*']
  }
});
