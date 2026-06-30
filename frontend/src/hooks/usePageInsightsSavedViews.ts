import { useCallback, useEffect, useState } from 'react';

import {
  deletePageInsightsView,
  listPageInsightsSavedViews,
  savePageInsightsView,
  type PageInsightsSavedView,
} from '../lib/metaPageInsights';

type Status = 'idle' | 'loading' | 'loaded' | 'error';

export default function usePageInsightsSavedViews(pageId: string) {
  const [views, setViews] = useState<PageInsightsSavedView[]>([]);
  const [status, setStatus] = useState<Status>('idle');
  const [error, setError] = useState<string | undefined>();

  const load = useCallback(async () => {
    if (!pageId) return;
    setStatus('loading');
    try {
      const result = await listPageInsightsSavedViews(pageId);
      setViews(result);
      setStatus('loaded');
      setError(undefined);
    } catch (err) {
      setStatus('error');
      setError(err instanceof Error ? err.message : 'Failed to load saved views');
    }
  }, [pageId]);

  useEffect(() => {
    void load();
  }, [load]);

  const save = useCallback(
    async (name: string, filters: PageInsightsSavedView['filters']) => {
      const created = await savePageInsightsView(name, { ...filters, page_id: pageId });
      setViews((prev) => [created, ...prev]);
      return created;
    },
    [pageId],
  );

  const remove = useCallback(async (id: string) => {
    await deletePageInsightsView(id);
    setViews((prev) => prev.filter((v) => v.id !== id));
  }, []);

  return { views, status, error, load, save, remove };
}
