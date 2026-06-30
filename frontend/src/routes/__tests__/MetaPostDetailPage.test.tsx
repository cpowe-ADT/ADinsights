import React from 'react';
import { render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import MetaPostDetailPage from '../MetaPostDetailPage';

vi.mock('react-router-dom', async () => {
  const actual = await vi.importActual('react-router-dom');
  return { ...actual, useParams: () => ({ postId: 'post-123' }) };
});

const pageInsightsStoreMock = vi.hoisted(() => ({
  pages: [] as Array<{ page_id: string; name: string }>,
  postStatus: 'loaded' as string,
  postSeriesStatus: 'idle' as string,
  postDetail: {
    post_id: 'post-123',
    page_id: 'page-1',
    message: 'Hello world post',
    media_type: 'PHOTO',
    last_synced_at: '2026-04-01T12:00:00Z',
    permalink: 'https://facebook.com/post-123',
    metric_availability: {
      post_media_view: 'available',
      post_impressions_unique: 'available',
      post_impressions: 'available',
      post_reactions_like_total: 'available',
      post_shares: 'available',
    },
    metrics: {
      post_impressions_unique: 1200,
      post_impressions: 3200,
      post_reactions_like_total: 88,
      post_shares: 14,
      post_media_view: 500,
    },
  } as {
    post_id: string;
    page_id: string;
    message: string;
    media_type: string;
    last_synced_at: string;
    permalink: string;
    metric_availability: Record<string, string>;
    metrics: Record<string, number>;
  } | null,
  postTimeseries: null as { points: Array<{ end_time: string; value: number }> } | null,
  error: null as string | null,
  loadPages: vi.fn(),
  loadPostDetail: vi.fn(),
  loadPostTimeseries: vi.fn(),
  setFilters: vi.fn(),
}));

vi.mock('../../state/useMetaPageInsightsStore', () => {
  const fn = (selector?: (s: typeof pageInsightsStoreMock) => unknown) =>
    selector ? selector(pageInsightsStoreMock) : pageInsightsStoreMock;
  fn.getState = () => pageInsightsStoreMock;
  fn.subscribe = () => () => {};
  return { __esModule: true, default: fn };
});

vi.mock('../../components/Breadcrumbs', () => ({
  __esModule: true,
  default: () => <nav data-testid="breadcrumbs" />,
}));

vi.mock('../../components/EmptyState', () => ({
  __esModule: true,
  default: ({ title }: { title: string }) => <div>{title}</div>,
}));

vi.mock('../../components/MetricAvailabilityBadge', () => ({
  __esModule: true,
  default: () => <span data-testid="metric-badge" />,
}));

vi.mock('../../components/TrendChart', () => ({
  __esModule: true,
  default: () => <div data-testid="trend-chart" />,
}));

vi.mock('../../components/viz', async () => {
  const actual = await vi.importActual<Record<string, unknown>>('../../components/viz');
  return {
    ...actual,
    TrendLine: ({ ariaLabel }: { ariaLabel: string }) => (
      <div data-testid="viz-trend-line" aria-label={ariaLabel} />
    ),
    KpiTile: ({ label, value, hint }: { label: string; value: number | null; hint?: string }) => (
      <article className="kpi-tile" data-hint={hint}>
        <p>{label}</p>
        <strong>{value ?? '—'}</strong>
      </article>
    ),
    AccessibleTableToggle: ({ chart }: { chart: React.ReactNode }) => <div>{chart}</div>,
  };
});

vi.mock('../../styles/dashboard.css', () => ({}));

describe('MetaPostDetailPage', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    pageInsightsStoreMock.postDetail = {
      post_id: 'post-123',
      page_id: 'page-1',
      message: 'Hello world post',
      media_type: 'PHOTO',
      last_synced_at: '2026-04-01T12:00:00Z',
      permalink: 'https://facebook.com/post-123',
      metric_availability: {
        post_media_view: 'available',
        post_impressions_unique: 'available',
        post_impressions: 'available',
        post_reactions_like_total: 'available',
        post_shares: 'available',
      },
      metrics: {
        post_impressions_unique: 1200,
        post_impressions: 3200,
        post_reactions_like_total: 88,
        post_shares: 14,
        post_media_view: 500,
      },
    };
    pageInsightsStoreMock.postStatus = 'loaded';
    pageInsightsStoreMock.error = null;
  });

  it('renders post detail heading', () => {
    render(
      <MemoryRouter>
        <MetaPostDetailPage />
      </MemoryRouter>,
    );

    expect(screen.getByRole('heading', { name: 'Post Detail' })).toBeInTheDocument();
  });

  it('shows post message content', () => {
    render(
      <MemoryRouter>
        <MetaPostDetailPage />
      </MemoryRouter>,
    );

    expect(screen.getByText('Hello world post')).toBeInTheDocument();
  });

  it('renders KpiTile × 4 for available metric categories', () => {
    render(
      <MemoryRouter>
        <MetaPostDetailPage />
      </MemoryRouter>,
    );

    const strip = screen.getByTestId('meta-post-kpi-strip');
    expect(strip).toBeInTheDocument();
    expect(strip.querySelectorAll('.kpi-tile').length).toBe(4);
    expect(screen.getByText('Reach')).toBeInTheDocument();
    expect(screen.getByText('Impressions')).toBeInTheDocument();
    expect(screen.getByText('Reactions')).toBeInTheDocument();
    expect(screen.getByText('Shares')).toBeInTheDocument();
  });

  it('omits KPI tile for a category when no availability key matches', () => {
    pageInsightsStoreMock.postDetail = {
      post_id: 'post-123',
      page_id: 'page-1',
      message: 'Hello',
      media_type: 'PHOTO',
      last_synced_at: null as unknown as string,
      permalink: 'https://example.com',
      metric_availability: {
        post_impressions_unique: 'available',
        post_impressions: 'available',
      },
      metrics: { post_impressions_unique: 10, post_impressions: 20 },
    };
    render(
      <MemoryRouter>
        <MetaPostDetailPage />
      </MemoryRouter>,
    );

    const strip = screen.getByTestId('meta-post-kpi-strip');
    expect(strip.querySelectorAll('.kpi-tile').length).toBe(2);
    expect(screen.queryByText('Reactions')).not.toBeInTheDocument();
    expect(screen.queryByText('Shares')).not.toBeInTheDocument();
  });

  it('does not render a Comments section (suppressed in S2)', () => {
    render(
      <MemoryRouter>
        <MetaPostDetailPage />
      </MemoryRouter>,
    );

    expect(screen.queryByRole('heading', { name: /comments/i })).not.toBeInTheDocument();
    expect(screen.queryByTestId('post-comments')).not.toBeInTheDocument();
  });

  it('shows error state when post fails to load', () => {
    pageInsightsStoreMock.postStatus = 'error';
    pageInsightsStoreMock.postDetail = null;
    pageInsightsStoreMock.error = 'Failed to load';

    render(
      <MemoryRouter>
        <MetaPostDetailPage />
      </MemoryRouter>,
    );

    expect(screen.getByText('Unable to load post details')).toBeInTheDocument();
  });
});
