import { render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import SummaryDetailPage from '../SummaryDetailPage';
import type { AISummary } from '../../lib/phase2Api';

const phase2ApiMock = vi.hoisted(() => ({
  getSummary: vi.fn(),
}));

vi.mock('../../lib/phase2Api', () => ({
  getSummary: phase2ApiMock.getSummary,
}));

const sampleSummary: AISummary = {
  id: 'sum-1',
  title: 'Weekly Digest: April 1-7',
  summary: 'Ad spend increased 12% week-over-week with stable ROAS across Kingston parishes.',
  payload: { spend: 15200, roas: 3.4, top_parish: 'Kingston' },
  source: 'Daily',
  model_name: 'gpt-4o',
  status: 'generated',
  generated_at: '2026-04-07T06:00:00Z',
  created_at: '2026-04-07T06:00:00Z',
  updated_at: '2026-04-07T06:00:00Z',
};

function renderPage(summaryId = 'sum-1') {
  return render(
    <MemoryRouter initialEntries={[`/summaries/${summaryId}`]}>
      <Routes>
        <Route path="/summaries/:summaryId" element={<SummaryDetailPage />} />
      </Routes>
    </MemoryRouter>,
  );
}

describe('SummaryDetailPage', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    phase2ApiMock.getSummary.mockResolvedValue(sampleSummary);
  });

  it('renders summary title and text', async () => {
    renderPage();

    expect(await screen.findByRole('heading', { name: 'Weekly Digest: April 1-7' })).toBeInTheDocument();
    expect(
      screen.getByText('Ad spend increased 12% week-over-week with stable ROAS across Kingston parishes.'),
    ).toBeInTheDocument();
  });

  it('displays source badge', async () => {
    renderPage();

    await waitFor(() => expect(phase2ApiMock.getSummary).toHaveBeenCalledWith('sum-1'));

    // The status pill acts as the source badge on the detail page
    const statusPill = await screen.findByText('generated');
    expect(statusPill).toHaveClass('phase2-pill--generated');
  });

  it('displays status for Manual source summary', async () => {
    phase2ApiMock.getSummary.mockResolvedValue({
      ...sampleSummary,
      source: 'Manual',
      status: 'fallback',
    });

    renderPage();

    const pill = await screen.findByText('fallback');
    expect(pill).toHaveClass('phase2-pill--fallback');
  });

  it('has raw payload section with JSON content', async () => {
    renderPage();

    await screen.findByRole('heading', { name: 'Weekly Digest: April 1-7' });

    expect(screen.getByText('Payload snapshot')).toBeInTheDocument();

    const preElement = document.querySelector('.phase2-json');
    expect(preElement).not.toBeNull();
    expect(preElement!.textContent).toContain('"spend": 15200');
    expect(preElement!.textContent).toContain('"roas": 3.4');
    expect(preElement!.textContent).toContain('"top_parish": "Kingston"');
  });

  it('shows error state when API fails', async () => {
    phase2ApiMock.getSummary.mockRejectedValue(new Error('Summary not found'));

    renderPage();

    await waitFor(() => expect(screen.getByText('Summary unavailable')).toBeInTheDocument());
    expect(screen.getByText('Summary not found')).toBeInTheDocument();
  });

  it('renders back to summaries link', async () => {
    renderPage();

    await screen.findByRole('heading', { name: 'Weekly Digest: April 1-7' });

    const backLink = screen.getByRole('link', { name: /back to summaries/i });
    expect(backLink).toHaveAttribute('href', '/summaries');
  });
});
