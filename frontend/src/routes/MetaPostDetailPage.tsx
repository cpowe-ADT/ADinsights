import { useEffect, useMemo, useState } from 'react';
import { Link, useParams } from 'react-router-dom';

import Breadcrumbs from '../components/Breadcrumbs';
import EmptyState from '../components/EmptyState';
import MetricAvailabilityBadge from '../components/MetricAvailabilityBadge';
import { AccessibleTableToggle, KpiTile, TrendLine } from '../components/viz';
import useMetaPageInsightsStore from '../state/useMetaPageInsightsStore';
import '../styles/dashboard.css';

type KpiCategory = 'reach' | 'impressions' | 'reactions' | 'shares';

const METRIC_KEYS_BY_CATEGORY: Record<KpiCategory, string[]> = {
  reach: ['post_impressions_unique', 'page_total_media_view_unique'],
  impressions: ['post_impressions', 'page_impressions'],
  reactions: ['post_reactions_by_type_total', 'post_reactions_like_total'],
  shares: ['post_shares'],
};

const CATEGORY_LABELS: Record<KpiCategory, string> = {
  reach: 'Reach',
  impressions: 'Impressions',
  reactions: 'Reactions',
  shares: 'Shares',
};

const CATEGORY_ORDER: KpiCategory[] = ['reach', 'impressions', 'reactions', 'shares'];

const MetaPostDetailPage = () => {
  const { postId = '' } = useParams();
  const [metric, setMetric] = useState('post_media_view');
  const [period, setPeriod] = useState('lifetime');
  const [showFullMessage, setShowFullMessage] = useState(false);

  const {
    pages,
    postStatus,
    postSeriesStatus,
    postDetail,
    postTimeseries,
    error,
    loadPages,
    loadPostDetail,
    loadPostTimeseries,
    setFilters,
  } = useMetaPageInsightsStore((state) => ({
    pages: state.pages,
    postStatus: state.postStatus,
    postSeriesStatus: state.postSeriesStatus,
    postDetail: state.postDetail,
    postTimeseries: state.postTimeseries,
    error: state.error,
    loadPages: state.loadPages,
    loadPostDetail: state.loadPostDetail,
    loadPostTimeseries: state.loadPostTimeseries,
    setFilters: state.setFilters,
  }));

  useEffect(() => {
    void loadPages();
  }, [loadPages]);

  useEffect(() => {
    if (!postId) {
      return;
    }
    void loadPostDetail(postId);
  }, [postId, loadPostDetail]);

  const parentPageId = postDetail?.page_id ?? '';
  const parentPage = useMemo(() => pages.find((p) => p.page_id === parentPageId), [pages, parentPageId]);
  const pageName = parentPage?.name ?? 'Facebook Page';
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
    // M16: pass metric/period as direct params so the fetch uses the current
    // values even if Zustand's synchronous setFilters hasn't flushed yet.
    setFilters({ metric, period });
    void loadPostTimeseries(postId, { metric, period });
  }, [postId, metric, period, loadPostTimeseries, setFilters]);

  const points = useMemo(
    () =>
      (postTimeseries?.points ?? []).map((point) => ({
        date: point.end_time.slice(0, 10),
        value: point.value ?? 0,
      })),
    [postTimeseries?.points],
  );

  const kpiEntries = useMemo(() => {
    if (!postDetail) return [];
    const availability = postDetail.metric_availability ?? {};
    const metrics = postDetail.metrics ?? {};
    return CATEGORY_ORDER.map((category) => {
      const picked = METRIC_KEYS_BY_CATEGORY[category].find((key) => key in availability);
      if (!picked) return null;
      const raw = metrics[picked];
      const value = typeof raw === 'number' && Number.isFinite(raw) ? raw : null;
      return { category, metricKey: picked, value };
    }).filter((entry): entry is { category: KpiCategory; metricKey: string; value: number | null } => entry !== null);
  }, [postDetail]);

  const trendSparkValues = useMemo(() => points.slice(-7).map((p) => p.value), [points]);

  return (
    <section className="dashboardPage">
      <Breadcrumbs
        items={[
          { label: 'Dashboards', to: '/dashboards' },
          { label: 'Facebook Pages', to: '/dashboards/meta/pages' },
          ...(parentPageId
            ? [
                { label: pageName, to: `/dashboards/meta/pages/${parentPageId}/overview` },
                { label: 'Posts', to: `/dashboards/meta/pages/${parentPageId}/posts` },
              ]
            : []),
          { label: 'Post Detail' },
        ]}
      />
      <header className="dashboardPageHeader">
        <h1 className="dashboardHeading">Post Detail</h1>
        <div className="dashboard-header__actions-row">
          {postDetail ? (
            <Link className="button tertiary" to={`/dashboards/meta/pages/${postDetail.page_id}/posts`}>
              Back to posts
            </Link>
          ) : null}
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
          reasonCode="error"
        />
      ) : null}

      {postDetail ? (
        <>
          <article className="panel">
            <h3>{postDetail.post_id}</h3>
            {postDetail.message ? (
              <>
                <p>
                  {showFullMessage || postDetail.message.length <= 280
                    ? postDetail.message
                    : `${postDetail.message.slice(0, 280)}…`}
                </p>
                {postDetail.message.length > 280 ? (
                  <button
                    type="button"
                    className="button tertiary"
                    onClick={() => setShowFullMessage((prev) => !prev)}
                  >
                    {showFullMessage ? 'Show less' : 'Show more'}
                  </button>
                ) : null}
              </>
            ) : (
              <p>No message</p>
            )}
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

          {kpiEntries.length > 0 ? (
            <div className="dashboard-grid" data-testid="meta-post-kpi-strip" style={{ marginBottom: '1rem' }}>
              {kpiEntries.map((entry) => (
                <KpiTile
                  key={entry.category}
                  label={CATEGORY_LABELS[entry.category]}
                  value={entry.value}
                  format="number"
                  hint={entry.metricKey}
                  reasonCode={`meta_post_${entry.category}`}
                  trend={entry.metricKey === metric ? trendSparkValues : undefined}
                />
              ))}
            </div>
          ) : null}

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
            <div className="meta-posts-metric-select" style={{ marginTop: '0.75rem' }}>
              <label htmlFor="meta-post-detail-period">Period</label>
              <select id="meta-post-detail-period" value={period} onChange={(event) => setPeriod(event.target.value)}>
                <option value="lifetime">lifetime</option>
                <option value="day">day</option>
                <option value="week">week</option>
                <option value="days_28">days_28</option>
              </select>
            </div>
          </article>

          {postSeriesStatus === 'loading' ? <div className="dashboard-state">Loading timeseries…</div> : null}
          {points.length > 0 ? (
            <article className="panel" data-testid="meta-post-trend-panel">
              <h3>{`${metric} trend`}</h3>
              <AccessibleTableToggle
                chartAriaLabel={`${metric} trend`}
                chart={
                  <TrendLine
                    data={points}
                    series={[{ key: 'value', label: metric }]}
                    ariaLabel={`${metric} trend`}
                    height={260}
                  />
                }
                table={
                  <div className="table-responsive">
                    <table className="dashboard-table">
                      <thead>
                        <tr>
                          <th className="dashboard-table__header-cell">Date</th>
                          <th className="dashboard-table__header-cell">{metric}</th>
                        </tr>
                      </thead>
                      <tbody>
                        {points.map((row) => (
                          <tr key={row.date} className="dashboard-table__row">
                            <td className="dashboard-table__cell">{row.date}</td>
                            <td className="dashboard-table__cell">{row.value}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                }
              />
            </article>
          ) : null}
        </>
      ) : null}
    </section>
  );
};

export default MetaPostDetailPage;
