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

const mockSummaries = [
  {
    id: '1',
    title: 'Daily Summary 2026-04-10',
    summary: 'Performance was strong.',
    payload: {},
    source: 'daily_summary',
    model_name: 'gpt-4',
    status: 'generated' as const,
    generated_at: '2026-04-10T06:10:00Z',
    created_at: '2026-04-10T06:10:00Z',
    updated_at: '2026-04-10T06:10:00Z',
  },
  {
    id: '2',
    title: 'Manual Summary',
    summary: 'Ad hoc refresh.',
    payload: {},
    source: 'manual_refresh',
    model_name: 'gpt-4',
    status: 'generated' as const,
    generated_at: '2026-04-10T12:00:00Z',
    created_at: '2026-04-10T12:00:00Z',
    updated_at: '2026-04-10T12:00:00Z',
  },
];

describe('SummariesPage', () => {
  beforeEach(() => {
    phase2ApiMock.listSummaries.mockResolvedValue(mockSummaries);
    phase2ApiMock.refreshSummary.mockResolvedValue(mockSummaries[0]);
  });

  it('renders automatic generation info banner', async () => {
    render(
      <MemoryRouter>
        <SummariesPage />
      </MemoryRouter>,
    );

    await waitFor(() => expect(screen.getByText(/6:10 AM/)).toBeInTheDocument());
    expect(screen.getByText(/Automatic generation/)).toBeInTheDocument();
  });

  it('shows source badges in table', async () => {
    render(
      <MemoryRouter>
        <SummariesPage />
      </MemoryRouter>,
    );

    await waitFor(() => expect(phase2ApiMock.listSummaries).toHaveBeenCalled());
    expect(screen.getByText('Daily')).toBeInTheDocument();
    expect(screen.getByText('Manual')).toBeInTheDocument();
  });

  it('refresh button shows loading state', async () => {
    const user = userEvent.setup();
    // Make refreshSummary hang so we can observe the loading state
    phase2ApiMock.refreshSummary.mockReturnValue(new Promise(() => {}));

    render(
      <MemoryRouter>
        <SummariesPage />
      </MemoryRouter>,
    );

    await waitFor(() => expect(phase2ApiMock.listSummaries).toHaveBeenCalled());

    const button = screen.getByRole('button', { name: /generate new summary/i });
    await user.click(button);

    expect(screen.getByText('Generating…')).toBeInTheDocument();
  });
});
