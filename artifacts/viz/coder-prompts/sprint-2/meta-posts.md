# Meta Page Posts List — Visualization Upgrade

**Sprint:** 2
**Estimated size:** S
**Depends on:** sprint-1/kpi-tile.md, sprint-1/pie-composition.md, sprint-1/data-table.md, sprint-1/chart-skeleton.md
**Blocks:** meta-post-detail.md
**Role needed:** frontend-engineer

## Context

`MetaPagePostsPage` at `/dashboards/meta/pages/:pageId/posts` shows a paginated list of posts for a Facebook Page with KPI summary, post type mix pie, and a posts table. Endpoint: `GET /api/integrations/pages/:pageId/posts/`. No combined call.

## Inputs already in the repo (do not re-invent)

- `frontend/src/routes/MetaPagePostsPage.tsx`: existing file.
- All Sprint 1 viz components.
- `frontend/src/components/EmptyState.tsx`: `reasonCode` prop present.

## Deliverable

- **File(s) to create/modify**:
  - `frontend/src/routes/MetaPagePostsPage.tsx` (modify)
  - `frontend/src/routes/__tests__/MetaPagePostsPage.test.tsx` (create or modify)

- **Data binding**:

Response from `GET /api/integrations/pages/:pageId/posts/`:
```typescript
{
  results: Array<{
    post_id: string
    created_time: string    // ISO timestamp
    media_type: string      // 'PHOTO' | 'VIDEO' | 'LINK' | 'STATUS' | 'REEL'
    message: string | null
    thumbnail_url: string | null
    metrics: {
      post_impressions?: number
      post_reach?: number
      post_engaged_users?: number
      post_reactions_like_total?: number
      post_clicks?: number
      shares?: number
    }
  }>
  page_id: string
  since: string
  until: string
  total_count: number
  page: number
  page_size: number
}
```

  - KPI strip (3 tiles): Total Posts = `total_count`; Avg Reach = mean of `results[].metrics.post_reach` (filter out null); Avg Engagement = mean of `results[].metrics.post_engaged_users`.
  - PieComposition: group `results[]` by `media_type`, count per type. Data: `[{ label: 'Photo', value: N }, ...]`.
  - DataTable: columns — Thumbnail (render as `<img>` cell, 40×40px, fallback to media_type icon), Message (truncated at 80 chars), Created (formatted date), Reach, Reactions, Shares, Media Type. `onRowClick` → navigate to `/dashboards/meta/posts/{post_id}`.

- **Pagination**: The endpoint is server-paginated (`page`, `page_size`). `DataTable` must trigger a new fetch when page changes. Pass `onPageChange(page: number)` callback to `DataTable` (add this optional prop to `DataTable` if not already there). On page change, call the store's loadPosts action with the new page number.

- **Empty/loading/error states**:
  - Loading: ChartSkeleton variant `kpi-strip` for KPIs, `pie` for pie, `table` for table.
  - `results.length === 0`: `EmptyState reasonCode="no_posts"`.

- **A11y**: Thumbnail `<img>` must have `alt={post.media_type}` or `alt="Post thumbnail"`. Table uses DataTable a11y.

## Design

```
┌────────────────────────────────────────────────────────┐
│ [Total Posts] [Avg Reach] [Avg Engagement]             │  ← 3 KpiTiles
├──────────────────────────────┬─────────────────────────┤
│ Post Type Mix (PieComposition│  [reserved]             │
│ PHOTO/VIDEO/LINK/REEL/STATUS)│                        │
├──────────────────────────────┴─────────────────────────┤
│ DataTable: Thumb | Message | Created | Reach | ...     │  ← paginated, row click → detail
└────────────────────────────────────────────────────────┘
```

## Definition of Done

- [ ] 3 KpiTiles render (Total Posts, Avg Reach, Avg Engagement)
- [ ] PieComposition shows post type distribution
- [ ] DataTable renders posts with thumbnail, truncated message, metrics
- [ ] Row click navigates to `/dashboards/meta/posts/{post_id}`
- [ ] Server-side pagination: page change triggers new fetch
- [ ] No `/api/metrics/combined/` call
- [ ] `EmptyState reasonCode="no_posts"` when no posts
- [ ] Tests green: `cd frontend && npm test -- --run src/routes/__tests__/MetaPagePostsPage.test.tsx`
- [ ] Lint clean: `cd frontend && npm run lint`
- [ ] Build clean: `cd frontend && npm run build`

## Test deltas

`MetaPagePostsPage.test.tsx`:
```typescript
it('renders 3 KpiTiles', () => { ... })
it('renders PieComposition for post type mix', () => { ... })
it('renders DataTable with post rows', () => { ... })
it('row click navigates to post detail', async () => {
  await user.click(screen.getByText('First post message...'))
  expect(mockNavigate).toHaveBeenCalledWith('/dashboards/meta/posts/post_123')
})
it('does NOT call /api/metrics/combined/', () => { ... })
it('shows EmptyState reasonCode="no_posts" when empty', () => { ... })
```

## Out of scope

- Do NOT add comments functionality to this page
- Do NOT add inline post preview/modal
- Do NOT implement infinite scroll — use page-based pagination only
