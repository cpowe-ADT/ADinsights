import { useEffect, useMemo, useState } from 'react';
import { Link, useParams } from 'react-router-dom';

import EmptyState from '../components/EmptyState';
import MetricAvailabilityBadge from '../components/MetricAvailabilityBadge';
import TrendChart from '../components/TrendChart';
import useMetaPageInsightsStore from '../state/useMetaPageInsightsStore';
import '../styles/dashboard.css';

const MetaPostDetailPage = () => {
  const { postId = '' } = useParams();
  const [metric, setMetric] = useState('post_media_view');

  const {
    postStatus,
    postSeriesStatus,
    postDetail,
    postTimeseries,
    error,
    loadPostDetail,
    loadPostTimeseries,
    setFilters,
  } = useMetaPageInsightsStore((state) => ({
    postStatus: state.postStatus,
    postSeriesStatus: state.postSeriesStatus,
    postDetail: state.postDetail,
    postTimeseries: state.postTimeseries,
    error: state.error,
    loadPostDetail: state.loadPostDetail,
    loadPostTimeseries: state.loadPostTimeseries,
    setFilters: state.setFilters,
  }));

  useEffect(() => {
    if (!postId) {
      return;
    }
    void loadPostDetail(postId);
  }, [postId, loadPostDetail]);

  const metricKeys = useMemo(() => Object.keys(postDetail?.metric_availability ?? {}), [postDetail]);
  useEffect(() => {
    if (metricKeys.length > 0 && !metricKeys.includes(metric)) {
      setMetric(metricKeys[0] ?? 'post_media_view');
    }
  }, [metric, metricKeys]);

  useEffect(() => {
    if (!postId || !metric) {
      return;
    }
    setFilters({ metric });
    void loadPostTimeseries(postId);
  }, [postId, metric, loadPostTimeseries, setFilters]);

  const points = (postTimeseries?.points ?? []).map((point) => ({
    date: point.end_time.slice(0, 10),
    value: point.value,
  }));

  return (
    <section className="dashboardPage">
      <header className="dashboardPageHeader">
        <p className="dashboardEyebrow">Facebook Analytics</p>
        <h1 className="dashboardHeading">Post Detail</h1>
        <div className="dashboard-header__actions-row">
          {postDetail ? (
            <Link className="button tertiary" to={`/dashboards/meta/pages/${postDetail.page_id}/posts`}>
              Back to posts
            </Link>
          ) : null}
          <Link className="button tertiary" to="/dashboards/meta/pages">
            All pages
          </Link>
        </div>
      </header>

      {postStatus === 'loading' ? <div className="dashboard-state">Loading post details…</div> : null}
      {postStatus === 'error' ? (
        <EmptyState
          icon={<span aria-hidden>!</span>}
          title="Unable to load post details"
          message={error ?? 'Try again.'}
          actionLabel="Retry"
          onAction={() => postId && void loadPostDetail(postId)}
          className="panel"
        />
      ) : null}

      {postDetail ? (
        <>
          <article className="panel">
            <h3>{postDetail.post_id}</h3>
            <p>{postDetail.message || 'No message'}</p>
            <p>
              <strong>Media:</strong> {postDetail.media_type || '—'}
            </p>
            <p>
              <strong>Last synced:</strong> {postDetail.last_synced_at ?? 'Never'}
            </p>
            <a href={postDetail.permalink} target="_blank" rel="noreferrer">
              Open on Facebook
            </a>
          </article>

          <article className="panel">
            <div className="meta-posts-metric-select">
              <label htmlFor="meta-post-detail-metric">Timeseries metric</label>
              <select
                id="meta-post-detail-metric"
                value={metric}
                onChange={(event) => setMetric(event.target.value)}
              >
                {metricKeys.map((metricKey) => (
                  <option key={metricKey} value={metricKey}>
                    {metricKey}
                  </option>
                ))}
              </select>
              <MetricAvailabilityBadge metric={metric} availability={postDetail.metric_availability[metric]} />
            </div>
          </article>

          {postSeriesStatus === 'loading' ? <div className="dashboard-state">Loading timeseries…</div> : null}
          {points.length > 0 ? <TrendChart title={`${metric} trend`} points={points} /> : null}
        </>
      ) : null}
    </section>
  );
};

export default MetaPostDetailPage;
