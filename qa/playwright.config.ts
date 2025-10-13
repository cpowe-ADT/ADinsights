import { defineConfig, devices } from '@playwright/test';

const isMock = (process.env.MOCK_MODE ?? 'true') === 'true';

// Allow overriding via QA_BASE_URL; otherwise use defaults.
const devUrl = process.env.QA_BASE_URL || 'http://127.0.0.1:5173';
const previewUrl = process.env.QA_BASE_URL || 'http://127.0.0.1:4173';

export default defineConfig({
  testDir: './tests',
  timeout: 30_000,
  expect: { timeout: 10_000 },
  fullyParallel: true,
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 1 : 0,
  reporter: [['list']],

  use: {
    baseURL: isMock ? devUrl : previewUrl,
    trace: 'on-first-retry'
  },

  projects: [
    {
      name: 'chromium-desktop',
      use: {
        ...devices['Desktop Chrome'],
        viewport: { width: 1280, height: 720 }
      }
    }
  ],

  // Start the right server before tests:
  webServer: isMock
    ? {
        command: 'npm run dev -- --host --port=5173',
        url: devUrl,
        reuseExistingServer: true,
        timeout: 120_000
      }
    : {
        command: 'npm run build && npm run preview -- --host --port=4173',
        url: previewUrl,
        reuseExistingServer: true,
        timeout: 120_000
      }
});
