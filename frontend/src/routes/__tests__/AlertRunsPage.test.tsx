import { render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import AlertRunsPage from '../AlertRunsPage';

const phase2ApiMock = vi.hoisted(() => ({
  listAlertRuns: vi.fn(),
}));

vi.mock('../../lib/phase2Api', () => ({
  listAlertRuns: phase2ApiMock.listAlertRuns,
}));

const mockRuns = [
  {
    id: 'run-1',
    rule_slug: 'high-spend',
    rule_name: 'High Spend Alert',
    rule_description: null,
    severity: 'critical',
    status: 'success' as const,
    row_count: 12,
    llm_summary: 'Spend exceeded threshold across 3 campaigns in Kingston parish.',
    error_message: '',
    duration_ms: 1250,
    created_at: '2026-04-10T10:00:00Z',
    completed_at: '2026-04-10T10:00:01Z',
  },
  {
    id: 'run-2',
    rule_slug: 'low-ctr',
    rule_name: null,
    rule_description: null,
    severity: 'warning',
    status: 'failed' as const,
    row_count: 0,
    llm_summary: '',
    error_message: 'Query timeout after 30s',
    duration_ms: 30000,
    created_at: '2026-04-10T09:00:00Z',
    completed_at: null,
  },
  {
    id: 'run-3',
    rule_slug: 'no-impressions',
    rule_name: 'No Impressions Check',
    rule_description: null,
    severity: null,
    status: 'no_results' as const,
    row_count: 0,
    llm_summary: 'No campaigns matched the threshold criteria.',
    error_message: '',
    duration_ms: 340,
    created_at: '2026-04-10T08:00:00Z',
    completed_at: '2026-04-10T08:00:00Z',
  },
];

describe('AlertRunsPage', () => {
  beforeEach(() => {
    phase2ApiMock.listAlertRuns.mockResolvedValue({
      count: mockRuns.length,
      next: null,
      previous: null,
      results: mockRuns,
    });
  });

  it('renders alert runs table after loading', async () => {
    render(
      <MemoryRouter>
        <AlertRunsPage />
      </MemoryRouter>,
    );

    await waitFor(() => expect(phase2ApiMock.listAlertRuns).toHaveBeenCalled());
    expect(screen.getByText('High Spend Alert')).toBeInTheDocument();
    expect(screen.getByText('low-ctr')).toBeInTheDocument();
    expect(screen.getByText('No Impressions Check')).toBeInTheDocument();
    expect(screen.getByText(/Showing 3 of 3 runs/)).toBeInTheDocument();
  });

  it('shows status filter buttons', async () => {
    render(
      <MemoryRouter>
        <AlertRunsPage />
      </MemoryRouter>,
    );

    await waitFor(() => expect(phase2ApiMock.listAlertRuns).toHaveBeenCalled());
    expect(screen.getByRole('button', { name: 'All' })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Success' })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'No Results' })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Partial' })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Failed' })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Started' })).toBeInTheDocument();
  });

  it('shows empty state when no runs exist', async () => {
    phase2ApiMock.listAlertRuns.mockResolvedValue({
      count: 0,
      next: null,
      previous: null,
      results: [],
    });

    render(
      <MemoryRouter>
        <AlertRunsPage />
      </MemoryRouter>,
    );

    await waitFor(() => expect(phase2ApiMock.listAlertRuns).toHaveBeenCalled());
    expect(screen.getByText('No alert runs')).toBeInTheDocument();
  });

  it('displays run status pills with correct classes', async () => {
    render(
      <MemoryRouter>
        <AlertRunsPage />
      </MemoryRouter>,
    );

    await waitFor(() => expect(phase2ApiMock.listAlertRuns).toHaveBeenCalled());

    const successPill = screen.getByText('success');
    expect(successPill).toHaveClass('phase2-pill', 'phase2-pill--fresh');

    const failedPill = screen.getByText('failed');
    expect(failedPill).toHaveClass('phase2-pill', 'phase2-pill--failed');

    const noResultsPill = screen.getByText('no results');
    expect(noResultsPill).toHaveClass('phase2-pill', 'phase2-pill--inactive');
  });
});
