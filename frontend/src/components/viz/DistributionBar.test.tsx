import { render, screen } from '@testing-library/react';
import { axe } from 'jest-axe';
import { describe, expect, it } from 'vitest';

import DistributionBar from './DistributionBar';

const data = [
  { label: 'Kingston', value: 100 },
  { label: 'St. Andrew', value: 80 },
  { label: 'Clarendon', value: 60 },
];

describe('DistributionBar', () => {
  it('renders chart with role="img" and aria-label', () => {
    render(<DistributionBar data={data} ariaLabel="Spend by parish" />);
    expect(screen.getByRole('img', { name: /spend by parish/i })).toBeInTheDocument();
  });

  it('renders a hidden accessible table with one row per datum', () => {
    const { container } = render(
      <DistributionBar data={data} ariaLabel="Spend by parish" />,
    );
    const table = container.querySelector('table.sr-only');
    expect(table).toBeInTheDocument();
    expect(table?.querySelectorAll('tbody tr').length).toBe(data.length);
  });

  it('renders share column when showPercent', () => {
    const { container } = render(
      <DistributionBar data={data} ariaLabel="Spend share" showPercent />,
    );
    const headers = Array.from(
      container.querySelectorAll('table.sr-only thead th'),
    ).map((h) => h.textContent);
    expect(headers).toContain('Share');
  });

  it('renders skeleton when isLoading', () => {
    const { container } = render(
      <DistributionBar data={[]} ariaLabel="Spend" isLoading />,
    );
    expect(container.querySelector('.viz-chart-skeleton')).toBeInTheDocument();
  });

  it('renders EmptyState with reason code when data empty', () => {
    const { container } = render(
      <DistributionBar
        data={[]}
        ariaLabel="Spend"
        emptyReasonCode="no_data_for_range"
      />,
    );
    expect(
      container.querySelector('[data-reason-code="no_data_for_range"]'),
    ).toBeInTheDocument();
  });

  it('has no a11y violations', async () => {
    const { container } = render(
      <DistributionBar data={data} ariaLabel="Spend by parish" />,
    );
    expect(await axe(container)).toHaveNoViolations();
  });

  it('has no a11y violations in empty state', async () => {
    const { container } = render(
      <DistributionBar data={[]} ariaLabel="Spend" emptyReasonCode="no_data_for_range" />,
    );
    expect(await axe(container)).toHaveNoViolations();
  });
});
