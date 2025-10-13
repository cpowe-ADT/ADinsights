import { test as base, expect } from "@playwright/test";
import { Buffer } from "node:buffer";
import { getLiveApiState, type LiveApiState } from "../../utils/live";

const STORAGE_KEY = "adinsights.auth";

function createAccessToken(): string {
  const futureExp = Math.floor(Date.now() / 1000) + 60 * 60;
  const header = Buffer.from(JSON.stringify({ alg: "HS256", typ: "JWT" }), "utf-8").toString("base64url");
  const payload = Buffer.from(JSON.stringify({ exp: futureExp }), "utf-8").toString("base64url");
  return `${header}.${payload}.signature`;
}

const envMock =
  process.env.MOCK === "1" ||
  String(process.env.MOCK_MODE || "").toLowerCase() === "true";

const defaultAuthState = {
  access: createAccessToken(),
  refresh: "refresh-token",
  tenantId: "tenant-qa",
  user: { email: "qa@example.com" },
};

const TRANSPARENT_TILE = Buffer.from(
  "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVQIW2P8/5+hHgAHggJ/lzh7LwAAAABJRU5ErkJggg==",
  "base64"
);

type Fixtures = {
  mockMode: boolean;
  liveApi: LiveApiState;
};

export const test = base.extend<Fixtures>({
  mockMode: [envMock, { option: true }],
  liveApi: [async ({}, use) => {
    await use(getLiveApiState());
  }, { scope: "worker" }],
  page: async ({ page, mockMode }, use) => {
    await page.addInitScript(({ storageKey, state }) => {
      window.localStorage.setItem(storageKey, JSON.stringify(state));
    }, { storageKey: STORAGE_KEY, state: defaultAuthState });

    await page.route("https://{a-c}.tile.openstreetmap.org/**", (route) => {
      void route.fulfill({ status: 200, body: TRANSPARENT_TILE, contentType: "image/png" });
    });

    if (mockMode) {
      const access = createAccessToken();
      await page.route("**/api/auth/refresh/**", (route) => {
        void route.fulfill({
          status: 200,
          contentType: "application/json",
          body: JSON.stringify({ access }),
        });
      });
      await page.route("**/api/auth/login/**", (route) => {
        void route.fulfill({
          status: 200,
          contentType: "application/json",
          body: JSON.stringify({ ...defaultAuthState, access }),
        });
      });
    }

    await use(page);

    await page.unroute("https://{a-c}.tile.openstreetmap.org/**");
    if (mockMode) {
      await page.unroute("**/api/auth/refresh/**");
      await page.unroute("**/api/auth/login/**");
    }
  },
});

export { expect };
