import { useCallback, useEffect, useState } from 'react';

import { saveBlobAsFile } from '../lib/download';
import {
  createMetaPageExport,
  downloadExportArtifact,
  listMetaPageExports,
  type MetaExportJob,
} from '../lib/metaPageInsights';

type ExportStatus = 'idle' | 'loading' | 'error';

function getErrorMessage(error: unknown, fallback: string): string {
  if (error instanceof Error && error.message) {
    return error.message;
  }
  return fallback;
}

const useMetaPageExports = (pageId: string) => {
  const [jobs, setJobs] = useState<MetaExportJob[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [status, setStatus] = useState<ExportStatus>('idle');

  const refresh = useCallback(async () => {
    if (!pageId) {
      setJobs([]);
      setError(null);
      setStatus('idle');
      return;
    }
    setStatus('loading');
    setError(null);
    try {
      const exportJobs = await listMetaPageExports(pageId);
      setJobs(exportJobs);
      setStatus('idle');
    } catch (loadError) {
      setStatus('error');
      setError(getErrorMessage(loadError, 'Unable to load exports.'));
    }
  }, [pageId]);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  const createExport = useCallback(
    async (payload: Parameters<typeof createMetaPageExport>[1]) => {
      if (!pageId) {
        return;
      }
      setStatus('loading');
      setError(null);
      try {
        await createMetaPageExport(pageId, payload);
        await refresh();
      } catch (createError) {
        setStatus('error');
        setError(getErrorMessage(createError, 'Unable to create export.'));
      }
    },
    [pageId, refresh],
  );

  const download = useCallback(async (jobId: string) => {
    const { blob, filename } = await downloadExportArtifact(jobId);
    saveBlobAsFile(blob, filename);
  }, []);

  return {
    jobs,
    error,
    status,
    refresh,
    createExport,
    download,
  };
};

export default useMetaPageExports;
