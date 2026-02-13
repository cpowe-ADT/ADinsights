import { useCallback, useEffect, useMemo, useState, type FormEvent } from 'react';
import { useLocation, useNavigate } from 'react-router-dom';

import EmptyState from '../components/EmptyState';
import { useToast } from '../components/ToastProvider';
import {
  disconnectIntegration,
  connectMetaPage,
  callbackIntegrationOAuth,
  loadIntegrationJobs,
  loadIntegrationStatus,
  reconnectIntegration,
  exchangeMetaOAuthCode,
  loadAirbyteConnections,
  loadAirbyteSummary,
  provisionIntegration,
  startIntegrationOAuth,
  startMetaOAuth,
  syncIntegration,
  triggerAirbyteSync,
  type AirbyteConnectionRecord,
  type AirbyteConnectionsSummary,
  type IntegrationProviderSlug,
  type IntegrationJobRecord,
  type IntegrationStatusResponse,
  type MetaOAuthPage,
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
type ConnectProvider = 'facebook_pages' | 'google_ads' | 'ga4' | 'search_console';

const OAUTH_PROVIDER_KEY = 'adinsights.integration.oauth.provider';
const OAUTH_ACCOUNT_KEY = 'adinsights.integration.oauth.account';

const CONNECT_PROVIDERS: ConnectProvider[] = [
  'facebook_pages',
  'google_ads',
  'ga4',
  'search_console',
];

interface ConnectFormState {
  accountId: string;
  linkConnection: boolean;
  connectionName: string;
  workspaceId: string;
  destinationId: string;
  scheduleType: 'manual' | 'interval' | 'cron';
  intervalMinutes: string;
  cronExpression: string;
  isActive: boolean;
}

interface MetaOAuthSelectionState {
  selectionToken: string | null;
  pages: MetaOAuthPage[];
  selectedPageId: string;
}

const CONNECT_PROVIDER_LABELS: Record<ConnectProvider, string> = {
  facebook_pages: 'Facebook Page',
  google_ads: 'Google Ads',
  ga4: 'Google Analytics 4',
  search_console: 'Google Search Console',
};

const CONNECT_PROVIDER_ACCOUNT_LABELS: Record<ConnectProvider, string> = {
  facebook_pages: 'Facebook page ID (optional)',
  google_ads: 'Google Ads customer/account ID',
  ga4: 'GA4 property ID',
  search_console: 'Search Console site URL',
};

const DEFAULT_CRON_EXPRESSION = '0 6-22 * * *';
const UUID_REGEX =
  /^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i;

const buildInitialConnectForm = (provider: ConnectProvider): ConnectFormState => ({
  accountId: '',
  linkConnection: true,
  connectionName:
    provider === 'facebook_pages'
      ? 'Facebook Page Metrics'
      : provider === 'google_ads'
        ? 'Google Ads Metrics'
        : provider === 'ga4'
          ? 'GA4 Reporting'
          : 'Search Console Reporting',
  workspaceId: '',
  destinationId: '',
  scheduleType: 'cron',
  intervalMinutes: '60',
  cronExpression: DEFAULT_CRON_EXPRESSION,
  isActive: true,
});

const resolveProviderLabel = (provider?: string | null): string => {
  if (!provider) {
    return PROVIDER_LABELS.UNKNOWN;
  }
  return PROVIDER_LABELS[provider] ?? provider.toUpperCase();
};

const stateToBadgeTone = (state: IntegrationStatusResponse['state']): 'success' | 'warning' | 'error' | 'muted' => {
  if (state === 'connected') return 'success';
  if (state === 'syncing' || state === 'needs_provisioning') return 'warning';
  if (state === 'needs_reauth') return 'error';
  if (state === 'error') return 'error';
  return 'muted';
};

const stateToLabel = (state: IntegrationStatusResponse['state']): string => {
  switch (state) {
    case 'needs_provisioning':
      return 'Needs provisioning';
    case 'not_connected':
      return 'Not connected';
    case 'connected':
      return 'Connected';
    case 'needs_reauth':
      return 'Needs re-auth';
    case 'syncing':
      return 'Syncing';
    case 'paused':
      return 'Paused';
    default:
      return 'Error';
  }
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
  const location = useLocation();
  const navigate = useNavigate();
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
  const [providerSyncing, setProviderSyncing] = useState<ConnectProvider | null>(null);
  const [oauthStartingProvider, setOAuthStartingProvider] = useState<ConnectProvider | null>(null);
  const [connectProvider, setConnectProvider] = useState<ConnectProvider | null>(null);
  const [connectForm, setConnectForm] = useState<ConnectFormState>(
    buildInitialConnectForm('facebook_pages'),
  );
  const [integrationStatuses, setIntegrationStatuses] = useState<
    Record<ConnectProvider, IntegrationStatusResponse | null>
  >({
    facebook_pages: null,
    google_ads: null,
    ga4: null,
    search_console: null,
  });
  const [integrationJobs, setIntegrationJobs] = useState<Record<ConnectProvider, IntegrationJobRecord[]>>({
    facebook_pages: [],
    google_ads: [],
    ga4: [],
    search_console: [],
  });
  const [providerDisconnecting, setProviderDisconnecting] = useState<ConnectProvider | null>(null);
  const [providerReconnecting, setProviderReconnecting] = useState<ConnectProvider | null>(null);
  const [savingConnect, setSavingConnect] = useState(false);
  const [metaOAuthExchanging, setMetaOAuthExchanging] = useState(false);
  const [metaOAuthSavingPage, setMetaOAuthSavingPage] = useState(false);
  const [metaOAuthSelection, setMetaOAuthSelection] = useState<MetaOAuthSelectionState>({
    selectionToken: null,
    pages: [],
    selectedPageId: '',
  });

  const loadData = useCallback(async () => {
    setStatus('loading');
    setError(null);
    try {
      const [connectionsPayload, summaryPayload, ...providerPayloads] = await Promise.all([
        loadAirbyteConnections(),
        loadAirbyteSummary(),
        ...CONNECT_PROVIDERS.flatMap((provider) => [
          loadIntegrationStatus(provider),
          loadIntegrationJobs(provider, 5),
        ]),
      ]);
      setConnections(connectionsPayload);
      setSummary(summaryPayload);
      const statusMap = {} as Record<ConnectProvider, IntegrationStatusResponse>;
      const jobsMap = {} as Record<ConnectProvider, IntegrationJobRecord[]>;
      CONNECT_PROVIDERS.forEach((provider, index) => {
        const statusPayload = providerPayloads[index * 2] as IntegrationStatusResponse;
        const jobsPayload = providerPayloads[index * 2 + 1] as { jobs: IntegrationJobRecord[] };
        statusMap[provider] = statusPayload;
        jobsMap[provider] = jobsPayload.jobs ?? [];
      });
      setIntegrationStatuses(statusMap);
      setIntegrationJobs(jobsMap);
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

  useEffect(() => {
    const interval = window.setInterval(() => {
      void loadData();
    }, 30000);
    return () => window.clearInterval(interval);
  }, [loadData]);

  const resetMetaOAuthSelection = useCallback(() => {
    setMetaOAuthSelection({
      selectionToken: null,
      pages: [],
      selectedPageId: '',
    });
    setOAuthStartingProvider(null);
    setMetaOAuthExchanging(false);
    setMetaOAuthSavingPage(false);
  }, []);

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

  useEffect(() => {
    const params = new URLSearchParams(location.search);
    const oauthError = params.get('error') || params.get('error_reason');
    const oauthErrorDescription = params.get('error_description');
    const code = params.get('code');
    const state = params.get('state');
    const oauthProviderRaw =
      typeof window !== 'undefined' ? window.sessionStorage.getItem(OAUTH_PROVIDER_KEY) : null;
    const oauthProvider = CONNECT_PROVIDERS.includes(oauthProviderRaw as ConnectProvider)
      ? (oauthProviderRaw as ConnectProvider)
      : null;
    const oauthAccountId =
      typeof window !== 'undefined' ? window.sessionStorage.getItem(OAUTH_ACCOUNT_KEY) ?? '' : '';

    if (!oauthError && (!code || !state)) {
      return;
    }

    if (oauthError) {
      pushToast(
        oauthErrorDescription?.trim()
          ? `OAuth failed: ${oauthErrorDescription}`
          : `OAuth failed: ${oauthError}`,
        { tone: 'error' },
      );
      if (typeof window !== 'undefined') {
        window.sessionStorage.removeItem(OAUTH_PROVIDER_KEY);
        window.sessionStorage.removeItem(OAUTH_ACCOUNT_KEY);
      }
      navigate(location.pathname, { replace: true });
      return;
    }

    const oauthCode = code ?? '';
    const oauthState = state ?? '';

    if (!oauthProvider || oauthProvider === 'facebook_pages') {
      setConnectProvider('facebook_pages');
      setConnectForm(buildInitialConnectForm('facebook_pages'));
      setMetaOAuthExchanging(true);
      void exchangeMetaOAuthCode({ code: oauthCode, state: oauthState })
        .then((response) => {
          const firstPageId = response.pages[0]?.id ?? '';
          setMetaOAuthSelection({
            selectionToken: response.selection_token,
            pages: response.pages,
            selectedPageId: firstPageId,
          });
          if (!response.pages.length) {
            pushToast('Meta OAuth completed, but no Facebook pages were returned.', {
              tone: 'error',
            });
            return;
          }
          pushToast('Meta OAuth complete. Select a Facebook page to finish connecting.', {
            tone: 'success',
          });
        })
        .catch((oauthExchangeError) => {
          const message =
            oauthExchangeError instanceof Error
              ? oauthExchangeError.message
              : 'Meta OAuth code exchange failed.';
          pushToast(message, { tone: 'error' });
        })
        .finally(() => {
          setMetaOAuthExchanging(false);
          if (typeof window !== 'undefined') {
            window.sessionStorage.removeItem(OAUTH_PROVIDER_KEY);
            window.sessionStorage.removeItem(OAUTH_ACCOUNT_KEY);
          }
          navigate(location.pathname, { replace: true });
        });
      return;
    }

    setConnectProvider(oauthProvider);
    setConnectForm((previous) => ({
      ...buildInitialConnectForm(oauthProvider),
      accountId: oauthAccountId,
    }));
    setMetaOAuthExchanging(true);
    void callbackIntegrationOAuth(oauthProvider, {
      code: oauthCode,
      state: oauthState,
      external_account_id: oauthAccountId || undefined,
    })
      .then(async () => {
        pushToast(`${CONNECT_PROVIDER_LABELS[oauthProvider]} OAuth connected.`, { tone: 'success' });
        if (oauthAccountId) {
          await provisionIntegration(oauthProvider, {
            external_account_id: oauthAccountId,
            connection_name: buildInitialConnectForm(oauthProvider).connectionName,
            schedule_type: 'cron',
            cron_expression: DEFAULT_CRON_EXPRESSION,
            is_active: true,
          });
          pushToast(`${CONNECT_PROVIDER_LABELS[oauthProvider]} provisioned.`, { tone: 'success' });
        }
        void loadData();
      })
      .catch((oauthExchangeError) => {
        const message =
          oauthExchangeError instanceof Error
            ? oauthExchangeError.message
            : 'Google OAuth callback failed.';
        pushToast(message, { tone: 'error' });
      })
      .finally(() => {
        setMetaOAuthExchanging(false);
        if (typeof window !== 'undefined') {
          window.sessionStorage.removeItem(OAUTH_PROVIDER_KEY);
          window.sessionStorage.removeItem(OAUTH_ACCOUNT_KEY);
        }
        navigate(location.pathname, { replace: true });
      });
  }, [loadData, location.pathname, location.search, navigate, pushToast]);

  const handleStartOAuth = useCallback(async () => {
    if (!connectProvider || oauthStartingProvider) {
      return;
    }
    setOAuthStartingProvider(connectProvider);
    try {
      const accountId = connectForm.accountId.trim();
      if (
        connectProvider !== 'facebook_pages' &&
        !accountId
      ) {
        pushToast('Account/property/site identifier is required before OAuth.', {
          tone: 'error',
        });
        return;
      }
      if (typeof window !== 'undefined') {
        window.sessionStorage.setItem(OAUTH_PROVIDER_KEY, connectProvider);
        window.sessionStorage.setItem(OAUTH_ACCOUNT_KEY, accountId);
      }
      const response =
        connectProvider === 'facebook_pages'
          ? await startMetaOAuth()
          : await startIntegrationOAuth(connectProvider as IntegrationProviderSlug);
      if (typeof window !== 'undefined') {
        window.location.assign(response.authorize_url);
      }
    } catch (oauthStartError) {
      const message =
        oauthStartError instanceof Error
          ? oauthStartError.message
          : 'Unable to start OAuth.';
      pushToast(message, { tone: 'error' });
    } finally {
      setOAuthStartingProvider(null);
    }
  }, [connectForm.accountId, connectProvider, oauthStartingProvider, pushToast]);

  const openConnectPanel = useCallback((provider: ConnectProvider) => {
    setConnectProvider(provider);
    setConnectForm(buildInitialConnectForm(provider));
    if (provider !== 'facebook_pages') {
      resetMetaOAuthSelection();
    }
  }, [resetMetaOAuthSelection]);

  const closeConnectPanel = useCallback(() => {
    setConnectProvider(null);
    setSavingConnect(false);
    resetMetaOAuthSelection();
  }, [resetMetaOAuthSelection]);

  const handleMetaPageConnect = useCallback(async () => {
    if (
      metaOAuthSavingPage ||
      !metaOAuthSelection.selectionToken ||
      !metaOAuthSelection.selectedPageId
    ) {
      return;
    }
    setMetaOAuthSavingPage(true);
    try {
      const response = await connectMetaPage({
        selection_token: metaOAuthSelection.selectionToken,
        page_id: metaOAuthSelection.selectedPageId,
      });
      pushToast(`Connected Facebook page ${response.page.name}.`, { tone: 'success' });
      closeConnectPanel();
      void loadData();
    } catch (metaConnectError) {
      const message =
        metaConnectError instanceof Error ? metaConnectError.message : 'Unable to connect page.';
      pushToast(message, { tone: 'error' });
    } finally {
      setMetaOAuthSavingPage(false);
    }
  }, [
    closeConnectPanel,
    loadData,
    metaOAuthSavingPage,
    metaOAuthSelection.selectedPageId,
    metaOAuthSelection.selectionToken,
    pushToast,
  ]);

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

  const handleProviderSync = useCallback(
    async (provider: ConnectProvider) => {
      if (providerSyncing) {
        return;
      }
      setProviderSyncing(provider);
      try {
        const payload = await syncIntegration(provider);
        pushToast(
          payload.job_id
            ? `${CONNECT_PROVIDER_LABELS[provider]} sync started (job ${payload.job_id}).`
            : `${CONNECT_PROVIDER_LABELS[provider]} sync started.`,
          { tone: 'success' },
        );
        void loadData();
      } catch (error) {
        const message = error instanceof Error ? error.message : 'Failed to start sync.';
        pushToast(message, { tone: 'error' });
      } finally {
        setProviderSyncing(null);
      }
    },
    [loadData, providerSyncing, pushToast],
  );

  const handleProviderDisconnect = useCallback(
    async (provider: ConnectProvider) => {
      if (providerDisconnecting) {
        return;
      }
      setProviderDisconnecting(provider);
      try {
        const activeAccount = integrationStatuses[provider]?.credentials[0]?.account_id;
        await disconnectIntegration(provider, {
          external_account_id: activeAccount || undefined,
        });
        pushToast(`${CONNECT_PROVIDER_LABELS[provider]} disconnected.`, { tone: 'success' });
        if (connectProvider === provider) {
          closeConnectPanel();
        }
        void loadData();
      } catch (error) {
        const message = error instanceof Error ? error.message : 'Disconnect failed.';
        pushToast(message, { tone: 'error' });
      } finally {
        setProviderDisconnecting(null);
      }
    },
    [closeConnectPanel, connectProvider, integrationStatuses, loadData, providerDisconnecting, pushToast],
  );

  const handleProviderReconnect = useCallback(
    async (provider: ConnectProvider) => {
      if (providerReconnecting) {
        return;
      }
      setProviderReconnecting(provider);
      try {
        const accountId = integrationStatuses[provider]?.credentials[0]?.account_id ?? '';
        if (typeof window !== 'undefined') {
          window.sessionStorage.setItem(OAUTH_PROVIDER_KEY, provider);
          window.sessionStorage.setItem(OAUTH_ACCOUNT_KEY, accountId);
        }
        const response = await reconnectIntegration(provider);
        if (typeof window !== 'undefined') {
          window.location.assign(response.authorize_url);
        }
      } catch (error) {
        const message = error instanceof Error ? error.message : 'Reconnect failed.';
        pushToast(message, { tone: 'error' });
      } finally {
        setProviderReconnecting(null);
      }
    },
    [integrationStatuses, providerReconnecting, pushToast],
  );

  const handleConnectFieldChange = useCallback(
    (field: keyof ConnectFormState, value: string | boolean) => {
      setConnectForm((previous) => ({
        ...previous,
        [field]: value,
      }));
    },
    [],
  );

  const handleConnectSubmit = useCallback(
    async (event: FormEvent<HTMLFormElement>) => {
      event.preventDefault();
      if (!connectProvider || savingConnect) {
        return;
      }

      const accountId = connectForm.accountId.trim();
      if (
        connectProvider !== 'facebook_pages' &&
        !accountId
      ) {
        pushToast('Account/property/site identifier is required.', { tone: 'error' });
        return;
      }

      if (connectForm.linkConnection) {
        const connectionName = connectForm.connectionName.trim();
        if (!connectionName) {
          pushToast('Connection name is required for provisioning.', {
            tone: 'error',
          });
          return;
        }
        if (connectForm.workspaceId.trim() && !UUID_REGEX.test(connectForm.workspaceId.trim())) {
          pushToast('Workspace UUID format is invalid.', { tone: 'error' });
          return;
        }
        if (connectForm.destinationId.trim() && !UUID_REGEX.test(connectForm.destinationId.trim())) {
          pushToast('Destination UUID format is invalid.', { tone: 'error' });
          return;
        }
        if (connectForm.scheduleType === 'interval') {
          const minutes = Number(connectForm.intervalMinutes);
          if (!Number.isFinite(minutes) || minutes <= 0) {
            pushToast('Interval minutes must be a positive number.', { tone: 'error' });
            return;
          }
        }
        if (connectForm.scheduleType === 'cron' && !connectForm.cronExpression.trim()) {
          pushToast('Cron expression is required for cron schedule.', { tone: 'error' });
          return;
        }
      }

      setSavingConnect(true);
      try {
        if (connectForm.linkConnection) {
          await provisionIntegration(connectProvider, {
            external_account_id: accountId || undefined,
            workspace_id: connectForm.workspaceId.trim() || null,
            destination_id: connectForm.destinationId.trim() || null,
            connection_name: connectForm.connectionName.trim(),
            schedule_type: connectForm.scheduleType,
            is_active: connectForm.isActive,
            interval_minutes:
              connectForm.scheduleType === 'interval' ? Number(connectForm.intervalMinutes) : null,
            cron_expression:
              connectForm.scheduleType === 'cron' ? connectForm.cronExpression.trim() : '',
          });
        }

        pushToast(
          connectForm.linkConnection
            ? `${CONNECT_PROVIDER_LABELS[connectProvider]} provisioned.`
            : `${CONNECT_PROVIDER_LABELS[connectProvider]} settings saved.`,
          { tone: 'success' },
        );
        closeConnectPanel();
        void loadData();
      } catch (connectError) {
        const message =
          connectError instanceof Error ? connectError.message : 'Connection setup failed.';
        pushToast(message, { tone: 'error' });
      } finally {
        setSavingConnect(false);
      }
    },
    [
      closeConnectPanel,
      connectForm,
      connectProvider,
      loadData,
      pushToast,
      savingConnect,
    ],
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
            {CONNECT_PROVIDERS.map((provider) => (
              <button
                key={provider}
                type="button"
                className="button secondary"
                onClick={() => openConnectPanel(provider)}
              >
                {`Connect ${CONNECT_PROVIDER_LABELS[provider]}`}
              </button>
            ))}
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

        <p className="status-message muted">
          OAuth connect supports Facebook Page, Google Ads, GA4, and Search Console. Use
          provisioning to create or reuse tenant-scoped Airbyte connections.
        </p>

        <div className="data-sources-summary">
          {CONNECT_PROVIDERS.map((provider) => {
            const providerStatus = integrationStatuses[provider];
            const providerState = providerStatus?.state ?? 'not_connected';
            const tone = stateToBadgeTone(providerState);
            const syncing = providerSyncing === provider;
            const disconnecting = providerDisconnecting === provider;
            const reconnecting = providerReconnecting === provider;
            const jobs = integrationJobs[provider] ?? [];
            return (
              <article className="summary-card" key={provider}>
                <p className="summary-card__label">{CONNECT_PROVIDER_LABELS[provider]}</p>
                <p className="summary-card__value">
                  <span className={`status-pill ${tone}`}>{stateToLabel(providerState)}</span>
                </p>
                <div className="data-source-card__actions">
                  <button type="button" className="button tertiary" onClick={() => openConnectPanel(provider)}>
                    Manage
                  </button>
                  <button
                    type="button"
                    className="button tertiary"
                    onClick={() => void handleProviderSync(provider)}
                    disabled={
                      syncing ||
                      providerState === 'not_connected' ||
                      providerState === 'needs_provisioning' ||
                      providerState === 'needs_reauth'
                    }
                    aria-busy={syncing}
                  >
                    {syncing ? 'Starting…' : 'Run initial sync'}
                  </button>
                  <button
                    type="button"
                    className="button tertiary"
                    onClick={() => void handleProviderReconnect(provider)}
                    disabled={reconnecting}
                    aria-busy={reconnecting}
                  >
                    {reconnecting ? 'Redirecting…' : 'Reconnect'}
                  </button>
                  <button
                    type="button"
                    className="button tertiary"
                    onClick={() => void handleProviderDisconnect(provider)}
                    disabled={disconnecting || providerState === 'not_connected'}
                    aria-busy={disconnecting}
                  >
                    {disconnecting ? 'Disconnecting…' : 'Disconnect'}
                  </button>
                  <button
                    type="button"
                    className="button tertiary"
                    onClick={() => navigate('/ops/sync-health')}
                  >
                    View sync health
                  </button>
                </div>
                <div className="status-message muted">
                  {jobs.length ? 'Recent sync jobs:' : 'No sync jobs recorded yet.'}
                </div>
                {jobs.length ? (
                  <ul className="status-message muted">
                    {jobs.slice(0, 3).map((job) => (
                      <li key={`${provider}-${job.job_id}`}>
                        {`${job.status} • ${formatRelativeTime(job.started_at) ?? 'just now'} • job ${job.job_id}`}
                      </li>
                    ))}
                  </ul>
                ) : null}
              </article>
            );
          })}
        </div>

        {connectProvider ? (
          <form className="data-sources-connect-form" onSubmit={handleConnectSubmit}>
            <header className="data-sources-connect-form__header">
              <div>
                <h3>{`Connect ${CONNECT_PROVIDER_LABELS[connectProvider]}`}</h3>
                <p className="status-message muted">
                  Complete OAuth, then provision a tenant-scoped Airbyte source and connection.
                </p>
              </div>
              <button
                type="button"
                className="button tertiary"
                onClick={closeConnectPanel}
                disabled={savingConnect}
              >
                Cancel
              </button>
            </header>

            {connectProvider === 'facebook_pages' ? (
              <section className="data-sources-oauth-card">
                <div>
                  <h4>{connectProvider === 'facebook_pages' ? 'Facebook Page OAuth' : 'Google OAuth'}</h4>
                  <p className="status-message muted">
                    Use provider OAuth to securely store tenant-scoped credentials.
                  </p>
                </div>
                <div className="data-sources-oauth-card__actions">
                  <button
                    type="button"
                    className="button secondary"
                    onClick={() => void handleStartOAuth()}
                    disabled={
                      oauthStartingProvider === connectProvider ||
                      metaOAuthExchanging ||
                      metaOAuthSavingPage
                    }
                    aria-busy={oauthStartingProvider === connectProvider || metaOAuthExchanging}
                  >
                    {oauthStartingProvider === connectProvider ? 'Redirecting…' : 'Connect with OAuth'}
                  </button>
                  {metaOAuthExchanging ? (
                    <span className="status-message muted">Finalizing OAuth callback…</span>
                  ) : null}
                </div>

                {metaOAuthSelection.selectionToken && metaOAuthSelection.pages.length ? (
                  <div className="data-sources-oauth-selection">
                    <label className="dashboard-field">
                      <span className="dashboard-field__label">Facebook page</span>
                      <select
                        value={metaOAuthSelection.selectedPageId}
                        onChange={(event) =>
                          setMetaOAuthSelection((previous) => ({
                            ...previous,
                            selectedPageId: event.target.value,
                          }))
                        }
                      >
                        {metaOAuthSelection.pages.map((page) => (
                          <option key={page.id} value={page.id}>
                            {page.name}
                          </option>
                        ))}
                      </select>
                    </label>
                    <button
                      type="button"
                      className="button secondary"
                      onClick={() => void handleMetaPageConnect()}
                      disabled={metaOAuthSavingPage || !metaOAuthSelection.selectedPageId}
                      aria-busy={metaOAuthSavingPage}
                    >
                      {metaOAuthSavingPage ? 'Saving page…' : 'Save selected page'}
                    </button>
                  </div>
                ) : null}
              </section>
            ) : null}

            {connectProvider !== 'facebook_pages' ? (
              <section className="data-sources-oauth-card">
                <div>
                  <h4>Google OAuth</h4>
                  <p className="status-message muted">
                    Enter the identifier below, then complete OAuth to save refresh credentials.
                  </p>
                </div>
                <div className="data-sources-oauth-card__actions">
                  <button
                    type="button"
                    className="button secondary"
                    onClick={() => void handleStartOAuth()}
                    disabled={oauthStartingProvider === connectProvider || metaOAuthExchanging}
                    aria-busy={oauthStartingProvider === connectProvider || metaOAuthExchanging}
                  >
                    {oauthStartingProvider === connectProvider ? 'Redirecting…' : 'Connect with Google'}
                  </button>
                </div>
              </section>
            ) : null}

            <div className="data-sources-connect-form__grid">
              <label className="dashboard-field">
                <span className="dashboard-field__label">
                  {CONNECT_PROVIDER_ACCOUNT_LABELS[connectProvider]}
                </span>
                <input
                  type="text"
                  value={connectForm.accountId}
                  onChange={(event) => handleConnectFieldChange('accountId', event.target.value)}
                  placeholder={
                    connectProvider === 'facebook_pages'
                      ? 'Optional'
                      : connectProvider === 'google_ads'
                        ? '1234567890'
                        : connectProvider === 'ga4'
                          ? '123456789'
                          : 'sc-domain:example.com'
                  }
                  required={connectProvider !== 'facebook_pages'}
                />
              </label>

              <label className="dashboard-field data-sources-checkbox-field">
                <span className="dashboard-field__label">Provision Airbyte connection</span>
                <div className="data-sources-checkbox-row">
                  <input
                    type="checkbox"
                    checked={connectForm.linkConnection}
                    onChange={(event) =>
                      handleConnectFieldChange('linkConnection', event.target.checked)
                    }
                  />
                  <span>Create/update a tenant-scoped source and connection now</span>
                </div>
              </label>
            </div>

            {connectForm.linkConnection ? (
              <div className="data-sources-connect-form__grid">
                <label className="dashboard-field">
                  <span className="dashboard-field__label">Connection name</span>
                  <input
                    type="text"
                    value={connectForm.connectionName}
                    onChange={(event) =>
                      handleConnectFieldChange('connectionName', event.target.value)
                    }
                    placeholder="Meta Metrics Connection"
                    required
                  />
                </label>
                <label className="dashboard-field">
                  <span className="dashboard-field__label">Airbyte workspace UUID (optional)</span>
                  <input
                    type="text"
                    value={connectForm.workspaceId}
                    onChange={(event) =>
                      handleConnectFieldChange('workspaceId', event.target.value)
                    }
                    placeholder="aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"
                  />
                </label>
                <label className="dashboard-field">
                  <span className="dashboard-field__label">Airbyte destination UUID (optional)</span>
                  <input
                    type="text"
                    value={connectForm.destinationId}
                    onChange={(event) =>
                      handleConnectFieldChange('destinationId', event.target.value)
                    }
                    placeholder="bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb"
                  />
                </label>
                <label className="dashboard-field">
                  <span className="dashboard-field__label">Schedule type</span>
                  <select
                    value={connectForm.scheduleType}
                    onChange={(event) =>
                      handleConnectFieldChange(
                        'scheduleType',
                        event.target.value as ConnectFormState['scheduleType'],
                      )
                    }
                  >
                    <option value="manual">Manual</option>
                    <option value="interval">Interval</option>
                    <option value="cron">Cron</option>
                  </select>
                </label>
                {connectForm.scheduleType === 'interval' ? (
                  <label className="dashboard-field">
                    <span className="dashboard-field__label">Interval minutes</span>
                    <input
                      type="number"
                      min={1}
                      value={connectForm.intervalMinutes}
                      onChange={(event) =>
                        handleConnectFieldChange('intervalMinutes', event.target.value)
                      }
                      required
                    />
                  </label>
                ) : null}
                {connectForm.scheduleType === 'cron' ? (
                  <label className="dashboard-field">
                    <span className="dashboard-field__label">Cron expression</span>
                    <input
                      type="text"
                      value={connectForm.cronExpression}
                      onChange={(event) =>
                        handleConnectFieldChange('cronExpression', event.target.value)
                      }
                      required
                    />
                  </label>
                ) : null}
                <label className="dashboard-field data-sources-checkbox-field">
                  <span className="dashboard-field__label">Active</span>
                  <div className="data-sources-checkbox-row">
                    <input
                      type="checkbox"
                      checked={connectForm.isActive}
                      onChange={(event) =>
                        handleConnectFieldChange('isActive', event.target.checked)
                      }
                    />
                    <span>Enable this connection immediately</span>
                  </div>
                </label>
              </div>
            ) : null}

            <div className="data-sources-connect-form__actions">
              <button
                type="submit"
                className="button secondary"
                disabled={savingConnect}
                aria-busy={savingConnect}
              >
                {savingConnect ? 'Saving…' : 'Save connection'}
              </button>
            </div>
          </form>
        ) : null}

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
            message="Connect providers with OAuth and provision Airbyte to begin syncing metrics."
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
