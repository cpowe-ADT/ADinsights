import { defineConfig, devices } from "@playwright/test";
import path from "path";

const isMockRun = process.env.MOCK === "1";
const mockMode = isMockRun || (process.env.MOCK_MODE ?? "true").toLowerCase() !== "false";
const includeQuarantine = (process.env.QA_INCLUDE_QUARANTINE ?? "false").toLowerCase() === "true";
const DEV_SERVER_PORT = 5173;
const PREVIEW_PORT = Number(process.env.QA_PORT ?? 4173);
const computedPort = isMockRun ? DEV_SERVER_PORT : PREVIEW_PORT;
const computedBaseUrl = `http://127.0.0.1:${computedPort}`;
const baseURL = process.env.QA_BASE_URL ?? computedBaseUrl;
const shouldStartServer = !process.env.QA_BASE_URL;

export default defineConfig({
  testDir: path.resolve(__dirname, "tests"),
  snapshotPathTemplate: "__screenshots__/{testFilePath}/{arg}{ext}",
  fullyParallel: true,
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 2 : 0,
  timeout: 60000,
  expect: {
    timeout: 5000,
  },
  reporter: process.env.CI ? "github" : [["html", { open: "never" }]],
  grepInvert: includeQuarantine ? undefined : /@quarantine/,
  use: {
    baseURL,
    trace: "retain-on-failure",
    video: "retain-on-failure",
    screenshot: "only-on-failure",
  },
  projects: [
    {
      name: "chromium-desktop",
      use: { ...devices["Desktop Chrome"] },
    },
    {
      name: "chromium-mobile",
      use: { ...devices["Pixel 5"] },
    },
    {
      name: "firefox-desktop",
      use: { ...devices["Desktop Firefox"] },
    },
    {
      name: "firefox-mobile",
      use: {
        ...devices["Desktop Firefox"],
        viewport: { width: 414, height: 896 },
        isMobile: true,
        hasTouch: true,
        userAgent:
          "Mozilla/5.0 (Android 13; Mobile; rv:109.0) Gecko/20100101 Firefox/117.0",
      },
    },
  ],
  webServer: shouldStartServer
    ? (isMockRun
        ? {
            command: "npm run dev -- --host --port=5173",
            url: "http://localhost:5173",
            cwd: path.resolve(__dirname, "../frontend"),
            reuseExistingServer: true,
            timeout: 120000,
            env: {
              ...process.env,
              MOCK_MODE: mockMode ? "true" : "false",
              VITE_MOCK_MODE: mockMode ? "true" : "false",
            },
          }
        : {
            command: "npm run build && npm run preview -- --host --port=4173",
            url: "http://localhost:4173",
            cwd: path.resolve(__dirname, "../frontend"),
            reuseExistingServer: true,
            timeout: 120000,
            env: {
              ...process.env,
              MOCK_MODE: mockMode ? "true" : "false",
              VITE_MOCK_MODE: mockMode ? "true" : "false",
            },
          })
    : undefined,
});
