import { beforeEach, describe, expect, it, vi } from 'vitest';

const apiGetMock = vi.fn();
const validateMock = vi.fn();

vi.mock('./apiClient', () => ({
  default: {
    get: (...args: unknown[]) => apiGetMock(...args),
  },
}));

vi.mock('./validate', () => ({
  validate: (...args: unknown[]) => validateMock(...args),
}));

import { fetchTenants } from './dataService';

describe('fetchTenants', () => {
  beforeEach(() => {
    apiGetMock.mockReset();
    validateMock.mockReset();
    validateMock.mockReturnValue(true);
  });

  it('normalizes paginated tenant responses before validation', async () => {
    apiGetMock.mockResolvedValueOnce({
      count: 2,
      next: null,
      previous: null,
      results: [
        { id: 'tenant-a', name: 'Alpha Tenant' },
        { id: 'tenant-b', name: 'Beta Tenant' },
      ],
    });

    const records = await fetchTenants({
      path: '/tenants/',
      mockPath: '/mock/tenants.json',
    });

    expect(records).toEqual([
      { id: 'tenant-a', name: 'Alpha Tenant' },
      { id: 'tenant-b', name: 'Beta Tenant' },
    ]);
    expect(validateMock).toHaveBeenCalledWith('tenants', records);
  });
});
