import { useEffect, useState } from 'react';

import { appendQueryParams, get } from '../../lib/apiClient';
import { resolveFilterRange } from '../../lib/dashboardFilters';
import useDashboardStore from '../../state/useDashboardStore';
import ConversionsTabSection from '../../components/google-ads/workspace/tab-sections/ConversionsTabSection';
import {
  fetchGoogleAdsWorkspaceSummary,
  type GoogleAdsWorkspaceSummaryResponse,
} from '../../lib/googleAdsDashboard';
import type { GoogleAdsConversionActionRow } from '../../lib/googleAdsCreativeConvAggregates';

type ConversionsPayload = {
  count?: number;
  results?: GoogleAdsConversionActionRow[];
};

/**
 * Sprint 3 — Legacy Conversions page.
 *
 * Rewritten per architect §8.2. The funnel stage chart reads from the
 * workspace summary metrics (per architect §6.6 audit — NOT from the
 * conversions rows), so we fetch both in parallel.
 */
const GoogleAdsConversionsPage = () => {
  const [data, setData] = useState<ConversionsPayload | null>(null);
  const [summary, setSummary] =
    useState<GoogleAdsWorkspaceSummaryResponse | null>(null);
  const [status, setStatus] = useState<'idle' | 'loading' | 'success' | 'error'>(
    'loading',
  );
  const [error, setError] = useState('');

  const filters = useDashboardStore((state) => state.filters);

  useEffect(() => {
    let active = true;
    const load = async () => {
      setStatus('loading');
      setError('');
      try {
        const { start, end } = resolveFilterRange(filters);
        const commonParams = {
          platforms: 'google_ads',
          customer_id: filters.accountId || undefined,
          start_date: start || undefined,
          end_date: end || undefined,
        } as const;
        const rowsPath = appendQueryParams(
          '/analytics/google-ads/conversions/actions/',
          commonParams,
        );
        const [rowsResponse, summaryResponse] = await Promise.all([
          get<ConversionsPayload>(rowsPath),
          fetchGoogleAdsWorkspaceSummary({ ...commonParams }),
        ]);
        if (!active) return;
        setData(rowsResponse);
        setSummary(summaryResponse);
        setStatus('success');
      } catch (err) {
        if (!active) return;
        setError(
          err instanceof Error ? err.message : 'Failed to load conversions.',
        );
        setStatus('error');
      }
    };
    void load();
    return () => {
      active = false;
    };
  }, [filters]);

  return (
    <section className="dashboardPage">
      <header className="dashboardPageHeader">
        <p className="dashboardEyebrow">Google Ads</p>
        <h1 className="dashboardHeading">Conversions &amp; Attribution</h1>
        <p className="dashboardSubtitle">
          Conversion action reporting with action-level conversion and value
          trends.
        </p>
      </header>
      <ConversionsTabSection
        data={data ?? {}}
        status={status}
        error={error}
        summary={summary}
      />
    </section>
  );
};

export default GoogleAdsConversionsPage;
