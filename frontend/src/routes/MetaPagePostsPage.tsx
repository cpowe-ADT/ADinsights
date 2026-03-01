import { useEffect, useMemo } from 'react';
import { Link, useNavigate, useParams } from 'react-router-dom';

import EmptyState from '../components/EmptyState';
import MetricAvailabilityBadge from '../components/MetricAvailabilityBadge';
import PostsTable from '../components/PostsTable';
import MetaPageExportHistory from '../components/meta/MetaPageExportHistory';
import MetaPagesFilterBar from '../components/meta/MetaPagesFilterBar';
import useMetaPageExports from '../hooks/useMetaPageExports';
import { toMetaPageDateParams } from '../lib/metaPageDateRange';
import useMetaPageInsightsStore from '../state/useMetaPageInsightsStore';
import '../styles/dashboard.css';

const MetaPagePostsPage = () => {
  const { pageId = '' } = useParams();
  const navigate = useNavigate();
  const { jobs: exportJobs, error: exportError, status: exportStatus, refresh: refreshExports, createExport, download } =
    useMetaPageExports(pageId);

  const {
    pages,
    postsStatus,
    posts,
    error,
    filters,
    postsQuery,
    setFilters,
    setPostsQuery,
    loadPages,
    loadPosts,
  } = useMetaPageInsightsStore((state) => ({
    pages: state.pages,
    postsStatus: state.postsStatus,
    posts: state.posts,
    error: state.error,
    filters: state.filters,
    postsQuery: state.postsQuery,
    setFilters: state.setFilters,
    setPostsQuery: state.setPostsQuery,
    loadPages: state.loadPages,
    loadPosts: state.loadPosts,
  }));

  useEffect(() => {
    if (!pageId) {
      return;
    }
    void loadPages();
  }, [pageId, loadPages]);

  useEffect(() => {
    if (!pageId) {
      return;
    }
    void loadPosts(pageId, {
      offset: 0,
      q: postsQuery.q,
      mediaType: postsQuery.mediaType,
      sort: postsQuery.sort,
      metric: postsQuery.metric,
      limit: postsQuery.limit,
    });
  }, [
    pageId,
    filters.datePreset,
    filters.since,
    filters.until,
    loadPosts,
    postsQuery.limit,
    postsQuery.mediaType,
    postsQuery.metric,
    postsQuery.q,
    postsQuery.sort,
  ]);

  const runExportCsv = async () => {
    if (!pageId) {
      return;
    }
    await createExport({
      export_format: 'csv',
      ...toMetaPageDateParams({
        datePreset: filters.datePreset,
        since: filters.since,
        until: filters.until,
      }),
      posts_metric: postsQuery.metric,
      posts_sort: postsQuery.sort,
      q: postsQuery.q || undefined,
      media_type: postsQuery.mediaType || undefined,
      posts_limit: postsQuery.limit,
    });
  };

  const metricKeys = useMemo(() => {
    return posts ? Object.keys(posts.metric_availability) : [];
  }, [posts]);

  useEffect(() => {
    if (metricKeys.length === 0) {
      return;
    }
    if (!metricKeys.includes(postsQuery.metric)) {
      setPostsQuery({ metric: metricKeys[0] ?? 'post_media_view', offset: 0 });
    }
  }, [metricKeys, postsQuery.metric, setPostsQuery]);

  return (
    <section className="dashboardPage">
      <header className="dashboardPageHeader">
        <p className="dashboardEyebrow">Facebook Analytics</p>
        <h1 className="dashboardHeading">Page Posts</h1>
        <div className="dashboard-header__actions-row">
          <Link className="button tertiary" to={`/dashboards/meta/pages/${pageId}/overview`}>
            Overview
          </Link>
          <Link className="button tertiary" to="/dashboards/meta/pages">
            All pages
          </Link>
          <button type="button" className="button tertiary" onClick={() => void runExportCsv()} disabled={exportStatus === 'loading'}>
            Export CSV
          </button>
        </div>
      </header>

      <MetaPagesFilterBar
        pages={pages}
        selectedPageId={pageId}
        datePreset={filters.datePreset}
        since={filters.since}
        until={filters.until}
        onChangePage={(nextPageId) => navigate(`/dashboards/meta/pages/${nextPageId}/posts`)}
        onChangeDatePreset={(preset) => setFilters({ datePreset: preset })}
        onChangeSince={(value) => setFilters({ since: value })}
        onChangeUntil={(value) => setFilters({ until: value })}
      />

      <div className="meta-posts-metric-select">
        <label htmlFor="meta-posts-metric">Table metric</label>
        <select
          id="meta-posts-metric"
          value={postsQuery.metric}
          onChange={(event) => setPostsQuery({ metric: event.target.value, offset: 0 })}
        >
          {metricKeys.map((metricKey) => (
            <option key={metricKey} value={metricKey}>
              {metricKey}
            </option>
          ))}
        </select>
        {posts ? (
          <MetricAvailabilityBadge
            metric={postsQuery.metric}
            availability={posts.metric_availability[postsQuery.metric]}
          />
        ) : null}
      </div>

      <div className="panel meta-controls-row" style={{ marginBottom: '1rem' }}>
        <label className="dashboard-field">
          <span className="dashboard-field__label">Search</span>
          <input
            type="search"
            value={postsQuery.q}
            onChange={(event) => setPostsQuery({ q: event.target.value, offset: 0 })}
            placeholder="Search post message"
          />
        </label>
        <label className="dashboard-field">
          <span className="dashboard-field__label">Type</span>
          <select
            value={postsQuery.mediaType}
            onChange={(event) => setPostsQuery({ mediaType: event.target.value, offset: 0 })}
          >
            <option value="">All</option>
            <option value="VIDEO">Video</option>
            <option value="PHOTO">Photo</option>
            <option value="LINK">Link</option>
            <option value="TEXT">Text</option>
            <option value="REEL">Reel</option>
          </select>
        </label>
        <label className="dashboard-field">
          <span className="dashboard-field__label">Sort</span>
          <select
            value={postsQuery.sort}
            onChange={(event) =>
              setPostsQuery({
                sort: event.target.value as 'created_desc' | 'metric_desc',
                offset: 0,
              })
            }
          >
            <option value="created_desc">Newest</option>
            <option value="metric_desc">Metric (desc)</option>
          </select>
        </label>
      </div>

      {postsStatus === 'loading' ? <div className="dashboard-state">Loading posts…</div> : null}
      {postsStatus === 'error' ? (
        <EmptyState
          icon={<span aria-hidden>!</span>}
          title="Unable to load posts"
          message={error ?? 'Try again.'}
          actionLabel="Retry"
          onAction={() =>
            pageId &&
            void loadPosts(pageId, {
              offset: 0,
              q: postsQuery.q,
              mediaType: postsQuery.mediaType,
              sort: postsQuery.sort,
              metric: postsQuery.metric,
              limit: postsQuery.limit,
            })
          }
          className="panel"
        />
      ) : null}

      {postsStatus === 'loaded' && posts ? (
        <PostsTable
          rows={posts.results}
          metricKey={postsQuery.metric}
          availability={posts.metric_availability[postsQuery.metric]}
          onOpenPost={(postId) => navigate(`/dashboards/meta/posts/${postId}`)}
        />
      ) : null}

      {postsStatus === 'loaded' && posts && posts.results.length === 0 ? (
        <div className="panel meta-warning-panel" role="status">
          <h3>No posts found</h3>
          <p>Adjust the date range in overview or run a sync.</p>
        </div>
      ) : null}

      {postsStatus === 'loaded' && posts && (posts.next_offset != null || posts.prev_offset != null) ? (
        <div className="panel" style={{ display: 'flex', gap: '0.5rem', justifyContent: 'flex-end' }}>
          <button
            type="button"
            className="button tertiary"
            disabled={posts.prev_offset == null}
            onClick={() => void loadPosts(pageId, { offset: posts.prev_offset ?? 0 })}
          >
            Prev
          </button>
          <button
            type="button"
            className="button tertiary"
            disabled={posts.next_offset == null}
            onClick={() => void loadPosts(pageId, { offset: posts.next_offset ?? 0 })}
          >
            Next
          </button>
        </div>
      ) : null}

      <MetaPageExportHistory
        jobs={exportJobs}
        error={exportError}
        isLoading={exportStatus === 'loading'}
        onRefresh={() => void refreshExports()}
        onDownload={(jobId) => void download(jobId)}
      />
    </section>
  );
};

export default MetaPagePostsPage;
