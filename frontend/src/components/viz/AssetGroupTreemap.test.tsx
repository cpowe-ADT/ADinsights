import { render, screen } from '@testing-library/react';
import { axe } from 'jest-axe';
import { describe, expect, it } from 'vitest';

import AssetGroupTreemap, { roasToOpacity } from './AssetGroupTreemap';

const data = [
  { name: 'Launch Push', spend: 5200, roas: 1.6 },
  { name: 'Evergreen', spend: 3100, roas: 0.9 },
  { name: 'Remarket', spend: 1800, roas: 0.3 },
  { name: 'Prospecting', spend: 900, roas: 2.4 },
];

describe('AssetGroupTreemap', () => {
  it('renders chart with role="img" and aria-label', () => {
    render(<AssetGroupTreemap data={data} ariaLabel="PMax asset groups" />);
    expect(
      screen.getByRole('img', { name: /pmax asset groups/i }),
    ).toBeInTheDocument();
  });

  it('renders a hidden accessible table with one row per asset group', () => {
    const { container } = render(
      <AssetGroupTreemap data={data} ariaLabel="PMax asset groups" />,
    );
    const table = container.querySelector('table.sr-only');
    expect(table).toBeInTheDocument();
    expect(table?.querySelectorAll('tbody tr').length).toBe(data.length);
    const headers = Array.from(table?.querySelectorAll('thead th') ?? []).map(
      (h) => h.textContent,
    );
    expect(headers).toEqual(['Asset Group', 'Spend', 'ROAS']);
  });

  it('renders skeleton when isLoading', () => {
    const { container } = render(
      <AssetGroupTreemap data={[]} ariaLabel="PMax asset groups" isLoading />,
    );
    expect(container.querySelector('.viz-chart-skeleton')).toBeInTheDocument();
  });

  it('renders EmptyState with reason code when data empty', () => {
    const { container } = render(
      <AssetGroupTreemap
        data={[]}
        ariaLabel="PMax asset groups"
        emptyReasonCode="no_pmax_groups"
      />,
    );
    expect(
      container.querySelector('[data-reason-code="no_pmax_groups"]'),
    ).toBeInTheDocument();
  });

  it('maps ROAS to opacity within [0.3, 1.0] and clamps high values', () => {
    expect(roasToOpacity(0)).toBeCloseTo(0.3, 5);
    expect(roasToOpacity(2)).toBeCloseTo(1.0, 5);
    expect(roasToOpacity(4)).toBeCloseTo(1.0, 5);
    expect(roasToOpacity(1)).toBeCloseTo(0.65, 5);
    expect(roasToOpacity(undefined)).toBeCloseTo(0.6, 5);
  });

  it('renders a hatch pattern so encoding is not color-only', () => {
    const { container } = render(
      <AssetGroupTreemap data={data} ariaLabel="PMax asset groups" />,
    );
    expect(container.querySelector('#viz-treemap-hatch')).toBeInTheDocument();
  });

  it('has no a11y violations', async () => {
    const { container } = render(
      <AssetGroupTreemap data={data} ariaLabel="PMax asset groups" />,
    );
    expect(await axe(container)).toHaveNoViolations();
  });

  it('has no a11y violations in empty state', async () => {
    const { container } = render(
      <AssetGroupTreemap
        data={[]}
        ariaLabel="PMax asset groups"
        emptyReasonCode="no_pmax_groups"
      />,
    );
    expect(await axe(container)).toHaveNoViolations();
  });
});
