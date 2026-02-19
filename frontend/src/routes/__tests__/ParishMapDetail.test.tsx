import '@testing-library/jest-dom';
import { render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { describe, expect, it, vi } from 'vitest';

import ParishMapDetail from '../ParishMapDetail';

const routerFuture = {
  v7_startTransition: true,
  v7_relativeSplatPath: true,
} as const;

vi.mock('../../components/ParishMap', () => ({
  __esModule: true,
  default: () => <div data-testid="parish-map-mock" />,
}));

describe('ParishMapDetail', () => {
  it('renders a back button and the full-width map panel', () => {
    render(
      <MemoryRouter future={routerFuture}>
        <ParishMapDetail />
      </MemoryRouter>,
    );

    expect(screen.getByRole('button', { name: /back to dashboard/i })).toBeInTheDocument();
    expect(screen.getByRole('heading', { level: 2, name: /parish heatmap/i })).toBeInTheDocument();
    expect(screen.getByTestId('parish-map-mock')).toBeInTheDocument();
  });
});
