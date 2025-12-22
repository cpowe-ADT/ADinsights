import { defineConfig, devices } from '@playwright/test';

const mockModeEnv = String(process.env.MOCK_MODE ?? '').toLowerCase();
const isMock = process.env.MOCK === '1' || (mockModeEnv ? mockModeEnv === 'true' : true);

// Let CI override, otherwise default to the standard ports
const devUrl = process.env.QA_BASE_URL || 'http://localhost:5173';
const previewUrl = process.env.QA_BASE_URL || 'http://localhost:4173';
const resolvePort = (url: string, fallback: number): number => {
  try {
    const parsed = new URL(url);
    if (parsed.port) {
      const port = Number(parsed.port);
      return Number.isFinite(port) ? port : fallback;
    }
  } catch {
    // ignore invalid URL
  }
  return fallback;
};
const devPort = resolvePort(devUrl, 5173);
const previewPort = resolvePort(previewUrl, 4173);

export default defineConfig({
  testDir: 'tests',
  timeout: 30_000,
  expect: { timeout: 10_000 },
  fullyParallel: true,
  retries: process.env.CI ? 1 : 0,
  reporter: [['list']],
  use: { baseURL: isMock ? devUrl : previewUrl, trace: 'on-first-retry' },
  projects: [
    {
      name: 'chromium-desktop',
      use: {
        ...devices['Desktop Chrome'],
        viewport: { width: 1280, height: 720 },
      },
    },
  ],
  webServer: isMock
    ? {
        command: `npm run dev -- --host --port=${devPort}`,
        url: devUrl,
        reuseExistingServer: true,
        timeout: 120_000,
        env: {
          VITE_MOCK_MODE: 'true',
          VITE_MOCK_ASSETS: 'true',
        },
      }
    : {
        command: `npm run build && npm run preview -- --host --port=${previewPort}`,
        url: previewUrl,
        reuseExistingServer: true,
        timeout: 120_000,
      },
});
