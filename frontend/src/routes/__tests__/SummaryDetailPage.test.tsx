import { render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import SummaryDetailPage from '../SummaryDetailPage';

const phase2ApiMock = vi.hoisted(() => ({
  getSummary: vi.fn(),
}));

vi.mock('../../lib/phase2Api', () => ({
  getSummary: phase2ApiMock.getSummary,
}));

vi.mock('react-router-dom', async () => {
  const actual = await vi.importActual('react-router-dom');
  return { ...actual, useParams: () => ({ summaryId: 'sum-1' }) };
});

describe('SummaryDetailPage', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('renders summary detail', async () => {
    phase2ApiMock.getSummary.mockResolvedValue({
      id: 'sum-1',
      title: 'Daily Recap',
      status: 'generated',
      source: 'ai',
      summary: 'Performance was strong across all campaigns.',
      payload: { top_metric: 'roas' },
      generated_at: '2026-04-09T06:10:00Z',
    });

    render(
      <MemoryRouter>
        <SummaryDetailPage />
      </MemoryRouter>,
    );

    await waitFor(() => expect(phase2ApiMock.getSummary).toHaveBeenCalled());
    expect(screen.getByRole('heading', { name: 'Daily Recap' })).toBeInTheDocument();
    expect(
      screen.getByText('Performance was strong across all campaigns.'),
    ).toBeInTheDocument();
  });

  it('shows error state', async () => {
    phase2ApiMock.getSummary.mockRejectedValue(new Error('Network error'));

    render(
      <MemoryRouter>
        <SummaryDetailPage />
      </MemoryRouter>,
    );

    await waitFor(() => expect(phase2ApiMock.getSummary).toHaveBeenCalled());
    expect(screen.getByText('Summary unavailable')).toBeInTheDocument();
  });
});
