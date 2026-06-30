import { render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import CsvUpload from '../CsvUpload';

const dataServiceMock = vi.hoisted(() => ({
  fetchUploadStatus: vi.fn(),
  uploadMetrics: vi.fn(),
  clearUploadedMetrics: vi.fn(),
}));

const dashboardStoreMock = vi.hoisted(() => ({
  uploadedDataset: null as unknown,
  uploadedActive: false,
  setUploadedDataset: vi.fn(),
  setUploadedActive: vi.fn(),
  clearUploadedDataset: vi.fn(),
}));

vi.mock('../../lib/dataService', () => ({
  fetchUploadStatus: dataServiceMock.fetchUploadStatus,
  uploadMetrics: dataServiceMock.uploadMetrics,
  clearUploadedMetrics: dataServiceMock.clearUploadedMetrics,
}));

vi.mock('../../lib/uploadedMetrics', () => ({
  parseCampaignCsv: vi.fn(() => ({ rows: [], errors: [], warnings: [] })),
  parseParishCsv: vi.fn(() => ({ rows: [], errors: [], warnings: [] })),
  parseBudgetCsv: vi.fn(() => ({ rows: [], errors: [], warnings: [] })),
}));

vi.mock('../../lib/apiClient', () => ({
  ApiError: class extends Error {
    payload: unknown;
    status: number;
    constructor(msg: string) {
      super(msg);
      this.payload = {};
      this.status = 400;
    }
  },
}));

vi.mock('../../state/useDashboardStore', () => {
  const fn = (selector?: (s: typeof dashboardStoreMock) => unknown) =>
    selector ? selector(dashboardStoreMock) : dashboardStoreMock;
  fn.getState = () => dashboardStoreMock;
  fn.subscribe = () => () => {};
  return { __esModule: true, default: fn };
});

vi.mock('../../components/EmptyState', () => ({
  __esModule: true,
  default: ({ title, message }: { title: string; message: string }) => (
    <div>
      <h3>{title}</h3>
      <p>{message}</p>
    </div>
  ),
}));

describe('CsvUpload', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    dataServiceMock.fetchUploadStatus.mockResolvedValue({ has_upload: false });
  });

  it('renders upload CSV heading', () => {
    render(
      <MemoryRouter>
        <CsvUpload />
      </MemoryRouter>,
    );

    expect(screen.getByRole('heading', { name: 'Upload CSV data' })).toBeInTheDocument();
  });

  it('shows empty state when no CSVs uploaded', () => {
    render(
      <MemoryRouter>
        <CsvUpload />
      </MemoryRouter>,
    );

    expect(screen.getByText('No CSVs uploaded yet')).toBeInTheDocument();
  });

  it('renders three upload sections', () => {
    render(
      <MemoryRouter>
        <CsvUpload />
      </MemoryRouter>,
    );

    expect(screen.getByRole('heading', { name: 'Daily campaign metrics' })).toBeInTheDocument();
    expect(screen.getByRole('heading', { name: 'Parish metrics' })).toBeInTheDocument();
    expect(screen.getByRole('heading', { name: 'Monthly budgets' })).toBeInTheDocument();
  });
});
