import { render, screen } from '@testing-library/react';
import { axe } from 'jest-axe';
import { describe, expect, it } from 'vitest';

import TrendLine from './TrendLine';
import type { TrendLinePoint, TrendLineSeries } from './TrendLine';

const series: TrendLineSeries[] = [{ key: 'spend', label: 'Spend' }];
const data: TrendLinePoint[] = [
  { date: '2025-04-01', spend: 100 },
  { date: '2025-04-02', spend: 120 },
  { date: '2025-04-03', spend: 140 },
];

describe('TrendLine', () => {
  it('renders chart with role="img" and aria-label', () => {
    render(
      <TrendLine data={data} series={series} ariaLabel="Daily spend trend" />,
    );
    const img = screen.getByRole('img', { name: /daily spend trend/i });
    expect(img).toBeInTheDocument();
  });

  it('renders a hidden accessible table with data rows', () => {
    const { container } = render(
      <TrendLine data={data} series={series} ariaLabel="Daily spend trend" />,
    );
    const table = container.querySelector('table.sr-only');
    expect(table).toBeInTheDocument();
    expect(table?.querySelectorAll('tbody tr').length).toBe(data.length);
  });

  it('renders the skeleton when isLoading', () => {
    const { container } = render(
      <TrendLine data={[]} series={series} ariaLabel="Daily spend trend" isLoading />,
    );
    expect(container.querySelector('.viz-chart-skeleton')).toBeInTheDocument();
  });

  it('renders EmptyState with the reason code when data is empty', () => {
    const { container } = render(
      <TrendLine
        data={[]}
        series={series}
        ariaLabel="Daily spend trend"
        emptyReasonCode="no_data_for_range"
      />,
    );
    const status = container.querySelector('[data-reason-code="no_data_for_range"]');
    expect(status).toBeInTheDocument();
  });

  it('renders a Peer avg column in the accessible table when peerData present', () => {
    const peerData = data.map((d) => ({ date: d.date, value: 90 }));
    const { container } = render(
      <TrendLine
        data={data}
        series={series}
        peerData={peerData}
        ariaLabel="Peer comparison"
      />,
    );
    const headers = container.querySelectorAll('table.sr-only thead th');
    const texts = Array.from(headers).map((h) => h.textContent);
    expect(texts).toContain('Peer avg');
  });

  it('has no a11y violations (chart + sr-only table)', async () => {
    const { container } = render(
      <TrendLine data={data} series={series} ariaLabel="Daily spend trend" />,
    );
    expect(await axe(container)).toHaveNoViolations();
  });

  it('has no a11y violations in empty state', async () => {
    const { container } = render(
      <TrendLine
        data={[]}
        series={series}
        ariaLabel="Daily spend trend"
        emptyReasonCode="no_data_for_range"
      />,
    );
    expect(await axe(container)).toHaveNoViolations();
  });
});
