import { render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';

import type { MetaKpi, MetricAvailabilityEntry } from '../../lib/metaPageInsights';
import KPIGrid from '../KPIGrid';

const supportedAvailability: MetricAvailabilityEntry = {
  supported: true,
  last_checked_at: null,
  reason: '',
};

function buildKpi(overrides: Partial<MetaKpi> = {}): MetaKpi {
  return {
    metric: 'page_post_engagements',
    resolved_metric: 'page_post_engagements',
    value: 100,
    today_value: 10,
    ...overrides,
  };
}

describe('KPIGrid', () => {
  it('renders basic KPI card', () => {
    render(
      <KPIGrid
        kpis={[buildKpi()]}
        metricAvailability={{ page_post_engagements: supportedAvailability }}
      />,
    );
    expect(screen.getByText('100')).toBeTruthy();
  });

  it('shows positive delta indicator when change_pct is positive', () => {
    render(
      <KPIGrid
        kpis={[buildKpi({ change_pct: 50.5, prior_value: 66 })]}
        metricAvailability={{ page_post_engagements: supportedAvailability }}
      />,
    );
    const delta = screen.getByLabelText('positive change');
    expect(delta.textContent).toContain('+50.5%');
    expect(delta.classList.contains('meta-kpi-delta--positive')).toBe(true);
    expect(screen.getByText('Prior: 66')).toBeTruthy();
  });

  it('shows negative delta indicator when change_pct is negative', () => {
    render(
      <KPIGrid
        kpis={[buildKpi({ change_pct: -25.0, prior_value: 133 })]}
        metricAvailability={{ page_post_engagements: supportedAvailability }}
      />,
    );
    const delta = screen.getByLabelText('negative change');
    expect(delta.textContent).toContain('-25.0%');
    expect(delta.classList.contains('meta-kpi-delta--negative')).toBe(true);
  });

  it('shows neutral delta indicator when change_pct is zero', () => {
    render(
      <KPIGrid
        kpis={[buildKpi({ change_pct: 0, prior_value: 100 })]}
        metricAvailability={{ page_post_engagements: supportedAvailability }}
      />,
    );
    const delta = screen.getByLabelText('no change');
    expect(delta.textContent).toContain('0.0%');
    expect(delta.classList.contains('meta-kpi-delta--neutral')).toBe(true);
  });

  it('hides delta indicator when change_pct is null', () => {
    render(
      <KPIGrid
        kpis={[buildKpi({ change_pct: null, prior_value: null })]}
        metricAvailability={{ page_post_engagements: supportedAvailability }}
      />,
    );
    expect(screen.queryByLabelText('positive change')).toBeNull();
    expect(screen.queryByLabelText('negative change')).toBeNull();
    expect(screen.queryByLabelText('no change')).toBeNull();
  });

  it('hides prior value text when prior_value is null', () => {
    render(
      <KPIGrid
        kpis={[buildKpi({ change_pct: null, prior_value: null })]}
        metricAvailability={{ page_post_engagements: supportedAvailability }}
      />,
    );
    expect(screen.queryByText(/Prior:/)).toBeNull();
  });
});
