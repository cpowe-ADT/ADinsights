import { test as base, expect } from '@playwright/test';
import { Buffer } from 'node:buffer';
import { getLiveApiState, type LiveApiState } from '../../utils/live';

const STORAGE_KEY = 'adinsights.auth';
const DATASET_STORAGE_KEY = 'dataset-mode';

function createAccessToken(): string {
  const futureExp = Math.floor(Date.now() / 1000) + 60 * 60;
  const header = Buffer.from(JSON.stringify({ alg: 'HS256', typ: 'JWT' }), 'utf-8').toString(
    'base64url',
  );
  const payload = Buffer.from(JSON.stringify({ exp: futureExp }), 'utf-8').toString('base64url');
  return `${header}.${payload}.signature`;
}

const mockModeEnv = String(process.env.MOCK_MODE ?? '').toLowerCase();
const envMock = process.env.MOCK === '1' || (mockModeEnv ? mockModeEnv === 'true' : true);

const defaultAuthState = {
  access: createAccessToken(),
  refresh: 'refresh-token',
  tenantId: 'tenant-qa',
  user: { email: 'qa@example.com' },
};

const defaultDatasetState = {
  state: { mode: 'dummy', demoTenantId: 'tenant-qa' },
  version: 0,
};

const mockAdapters = [
  { key: 'warehouse', name: 'Warehouse', description: '', interfaces: [] },
  {
    key: 'demo',
    name: 'Demo',
    description: '',
    interfaces: [],
    options: { demo_tenants: [{ id: 'tenant-qa', label: 'Tenant QA' }] },
  },
];

const TRANSPARENT_TILE = Buffer.from(
  'iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVQIW2P8/5+hHgAHggJ/lzh7LwAAAABJRU5ErkJggg==',
  'base64',
);

type Fixtures = {
  mockMode: boolean;
  liveApi: LiveApiState;
};

export const test = base.extend<Fixtures>({
  mockMode: [envMock, { option: true }],
  liveApi: [
    async ({}, use) => {
      await use(getLiveApiState());
    },
    { scope: 'worker' },
  ],
  page: async ({ page, mockMode }, use) => {
    await page.addInitScript(
      ({ storageKey, state }) => {
        window.localStorage.setItem(storageKey, JSON.stringify(state));
      },
      { storageKey: STORAGE_KEY, state: defaultAuthState },
    );
    await page.addInitScript(
      ({ storageKey, state }) => {
        window.localStorage.setItem(storageKey, JSON.stringify(state));
      },
      { storageKey: DATASET_STORAGE_KEY, state: defaultDatasetState },
    );

    await page.route('https://{a-c}.tile.openstreetmap.org/**', (route) => {
      void route.fulfill({ status: 200, body: TRANSPARENT_TILE, contentType: 'image/png' });
    });

    if (mockMode) {
      const access = createAccessToken();
      await page.route('**/api/auth/refresh/**', (route) => {
        void route.fulfill({
          status: 200,
          contentType: 'application/json',
          body: JSON.stringify({ access }),
        });
      });
      await page.route('**/api/auth/login/**', (route) => {
        void route.fulfill({
          status: 200,
          contentType: 'application/json',
          body: JSON.stringify({ ...defaultAuthState, access }),
        });
      });
      await page.route('**/api/health/**', (route) =>
        route.fulfill({ status: 200, contentType: 'application/json', body: '{"status":"ok"}' }),
      );
      await page.route('**/api/timezone/**', (route) =>
        route.fulfill({ status: 200, contentType: 'application/json', body: '{"timezone":"America/Jamaica"}' }),
      );
      await page.route('**/api/me/**', (route) =>
        route.fulfill({
          status: 200,
          contentType: 'application/json',
          body: JSON.stringify({ tenant_id: defaultAuthState.tenantId, email: defaultAuthState.user.email }),
        }),
      );
      await page.route('**/api/adapters/**', (route) =>
        route.fulfill({
          status: 200,
          contentType: 'application/json',
          body: JSON.stringify(mockAdapters),
        }),
      );
      // Catch-all stub to prevent proxy errors when backend is not running.
      await page.route('**/api/**', (route) =>
        route.fulfill({ status: 200, contentType: 'application/json', body: '{}' }),
      );
    }

    await use(page);

    await page.unroute('https://{a-c}.tile.openstreetmap.org/**');
    if (mockMode) {
      await page.unroute('**/api/auth/refresh/**');
      await page.unroute('**/api/auth/login/**');
      await page.unroute('**/api/health/**');
      await page.unroute('**/api/timezone/**');
      await page.unroute('**/api/me/**');
      await page.unroute('**/api/adapters/**');
      await page.unroute('**/api/**');
    }
  },
});

export { expect };
