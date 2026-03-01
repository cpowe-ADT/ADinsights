import { act, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import useMetaPageExports from './useMetaPageExports';

const exportMocks = vi.hoisted(() => ({
  listMetaPageExports: vi.fn(),
  createMetaPageExport: vi.fn(),
  downloadExportArtifact: vi.fn(),
}));

const downloadMocks = vi.hoisted(() => ({
  saveBlobAsFile: vi.fn(),
}));

vi.mock('../lib/metaPageInsights', () => ({
  listMetaPageExports: exportMocks.listMetaPageExports,
  createMetaPageExport: exportMocks.createMetaPageExport,
  downloadExportArtifact: exportMocks.downloadExportArtifact,
}));

vi.mock('../lib/download', () => ({
  saveBlobAsFile: downloadMocks.saveBlobAsFile,
}));

type HarnessProps = {
  pageId?: string;
};

const sampleJob = {
  id: 'job-1',
  report_id: 'report-1',
  export_format: 'csv' as const,
  status: 'completed' as const,
  artifact_path: '/tmp/export.csv',
  error_message: '',
  metadata: {},
  completed_at: null,
  created_at: '2026-02-21T00:00:00Z',
  updated_at: '2026-02-21T00:00:00Z',
};

const ExportHarness = ({ pageId = 'page-1' }: HarnessProps) => {
  const { jobs, status, createExport, download } = useMetaPageExports(pageId);
  return (
    <div>
      <span data-testid="status">{status}</span>
      <span data-testid="jobs-count">{jobs.length}</span>
      <button
        type="button"
        onClick={() =>
          void createExport({
            export_format: 'csv',
            date_preset: 'last_28d',
          })
        }
      >
        Create export
      </button>
      <button type="button" onClick={() => void download('job-1')}>
        Download export
      </button>
    </div>
  );
};

describe('useMetaPageExports', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('loads exports on mount', async () => {
    exportMocks.listMetaPageExports.mockResolvedValue([sampleJob]);

    render(<ExportHarness />);

    await waitFor(() => expect(exportMocks.listMetaPageExports).toHaveBeenCalledWith('page-1'));
    expect(screen.getByTestId('jobs-count').textContent).toBe('1');
    expect(screen.getByTestId('status').textContent).toBe('idle');
  });

  it('creates export and refreshes history', async () => {
    exportMocks.listMetaPageExports
      .mockResolvedValueOnce([])
      .mockResolvedValueOnce([sampleJob]);
    exportMocks.createMetaPageExport.mockResolvedValue(sampleJob);

    render(<ExportHarness />);

    await waitFor(() => expect(exportMocks.listMetaPageExports).toHaveBeenCalledTimes(1));

    await act(async () => {
      fireEvent.click(screen.getByRole('button', { name: 'Create export' }));
    });

    await waitFor(() =>
      expect(exportMocks.createMetaPageExport).toHaveBeenCalledWith('page-1', {
        export_format: 'csv',
        date_preset: 'last_28d',
      }),
    );
    await waitFor(() => expect(exportMocks.listMetaPageExports).toHaveBeenCalledTimes(2));
    expect(screen.getByTestId('jobs-count').textContent).toBe('1');
  });

  it('downloads artifacts through shared file helper', async () => {
    exportMocks.listMetaPageExports.mockResolvedValue([]);
    const blob = new Blob(['id,value\n1,2']);
    exportMocks.downloadExportArtifact.mockResolvedValue({
      blob,
      filename: 'export.csv',
      contentType: 'text/csv',
    });

    render(<ExportHarness />);

    await waitFor(() => expect(exportMocks.listMetaPageExports).toHaveBeenCalledTimes(1));

    await act(async () => {
      fireEvent.click(screen.getByRole('button', { name: 'Download export' }));
    });

    await waitFor(() => expect(exportMocks.downloadExportArtifact).toHaveBeenCalledWith('job-1'));
    expect(downloadMocks.saveBlobAsFile).toHaveBeenCalledWith(blob, 'export.csv');
  });
});
