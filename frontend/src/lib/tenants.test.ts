import { describe, expect, it, vi, beforeEach } from 'vitest';

const fetchTenantsMock = vi.fn();

vi.mock('./dataService', () => ({
  fetchTenants: (...args: unknown[]) => fetchTenantsMock(...args),
}));

import { loadTenants } from './tenants';

describe('loadTenants', () => {
  beforeEach(() => {
    fetchTenantsMock.mockReset();
  });

  it('accepts paginated tenant payloads', async () => {
    fetchTenantsMock.mockResolvedValue({
      count: 2,
      next: null,
      previous: null,
      results: [
        { id: 'tenant-b', name: 'Beta Tenant' },
        { id: 'tenant-a', name: 'Alpha Tenant' },
      ],
    });

    await expect(loadTenants()).resolves.toEqual([
      { id: 'tenant-a', name: 'Alpha Tenant', slug: undefined, status: undefined },
      { id: 'tenant-b', name: 'Beta Tenant', slug: undefined, status: undefined },
    ]);
  });
});
