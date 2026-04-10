import type { BreakdownEntry } from '../lib/metaPageInsights';
import { formatNumber } from '../lib/format';

type EngagementBreakdownPanelProps = {
  breakdown?: Record<string, BreakdownEntry[]>;
};

const METRIC_LABELS: Record<string, string> = {
  page_post_engagements: 'Post Engagements',
  page_total_actions: 'Total Actions',
  page_actions_post_reactions_total: 'Reactions',
};

function metricLabel(metric: string): string {
  return METRIC_LABELS[metric] ?? metric;
}

const EngagementBreakdownPanel = ({ breakdown }: EngagementBreakdownPanelProps) => {
  if (!breakdown) {
    return null;
  }
  const metrics = Object.keys(breakdown).filter((key) => breakdown[key].length > 0);
  if (metrics.length === 0) {
    return null;
  }

  return (
    <section className="panel" aria-label="Engagement Breakdown">
      <h3 className="panel-heading">Engagement Breakdown</h3>
      {metrics.map((metric) => (
        <div key={metric} style={{ marginBottom: '1rem' }}>
          <h4 style={{ margin: '0.5rem 0' }}>{metricLabel(metric)}</h4>
          <table className="dashboard-table">
            <thead>
              <tr>
                <th>Type</th>
                <th style={{ textAlign: 'right' }}>Value</th>
              </tr>
            </thead>
            <tbody>
              {breakdown[metric].map((entry) => (
                <tr key={entry.type}>
                  <td>{entry.type}</td>
                  <td style={{ textAlign: 'right' }}>
                    {entry.value == null ? '—' : formatNumber(entry.value)}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ))}
    </section>
  );
};

export default EngagementBreakdownPanel;
