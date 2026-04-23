import { render, screen } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import ChangesTabSection from '../tab-sections/ChangesTabSection';
import type { GoogleAdsChangeRow } from '../../../../lib/googleAdsAggregates';

const toastMock = vi.hoisted(() => ({
  addToast: vi.fn(),
  removeToast: vi.fn(),
  toasts: [] as Array<{ id: string; message: string; variant: string }>,
}));

vi.mock('../../../../stores/useToastStore', () => ({
  useToastStore: (selector: (state: typeof toastMock) => unknown) =>
    selector(toastMock),
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

describe('ChangesTabSection — integration', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('renders loading state', () => {
    render(<ChangesTabSection data={null} status="loading" error="" />);
    expect(screen.getByText('Loading change events...')).toBeInTheDocument();
  });

  it('renders empty state', () => {
    render(
      <ChangesTabSection
        data={{ count: 0, results: [] }}
        status="success"
        error=""
      />,
    );
    expect(screen.getByText('No change events')).toBeInTheDocument();
  });

  it('renders populated state', () => {
    const payload = { count: 2, results: [row(1), row(2)] };
    render(<ChangesTabSection data={payload} status="success" error="" />);
    expect(
      screen.getByTestId('google-ads-changes-section'),
    ).toBeInTheDocument();
    // Two change rows in the log table (plus header).
    const tables = document.querySelectorAll('table.dashboard-table');
    const logTable = tables[tables.length - 1] as HTMLTableElement;
    expect(logTable.querySelectorAll('tbody tr').length).toBe(2);
    expect(screen.getByText('user1@example.com')).toBeInTheDocument();
  });
});
