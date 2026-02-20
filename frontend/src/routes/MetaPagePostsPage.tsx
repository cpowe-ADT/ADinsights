import { useEffect, useMemo, useState } from 'react';
import { Link, useNavigate, useParams } from 'react-router-dom';

import EmptyState from '../components/EmptyState';
import MetricAvailabilityBadge from '../components/MetricAvailabilityBadge';
import PostsTable from '../components/PostsTable';
import useMetaPageInsightsStore from '../state/useMetaPageInsightsStore';
import '../styles/dashboard.css';

const MetaPagePostsPage = () => {
  const { pageId = '' } = useParams();
  const navigate = useNavigate();
  const [metric, setMetric] = useState('post_media_view');

  const { postsStatus, posts, error, loadPosts } = useMetaPageInsightsStore((state) => ({
    postsStatus: state.postsStatus,
    posts: state.posts,
    error: state.error,
    loadPosts: state.loadPosts,
  }));

  useEffect(() => {
    if (!pageId) {
      return;
    }
    void loadPosts(pageId);
  }, [pageId, loadPosts]);

  const metricKeys = useMemo(() => {
    return posts ? Object.keys(posts.metric_availability) : [];
  }, [posts]);

  useEffect(() => {
    if (metricKeys.length === 0) {
      return;
    }
    if (!metricKeys.includes(metric)) {
      setMetric(metricKeys[0] ?? 'post_media_view');
    }
  }, [metric, metricKeys]);

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
        </div>
      </header>

      <div className="meta-posts-metric-select">
        <label htmlFor="meta-posts-metric">Table metric</label>
        <select id="meta-posts-metric" value={metric} onChange={(event) => setMetric(event.target.value)}>
          {metricKeys.map((metricKey) => (
            <option key={metricKey} value={metricKey}>
              {metricKey}
            </option>
          ))}
        </select>
        {posts ? <MetricAvailabilityBadge metric={metric} availability={posts.metric_availability[metric]} /> : null}
      </div>

      {postsStatus === 'loading' ? <div className="dashboard-state">Loading posts…</div> : null}
      {postsStatus === 'error' ? (
        <EmptyState
          icon={<span aria-hidden>!</span>}
          title="Unable to load posts"
          message={error ?? 'Try again.'}
          actionLabel="Retry"
          onAction={() => pageId && void loadPosts(pageId)}
          className="panel"
        />
      ) : null}

      {postsStatus === 'loaded' && posts ? (
        <PostsTable
          rows={posts.results}
          metricKey={metric}
          availability={posts.metric_availability[metric]}
          onOpenPost={(postId) => navigate(`/dashboards/meta/posts/${postId}`)}
        />
      ) : null}

      {postsStatus === 'loaded' && posts && posts.results.length === 0 ? (
        <div className="panel meta-warning-panel" role="status">
          <h3>No posts found</h3>
          <p>Adjust the date range in overview or run a sync.</p>
        </div>
      ) : null}
    </section>
  );
};

export default MetaPagePostsPage;
