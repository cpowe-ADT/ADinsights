import '@testing-library/jest-dom';
import { render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import CsvUploadDetail from '../CsvUploadDetail';

const dataServiceMocks = vi.hoisted(() => ({
  fetchUploadStatus: vi.fn(),
}));

vi.mock('../../lib/dataService', async () => {
  const actual = await vi.importActual('../../lib/dataService');
  return {
    ...actual,
    fetchUploadStatus: dataServiceMocks.fetchUploadStatus,
  };
});

function renderWithRouter(uploadId = 'current', state?: Record<string, unknown>) {
  return render(
    <MemoryRouter
      initialEntries={[{ pathname: `/dashboards/uploads/${uploadId}`, state }]}
    >
      <Routes>
        <Route path="/dashboards/uploads/:uploadId" element={<CsvUploadDetail />} />
      </Routes>
    </MemoryRouter>,
  );
}

describe('CsvUploadDetail', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('renders upload detail information from route state', () => {
    renderWithRouter('current', {
      status: {
        has_upload: true,
        snapshot_generated_at: '2026-04-10T14:00:00Z',
        counts: { campaign_rows: 25, parish_rows: 14, budget_rows: 3 },
      },
    });

    expect(screen.getByText('CSV Uploads')).toBeInTheDocument();
    expect(screen.getByText('Upload (current)')).toBeInTheDocument();
    expect(screen.getByText('Upload summary')).toBeInTheDocument();
    expect(screen.getByText('25')).toBeInTheDocument();
    expect(screen.getByText('14')).toBeInTheDocument();
    expect(screen.getByText('3')).toBeInTheDocument();
    expect(screen.getByText('42')).toBeInTheDocument(); // total
    expect(screen.getByText('campaign, parish, budget')).toBeInTheDocument();
  });

  it('shows back to uploads link', () => {
    renderWithRouter('current', {
      status: {
        has_upload: true,
        snapshot_generated_at: '2026-04-10T14:00:00Z',
        counts: { campaign_rows: 10, parish_rows: 0, budget_rows: 0 },
      },
    });

    const backLink = screen.getByRole('link', { name: /back to uploads/i });
    expect(backLink).toBeInTheDocument();
    expect(backLink).toHaveAttribute('href', '/dashboards/uploads');
  });

  it('shows empty state when upload not found', async () => {
    dataServiceMocks.fetchUploadStatus.mockResolvedValue({ has_upload: false });

    renderWithRouter('nonexistent');

    await waitFor(() => {
      expect(screen.getByText('Upload not found')).toBeInTheDocument();
    });

    expect(screen.getByText('No upload data')).toBeInTheDocument();
    expect(
      screen.getByText('This upload does not exist or has been cleared.'),
    ).toBeInTheDocument();

    const backLink = screen.getByRole('link', { name: /back to uploads/i });
    expect(backLink).toBeInTheDocument();
  });

  it('shows error state when fetch fails', async () => {
    dataServiceMocks.fetchUploadStatus.mockRejectedValue(
      new Error('Network error'),
    );

    renderWithRouter('current');

    await waitFor(() => {
      expect(screen.getByText('Upload unavailable')).toBeInTheDocument();
    });

    expect(screen.getByText('Network error')).toBeInTheDocument();
  });

  it('fetches from backend when no route state is provided', async () => {
    dataServiceMocks.fetchUploadStatus.mockResolvedValue({
      has_upload: true,
      snapshot_generated_at: '2026-04-09T10:00:00Z',
      counts: { campaign_rows: 50, parish_rows: 7, budget_rows: 0 },
    });

    renderWithRouter('current');

    await waitFor(() => {
      expect(screen.getByText('Upload summary')).toBeInTheDocument();
    });

    expect(screen.getByText('50')).toBeInTheDocument();
    expect(screen.getByText('7')).toBeInTheDocument();
    expect(screen.getByText('campaign, parish')).toBeInTheDocument();
    expect(dataServiceMocks.fetchUploadStatus).toHaveBeenCalledTimes(1);
  });
});
