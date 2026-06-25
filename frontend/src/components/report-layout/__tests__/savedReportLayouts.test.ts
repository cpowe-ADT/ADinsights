import { beforeEach, describe, expect, it, vi } from 'vitest';

import { liveDashboardLayout } from '../sampleLayouts';
import type { DashboardLayoutConfig } from '../layoutSchema';

const api = vi.hoisted(() => ({
  get: vi.fn(),
  post: vi.fn(),
  patch: vi.fn(),
  del: vi.fn(),
}));

vi.mock('../../../lib/apiClient', () => ({
  get: api.get,
  post: api.post,
  patch: api.patch,
  del: api.del,
}));

// Imported after the mock is registered.
const {
  listSavedLayouts,
  createSavedLayout,
  updateSavedLayout,
  deleteSavedLayout,
  saveLayoutToApi,
} = await import('../savedReportLayouts');

const row = (over: Record<string, unknown> = {}) => ({
  id: 'row-1',
  name: 'Overview',
  description: '',
  config: liveDashboardLayout,
  is_shared: false,
  created_at: '2026-06-25T00:00:00Z',
  updated_at: '2026-06-25T00:00:00Z',
  ...over,
});

describe('savedReportLayouts API client', () => {
  beforeEach(() => {
    api.get.mockReset();
    api.post.mockReset();
    api.patch.mockReset();
    api.del.mockReset();
  });

  it('unwraps a paginated list response', async () => {
    api.get.mockResolvedValue({ results: [row()] });
    const rows = await listSavedLayouts();
    expect(api.get).toHaveBeenCalledWith('/analytics/report-layouts/', undefined);
    expect(rows).toHaveLength(1);
    expect(rows[0].id).toBe('row-1');
  });

  it('passes a bare array list response through', async () => {
    api.get.mockResolvedValue([row(), row({ id: 'row-2' })]);
    const rows = await listSavedLayouts();
    expect(rows.map((r) => r.id)).toEqual(['row-1', 'row-2']);
  });

  it('creates via POST to the collection', async () => {
    api.post.mockResolvedValue(row());
    await createSavedLayout({ name: 'Overview', config: liveDashboardLayout });
    expect(api.post).toHaveBeenCalledWith('/analytics/report-layouts/', {
      name: 'Overview',
      config: liveDashboardLayout,
    });
  });

  it('updates via PATCH to the detail path', async () => {
    api.patch.mockResolvedValue(row({ name: 'Renamed' }));
    await updateSavedLayout('row-1', { name: 'Renamed' });
    expect(api.patch).toHaveBeenCalledWith('/analytics/report-layouts/row-1/', {
      name: 'Renamed',
    });
  });

  it('deletes via DELETE to the detail path', async () => {
    api.del.mockResolvedValue(undefined);
    await deleteSavedLayout('row-1');
    expect(api.del).toHaveBeenCalledWith('/analytics/report-layouts/row-1/');
  });

  it('saveLayoutToApi creates when no id is given', async () => {
    api.post.mockResolvedValue(row());
    await saveLayoutToApi(liveDashboardLayout, { name: 'Overview' });
    expect(api.post).toHaveBeenCalledTimes(1);
    expect(api.patch).not.toHaveBeenCalled();
  });

  it('saveLayoutToApi patches when an id is given', async () => {
    api.patch.mockResolvedValue(row());
    await saveLayoutToApi(liveDashboardLayout, { id: 'row-1', name: 'Overview' });
    expect(api.patch).toHaveBeenCalledWith('/analytics/report-layouts/row-1/', {
      name: 'Overview',
      config: liveDashboardLayout,
      is_shared: undefined,
    });
    expect(api.post).not.toHaveBeenCalled();
  });

  it('saveLayoutToApi rejects an invalid config without calling the network', async () => {
    await expect(
      saveLayoutToApi({} as unknown as DashboardLayoutConfig, { name: 'Bad' }),
    ).rejects.toThrow(/invalid layout/i);
    expect(api.post).not.toHaveBeenCalled();
    expect(api.patch).not.toHaveBeenCalled();
  });
});
