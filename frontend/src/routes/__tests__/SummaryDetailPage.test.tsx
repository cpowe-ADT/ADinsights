import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import SummaryDetailPage from '../SummaryDetailPage';

const phase2ApiMock = vi.hoisted(() => ({
  getSummary: vi.fn(),
}));

vi.mock('../../lib/phase2Api', () => ({
  getSummary: phase2ApiMock.getSummary,
}));

vi.mock('../../lib/format', () => ({
  formatRelativeTime: (v: string) => `rel(${v})`,
  formatAbsoluteTime: (v: string) => `abs(${v})`,
}));

function renderPage(summaryId = 's1') {
  return render(
    <MemoryRouter initialEntries={[`/summaries/${summaryId}`]}>
      <Routes>
        <Route path="/summaries/:summaryId" element={<SummaryDetailPage />} />
        <Route path="/summaries" element={<div>Summaries list</div>} />
      </Routes>
    </MemoryRouter>,
  );
}

describe('SummaryDetailPage', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('renders summary detail with title, text, and payload', async () => {
    phase2ApiMock.getSummary.mockResolvedValue({
      id: 's1',
      title: 'Weekly digest',
      summary: 'Campaign spend increased by 12%.',
      payload: { campaigns: 5 },
      source: 'openai',
      model_name: 'gpt-4',
      status: 'generated',
      generated_at: '2026-04-01T12:00:00Z',
      created_at: '2026-04-01T12:00:00Z',
      updated_at: '2026-04-01T12:00:00Z',
    });

    renderPage();

    expect(await screen.findByText('Weekly digest')).toBeInTheDocument();
    expect(screen.getByText('Campaign spend increased by 12%.')).toBeInTheDocument();
    expect(screen.getByText('generated')).toBeInTheDocument();
    expect(screen.getByRole('link', { name: 'Back to summaries' })).toHaveAttribute(
      'href',
      '/summaries',
    );
  });

  it('shows error state when API fails', async () => {
    phase2ApiMock.getSummary.mockRejectedValue(new Error('Not found'));

    renderPage();

    expect(await screen.findByText('Summary unavailable')).toBeInTheDocument();
    expect(screen.getByText('Not found')).toBeInTheDocument();
  });

  it('retry reloads the summary', async () => {
    phase2ApiMock.getSummary.mockRejectedValueOnce(new Error('fail'));

    renderPage();

    await screen.findByText('Summary unavailable');

    phase2ApiMock.getSummary.mockResolvedValue({
      id: 's1',
      title: 'Recovered summary',
      summary: 'Text here',
      payload: {},
      source: 'openai',
      model_name: 'gpt-4',
      status: 'generated',
      generated_at: '2026-04-01T12:00:00Z',
      created_at: '2026-04-01T12:00:00Z',
      updated_at: '2026-04-01T12:00:00Z',
    });

    const user = userEvent.setup();
    await user.click(screen.getByRole('button', { name: 'Retry' }));

    expect(await screen.findByText('Recovered summary')).toBeInTheDocument();
  });

  it('displays payload as JSON', async () => {
    phase2ApiMock.getSummary.mockResolvedValue({
      id: 's1',
      title: 'Test summary',
      summary: 'text',
      payload: { key: 'value' },
      source: 'openai',
      model_name: 'gpt-4',
      status: 'generated',
      generated_at: '2026-04-01T12:00:00Z',
      created_at: '2026-04-01T12:00:00Z',
      updated_at: '2026-04-01T12:00:00Z',
    });

    renderPage();

    await screen.findByText('Test summary');
    expect(screen.getByText(/\"key\": \"value\"/)).toBeInTheDocument();
  });
});
