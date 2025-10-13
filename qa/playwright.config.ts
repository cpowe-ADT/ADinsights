import { defineConfig, devices } from "@playwright/test";
import path from "path";

const mockMode = (process.env.MOCK_MODE ?? "true").toLowerCase() !== "false";
const port = Number(process.env.QA_PORT ?? 4173);
const computedBaseUrl = `http://127.0.0.1:${port}`;
const baseURL = process.env.QA_BASE_URL ?? computedBaseUrl;

export default defineConfig({
  testDir: path.resolve(__dirname, "tests"),
  fullyParallel: true,
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 2 : 0,
  timeout: 60000,
  expect: {
    timeout: 5000,
  },
  reporter: process.env.CI ? "github" : [["html", { open: "never" }]],
  use: {
    baseURL,
    trace: "retain-on-failure",
    video: "retain-on-failure",
    screenshot: "only-on-failure",
  },
  projects: [
    {
      name: "chromium",
      use: { ...devices["Desktop Chrome"] },
    },
  ],
  webServer: {
    command: `npm run dev -- --host 127.0.0.1 --port ${port}`,
    url: baseURL,
    cwd: path.resolve(__dirname, "../frontend"),
    timeout: 120000,
    reuseExistingServer: !process.env.CI,
    env: {
      ...process.env,
      MOCK_MODE: mockMode ? "true" : "false",
      VITE_MOCK_MODE: mockMode ? "true" : "false",
    },
  },
});
