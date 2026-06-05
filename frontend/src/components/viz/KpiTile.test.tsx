import { render, screen } from '@testing-library/react';
import { axe } from 'jest-axe';
import { describe, expect, it } from 'vitest';

import KpiTile from './KpiTile';

describe('KpiTile', () => {
  it('renders the formatted value and label', () => {
    render(<KpiTile label="Spend" value={24850} format="currency" currency="JMD" />);
    expect(screen.getByText('Spend')).toBeInTheDocument();
    // Currency formatter returns something containing the numeric portion.
    expect(screen.getByText(/24,850|24\.85K|24850/)).toBeInTheDocument();
  });

  it('renders the no-data dash with an aria-label when value is null', () => {
    render(<KpiTile label="Spend" value={null} format="currency" />);
    const valueNode = screen.getByLabelText('Spend: no data');
    expect(valueNode).toHaveTextContent('—');
  });

  it('renders a delta with aria-label describing direction', () => {
    render(<KpiTile label="Conversions" value={100} format="number" change={0.123} />);
    const delta = screen.getByLabelText(/increased by/i);
    expect(delta).toBeInTheDocument();
  });

  it('renders decreased aria-label for negative change', () => {
    render(<KpiTile label="CTR" value={0.04} format="percent" change={-0.05} />);
    expect(screen.getByLabelText(/decreased by/i)).toBeInTheDocument();
  });

  it('renders the skeleton when isLoading', () => {
    const { container } = render(<KpiTile label="Spend" value={null} isLoading />);
    const article = container.querySelector('article');
    expect(article).toHaveAttribute('aria-busy', 'true');
    expect(container.querySelector('.kpi-tile__skeleton')).toBeInTheDocument();
  });

  it('propagates reasonCode as data attribute', () => {
    const { container } = render(
      <KpiTile label="Spend" value={null} reasonCode="no_data_for_range" />,
    );
    expect(container.querySelector('article')).toHaveAttribute(
      'data-reason-code',
      'no_data_for_range',
    );
  });

  it('has no a11y violations', async () => {
    const { container } = render(
      <KpiTile
        label="Spend"
        value={24850}
        format="currency"
        currency="JMD"
        change={0.1}
        trend={[1, 2, 3, 4, 5]}
      />,
    );
    expect(await axe(container)).toHaveNoViolations();
  });

  it('has no a11y violations in loading state', async () => {
    const { container } = render(<KpiTile label="Spend" value={null} isLoading />);
    expect(await axe(container)).toHaveNoViolations();
  });
});
