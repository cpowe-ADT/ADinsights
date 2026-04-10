import { act, render, screen, waitFor } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import usePageInsightsSavedViews from './usePageInsightsSavedViews';

const mocks = vi.hoisted(() => ({
  listPageInsightsSavedViews: vi.fn(),
  savePageInsightsView: vi.fn(),
  deletePageInsightsView: vi.fn(),
}));

vi.mock('../lib/metaPageInsights', () => ({
  listPageInsightsSavedViews: mocks.listPageInsightsSavedViews,
  savePageInsightsView: mocks.savePageInsightsView,
  deletePageInsightsView: mocks.deletePageInsightsView,
}));

const sampleView = {
  id: 'view-1',
  name: 'My View',
  description: '',
  template_key: 'meta_page_insights' as const,
  filters: { page_id: 'page-1', date_preset: 'last_28d', metric: 'page_post_engagements', period: 'day' },
  layout: {},
  default_metric: 'page_post_engagements',
  is_active: true,
  owner_email: null,
  created_at: '2026-04-10T00:00:00Z',
  updated_at: '2026-04-10T00:00:00Z',
};

type HarnessProps = { pageId?: string };

const Harness = ({ pageId = 'page-1' }: HarnessProps) => {
  const { views, status, save, remove } = usePageInsightsSavedViews(pageId);
  return (
    <div>
      <span data-testid="status">{status}</span>
      <span data-testid="count">{views.length}</span>
      {views.map((v) => (
        <span key={v.id} data-testid={`view-${v.id}`}>
          {v.name}
        </span>
      ))}
      <button
        type="button"
        data-testid="save"
        onClick={() => void save('New View', { page_id: pageId, date_preset: 'last_7d' })}
      >
        Save
      </button>
      <button
        type="button"
        data-testid="remove"
        onClick={() => void remove('view-1')}
      >
        Remove
      </button>
    </div>
  );
};

describe('usePageInsightsSavedViews', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('loads saved views on mount', async () => {
    mocks.listPageInsightsSavedViews.mockResolvedValue([sampleView]);
    render(<Harness />);

    await waitFor(() => {
      expect(screen.getByTestId('status').textContent).toBe('loaded');
    });
    expect(screen.getByTestId('count').textContent).toBe('1');
    expect(screen.getByTestId('view-view-1').textContent).toBe('My View');
  });

  it('saves a new view and appends it', async () => {
    mocks.listPageInsightsSavedViews.mockResolvedValue([]);
    const newView = { ...sampleView, id: 'view-2', name: 'New View' };
    mocks.savePageInsightsView.mockResolvedValue(newView);

    render(<Harness />);

    await waitFor(() => {
      expect(screen.getByTestId('status').textContent).toBe('loaded');
    });

    await act(async () => {
      screen.getByTestId('save').click();
    });

    expect(mocks.savePageInsightsView).toHaveBeenCalledWith('New View', {
      page_id: 'page-1',
      date_preset: 'last_7d',
    });
    expect(screen.getByTestId('count').textContent).toBe('1');
  });

  it('removes a view', async () => {
    mocks.listPageInsightsSavedViews.mockResolvedValue([sampleView]);
    mocks.deletePageInsightsView.mockResolvedValue(undefined);

    render(<Harness />);

    await waitFor(() => {
      expect(screen.getByTestId('count').textContent).toBe('1');
    });

    await act(async () => {
      screen.getByTestId('remove').click();
    });

    expect(mocks.deletePageInsightsView).toHaveBeenCalledWith('view-1');
    expect(screen.getByTestId('count').textContent).toBe('0');
  });

  it('handles load error', async () => {
    mocks.listPageInsightsSavedViews.mockRejectedValue(new Error('Network error'));
    render(<Harness />);

    await waitFor(() => {
      expect(screen.getByTestId('status').textContent).toBe('error');
    });
    expect(screen.getByTestId('count').textContent).toBe('0');
  });
});
