import { render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';

import PacingTabSection from '../PacingTabSection';

const baseFixture = {
  month: 'April 2026',
  spend_mtd: 250,
  budget_month: 1000,
  forecast_month_end: 900,
  over_under: -50,
  runway_days: 12,
  alerts: { overspend_risk: false, underdelivery: false },
};

describe('PacingTabSection', () => {
  it('renders GaugeRing with role=meter and aria-label', () => {
    render(<PacingTabSection data={baseFixture} status="success" error="" />);
    const meter = screen.getByRole('meter');
    expect(meter).toBeInTheDocument();
    expect(meter.getAttribute('aria-label')).toMatch(/Pacing/);
    // KpiTiles
    expect(screen.getByText('Spend MTD')).toBeInTheDocument();
    expect(screen.getByText('Budget Month')).toBeInTheDocument();
    expect(screen.getByText('Forecast Month End')).toBeInTheDocument();
  });

  it('derives pacing_pct via spend_mtd / budget_month when missing', () => {
    render(<PacingTabSection data={baseFixture} status="success" error="" />);
    const meter = screen.getByRole('meter');
    // 250 / 1000 = 0.25 → aria-valuenow 0.25
    expect(Number(meter.getAttribute('aria-valuenow'))).toBeCloseTo(0.25, 4);
  });

  it('prefers pacing_pct when directly provided by payload', () => {
    render(
      <PacingTabSection data={{ ...baseFixture, pacing_pct: 0.87 }} status="success" error="" />,
    );
    const meter = screen.getByRole('meter');
    expect(Number(meter.getAttribute('aria-valuenow'))).toBeCloseTo(0.87, 4);
  });

  it('variance bar is deferred (must NOT render)', () => {
    render(<PacingTabSection data={baseFixture} status="success" error="" />);
    expect(screen.queryByText(/variance/i)).toBeNull();
  });

  it('renders reasonCode=no_pacing_data when spend and budget are both zero', () => {
    render(
      <PacingTabSection
        data={{ spend_mtd: 0, budget_month: 0, alerts: {} }}
        status="success"
        error=""
      />,
    );
    expect(document.querySelector('[data-reason-code="no_pacing_data"]')).not.toBeNull();
  });
});
