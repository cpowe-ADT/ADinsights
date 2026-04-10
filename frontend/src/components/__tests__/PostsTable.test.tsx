import { render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';

import PostsTable from '../PostsTable';
import type { MetaPostListItem } from '../../lib/metaPageInsights';

const baseRow: MetaPostListItem = {
  post_id: 'post-1',
  page_id: 'page-1',
  created_time: '2026-01-28T00:00:00Z',
  permalink: 'https://example.com/1',
  media_type: 'PHOTO',
  message_snippet: 'Hello world',
  metrics: { post_media_view: 120 },
  last_synced_at: '2026-01-28T00:00:00Z',
};

describe('PostsTable', () => {
  it('renders thumbnail image when thumbnail_url is present', () => {
    const row: MetaPostListItem = {
      ...baseRow,
      thumbnail_url: 'https://scontent.xx.fbcdn.net/v/thumb.jpg',
    };

    render(
      <PostsTable
        rows={[row]}
        metricKey="post_media_view"
        onOpenPost={vi.fn()}
      />,
    );

    const img = screen.getByRole('img');
    expect(img).toBeInTheDocument();
    expect(img).toHaveAttribute('src', 'https://scontent.xx.fbcdn.net/v/thumb.jpg');
    expect(img).toHaveStyle({ width: '48px', height: '48px' });
    // Media type label should still appear
    expect(screen.getByText('PHOTO')).toBeInTheDocument();
  });

  it('renders media type text only when no thumbnail_url', () => {
    render(
      <PostsTable
        rows={[baseRow]}
        metricKey="post_media_view"
        onOpenPost={vi.fn()}
      />,
    );

    expect(screen.queryByRole('img')).not.toBeInTheDocument();
    expect(screen.getByText('PHOTO')).toBeInTheDocument();
  });
});
