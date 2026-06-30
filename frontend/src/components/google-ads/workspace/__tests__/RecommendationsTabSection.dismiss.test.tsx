import { act, render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import RecommendationsTabSection from '../tab-sections/RecommendationsTabSection';
import type { GoogleAdsRecommendationRow } from '../../../../lib/googleAdsAggregates';

const googleAdsDashboardMock = vi.hoisted(() => ({
  dismissGoogleAdsRecommendation: vi.fn(),
}));

const toastMock = vi.hoisted(() => ({
  addToast: vi.fn(),
  removeToast: vi.fn(),
  toasts: [] as Array<{ id: string; message: string; variant: string }>,
}));

vi.mock('../../../../lib/googleAdsDashboard', () => ({
  dismissGoogleAdsRecommendation: googleAdsDashboardMock.dismissGoogleAdsRecommendation,
}));

vi.mock('../../../../stores/useToastStore', () => ({
  useToastStore: (selector: (state: typeof toastMock) => unknown) => selector(toastMock),
}));

const activeRow: GoogleAdsRecommendationRow = {
  id: 42,
  recommendation_type: 'KEYWORD',
  resource_name: 'customers/1234567890/recommendations/abc',
  campaign_id: '987',
  dismissed: false,
  dismissed_at: null,
  dismissed_by_user_id: null,
  last_seen_at: '2026-04-23T09:00:00-05:00',
};

const dismissedRow: GoogleAdsRecommendationRow = {
  id: 43,
  recommendation_type: 'BUDGET',
  resource_name: 'customers/1234567890/recommendations/xyz',
  campaign_id: '988',
  dismissed: true,
  dismissed_at: '2026-04-22T09:00:00-05:00',
  dismissed_by_user_id: '7',
  last_seen_at: '2026-04-23T09:00:00-05:00',
};

const basePayload = {
  count: 2,
  results: [activeRow, dismissedRow],
};

describe('RecommendationsTabSection — GA-A2 dismiss', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('non-dismissed row shows Dismiss button; dismissed row shows chip (no button)', () => {
    render(<RecommendationsTabSection data={basePayload} status="success" error="" />);
    const buttons = screen.getAllByRole('button', { name: 'Dismiss' });
    expect(buttons).toHaveLength(1);
    expect(buttons[0].getAttribute('data-recommendation-id')).toBe('42');
    // Dismissed row renders a chip with data-status="dismissed". The
    // KpiTile labelled "Dismissed" also has the text — anchor on the chip
    // by data attribute to avoid that ambiguity.
    const chips = document.querySelectorAll('[data-status="dismissed"]');
    expect(chips.length).toBe(1);
    expect((chips[0] as HTMLElement).tagName.toLowerCase()).toBe('span');
  });

  it('clicking Dismiss calls helper with the row id', async () => {
    googleAdsDashboardMock.dismissGoogleAdsRecommendation.mockResolvedValue({
      id: 42,
      dismissed: true,
    });
    const user = userEvent.setup();
    render(<RecommendationsTabSection data={basePayload} status="success" error="" />);
    await user.click(screen.getByRole('button', { name: 'Dismiss' }));
    await waitFor(() => {
      expect(googleAdsDashboardMock.dismissGoogleAdsRecommendation).toHaveBeenCalledWith(42);
    });
  });

  it('applies optimistic update before the API resolves', async () => {
    let resolveFn: ((value: unknown) => void) | undefined;
    googleAdsDashboardMock.dismissGoogleAdsRecommendation.mockImplementation(
      () =>
        new Promise((resolve) => {
          resolveFn = resolve;
        }),
    );
    const user = userEvent.setup();
    render(<RecommendationsTabSection data={basePayload} status="success" error="" />);
    await user.click(screen.getByRole('button', { name: 'Dismiss' }));
    // Row 42's Status cell should now show a "Dismissed" chip while the
    // network call is still pending. Anchor on the unique data attribute.
    await waitFor(() => {
      const chips = document.querySelectorAll('[data-status="dismissed"]');
      // Both rows (42 pending + 43 already dismissed) render the chip.
      expect(chips.length).toBe(2);
    });
    expect(screen.queryByRole('button', { name: 'Dismiss' })).toBeNull();
    // Resolve so the test doesn't leak an unresolved promise.
    await act(async () => {
      resolveFn?.({ id: 42, dismissed: true });
    });
  });

  it('rolls back local state and shows error toast on failure', async () => {
    googleAdsDashboardMock.dismissGoogleAdsRecommendation.mockRejectedValue(new Error('boom'));
    const user = userEvent.setup();
    render(<RecommendationsTabSection data={basePayload} status="success" error="" />);
    await user.click(screen.getByRole('button', { name: 'Dismiss' }));
    await waitFor(() => {
      // Button should be re-enabled and visible again (rollback).
      expect(screen.getByRole('button', { name: 'Dismiss' })).toBeInTheDocument();
    });
    expect(toastMock.addToast).toHaveBeenCalledWith('boom', 'error');
  });

  it('success path emits a confirmation toast', async () => {
    googleAdsDashboardMock.dismissGoogleAdsRecommendation.mockResolvedValue({
      id: 42,
      dismissed: true,
    });
    const user = userEvent.setup();
    render(<RecommendationsTabSection data={basePayload} status="success" error="" />);
    await user.click(screen.getByRole('button', { name: 'Dismiss' }));
    await waitFor(() => {
      expect(toastMock.addToast).toHaveBeenCalledWith('Recommendation dismissed');
    });
  });

  it('renders the Dismiss button inside a table cell with the right id', () => {
    render(<RecommendationsTabSection data={basePayload} status="success" error="" />);
    // Locate the dismiss button by its data attribute, then verify its
    // ancestor is a Status table cell (`td.dashboard-table__cell`).
    const button = screen.getByRole('button', { name: 'Dismiss' });
    expect(button.getAttribute('data-recommendation-id')).toBe('42');
    const td = button.closest('td');
    expect(td).not.toBeNull();
    expect(td!.classList.contains('dashboard-table__cell')).toBe(true);
  });
});
