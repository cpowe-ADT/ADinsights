import { beforeEach, describe, expect, it, vi } from 'vitest';

const getMock = vi.fn();

vi.mock('./apiClient', () => ({
  appendQueryParams: (path: string) => path,
  get: (...args: unknown[]) => getMock(...args),
  patch: vi.fn(),
  post: vi.fn(),
}));

import { fetchGoogleAdsSavedViews } from './googleAdsDashboard';

describe('fetchGoogleAdsSavedViews', () => {
  beforeEach(() => {
    getMock.mockReset();
  });

  it('normalizes paginated saved view responses', async () => {
    getMock.mockResolvedValueOnce({
      count: 2,
      results: [
        {
          id: 'view-1',
          name: 'Exec',
          description: 'Executive view',
          filters: {},
          columns: [],
          is_shared: true,
          created_at: '2026-04-01T00:00:00Z',
          updated_at: '2026-04-01T00:00:00Z',
        },
        {
          id: 'view-2',
          name: 'Pacing',
          description: 'Pacing view',
          filters: {},
          columns: [],
          is_shared: false,
          created_at: '2026-04-02T00:00:00Z',
          updated_at: '2026-04-02T00:00:00Z',
        },
      ],
    });

    await expect(fetchGoogleAdsSavedViews()).resolves.toEqual([
      expect.objectContaining({ id: 'view-1', name: 'Exec' }),
      expect.objectContaining({ id: 'view-2', name: 'Pacing' }),
    ]);
  });
});
