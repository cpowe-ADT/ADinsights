import { render, screen } from '@testing-library/react';
import { axe } from 'jest-axe';
import { describe, expect, it } from 'vitest';

import GaugeRing, { derivePacingVariant } from './GaugeRing';

describe('GaugeRing', () => {
  it('renders with role="meter" and aria-value attributes', () => {
    render(<GaugeRing value={0.87} max={1.2} label="Pacing" variant="ok" ariaLabel="Pacing 87%" />);
    const meter = screen.getByRole('meter', { name: /pacing 87%/i });
    expect(meter).toBeInTheDocument();
    expect(meter).toHaveAttribute('aria-valuenow', '0.87');
    expect(meter).toHaveAttribute('aria-valuemin', '0');
    expect(meter).toHaveAttribute('aria-valuemax', '1.2');
    expect(meter).toHaveAttribute('aria-valuetext', '87%');
  });

  it('renders visible label and center percent', () => {
    render(<GaugeRing value={0.5} max={1.2} label="Pacing" ariaLabel="Pacing 50%" />);
    // "Pacing" appears both as visible label and as sr-only table row header;
    // assert at least one visible occurrence and the center percent.
    expect(screen.getAllByText('Pacing').length).toBeGreaterThanOrEqual(1);
    expect(screen.getAllByText('50%').length).toBeGreaterThanOrEqual(1);
  });

  it('renders a hidden accessible table describing the meter', () => {
    const { container } = render(
      <GaugeRing value={0.95} max={1.2} label="Pacing" ariaLabel="Pacing 95%" />,
    );
    const table = container.querySelector('table.sr-only');
    expect(table).toBeInTheDocument();
    expect(table?.querySelectorAll('tbody tr').length).toBeGreaterThanOrEqual(2);
  });

  it('clamps out-of-range values to max', () => {
    render(<GaugeRing value={5} max={1.2} label="Pacing" ariaLabel="Pacing 500%" />);
    const meter = screen.getByRole('meter');
    expect(meter).toHaveAttribute('aria-valuenow', '1.2');
  });

  it('renders skeleton when isLoading', () => {
    const { container } = render(
      <GaugeRing value={0.5} max={1.2} label="Pacing" ariaLabel="Pacing" isLoading />,
    );
    expect(container.querySelector('.viz-chart-skeleton')).toBeInTheDocument();
  });

  it('renders EmptyState when value is null/NaN', () => {
    const { container } = render(
      <GaugeRing
        value={Number.NaN}
        max={1.2}
        label="Pacing"
        ariaLabel="Pacing"
        emptyReasonCode="no_pacing_data"
      />,
    );
    expect(container.querySelector('[data-reason-code="no_pacing_data"]')).toBeInTheDocument();
  });

  it('renders tick-mark overlay for non-color threshold encoding', () => {
    const { container } = render(
      <GaugeRing value={0.87} max={1.2} label="Pacing" ariaLabel="Pacing 87%" />,
    );
    // Tick marks are rendered as <line> elements inside the overlay SVG.
    const lines = container.querySelectorAll('svg line');
    expect(lines.length).toBeGreaterThanOrEqual(4);
  });

  it('derivePacingVariant maps thresholds correctly', () => {
    expect(derivePacingVariant(0)).toBe('warning');
    expect(derivePacingVariant(0.5)).toBe('warning');
    expect(derivePacingVariant(0.85)).toBe('ok');
    expect(derivePacingVariant(1.0)).toBe('ok');
    expect(derivePacingVariant(1.2)).toBe('danger');
    expect(derivePacingVariant(-0.1)).toBe('danger');
  });

  it('exposes variant via data-variant for CSS targeting', () => {
    render(<GaugeRing value={1.3} max={1.5} label="Pacing" ariaLabel="Pacing 87%" />);
    const meter = screen.getByRole('meter');
    expect(meter).toHaveAttribute('data-variant', 'danger');
  });

  it('has no a11y violations', async () => {
    const { container } = render(
      <GaugeRing value={0.87} max={1.2} label="Pacing" ariaLabel="Pacing 87%" />,
    );
    expect(await axe(container)).toHaveNoViolations();
  });

  it('has no a11y violations in empty state', async () => {
    const { container } = render(
      <GaugeRing
        value={Number.NaN}
        max={1.2}
        label="Pacing"
        ariaLabel="Pacing"
        emptyReasonCode="no_pacing_data"
      />,
    );
    expect(await axe(container)).toHaveNoViolations();
  });
});
