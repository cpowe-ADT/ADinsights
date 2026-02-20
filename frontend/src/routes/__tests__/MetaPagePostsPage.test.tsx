import { fireEvent, render, screen } from '@testing-library/react';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import MetaPagePostsPage from '../MetaPagePostsPage';

const storeMock = vi.hoisted(() => ({
  state: {
    postsStatus: 'loaded',
    posts: {
      page_id: 'page-1',
      date_preset: 'last_28d',
      since: '2026-01-01',
      until: '2026-01-28',
      last_synced_at: '2026-01-28T00:00:00Z',
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
    loadPosts: vi.fn(),
  },
}));

vi.mock('../../state/useMetaPageInsightsStore', () => ({
  default: (selector: (state: typeof storeMock.state) => unknown) => selector(storeMock.state),
}));

describe('MetaPagePostsPage', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('renders posts table with filter and availability badge', () => {
    render(
      <MemoryRouter initialEntries={['/dashboards/meta/pages/page-1/posts']}>
        <Routes>
          <Route path="/dashboards/meta/pages/:pageId/posts" element={<MetaPagePostsPage />} />
          <Route path="/dashboards/meta/posts/:postId" element={<div>Post detail</div>} />
        </Routes>
      </MemoryRouter>,
    );

    expect(screen.getByText('post-1')).toBeInTheDocument();
    expect(screen.getAllByText('Not available for this Page').length).toBeGreaterThan(0);

    const input = screen.getByLabelText('Filter posts');
    fireEvent.change(input, { target: { value: 'Another' } });
    expect(screen.queryByText('post-1')).not.toBeInTheDocument();
    expect(screen.getByText('post-2')).toBeInTheDocument();
  });
});
