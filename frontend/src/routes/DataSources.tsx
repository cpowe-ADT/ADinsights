import { useCallback, useEffect, useMemo, useState } from 'react';

import EmptyState from '../components/EmptyState';
import { useToast } from '../components/ToastProvider';
import {
  loadAirbyteConnections,
  loadAirbyteSummary,
  triggerAirbyteSync,
  type AirbyteConnectionRecord,
  type AirbyteConnectionsSummary,
} from '../lib/airbyte';
import { formatAbsoluteTime, formatRelativeTime, isTimestampStale } from '../lib/format';

const DataSourcesIcon = () => (
  <svg width="48" height="48" viewBox="0 0 48 48" fill="none" stroke="currentColor" strokeWidth="2.2">
    <rect x="8" y="10" width="32" height="26" rx="4" />
    <path d="M14 18h20" strokeLinecap="round" />
    <path d="M14 24h14" strokeLinecap="round" />
    <path d="M14 30h10" strokeLinecap="round" />
    <circle cx="34" cy="30" r="3.5" />
  </svg>
);

const STATUS_THRESHOLD_MINUTES = 60;

const PROVIDER_LABELS: Record<string, string> = {
  META: 'Meta',
  GOOGLE: 'Google Ads',
  LINKEDIN: 'LinkedIn',
  TIKTOK: 'TikTok',
  UNKNOWN: 'Unknown provider',
};

const FAILURE_STATUSES = new Set(['failed', 'error', 'cancelled']);
const RUNNING_STATUSES = new Set(['running', 'pending', 'in_progress']);

type LoadStatus = 'loading' | 'loaded' | 'error';

type ConnectionState = 'healthy' | 'stale' | 'paused' | 'needs-attention' | 'syncing';

const resolveProviderLabel = (provider?: string | null): string => {
  if (!provider) {
    return PROVIDER_LABELS.UNKNOWN;
  }
  return PROVIDER_LABELS[provider] ?? provider.toUpperCase();
};

const formatSchedule = (connection: AirbyteConnectionRecord): string => {
  const scheduleType = connection.schedule_type ?? 'interval';
  if (scheduleType === 'manual') {
    return 'Manual';
  }
  if (scheduleType === 'cron') {
    return connection.cron_expression?.trim() ? `Cron · ${connection.cron_expression}` : 'Cron schedule';
  }
  if (scheduleType === 'interval') {
    const minutes = connection.interval_minutes ?? 0;
    if (minutes >= 60 && minutes % 60 === 0) {
      const hours = minutes / 60;
      return `Every ${hours} hour${hours === 1 ? '' : 's'}`;
    }
    if (minutes > 0) {
      return `Every ${minutes} min`;
    }
    return 'Interval schedule';
  }
  return scheduleType;
};

const resolveConnectionState = (connection: AirbyteConnectionRecord): ConnectionState => {
  if (connection.is_active === false) {
    return 'paused';
  }

  const statusValue = (connection.last_job_status ?? '').toLowerCase();
  if (RUNNING_STATUSES.has(statusValue)) {
    return 'syncing';
  }
  if (connection.last_job_error || FAILURE_STATUSES.has(statusValue)) {
    return 'needs-attention';
  }
  if (isTimestampStale(connection.last_synced_at ?? null, STATUS_THRESHOLD_MINUTES)) {
    return 'stale';
  }
  return 'healthy';
};

const resolveStateLabel = (state: ConnectionState): string => {
  switch (state) {
    case 'paused':
      return 'Paused';
    case 'needs-attention':
      return 'Needs attention';
    case 'stale':
      return 'Stale';
    case 'syncing':
      return 'Syncing';
    default:
      return 'Healthy';
  }
};

const resolveStateTone = (state: ConnectionState): 'success' | 'warning' | 'error' | 'muted' => {
  switch (state) {
    case 'paused':
      return 'muted';
    case 'needs-attention':
      return 'error';
    case 'stale':
    case 'syncing':
      return 'warning';
    default:
      return 'success';
  }
};

const DataSources = () => {
  const docsUrl =
    import.meta.env.VITE_DOCS_URL?.trim() ||
    'https://github.com/cpowe-ADT/ADinsights/blob/main/docs/ops/doc-index.md';
  const csvDocsUrl =
    import.meta.env.VITE_DOCS_CSV_URL?.trim() ||
    'https://github.com/cpowe-ADT/ADinsights/blob/main/docs/runbooks/csv-uploads.md';

  const { pushToast } = useToast();
  const [status, setStatus] = useState<LoadStatus>('loading');
  const [connections, setConnections] = useState<AirbyteConnectionRecord[]>([]);
  const [summary, setSummary] = useState<AirbyteConnectionsSummary | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [providerFilter, setProviderFilter] = useState('all');
  const [statusFilter, setStatusFilter] = useState<ConnectionState | 'all'>('all');
  const [query, setQuery] = useState('');
  const [syncingId, setSyncingId] = useState<string | null>(null);

  const loadData = useCallback(async () => {
    setStatus('loading');
    setError(null);
    try {
      const [connectionsPayload, summaryPayload] = await Promise.all([
        loadAirbyteConnections(),
        loadAirbyteSummary(),
      ]);
      setConnections(connectionsPayload);
      setSummary(summaryPayload);
      setStatus('loaded');
    } catch (loadError) {
      const message = loadError instanceof Error ? loadError.message : 'Unable to load data sources.';
      setError(message);
      setStatus('error');
    }
  }, []);

  useEffect(() => {
    void loadData();
  }, [loadData]);

  const handleViewDocs = useCallback(() => {
    if (typeof window !== 'undefined') {
      window.open(docsUrl, '_blank', 'noopener,noreferrer');
    }
  }, [docsUrl]);

  const handleViewCsvGuide = useCallback(() => {
    if (typeof window !== 'undefined') {
      window.open(csvDocsUrl, '_blank', 'noopener,noreferrer');
    }
  }, [csvDocsUrl]);

  const handleRefresh = useCallback(() => {
    void loadData();
  }, [loadData]);

  const handleRunNow = useCallback(
    async (connection: AirbyteConnectionRecord) => {
      if (!connection.id || syncingId === connection.id) {
        return;
      }
      setSyncingId(connection.id);
      try {
        const response = await triggerAirbyteSync(connection.id);
        const jobId = response?.job_id;
        pushToast(
          jobId ? `Sync triggered (job ${jobId}).` : 'Sync triggered.',
          { tone: 'success' },
        );
        void loadData();
      } catch (syncError) {
        const message = syncError instanceof Error ? syncError.message : 'Sync failed to start.';
        pushToast(message, { tone: 'error' });
      } finally {
        setSyncingId(null);
      }
    },
    [loadData, pushToast, syncingId],
  );

  const providerOptions = useMemo(() => {
    const providers = new Set<string>();
    connections.forEach((connection) => {
      providers.add(connection.provider ?? 'UNKNOWN');
    });
    return Array.from(providers)
      .map((provider) => ({
        value: provider,
        label: resolveProviderLabel(provider),
      }))
      .sort((a, b) => a.label.localeCompare(b.label, undefined, { sensitivity: 'base' }));
  }, [connections]);

  const filteredConnections = useMemo(() => {
    const normalizedQuery = query.trim().toLowerCase();
    return connections.filter((connection) => {
      const provider = connection.provider ?? 'UNKNOWN';
      if (providerFilter !== 'all' && provider !== providerFilter) {
        return false;
      }
      const state = resolveConnectionState(connection);
      if (statusFilter !== 'all' && state !== statusFilter) {
        return false;
      }
      if (!normalizedQuery) {
        return true;
      }
      const haystack = `${connection.name ?? ''} ${provider}`.toLowerCase();
      return haystack.includes(normalizedQuery);
    });
  }, [connections, providerFilter, query, statusFilter]);

  const latestSyncLabel = useMemo(() => {
    const lastSyncedAt = summary?.latest_sync?.last_synced_at;
    if (!lastSyncedAt) {
      return 'No sync yet';
    }
    return formatRelativeTime(lastSyncedAt) ?? 'No sync yet';
  }, [summary?.latest_sync?.last_synced_at]);

  const latestSyncTimestamp = useMemo(() => {
    const lastSyncedAt = summary?.latest_sync?.last_synced_at;
    return lastSyncedAt ? formatAbsoluteTime(lastSyncedAt) : null;
  }, [summary?.latest_sync?.last_synced_at]);

  const summaryCounts = useMemo(() => {
    if (summary) {
      return summary;
    }
    const total = connections.length;
    const active = connections.filter((connection) => connection.is_active !== false).length;
    return {
      total,
      active,
      inactive: total - active,
      due: connections.filter((connection) => resolveConnectionState(connection) === 'stale').length,
      by_provider: {},
    };
  }, [connections, summary]);

  const hasConnections = connections.length > 0;
  const hasFiltered = filteredConnections.length > 0;

  return (
    <div className="dashboard-grid single-panel">
      <section className="panel full-width data-sources-panel">
        <header className="panel-header">
          <div className="panel-header__title-row">
            <h2>Data sources</h2>
            {latestSyncTimestamp ? (
              <span className="status-pill muted" title={latestSyncTimestamp}>
                Latest sync {latestSyncLabel}
              </span>
            ) : null}
          </div>
          <p className="status-message muted">
            Monitor connection health, schedules, and recent sync activity.
          </p>
        </header>

        <div className="data-sources-summary">
          <div className="summary-card">
            <p className="summary-card__label">Total connections</p>
            <p className="summary-card__value">{summaryCounts.total}</p>
          </div>
          <div className="summary-card">
            <p className="summary-card__label">Active</p>
            <p className="summary-card__value">{summaryCounts.active}</p>
          </div>
          <div className="summary-card">
            <p className="summary-card__label">Paused</p>
            <p className="summary-card__value">{summaryCounts.inactive}</p>
          </div>
          <div className="summary-card">
            <p className="summary-card__label">Due for sync</p>
            <p className="summary-card__value">{summaryCounts.due}</p>
          </div>
        </div>

        <div className="data-sources-controls">
          <label className="dashboard-field">
            <span className="dashboard-field__label">Provider</span>
            <select value={providerFilter} onChange={(event) => setProviderFilter(event.target.value)}>
              <option value="all">All providers</option>
              {providerOptions.map((provider) => (
                <option key={provider.value} value={provider.value}>
                  {provider.label}
                </option>
              ))}
            </select>
          </label>
          <label className="dashboard-field">
            <span className="dashboard-field__label">Status</span>
            <select
              value={statusFilter}
              onChange={(event) => setStatusFilter(event.target.value as ConnectionState | 'all')}
            >
              <option value="all">All statuses</option>
              <option value="healthy">Healthy</option>
              <option value="stale">Stale</option>
              <option value="syncing">Syncing</option>
              <option value="needs-attention">Needs attention</option>
              <option value="paused">Paused</option>
            </select>
          </label>
          <label className="dashboard-field data-sources-search">
            <span className="dashboard-field__label">Search</span>
            <input
              type="search"
              placeholder="Search by name"
              value={query}
              onChange={(event) => setQuery(event.target.value)}
            />
          </label>
          <div className="data-sources-actions">
            <button type="button" className="button secondary" onClick={handleRefresh}>
              Refresh
            </button>
            <button type="button" className="button tertiary" onClick={handleViewDocs}>
              Open runbook
            </button>
            <button type="button" className="button tertiary" onClick={handleViewCsvGuide}>
              CSV format guide
            </button>
          </div>
        </div>

        {status === 'loading' ? <p className="status-message muted">Loading connections…</p> : null}
        {status === 'error' ? (
          <EmptyState
            icon={<DataSourcesIcon />}
            title="Unable to load data sources"
            message={error ?? 'Check the Airbyte service and try again.'}
            actionLabel="Retry"
            actionVariant="secondary"
            onAction={handleRefresh}
          />
        ) : null}
        {status === 'loaded' && !hasConnections ? (
          <EmptyState
            icon={<DataSourcesIcon />}
            title="No sources connected"
            message="Connect Meta, Google, or other sources in Airbyte to begin syncing metrics."
            actionLabel="Open setup guide"
            actionVariant="secondary"
            onAction={handleViewDocs}
            secondaryActionLabel="CSV format guide"
            onSecondaryAction={handleViewCsvGuide}
          />
        ) : null}
        {status === 'loaded' && hasConnections ? (
          <div className="data-sources-list">
            {!hasFiltered ? (
              <p className="status-message muted">No connections match these filters.</p>
            ) : null}
            {filteredConnections.map((connection) => {
              const state = resolveConnectionState(connection);
              const tone = resolveStateTone(state);
              const lastSyncedLabel =
                formatRelativeTime(connection.last_synced_at ?? null) ?? 'Never synced';
              const lastSyncedAbsolute = formatAbsoluteTime(connection.last_synced_at ?? null);
              const providerLabel = resolveProviderLabel(connection.provider);
              const scheduleLabel = formatSchedule(connection);
              const isSyncing = syncingId === connection.id;

              return (
                <article key={connection.id} className="data-source-card">
                  <div className="data-source-card__header">
                    <div>
                      <h3>{connection.name}</h3>
                      <p className="muted">{providerLabel}</p>
                    </div>
                    <span className={`status-pill ${tone}`}>{resolveStateLabel(state)}</span>
                  </div>
                  <div className="data-source-card__meta">
                    <div>
                      <p className="status-message muted">Schedule</p>
                      <p>{scheduleLabel}</p>
                    </div>
                    <div>
                      <p className="status-message muted">Last sync</p>
                      <p title={lastSyncedAbsolute ?? undefined}>{lastSyncedLabel}</p>
                    </div>
                    <div>
                      <p className="status-message muted">Last job</p>
                      <p>{connection.last_job_status || '—'}</p>
                    </div>
                    <div>
                      <p className="status-message muted">Workspace</p>
                      <p>{connection.workspace_id ?? '—'}</p>
                    </div>
                  </div>
                  {connection.last_job_error ? (
                    <p className="status-message error">{connection.last_job_error}</p>
                  ) : null}
                  <div className="data-source-card__actions">
                    <button
                      type="button"
                      className="button secondary"
                      onClick={() => void handleRunNow(connection)}
                      disabled={connection.is_active === false || isSyncing}
                      aria-busy={isSyncing}
                    >
                      {isSyncing ? 'Starting sync…' : 'Run now'}
                    </button>
                  </div>
                </article>
              );
            })}
          </div>
        ) : null}
      </section>
    </div>
  );
};

export default DataSources;
