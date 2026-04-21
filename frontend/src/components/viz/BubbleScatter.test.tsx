import { render, screen } from '@testing-library/react';
import { axe } from 'jest-axe';
import { describe, expect, it } from 'vitest';

import BubbleScatter from './BubbleScatter';
import type { BubbleScatterDatum } from './BubbleScatter';

const data: BubbleScatterDatum[] = [
  { id: 'a', label: 'Alpha', x: 10, y: 0.02, z: 80 },
  { id: 'b', label: 'Beta', x: 20, y: 0.05, z: 120, shape: 'triangle' },
  { id: 'c', label: 'Gamma', x: 30, y: 0.03, z: 60 },
];

describe('BubbleScatter', () => {
  it('renders chart with role="img" and aria-label', () => {
    render(
      <BubbleScatter
        data={data}
        xLabel="Spend"
        yLabel="CTR"
        zLabel="Conversions"
        ariaLabel="Campaign scatter"
      />,
    );
    expect(screen.getByRole('img', { name: /campaign scatter/i })).toBeInTheDocument();
  });

  it('renders a hidden accessible table with one row per bubble', () => {
    const { container } = render(
      <BubbleScatter
        data={data}
        xLabel="Spend"
        yLabel="CTR"
        zLabel="Conversions"
        ariaLabel="Campaign scatter"
      />,
    );
    const table = container.querySelector('table.sr-only');
    expect(table).toBeInTheDocument();
    expect(table?.querySelectorAll('tbody tr').length).toBe(data.length);
  });

  it('includes a Shape column for non-color categorical encoding', () => {
    const { container } = render(
      <BubbleScatter
        data={data}
        xLabel="Spend"
        yLabel="CTR"
        zLabel="Conversions"
        ariaLabel="Campaign scatter"
      />,
    );
    const headers = Array.from(
      container.querySelectorAll('table.sr-only thead th'),
    ).map((h) => h.textContent);
    expect(headers).toContain('Shape');
  });

  it('renders skeleton when isLoading', () => {
    const { container } = render(
      <BubbleScatter
        data={[]}
        xLabel="Spend"
        yLabel="CTR"
        zLabel="Conversions"
        ariaLabel="Campaign scatter"
        isLoading
      />,
    );
    expect(container.querySelector('.viz-chart-skeleton')).toBeInTheDocument();
  });

  it('renders EmptyState with reason code when data is empty', () => {
    const { container } = render(
      <BubbleScatter
        data={[]}
        xLabel="Spend"
        yLabel="CTR"
        zLabel="Conversions"
        ariaLabel="Campaign scatter"
        emptyReasonCode="no_data_for_scope"
      />,
    );
    expect(
      container.querySelector('[data-reason-code="no_data_for_scope"]'),
    ).toBeInTheDocument();
  });

  it('has no a11y violations', async () => {
    const { container } = render(
      <BubbleScatter
        data={data}
        xLabel="Spend"
        yLabel="CTR"
        zLabel="Conversions"
        ariaLabel="Campaign scatter"
      />,
    );
    expect(await axe(container)).toHaveNoViolations();
  });
});
