import { render, screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import ChangesTabSection from '../tab-sections/ChangesTabSection';
import type { GoogleAdsChangeRow } from '../../../../lib/googleAdsAggregates';

/**
 * GA-B1 — Load-more pagination in ChangesTabSection.
 *
 * Uses the same test harness as Phase A: hoisted vi mocks for the
 * googleAdsDashboard helpers + useToastStore. The component calls the
 * provided `loadMore` prop directly, so we stub the prop inline rather
 * than importing from the helper module — but we still mock the helper
 * module to avoid accidental real imports.
 */
const googleAdsDashboardMock = vi.hoisted(() => ({
  fetchGoogleAdsChangeEventsPage: vi.fn(),
}));

const toastMock = vi.hoisted(() => ({
  addToast: vi.fn(),
  removeToast: vi.fn(),
  toasts: [] as Array<{ id: string; message: string; variant: string }>,
}));

vi.mock('../../../../lib/googleAdsDashboard', () => ({
  fetchGoogleAdsChangeEventsPage: googleAdsDashboardMock.fetchGoogleAdsChangeEventsPage,
}));

vi.mock('../../../../stores/useToastStore', () => ({
  useToastStore: (selector: (state: typeof toastMock) => unknown) => selector(toastMock),
}));

const row = (i: number): GoogleAdsChangeRow => ({
  customer_id: '1234567890',
  change_date_time: `2026-04-${String(10 + i).padStart(2, '0')}T09:00:00-05:00`,
  user_email: `user${i}@example.com`,
  change_resource_type: 'CAMPAIGN',
  resource_change_operation: 'UPDATE',
  campaign_id: `100${i}`,
  changed_fields: ['status'],
});

function countTableRows(): number {
  // The change log is rendered as <table class="dashboard-table"> inside the
  // section — DistributionBar also renders a table-shaped DOM, so we target
  // by class rather than role.
  const tables = document.querySelectorAll('table.dashboard-table');
  const logTable = tables[tables.length - 1] as HTMLTableElement;
  return within(logTable).getAllByRole('row').length - 1; // minus header
}

describe('ChangesTabSection — GA-B1 load-more pagination', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('renders Load more button when next_cursor is present', () => {
    const payload = {
      count: 4,
      results: [row(1), row(2)],
      next_cursor: '2',
    };
    render(<ChangesTabSection data={payload} status="success" error="" loadMore={vi.fn()} />);
    expect(screen.getByTestId('google-ads-changes-load-more')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Load more' })).toBeInTheDocument();
  });

  it('appends results from second page after Load more click', async () => {
    const payload = {
      count: 4,
      results: [row(1), row(2)],
      next_cursor: '2',
    };
    const loadMore = vi.fn().mockResolvedValue({
      count: 4,
      results: [row(3), row(4)],
      next_cursor: null,
    });
    const user = userEvent.setup();
    render(<ChangesTabSection data={payload} status="success" error="" loadMore={loadMore} />);

    expect(countTableRows()).toBe(2);

    await user.click(screen.getByRole('button', { name: 'Load more' }));

    await waitFor(() => {
      expect(loadMore).toHaveBeenCalledWith('2');
    });
    await waitFor(() => {
      expect(countTableRows()).toBe(4);
    });
    expect(screen.queryByRole('button', { name: 'Load more' })).toBeNull();
  });

  it('hides Load more button when next_cursor becomes null', async () => {
    const payload = {
      count: 4,
      results: [row(1), row(2)],
      next_cursor: '2',
    };
    const loadMore = vi.fn().mockResolvedValue({
      count: 4,
      results: [row(3), row(4)],
      next_cursor: null,
    });
    const user = userEvent.setup();
    render(<ChangesTabSection data={payload} status="success" error="" loadMore={loadMore} />);

    expect(screen.getByRole('button', { name: 'Load more' })).toBeInTheDocument();
    await user.click(screen.getByRole('button', { name: 'Load more' }));

    await waitFor(() => {
      expect(screen.queryByTestId('google-ads-changes-load-more')).not.toBeInTheDocument();
    });
    expect(screen.queryByRole('button', { name: 'Load more' })).toBeNull();
  });
});
