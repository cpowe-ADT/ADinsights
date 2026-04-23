import { render, screen } from '@testing-library/react';
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
  dismissGoogleAdsRecommendation:
    googleAdsDashboardMock.dismissGoogleAdsRecommendation,
}));

vi.mock('../../../../stores/useToastStore', () => ({
  useToastStore: (selector: (state: typeof toastMock) => unknown) =>
    selector(toastMock),
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

describe('RecommendationsTabSection — integration', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('renders loading state', () => {
    render(
      <RecommendationsTabSection data={null} status="loading" error="" />,
    );
    expect(screen.getByText('Loading recommendations...')).toBeInTheDocument();
  });

  it('renders empty state', () => {
    render(
      <RecommendationsTabSection
        data={{ count: 0, results: [] }}
        status="success"
        error=""
      />,
    );
    expect(screen.getByText('No recommendations')).toBeInTheDocument();
  });

  it('renders populated state', () => {
    render(
      <RecommendationsTabSection
        data={{ count: 1, results: [activeRow] }}
        status="success"
        error=""
      />,
    );
    expect(
      screen.getByTestId('google-ads-recommendations-section'),
    ).toBeInTheDocument();
    expect(
      screen.getByRole('button', { name: 'Dismiss' }),
    ).toBeInTheDocument();
    expect(screen.getAllByText('KEYWORD').length).toBeGreaterThan(0);
  });
});
