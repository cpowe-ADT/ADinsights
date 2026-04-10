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
    metric_availability: { post_media_view: 'available' },
  } as {
    post_id: string;
    page_id: string;
    message: string;
    media_type: string;
    last_synced_at: string;
    permalink: string;
    metric_availability: Record<string, string>;
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
      metric_availability: { post_media_view: 'available' },
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
