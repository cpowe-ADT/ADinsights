import { render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';

import WorkspaceKpiStrip from '../WorkspaceKpiStrip';
import type { SummaryRecord } from '../types';

const summaryFixture: SummaryRecord = {
  window: {
    start_date: '2026-02-01',
    end_date: '2026-02-10',
    compare_start_date: '2026-01-22',
    compare_end_date: '2026-01-31',
  },
  metrics: {
    spend: 1234.56,
    conversions: 250,
    cpa: 4.94,
    roas: 3.2,
    impressions: 100000,
    clicks: 9000,
    conversion_value: 3950.12,
  },
  comparison: {},
  pacing: {},
  trend: [],
  movers: [],
  data_freshness_ts: '2026-02-23T10:00:00Z',
  source_engine: 'sdk',
  alerts_summary: {
    overspend_risk: false,
    underdelivery: false,
    spend_spike: false,
    conversion_drop: false,
  },
  governance_summary: { recent_changes_7d: 2, active_recommendations: 5, disapproved_ads: 1 },
  top_insights: [],
  workspace_generated_at: '2026-02-23T10:01:00Z',
};

describe('WorkspaceKpiStrip', () => {
  it('renders the 4 KPI tiles (architect §4: IS% deferred → 4 tiles, not 5)', () => {
    render(<WorkspaceKpiStrip summary={summaryFixture} status="success" error="" />);
    expect(screen.getByText('Cost')).toBeInTheDocument();
    expect(screen.getByText('Conversions')).toBeInTheDocument();
    expect(screen.getByText('CPA')).toBeInTheDocument();
    expect(screen.getByText('ROAS')).toBeInTheDocument();
  });

  it('renders exactly 4 KpiTile cards (no IS% tile)', () => {
    const { container } = render(
      <WorkspaceKpiStrip summary={summaryFixture} status="success" error="" />,
    );
    const tiles = container.querySelectorAll('.kpi-tile');
    expect(tiles).toHaveLength(4);
  });

  it('shows loading skeletons when loading with no summary', () => {
    const { container } = render(
      <WorkspaceKpiStrip summary={null} status="loading" error="" />,
    );
    const busyTiles = container.querySelectorAll('[aria-busy="true"]');
    expect(busyTiles.length).toBeGreaterThan(0);
  });

  it('renders role=alert when error and no summary', () => {
    render(<WorkspaceKpiStrip summary={null} status="error" error="Bad thing" />);
    expect(screen.getByRole('alert')).toHaveTextContent('Bad thing');
  });

  it('tags KPI tiles with reasonCode=no_data_for_range when a value is null', () => {
    const emptySummary: SummaryRecord = {
      ...summaryFixture,
      metrics: { spend: 1, conversions: 2, cpa: 3 }, // roas missing
    };
    const { container } = render(
      <WorkspaceKpiStrip summary={emptySummary} status="success" error="" />,
    );
    const emptyTile = container.querySelector('[data-reason-code="no_data_for_range"]');
    expect(emptyTile).not.toBeNull();
  });
});
