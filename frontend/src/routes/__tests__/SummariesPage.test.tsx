import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
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

vi.mock('../../lib/format', () => ({
  formatRelativeTime: (v: string) => `rel(${v})`,
  formatAbsoluteTime: (v: string) => `abs(${v})`,
}));

function renderPage() {
  return render(
    <MemoryRouter>
      <SummariesPage />
    </MemoryRouter>,
  );
}

describe('SummariesPage', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('renders table with summary data', async () => {
    phase2ApiMock.listSummaries.mockResolvedValue([
      {
        id: 's1',
        title: 'Weekly overview',
        summary: 'Summary text',
        payload: {},
        source: 'openai',
        model_name: 'gpt-4',
        status: 'generated',
        generated_at: '2026-04-01T12:00:00Z',
        created_at: '2026-04-01T12:00:00Z',
        updated_at: '2026-04-01T12:00:00Z',
      },
    ]);

    renderPage();

    expect(await screen.findByText('Weekly overview')).toBeInTheDocument();
    expect(screen.getByText('generated')).toBeInTheDocument();
    expect(screen.getByText('openai')).toBeInTheDocument();
    expect(screen.getByRole('link', { name: 'Open' })).toHaveAttribute('href', '/summaries/s1');
  });

  it('shows empty state when no summaries', async () => {
    phase2ApiMock.listSummaries.mockResolvedValue([]);

    renderPage();

    expect(await screen.findByText('No summaries yet')).toBeInTheDocument();
    expect(screen.getByText('Generate a summary to seed this timeline.')).toBeInTheDocument();
  });

  it('shows error state when API fails', async () => {
    phase2ApiMock.listSummaries.mockRejectedValue(new Error('Network error'));

    renderPage();

    expect(await screen.findByText('Summaries unavailable')).toBeInTheDocument();
    expect(screen.getByText('Network error')).toBeInTheDocument();
  });

  it('refresh list button reloads data', async () => {
    phase2ApiMock.listSummaries.mockResolvedValue([]);

    renderPage();

    await screen.findByText('No summaries yet');

    phase2ApiMock.listSummaries.mockResolvedValue([
      {
        id: 's2',
        title: 'New summary',
        summary: 'text',
        payload: {},
        source: 'openai',
        model_name: 'gpt-4',
        status: 'generated',
        generated_at: '2026-04-02T12:00:00Z',
        created_at: '2026-04-02T12:00:00Z',
        updated_at: '2026-04-02T12:00:00Z',
      },
    ]);

    const user = userEvent.setup();
    await user.click(screen.getByRole('button', { name: 'Refresh list' }));

    expect(await screen.findByText('New summary')).toBeInTheDocument();
  });

  it('generate new summary button calls refreshSummary', async () => {
    phase2ApiMock.listSummaries.mockResolvedValue([]);
    phase2ApiMock.refreshSummary.mockResolvedValue({
      id: 's3',
      title: 'Generated',
      summary: 'text',
      payload: {},
      source: 'openai',
      model_name: 'gpt-4',
      status: 'generated',
      generated_at: '2026-04-03T12:00:00Z',
      created_at: '2026-04-03T12:00:00Z',
      updated_at: '2026-04-03T12:00:00Z',
    });

    renderPage();

    await screen.findByText('No summaries yet');

    const user = userEvent.setup();
    await user.click(screen.getByRole('button', { name: 'Generate new summary' }));

    await waitFor(() => expect(phase2ApiMock.refreshSummary).toHaveBeenCalled());
  });

  it('retry action reloads data after error', async () => {
    phase2ApiMock.listSummaries.mockRejectedValueOnce(new Error('fail'));

    renderPage();

    await screen.findByText('Summaries unavailable');

    phase2ApiMock.listSummaries.mockResolvedValue([]);

    const user = userEvent.setup();
    await user.click(screen.getByRole('button', { name: 'Retry' }));

    expect(await screen.findByText('No summaries yet')).toBeInTheDocument();
  });
});
