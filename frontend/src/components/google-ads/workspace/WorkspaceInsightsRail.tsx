import type { SummaryRecord, WorkspaceTab } from './types';

type Props = {
  summary: SummaryRecord | null;
  activeTab: WorkspaceTab;
};

const WorkspaceInsightsRail = ({ summary, activeTab }: Props) => {
  if (!summary) {
    return (
      <aside className="panel gads-workspace__rail" aria-label="Insights rail">
        <p className="muted">Insights and alerts will appear once data is loaded.</p>
      </aside>
    );
  }

  return (
    <aside className="panel gads-workspace__rail" aria-label="Insights rail">
      <h2>Top insights</h2>
      <ul className="gads-workspace__insight-list" role="list">
        {summary.top_insights.length === 0 ? <li className="muted">No major changes detected.</li> : null}
        {summary.top_insights.map((insight) => (
          <li key={insight.id}>
            <strong>{insight.title}</strong>
            <p>{insight.detail}</p>
          </li>
        ))}
      </ul>

      <h3>Governance</h3>
      <dl className="gads-workspace__keyvals">
        <dt>Recent changes (7d)</dt>
        <dd>{summary.governance_summary.recent_changes_7d}</dd>
        <dt>Active recommendations</dt>
        <dd>{summary.governance_summary.active_recommendations}</dd>
        <dt>Disapproved ads</dt>
        <dd>{summary.governance_summary.disapproved_ads}</dd>
      </dl>

      <h3>Alerts</h3>
      <ul className="gads-workspace__alert-list" role="list">
        <li>{summary.alerts_summary.overspend_risk ? 'Overspend risk' : 'No overspend risk'}</li>
        <li>{summary.alerts_summary.underdelivery ? 'Underdelivery risk' : 'No underdelivery risk'}</li>
        <li>{summary.alerts_summary.spend_spike ? 'Spend spike detected' : 'No spend spike'}</li>
        <li>{summary.alerts_summary.conversion_drop ? 'Conversion drop detected' : 'No conversion drop'}</li>
      </ul>

      <p className="muted">Current section: {activeTab.replace('_', ' ')}</p>
    </aside>
  );
};

export default WorkspaceInsightsRail;
