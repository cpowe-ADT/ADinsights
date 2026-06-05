import { render, screen } from '@testing-library/react';
import { axe } from 'jest-axe';
import { describe, expect, it } from 'vitest';

import PieComposition from './PieComposition';

const data = [
  { label: 'Mobile', value: 60 },
  { label: 'Desktop', value: 30 },
  { label: 'Tablet', value: 10 },
];

describe('PieComposition', () => {
  it('renders with role="img" and aria-label', () => {
    render(<PieComposition data={data} ariaLabel="Spend by device" />);
    expect(screen.getByRole('img', { name: /spend by device/i })).toBeInTheDocument();
  });

  it('renders a hidden accessible table with shares', () => {
    const { container } = render(<PieComposition data={data} ariaLabel="Spend by device" />);
    const table = container.querySelector('table.sr-only');
    expect(table).toBeInTheDocument();
    const headers = Array.from(table?.querySelectorAll('thead th') ?? []).map((h) => h.textContent);
    expect(headers).toEqual(['Label', 'Value', 'Share']);
    expect(table?.querySelectorAll('tbody tr').length).toBe(data.length);
  });

  it('renders center label when provided on a donut', () => {
    render(
      <PieComposition
        data={data}
        innerRadius={60}
        centerLabel="Total: 100"
        ariaLabel="Device share"
      />,
    );
    expect(screen.getByText('Total: 100')).toBeInTheDocument();
  });

  it('renders skeleton when isLoading', () => {
    const { container } = render(<PieComposition data={[]} ariaLabel="Device share" isLoading />);
    expect(container.querySelector('.viz-chart-skeleton')).toBeInTheDocument();
  });

  it('renders EmptyState with reason code when empty', () => {
    const { container } = render(
      <PieComposition data={[]} ariaLabel="Device share" emptyReasonCode="no_data_for_range" />,
    );
    expect(container.querySelector('[data-reason-code="no_data_for_range"]')).toBeInTheDocument();
  });

  it('has no a11y violations', async () => {
    const { container } = render(<PieComposition data={data} ariaLabel="Spend by device" />);
    expect(await axe(container)).toHaveNoViolations();
  });
});
