import { render, screen, waitFor } from '@testing-library/react';
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

function renderWithRoute(summaryId = '1') {
  return render(
    <MemoryRouter initialEntries={[`/summaries/${summaryId}`]}>
      <Routes>
        <Route path="/summaries/:summaryId" element={<SummaryDetailPage />} />
      </Routes>
    </MemoryRouter>,
  );
}

const baseSummary = {
  id: '1',
  title: 'Daily Summary 2026-04-10',
  summary: 'Performance was strong across all campaigns.',
  payload: { impressions: 12000, clicks: 300 },
  source: 'daily_summary',
  model_name: 'gpt-4',
  status: 'generated' as const,
  generated_at: '2026-04-10T06:10:00Z',
  created_at: '2026-04-10T06:10:00Z',
  updated_at: '2026-04-10T06:10:00Z',
};

describe('SummaryDetailPage', () => {
  beforeEach(() => {
    phase2ApiMock.getSummary.mockResolvedValue(baseSummary);
  });

  it('shows source badge on detail page', async () => {
    renderWithRoute();

    await waitFor(() => expect(phase2ApiMock.getSummary).toHaveBeenCalled());
    expect(screen.getByText('Daily summary')).toBeInTheDocument();
  });

  it('payload section is collapsible', async () => {
    const user = userEvent.setup();
    renderWithRoute();

    await waitFor(() => expect(phase2ApiMock.getSummary).toHaveBeenCalled());

    // Payload should not be visible initially
    expect(screen.queryByText(/"impressions"/)).not.toBeInTheDocument();

    // Click the toggle button
    const toggle = screen.getByRole('button', { name: /raw payload/i });
    await user.click(toggle);

    // Payload should now be visible
    expect(screen.getByText(/"impressions"/)).toBeInTheDocument();
  });

  it('shows model name when present', async () => {
    renderWithRoute();

    await waitFor(() => expect(phase2ApiMock.getSummary).toHaveBeenCalled());
    expect(screen.getByText(/Model: gpt-4/)).toBeInTheDocument();
  });
});
