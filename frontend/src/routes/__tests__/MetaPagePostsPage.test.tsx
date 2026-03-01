import { act, fireEvent, render, screen } from '@testing-library/react';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import MetaPagePostsPage from '../MetaPagePostsPage';

const storeMock = vi.hoisted(() => ({
  state: {
    pages: [{ id: '1', page_id: 'page-1', name: 'Page 1', can_analyze: true, is_default: true }],
    postsStatus: 'loaded',
    posts: {
      page_id: 'page-1',
      date_preset: 'last_28d',
      since: '2026-01-01',
      until: '2026-01-28',
      last_synced_at: '2026-01-28T00:00:00Z',
      count: 2,
      limit: 50,
      offset: 0,
      next_offset: null,
      prev_offset: null,
      metric_availability: {
        post_media_view: { supported: false, last_checked_at: null, reason: 'Not available for this Page' },
      },
      results: [
        {
          post_id: 'post-1',
          page_id: 'page-1',
          created_time: '2026-01-28T00:00:00Z',
          permalink: 'https://example.com/1',
          media_type: 'PHOTO',
          message_snippet: 'Hello world',
          metrics: { post_media_view: 120 },
          last_synced_at: '2026-01-28T00:00:00Z',
        },
        {
          post_id: 'post-2',
          page_id: 'page-1',
          created_time: '2026-01-27T00:00:00Z',
          permalink: 'https://example.com/2',
          media_type: 'VIDEO',
          message_snippet: 'Another post',
          metrics: { post_media_view: 55 },
          last_synced_at: '2026-01-28T00:00:00Z',
        },
      ],
    },
    error: undefined,
    filters: {
      datePreset: 'last_28d',
      since: '2026-01-01',
      until: '2026-01-28',
      metric: 'page_post_engagements',
      period: 'day',
      showAllMetrics: false,
    },
    postsQuery: {
      q: '',
      mediaType: '',
      sort: 'created_desc',
      metric: 'post_media_view',
      limit: 50,
      offset: 0,
    },
    setFilters: vi.fn(),
    setPostsQuery: vi.fn(),
    loadPages: vi.fn(),
    loadPosts: vi.fn(),
  },
}));

vi.mock('../../state/useMetaPageInsightsStore', () => ({
  default: (selector: (state: typeof storeMock.state) => unknown) => selector(storeMock.state),
}));

vi.mock('../../lib/metaPageInsights', async (importOriginal) => {
  const original = await importOriginal<typeof import('../../lib/metaPageInsights')>();
  return {
    ...original,
    listMetaPageExports: vi.fn().mockResolvedValue([]),
    createMetaPageExport: vi.fn().mockResolvedValue({}),
    downloadExportArtifact: vi.fn().mockResolvedValue({ blob: new Blob(), filename: 'export.csv', contentType: 'text/csv' }),
  };
});

describe('MetaPagePostsPage', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('renders posts table and updates query on search', async () => {
    await act(async () => {
      render(
        <MemoryRouter initialEntries={['/dashboards/meta/pages/page-1/posts']}>
          <Routes>
            <Route path="/dashboards/meta/pages/:pageId/posts" element={<MetaPagePostsPage />} />
            <Route path="/dashboards/meta/posts/:postId" element={<div>Post detail</div>} />
          </Routes>
        </MemoryRouter>,
      );
    });

    expect(screen.getByText('post-1')).toBeInTheDocument();
    expect(screen.getAllByText('Not available for this Page').length).toBeGreaterThan(0);

    storeMock.state.setPostsQuery.mockClear();
    const input = screen.getByPlaceholderText('Search post message');
    fireEvent.change(input, { target: { value: 'Another' } });
    expect(storeMock.state.setPostsQuery).toHaveBeenCalledWith({ q: 'Another', offset: 0 });
  });
});
