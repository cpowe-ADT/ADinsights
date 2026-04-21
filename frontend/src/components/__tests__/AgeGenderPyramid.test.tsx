import '@testing-library/jest-dom';
import { render, screen } from '@testing-library/react';
import { axe } from 'jest-axe';
import { describe, expect, it, vi } from 'vitest';

import AgeGenderPyramid from '../AgeGenderPyramid';
import type { AgeGenderBreakdown } from '../../state/useDashboardStore';

// Recharts needs a real width in JSDOM; ResponsiveContainer reads parent dims.
// Stub so the chart mounts without the usual "width(0) and height(0) are too
// small" warning clogging the test output.
vi.mock('recharts', async () => {
  const actual = await vi.importActual<typeof import('recharts')>('recharts');
  return {
    ...actual,
    ResponsiveContainer: ({ children }: { children: React.ReactNode }) => (
      <div style={{ width: 600, height: 320 }}>{children}</div>
    ),
  };
});

const sample: AgeGenderBreakdown[] = [
  {
    ageRange: '18-24',
    gender: 'male',
    impressions: 1000,
    reach: 600,
    clicks: 40,
    spend: 20,
    conversions: 2,
  },
  {
    ageRange: '18-24',
    gender: 'female',
    impressions: 1200,
    reach: 700,
    clicks: 50,
    spend: 25,
    conversions: 3,
  },
  {
    ageRange: '25-34',
    gender: 'male',
    impressions: 2000,
    reach: 1200,
    clicks: 80,
    spend: 50,
    conversions: 5,
  },
];

describe('AgeGenderPyramid — a11y', () => {
  it('renders a role="img" region with the caller-supplied ariaLabel', () => {
    render(
      <AgeGenderPyramid
        data={sample}
        metric="impressions"
        ariaLabel="Audience pyramid for Q1"
      />,
    );
    const region = screen.getByRole('img', { name: 'Audience pyramid for Q1' });
    expect(region).toBeInTheDocument();
  });

  it('falls back to a metric-keyed default label when ariaLabel is omitted', () => {
    render(<AgeGenderPyramid data={sample} metric="reach" />);
    const region = screen.getByRole('img', {
      name: /age and gender pyramid by reach/i,
    });
    expect(region).toBeInTheDocument();
  });

  it('has no axe violations on a populated default render', async () => {
    const { container } = render(
      <AgeGenderPyramid
        data={sample}
        metric="impressions"
        ariaLabel="Audience pyramid"
      />,
    );
    const results = await axe(container);
    expect(results).toHaveNoViolations();
  });

  it('renders with empty data without throwing (degrades quietly)', () => {
    render(
      <AgeGenderPyramid data={[]} metric="impressions" ariaLabel="Empty pyramid" />,
    );
    // Region still present so screen readers get the label even when the
    // chart has no bars — caller is responsible for swapping in an EmptyState
    // upstream, but the component itself should not crash.
    expect(
      screen.getByRole('img', { name: 'Empty pyramid' }),
    ).toBeInTheDocument();
  });
});
