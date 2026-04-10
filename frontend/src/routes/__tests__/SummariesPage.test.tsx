import { render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import SummariesPage from '../SummariesPage';

const phase2ApiMock = vi.hoisted(() => ({
  listSummaries: vi.fn(),
  refreshSummary: vi.fn(),
}));

vi.mock('../../lib/phase2Api', () => ({
  listSummaries: phase2ApiMock.listSummaries,
  refreshSummary: phase2ApiMock.refreshSummary,
}));

describe('SummariesPage', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('renders summaries table when data is available', async () => {
    phase2ApiMock.listSummaries.mockResolvedValue([
      {
        id: 'summary-1',
        title: 'Weekly performance digest',
        summary: 'Spend increased 12% WoW.',
        payload: {},
        source: 'openai',
        model_name: 'gpt-4',
        status: 'generated',
        generated_at: '2026-04-01T12:00:00Z',
        created_at: '2026-04-01T12:00:00Z',
        updated_at: '2026-04-01T12:00:00Z',
      },
    ]);

    render(
      <MemoryRouter>
        <SummariesPage />
      </MemoryRouter>,
    );

    await waitFor(() => expect(phase2ApiMock.listSummaries).toHaveBeenCalled());
    expect(screen.getByRole('heading', { name: 'Summaries' })).toBeInTheDocument();
    expect(screen.getByText('Weekly performance digest')).toBeInTheDocument();
    expect(screen.getByText('generated')).toBeInTheDocument();
    expect(screen.getByText('openai')).toBeInTheDocument();
  });

  it('shows empty state when no summaries exist', async () => {
    phase2ApiMock.listSummaries.mockResolvedValue([]);

    render(
      <MemoryRouter>
        <SummariesPage />
      </MemoryRouter>,
    );

    await waitFor(() => expect(phase2ApiMock.listSummaries).toHaveBeenCalled());
    expect(screen.getByText('No summaries yet')).toBeInTheDocument();
  });

  it('shows error state when fetch fails', async () => {
    phase2ApiMock.listSummaries.mockRejectedValue(new Error('Service unavailable'));

    render(
      <MemoryRouter>
        <SummariesPage />
      </MemoryRouter>,
    );

    await waitFor(() => expect(phase2ApiMock.listSummaries).toHaveBeenCalled());
    expect(screen.getByText('Summaries unavailable')).toBeInTheDocument();
    expect(screen.getByText('Service unavailable')).toBeInTheDocument();
  });
});
