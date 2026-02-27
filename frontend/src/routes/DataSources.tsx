import { useCallback, useEffect, useMemo, useRef, useState, type FormEvent } from 'react';

import EmptyState from '../components/EmptyState';
import { useToast } from '../components/ToastProvider';
import { ApiError } from '../lib/apiClient';
import {
  connectMetaPage,
  createAirbyteConnection,
  createPlatformCredential,
  exchangeMetaOAuthCode,
  loadAirbyteConnections,
  loadAirbyteSummary,
  loadMetaSetupStatus,
  logoutMetaOAuth,
  loadSocialConnectionStatus,
  provisionMetaIntegration,
  syncMetaIntegration,
  startMetaOAuth,
  triggerAirbyteSync,
  type AirbyteConnectionRecord,
  type AirbyteConnectionsSummary,
  type MetaAdAccount,
  type MetaInstagramAccount,
  type MetaOAuthPage,
  type MetaSetupStatusResponse,
  type PlatformCredentialRecord,
  type SocialConnectionStatus,
  type SocialPlatformStatusRecord,
} from '../lib/airbyte';
import { formatAbsoluteTime, formatRelativeTime, isTimestampStale } from '../lib/format';
import {
  callbackMetaOAuth,
  META_OAUTH_FLOW_PAGE_INSIGHTS,
  META_OAUTH_FLOW_SESSION_KEY,
} from '../lib/metaPageInsights';
import { buildRuntimeContextPayload } from '../lib/runtimeContext';
import { useDatasetStore } from '../state/useDatasetStore';

const DataSourcesIcon = () => (
  <svg
    width="48"
    height="48"
    viewBox="0 0 48 48"
    fill="none"
    stroke="currentColor"
    strokeWidth="2.2"
  >
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
type ConnectProvider = 'META' | 'GOOGLE';
type MetaConnectStep = 'idle' | 'oauth-pending' | 'page-selection' | 'credential-connected';
type SocialStatusLoad = 'loading' | 'loaded' | 'error';

interface ConnectFormState {
  accountId: string;
  accessToken: string;
  refreshToken: string;
  linkConnection: boolean;
  connectionName: string;
  connectionId: string;
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
  adAccounts: MetaAdAccount[];
  instagramAccounts: MetaInstagramAccount[];
  selectedPageId: string;
  selectedAdAccountId: string;
  selectedInstagramAccountId: string;
}

interface MetaPermissionDiagnosticsState {
  grantedPermissions: string[];
  declinedPermissions: string[];
  missingRequiredPermissions: string[];
  tokenDebugValid: boolean;
  oauthConnectedButMissingPermissions: boolean;
}

interface SocialPlatformCard extends Omit<SocialPlatformStatusRecord, 'platform'> {
  platform: string;
  isPlaceholder?: boolean;
}

const META_OAUTH_PROVIDER_KEY = 'adinsights.meta.oauth.provider';
const EMPTY_META_PERMISSION_DIAGNOSTICS: MetaPermissionDiagnosticsState = {
  grantedPermissions: [],
  declinedPermissions: [],
  missingRequiredPermissions: [],
  tokenDebugValid: false,
  oauthConnectedButMissingPermissions: false,
};

const CONNECT_PROVIDER_LABELS: Record<ConnectProvider, string> = {
  META: 'Meta (Facebook & Instagram)',
  GOOGLE: 'Google Ads',
};

const CONNECT_PROVIDER_ACCOUNT_LABELS: Record<ConnectProvider, string> = {
  META: 'Meta ad account ID',
  GOOGLE: 'Google Ads customer/account ID',
};

const SOCIAL_PLATFORM_ORDER: Array<SocialPlatformStatusRecord['platform']> = ['meta', 'instagram'];
const SOCIAL_PLACEHOLDERS: Array<{
  platform: string;
  display_name: string;
  description: string;
}> = [
  {
    platform: 'linkedin',
    display_name: 'LinkedIn (Coming soon)',
    description: 'LinkedIn social connector is planned and not yet enabled.',
  },
  {
    platform: 'tiktok',
    display_name: 'TikTok (Coming soon)',
    description: 'TikTok social connector is planned and not yet enabled.',
  },
];

const DEFAULT_CRON_EXPRESSION = '0 6-22 * * *';
const UUID_REGEX = /^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i;

const buildInitialConnectForm = (provider: ConnectProvider): ConnectFormState => ({
  accountId: '',
  accessToken: '',
  refreshToken: '',
  linkConnection: provider === 'META',
  connectionName: provider === 'META' ? 'Meta Metrics Connection' : 'Google Ads Metrics Connection',
  connectionId: '',
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

const formatSchedule = (connection: AirbyteConnectionRecord): string => {
  const scheduleType = connection.schedule_type ?? 'interval';
  if (scheduleType === 'manual') {
    return 'Manual';
  }
  if (scheduleType === 'cron') {
    return connection.cron_expression?.trim()
      ? `Cron · ${connection.cron_expression}`
      : 'Cron schedule';
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

const resolveSocialStatusTone = (
  value: SocialConnectionStatus,
): 'success' | 'warning' | 'error' | 'muted' => {
  if (value === 'active') {
    return 'success';
  }
  if (value === 'complete') {
    return 'warning';
  }
  if (value === 'started_not_complete') {
    return 'warning';
  }
  return 'muted';
};

const resolveSocialStatusLabel = (value: SocialConnectionStatus): string => {
  if (value === 'not_connected') {
    return 'Not connected';
  }
  if (value === 'started_not_complete') {
    return 'Started, not complete';
  }
  if (value === 'complete') {
    return 'Complete';
  }
  return 'Active';
};

const resolveSocialPrimaryAction = (status: SocialConnectionStatus, actions: string[]): string => {
  if (actions.includes('connect_oauth')) {
    return 'Connect with Facebook';
  }
  if (actions.includes('select_assets')) {
    return 'Continue setup';
  }
  if (actions.includes('provision')) {
    return 'Continue setup';
  }
  if (status === 'complete') {
    return 'Activate sync';
  }
  if (actions.includes('sync_now')) {
    return 'Run sync now';
  }
  return 'View details';
};

const DataSources = () => {
  const docsUrl =
    import.meta.env.VITE_DOCS_URL?.trim() ||
    'https://github.com/cpowe-ADT/ADinsights/blob/main/docs/ops/doc-index.md';
  const csvDocsUrl =
    import.meta.env.VITE_DOCS_CSV_URL?.trim() ||
    'https://github.com/cpowe-ADT/ADinsights/blob/main/docs/runbooks/csv-uploads.md';

  const { pushToast } = useToast();
  const datasetSource = useDatasetStore((state) => state.source);
  const runtimeContext = useMemo(
    () => buildRuntimeContextPayload(datasetSource),
    [datasetSource],
  );
  const [status, setStatus] = useState<LoadStatus>('loading');
  const [connections, setConnections] = useState<AirbyteConnectionRecord[]>([]);
  const [summary, setSummary] = useState<AirbyteConnectionsSummary | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [providerFilter, setProviderFilter] = useState('all');
  const [statusFilter, setStatusFilter] = useState<ConnectionState | 'all'>('all');
  const [query, setQuery] = useState('');
  const [syncingId, setSyncingId] = useState<string | null>(null);
  const [connectProvider, setConnectProvider] = useState<ConnectProvider | null>(null);
  const [connectForm, setConnectForm] = useState<ConnectFormState>(buildInitialConnectForm('META'));
  const [savingConnect, setSavingConnect] = useState(false);
  const [metaConnectStep, setMetaConnectStep] = useState<MetaConnectStep>('idle');
  const [metaOAuthSelection, setMetaOAuthSelection] = useState<MetaOAuthSelectionState>({
    selectionToken: null,
    pages: [],
    adAccounts: [],
    instagramAccounts: [],
    selectedPageId: '',
    selectedAdAccountId: '',
    selectedInstagramAccountId: '',
  });
  const [metaOAuthStarting, setMetaOAuthStarting] = useState(false);
  const [metaOAuthExchanging, setMetaOAuthExchanging] = useState(false);
  const [metaOAuthSavingPage, setMetaOAuthSavingPage] = useState(false);
  const [metaConnectedCredential, setMetaConnectedCredential] =
    useState<PlatformCredentialRecord | null>(null);
  const [metaConnectedInstagramAccount, setMetaConnectedInstagramAccount] =
    useState<MetaInstagramAccount | null>(null);
  const [metaSetupStatus, setMetaSetupStatus] = useState<MetaSetupStatusResponse | null>(null);
  const [metaSetupLoading, setMetaSetupLoading] = useState(false);
  const [metaPermissionDiagnostics, setMetaPermissionDiagnostics] =
    useState<MetaPermissionDiagnosticsState>(EMPTY_META_PERMISSION_DIAGNOSTICS);
  const [socialStatus, setSocialStatus] = useState<SocialPlatformStatusRecord[]>([]);
  const [socialStatusLoad, setSocialStatusLoad] = useState<SocialStatusLoad>('loading');
  const [socialStatusError, setSocialStatusError] = useState<string | null>(null);
  const [socialActionPendingPlatform, setSocialActionPendingPlatform] = useState<string | null>(
    null,
  );
  const socialSectionRef = useRef<HTMLElement | null>(null);
  const focusSocialView = useMemo(() => {
    if (typeof window === 'undefined') {
      return false;
    }
    const params = new URLSearchParams(window.location.search);
    return params.get('sources') === 'social';
  }, []);

  const loadData = useCallback(async () => {
    setStatus('loading');
    setError(null);
    setSocialStatusLoad('loading');
    setSocialStatusError(null);
    try {
      const [connectionsPayload, summaryPayload] = await Promise.all([
        loadAirbyteConnections(),
        loadAirbyteSummary(),
      ]);
      setConnections(connectionsPayload);
      setSummary(summaryPayload);
      setStatus('loaded');

      try {
        const socialPayload = await loadSocialConnectionStatus();
        setSocialStatus(socialPayload.platforms);
        setSocialStatusLoad('loaded');
      } catch (socialError) {
        const socialMessage =
          socialError instanceof Error
            ? socialError.message
            : 'Unable to load social connection status.';
        setSocialStatus([]);
        setSocialStatusLoad('error');
        setSocialStatusError(socialMessage);
      }
    } catch (loadError) {
      const message =
        loadError instanceof Error ? loadError.message : 'Unable to load data sources.';
      setError(message);
      setSocialStatus([]);
      setSocialStatusLoad('loaded');
      setSocialStatusError(null);
      setStatus('error');
    }
  }, []);

  useEffect(() => {
    void loadData();
  }, [loadData]);

  useEffect(() => {
    if (!focusSocialView) {
      return;
    }
    if (status !== 'loaded') {
      return;
    }
    const node = socialSectionRef.current;
    if (node && typeof node.scrollIntoView === 'function') {
      node.scrollIntoView({ behavior: 'smooth', block: 'start' });
    }
  }, [focusSocialView, status]);

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
    if (connectProvider !== 'META') {
      return;
    }
    let cancelled = false;
    setMetaSetupLoading(true);
    void loadMetaSetupStatus(runtimeContext)
      .then((payload) => {
        if (cancelled) {
          return;
        }
        setMetaSetupStatus(payload);
      })
      .catch(() => {
        if (cancelled) {
          return;
        }
        setMetaSetupStatus(null);
      })
      .finally(() => {
        if (!cancelled) {
          setMetaSetupLoading(false);
        }
      });

    return () => {
      cancelled = true;
    };
  }, [connectProvider, runtimeContext]);

  const resetMetaOAuthState = useCallback(() => {
    setMetaConnectStep('idle');
    setMetaOAuthSelection({
      selectionToken: null,
      pages: [],
      adAccounts: [],
      instagramAccounts: [],
      selectedPageId: '',
      selectedAdAccountId: '',
      selectedInstagramAccountId: '',
    });
    setMetaConnectedCredential(null);
    setMetaConnectedInstagramAccount(null);
    setMetaPermissionDiagnostics(EMPTY_META_PERMISSION_DIAGNOSTICS);
    setMetaOAuthStarting(false);
    setMetaOAuthExchanging(false);
    setMetaOAuthSavingPage(false);
  }, []);

  useEffect(() => {
    if (typeof window === 'undefined') {
      return;
    }
    const params = new URLSearchParams(window.location.search);
    const code = params.get('code');
    const state = params.get('state');
    const oauthError = params.get('error') || params.get('error_reason');
    const oauthErrorDescription = params.get('error_description');

    if (!oauthError && (!code || !state)) {
      return;
    }

    const clearOAuthParams = () => {
      window.sessionStorage.removeItem(META_OAUTH_PROVIDER_KEY);
      const nextUrl = `${window.location.pathname}${window.location.hash}`;
      window.history.replaceState({}, document.title, nextUrl);
    };
    const clearOAuthMarkers = () => {
      window.sessionStorage.removeItem(META_OAUTH_FLOW_SESSION_KEY);
      clearOAuthParams();
    };
    const oauthFlow = window.sessionStorage.getItem(META_OAUTH_FLOW_SESSION_KEY);

    const isWrongOAuthFlowError = (error: unknown): boolean => {
      if (error instanceof ApiError) {
        const code = (error.payload as { code?: unknown } | undefined)?.code;
        if (typeof code === 'string' && code === 'wrong_oauth_flow') {
          return true;
        }
      }
      if (!(error instanceof Error)) {
        return false;
      }
      const message = error.message.toLowerCase();
      return (
        message.includes('wrong_oauth_flow') ||
        message.includes('oauth state belongs to the marketing flow') ||
        message.includes('page insights flow')
      );
    };

    const handlePageInsightsCallback = async () => {
      const response = await callbackMetaOAuth(code ?? '', state ?? '');
      const missingPermissions = response.missing_required_permissions ?? [];
      if (missingPermissions.length > 0) {
        pushToast(
          `Missing required permissions: ${missingPermissions.join(', ')}`,
          { tone: 'error' },
        );
        return;
      }
      const pageCount = response.pages?.length ?? 0;
      const fallbackDefaultPageId =
        response.pages?.find((page) => page.is_default)?.page_id ?? response.pages?.[0]?.page_id;
      const defaultPageId = response.default_page_id ?? fallbackDefaultPageId;
      pushToast(
        pageCount > 0
          ? 'Meta Page Insights connected. Loading page dashboard.'
          : 'Meta connected, but no eligible Pages were returned.',
        { tone: pageCount > 0 ? 'success' : 'error' },
      );
      if (import.meta.env.MODE === 'test') {
        return;
      }
      const destination = defaultPageId
        ? `/dashboards/meta/pages/${defaultPageId}/overview`
        : '/dashboards/meta/pages';
      window.location.assign(destination);
    };

    const handleMarketingCallback = async () => {
      setConnectProvider('META');
      setConnectForm(buildInitialConnectForm('META'));
      setMetaConnectStep('oauth-pending');

      const response = await exchangeMetaOAuthCode({
        code: code ?? '',
        state: state ?? '',
        runtime_context: runtimeContext,
      });
      setMetaPermissionDiagnostics({
        grantedPermissions: response.granted_permissions ?? [],
        declinedPermissions: response.declined_permissions ?? [],
        missingRequiredPermissions: response.missing_required_permissions ?? [],
        tokenDebugValid: Boolean(response.token_debug_valid),
        oauthConnectedButMissingPermissions: Boolean(
          response.oauth_connected_but_missing_permissions,
        ),
      });
      if (response.missing_required_permissions.length) {
        setMetaConnectStep('oauth-pending');
        pushToast(
          'Meta OAuth connected, but required permissions are missing. Re-request permissions and reconnect.',
          { tone: 'error' },
        );
        return;
      }
      const firstPageId = response.pages[0]?.id ?? '';
      const firstAdAccountId = response.ad_accounts[0]?.id ?? '';
      const firstInstagramAccountId = response.instagram_accounts[0]?.id ?? '';
      setMetaOAuthSelection({
        selectionToken: response.selection_token,
        pages: response.pages,
        adAccounts: response.ad_accounts,
        instagramAccounts: response.instagram_accounts,
        selectedPageId: firstPageId,
        selectedAdAccountId: firstAdAccountId,
        selectedInstagramAccountId: firstInstagramAccountId,
      });
      if (!response.ad_accounts.length) {
        setMetaConnectStep('oauth-pending');
        pushToast(
          'Meta OAuth complete, but no ad accounts were returned. Add ad account access in Meta Business Manager and reconnect.',
          { tone: 'error' },
        );
        return;
      }
      setMetaConnectStep('page-selection');
      pushToast(
        'Meta OAuth complete. Select your business page and ad account to finish setup.',
        {
          tone: 'success',
        },
      );
    };

    if (oauthError) {
      pushToast(
        oauthErrorDescription?.trim()
          ? `OAuth failed: ${oauthErrorDescription}`
          : `OAuth failed: ${oauthError}`,
        { tone: 'error' },
      );
      clearOAuthMarkers();
      return;
    }

    setMetaOAuthExchanging(true);
    void (async () => {
      try {
        const shouldTryPageInsightsFirst =
          oauthFlow === META_OAUTH_FLOW_PAGE_INSIGHTS || !oauthFlow;
        if (shouldTryPageInsightsFirst) {
          try {
            await handlePageInsightsCallback();
            return;
          } catch (pageInsightsError) {
            const shouldFallbackToMarketing =
              oauthFlow !== META_OAUTH_FLOW_PAGE_INSIGHTS &&
              isWrongOAuthFlowError(pageInsightsError);
            if (!shouldFallbackToMarketing) {
              throw pageInsightsError;
            }
          }
        }
        await handleMarketingCallback();
      } catch (oauthExchangeError) {
        const message =
          oauthExchangeError instanceof Error
            ? oauthExchangeError.message
            : 'Meta OAuth callback failed.';
        pushToast(message, { tone: 'error' });
      } finally {
        setMetaOAuthExchanging(false);
        clearOAuthMarkers();
      }
    })();
  }, [pushToast, runtimeContext]);

  const handleStartMetaOAuth = useCallback(
    async (options?: { openPanelOnError?: boolean; authType?: 'rerequest' }) => {
      if (metaOAuthStarting || metaOAuthExchanging) {
        return;
      }
      setMetaOAuthStarting(true);
      try {
        if (typeof window !== 'undefined') {
          window.sessionStorage.setItem(META_OAUTH_PROVIDER_KEY, 'META');
        }
        const hasRuntimeContext = Boolean(
          runtimeContext.client_origin ||
            runtimeContext.client_port ||
            runtimeContext.dataset_source,
        );
        const response = await startMetaOAuth(
          options?.authType || hasRuntimeContext
            ? {
                ...(options?.authType ? { auth_type: options.authType } : {}),
                ...(hasRuntimeContext ? { runtime_context: runtimeContext } : {}),
              }
            : undefined,
        );
        if (typeof window !== 'undefined') {
          if (import.meta.env.MODE === 'test') {
            return;
          }
          window.location.assign(response.authorize_url);
        }
      } catch (oauthStartError) {
        const message =
          oauthStartError instanceof Error
            ? oauthStartError.message
            : 'Unable to start Meta OAuth.';
        pushToast(message, { tone: 'error' });
        if (options?.openPanelOnError) {
          setConnectProvider('META');
          setConnectForm(buildInitialConnectForm('META'));
          resetMetaOAuthState();
        }
      } finally {
        setMetaOAuthStarting(false);
      }
    },
    [metaOAuthExchanging, metaOAuthStarting, pushToast, resetMetaOAuthState, runtimeContext],
  );

  const handleMetaPageConnect = useCallback(async () => {
    if (metaPermissionDiagnostics.missingRequiredPermissions.length) {
      pushToast('Required Meta permissions are missing. Re-request permissions first.', {
        tone: 'error',
      });
      return;
    }
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
        ad_account_id: metaOAuthSelection.selectedAdAccountId,
        instagram_account_id: metaOAuthSelection.selectedInstagramAccountId || undefined,
      });
      setMetaPermissionDiagnostics((previous) => ({
        ...previous,
        grantedPermissions: response.granted_permissions ?? previous.grantedPermissions,
        declinedPermissions: response.declined_permissions ?? previous.declinedPermissions,
        missingRequiredPermissions:
          response.missing_required_permissions ?? previous.missingRequiredPermissions,
      }));
      setMetaConnectedCredential(response.credential);
      setMetaConnectedInstagramAccount(response.instagram_account ?? null);
      setMetaConnectStep('credential-connected');
      setConnectForm((previous) => ({
        ...previous,
        accountId: response.credential.account_id,
      }));
      const instagramSuffix =
        response.instagram_account?.username?.trim() || response.instagram_account?.id
          ? ` Instagram linked: ${response.instagram_account?.username?.trim() || response.instagram_account?.id}.`
          : '';
      pushToast(
        `Connected Meta business asset ${response.credential.account_id}.${instagramSuffix}`,
        {
          tone: 'success',
        },
      );
    } catch (metaConnectError) {
      const message =
        metaConnectError instanceof Error
          ? metaConnectError.message
          : 'Unable to connect selected Meta page.';
      pushToast(message, { tone: 'error' });
    } finally {
      setMetaOAuthSavingPage(false);
    }
  }, [metaOAuthSavingPage, metaOAuthSelection, metaPermissionDiagnostics, pushToast]);

  const handleRerequestMetaPermissions = useCallback(async () => {
    await handleStartMetaOAuth({ authType: 'rerequest' });
  }, [handleStartMetaOAuth]);

  const handleDisconnectMetaOAuth = useCallback(async () => {
    try {
      const payload = await logoutMetaOAuth();
      if (payload.disconnected) {
        pushToast('Meta OAuth disconnected for this tenant.', { tone: 'success' });
      } else {
        pushToast('No Meta OAuth credentials were connected.', { tone: 'info' });
      }
      resetMetaOAuthState();
      void loadData();
    } catch (disconnectError) {
      const message =
        disconnectError instanceof Error
          ? disconnectError.message
          : 'Unable to disconnect Meta OAuth.';
      pushToast(message, { tone: 'error' });
    }
  }, [loadData, pushToast, resetMetaOAuthState]);

  const openConnectPanel = useCallback(
    (provider: ConnectProvider) => {
      setConnectProvider(provider);
      setConnectForm(buildInitialConnectForm(provider));
      if (provider === 'META') {
        resetMetaOAuthState();
      }
    },
    [resetMetaOAuthState],
  );

  const closeConnectPanel = useCallback(() => {
    setConnectProvider(null);
    setSavingConnect(false);
    resetMetaOAuthState();
  }, [resetMetaOAuthState]);

  const handleRunNow = useCallback(
    async (connection: AirbyteConnectionRecord) => {
      if (!connection.id || syncingId === connection.id) {
        return;
      }
      setSyncingId(connection.id);
      try {
        const response = await triggerAirbyteSync(connection.id);
        const jobId = response?.job_id;
        pushToast(jobId ? `Sync triggered (job ${jobId}).` : 'Sync triggered.', {
          tone: 'success',
        });
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

  const handleConnectFieldChange = useCallback(
    (field: keyof ConnectFormState, value: string | boolean) => {
      setConnectForm((previous) => ({
        ...previous,
        [field]: value,
      }));
    },
    [],
  );

  const handleSocialPrimaryAction = useCallback(
    async (platformStatus: SocialPlatformCard) => {
      if (platformStatus.isPlaceholder) {
        return;
      }
      if (platformStatus.actions.includes('connect_oauth')) {
        setSocialActionPendingPlatform(platformStatus.platform);
        try {
          await handleStartMetaOAuth({ openPanelOnError: true });
        } finally {
          setSocialActionPendingPlatform(null);
        }
        return;
      }
      if (platformStatus.actions.includes('sync_now')) {
        const metaConnection = connections
          .filter((connection) => connection.provider === 'META')
          .sort((a, b) => {
            const aTime = a.updated_at ? new Date(a.updated_at).getTime() : 0;
            const bTime = b.updated_at ? new Date(b.updated_at).getTime() : 0;
            return bTime - aTime;
          })[0];
        if (metaConnection) {
          await handleRunNow(metaConnection);
          return;
        }
      }
      openConnectPanel('META');
    },
    [connections, handleRunNow, handleStartMetaOAuth, openConnectPanel],
  );

  const handleConnectSubmit = useCallback(
    async (event: FormEvent<HTMLFormElement>) => {
      event.preventDefault();
      if (!connectProvider || savingConnect) {
        return;
      }

      if (connectForm.linkConnection) {
        const connectionName = connectForm.connectionName.trim();
        if (!connectionName) {
          pushToast('Connection name is required.', { tone: 'error' });
          return;
        }
        if (connectForm.workspaceId.trim() && !UUID_REGEX.test(connectForm.workspaceId.trim())) {
          pushToast('Workspace UUID format is invalid.', { tone: 'error' });
          return;
        }
        if (
          connectForm.destinationId.trim() &&
          !UUID_REGEX.test(connectForm.destinationId.trim())
        ) {
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
        if (connectProvider === 'META') {
          if (metaPermissionDiagnostics.missingRequiredPermissions.length) {
            pushToast('Re-request required Meta permissions before provisioning or sync.', {
              tone: 'error',
            });
            return;
          }
          if (!metaConnectedCredential) {
            pushToast('Complete Meta OAuth and save a business page first.', { tone: 'error' });
            return;
          }

          if (connectForm.linkConnection) {
            const scheduleType = connectForm.scheduleType;
            await provisionMetaIntegration({
              external_account_id: metaConnectedCredential.account_id,
              workspace_id: connectForm.workspaceId.trim() || null,
              destination_id: connectForm.destinationId.trim() || null,
              connection_name: connectForm.connectionName.trim(),
              schedule_type: scheduleType,
              is_active: connectForm.isActive,
              interval_minutes:
                scheduleType === 'interval' ? Number(connectForm.intervalMinutes) : null,
              cron_expression: scheduleType === 'cron' ? connectForm.cronExpression.trim() : '',
            });
            const syncPayload = await syncMetaIntegration();
            if (syncPayload.job_id) {
              pushToast(`Meta insights sync started (job ${syncPayload.job_id}).`, {
                tone: 'success',
              });
            }
          }
        } else {
          const accountId = connectForm.accountId.trim();
          const accessToken = connectForm.accessToken.trim();
          if (!accountId || !accessToken) {
            pushToast('Account ID and access token are required.', { tone: 'error' });
            return;
          }

          await createPlatformCredential({
            provider: connectProvider,
            account_id: accountId,
            access_token: accessToken,
            refresh_token: connectForm.refreshToken.trim() || null,
          });

          if (connectForm.linkConnection) {
            const connectionId = connectForm.connectionId.trim();
            if (!connectionId) {
              pushToast('Airbyte connection UUID is required when linking Google.', {
                tone: 'error',
              });
              return;
            }
            if (!UUID_REGEX.test(connectionId)) {
              pushToast('Connection UUID format is invalid.', { tone: 'error' });
              return;
            }

            const scheduleType = connectForm.scheduleType;
            const payload = {
              name: connectForm.connectionName.trim(),
              connection_id: connectionId,
              workspace_id: connectForm.workspaceId.trim() || null,
              provider: connectProvider,
              schedule_type: scheduleType,
              is_active: connectForm.isActive,
              interval_minutes:
                scheduleType === 'interval' ? Number(connectForm.intervalMinutes) : null,
              cron_expression: scheduleType === 'cron' ? connectForm.cronExpression.trim() : '',
            } as const;
            await createAirbyteConnection(payload);
          }
        }

        pushToast(
          connectForm.linkConnection
            ? `${CONNECT_PROVIDER_LABELS[connectProvider]} connected and linked.`
            : `${CONNECT_PROVIDER_LABELS[connectProvider]} credentials saved.`,
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
      metaConnectedCredential,
      metaPermissionDiagnostics,
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

  const socialCards = useMemo<SocialPlatformCard[]>(() => {
    const sourceMap = new Map<string, SocialPlatformStatusRecord>();
    socialStatus.forEach((row) => {
      sourceMap.set(row.platform, row);
    });
    const ordered = SOCIAL_PLATFORM_ORDER.map((platform) => {
      const existing = sourceMap.get(platform);
      return (
        existing ?? {
          platform,
          display_name: platform === 'meta' ? 'Meta (Facebook)' : 'Instagram (Business)',
          status: 'not_connected' as SocialConnectionStatus,
          reason: { code: 'missing_status_payload', message: 'Status has not been loaded yet.' },
          last_checked_at: null,
          last_synced_at: null,
          actions: ['connect_oauth'],
          metadata: {},
        }
      );
    });
    const placeholders: SocialPlatformCard[] = SOCIAL_PLACEHOLDERS.map((row) => ({
      platform: row.platform,
      display_name: row.display_name,
      status: 'not_connected',
      reason: { code: 'coming_soon', message: row.description },
      last_checked_at: null,
      last_synced_at: null,
      actions: [],
      metadata: {},
      isPlaceholder: true,
    }));
    return [...ordered, ...placeholders];
  }, [socialStatus]);

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
      due: connections.filter((connection) => resolveConnectionState(connection) === 'stale')
        .length,
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

        <section
          className="social-connections-panel"
          aria-labelledby="social-connections-title"
          ref={socialSectionRef}
        >
          <div className="panel-header__title-row">
            <h3 id="social-connections-title">Social connections</h3>
            <span className={`status-pill ${focusSocialView ? 'warning' : 'muted'}`}>
              {focusSocialView ? 'Social setup view' : 'Status checker'}
            </span>
          </div>
          <p className="status-message muted">
            Track social connector progress across Meta and Instagram with actionable setup status.
          </p>
          <div className="dashboard-header__actions-row" style={{ marginBottom: '0.75rem' }}>
            <a className="button tertiary" href="/integrations/meta">
              New Meta integration
            </a>
            <a className="button tertiary" href="/dashboards/meta/accounts">
              Meta accounts
            </a>
            <a className="button tertiary" href="/dashboards/meta/campaigns">
              Campaign overview
            </a>
            <a className="button tertiary" href="/dashboards/meta/insights">
              Insights dashboard
            </a>
            <a className="button tertiary" href="/dashboards/meta/status">
              Connection status
            </a>
          </div>
          {socialStatusLoad === 'loading' ? (
            <p className="status-message muted">Loading social connection status…</p>
          ) : null}
          {socialStatusLoad === 'error' ? (
            <p className="status-message error">
              {socialStatusError ?? 'Could not load social connection status.'}
            </p>
          ) : null}
          <div className="social-connections-grid">
            {socialCards.map((platformStatus) => {
              const statusTone = resolveSocialStatusTone(platformStatus.status);
              const statusLabel = resolveSocialStatusLabel(platformStatus.status);
              const primaryActionLabel = resolveSocialPrimaryAction(
                platformStatus.status,
                platformStatus.actions,
              );
              const checkedLabel = formatRelativeTime(platformStatus.last_checked_at ?? null);
              const syncedLabel = formatRelativeTime(platformStatus.last_synced_at ?? null);
              return (
                <article key={platformStatus.platform} className="social-connection-card">
                  <div className="social-connection-card__header">
                    <h4>{platformStatus.display_name}</h4>
                    <span className={`status-pill ${statusTone}`}>{statusLabel}</span>
                  </div>
                  <p className="status-message muted">{platformStatus.reason.message}</p>
                  <dl className="social-connection-card__meta">
                    <div>
                      <dt>Checked</dt>
                      <dd>{checkedLabel ?? '—'}</dd>
                    </div>
                    <div>
                      <dt>Last sync</dt>
                      <dd>{syncedLabel ?? 'Never'}</dd>
                    </div>
                  </dl>
                  <div className="social-connection-card__actions">
                    <button
                      type="button"
                      className="button secondary"
                      onClick={() => void handleSocialPrimaryAction(platformStatus)}
                      disabled={
                        platformStatus.isPlaceholder ||
                        socialActionPendingPlatform === platformStatus.platform ||
                        (platformStatus.actions.includes('connect_oauth') &&
                          (metaOAuthStarting || metaOAuthExchanging))
                      }
                    >
                      {platformStatus.isPlaceholder
                        ? 'Coming soon'
                        : socialActionPendingPlatform === platformStatus.platform &&
                            platformStatus.actions.includes('connect_oauth')
                          ? 'Redirecting…'
                          : primaryActionLabel}
                    </button>
                  </div>
                </article>
              );
            })}
          </div>
        </section>

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
            <select
              value={providerFilter}
              onChange={(event) => setProviderFilter(event.target.value)}
            >
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
            <button
              type="button"
              className="button secondary"
              onClick={() => openConnectPanel('META')}
            >
              Connect Meta
            </button>
            <button
              type="button"
              className="button secondary"
              onClick={() => openConnectPanel('GOOGLE')}
            >
              Connect Google Ads
            </button>
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
          Meta connects through Facebook OAuth so you can select a business page, ad account, and
          optional Instagram business account, then provision insights sync. Google Ads currently
          uses direct credential entry.
        </p>

        {connectProvider ? (
          <form className="data-sources-connect-form" onSubmit={handleConnectSubmit}>
            <header className="data-sources-connect-form__header">
              <div>
                <h3>{`Connect ${CONNECT_PROVIDER_LABELS[connectProvider]}`}</h3>
                <p className="status-message muted">
                  Save API credentials and optionally link an existing Airbyte connection record.
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

            {connectProvider === 'META' ? (
              <>
                <div className="data-sources-connect-form__grid">
                  <div className="dashboard-field">
                    <span className="dashboard-field__label">Meta setup checklist</span>
                    {metaSetupLoading ? (
                      <p className="status-message muted">Checking backend setup…</p>
                    ) : null}
                    {!metaSetupLoading && !metaSetupStatus ? (
                      <p className="status-message error">
                        Could not load setup status. Confirm backend is running and authenticated.
                      </p>
                    ) : null}
                    {metaSetupStatus ? (
                      <div>
                        <p className="status-message muted">
                          OAuth ready:{' '}
                          <span
                            className={`status-pill ${metaSetupStatus.ready_for_oauth ? 'success' : 'error'}`}
                          >
                            {metaSetupStatus.ready_for_oauth ? 'Yes' : 'No'}
                          </span>{' '}
                          Provision defaults ready:{' '}
                          <span
                            className={`status-pill ${
                              metaSetupStatus.ready_for_provisioning_defaults
                                ? 'success'
                                : 'warning'
                            }`}
                          >
                            {metaSetupStatus.ready_for_provisioning_defaults
                              ? 'Yes'
                              : 'Missing defaults'}
                          </span>
                        </p>
                        {metaSetupStatus.missing_env_vars?.length ? (
                          <p className="status-message error">
                            Missing env vars:{' '}
                            {metaSetupStatus.missing_env_vars.map((name, index) => (
                              <span key={name}>
                                <code>{name}</code>
                                {index < metaSetupStatus.missing_env_vars!.length - 1 ? ', ' : ''}
                              </span>
                            ))}
                          </p>
                        ) : null}
                        <ul className="status-message muted">
                          {metaSetupStatus.checks.map((check) => (
                            <li key={check.key}>
                              <span className={`status-pill ${check.ok ? 'success' : 'error'}`}>
                                {check.ok ? 'OK' : 'Missing'}
                              </span>{' '}
                              {check.label}
                              {check.using_fallback_default ? ' (using built-in default)' : ''}
                              {!check.ok && check.missing_env_vars?.length ? (
                                <span className="status-message error">
                                  {' '}
                                  Set:{' '}
                                  {check.missing_env_vars.map((name, index) => (
                                    <span key={`${check.key}-${name}`}>
                                      <code>{name}</code>
                                      {index < check.missing_env_vars!.length - 1 ? ', ' : ''}
                                    </span>
                                  ))}
                                </span>
                              ) : null}
                            </li>
                          ))}
                        </ul>
                        <p className="status-message muted">
                          Graph API version: {metaSetupStatus.graph_api_version}
                        </p>
                        <p className="status-message muted">
                          Redirect URI: {metaSetupStatus.redirect_uri || 'Not configured'}
                        </p>
                        <p className="status-message muted">
                          Login configuration ID:{' '}
                          {metaSetupStatus.login_configuration_id || 'Not configured'}{' '}
                          {metaSetupStatus.login_configuration_required
                            ? '(required)'
                            : '(optional)'}
                        </p>
                        {metaSetupStatus.runtime_context ? (
                          <>
                            <p className="status-message muted">
                              Runtime redirect source:{' '}
                              {metaSetupStatus.runtime_context.redirect_source || 'unavailable'}
                            </p>
                            <p className="status-message muted">
                              Runtime frontend origin:{' '}
                              {metaSetupStatus.runtime_context.resolved_frontend_origin ||
                                'unresolved'}
                            </p>
                            <p className="status-message muted">
                              Runtime request host:{' '}
                              {metaSetupStatus.runtime_context.request_host || 'unavailable'}
                              {metaSetupStatus.runtime_context.request_port
                                ? `:${metaSetupStatus.runtime_context.request_port}`
                                : ''}
                            </p>
                            {metaSetupStatus.runtime_context.dev_active_profile ? (
                              <p className="status-message muted">
                                Active launcher profile:{' '}
                                {metaSetupStatus.runtime_context.dev_active_profile}
                              </p>
                            ) : null}
                            {metaSetupStatus.runtime_context.dataset_source ? (
                              <p className="status-message muted">
                                Dataset source:{' '}
                                {metaSetupStatus.runtime_context.dataset_source}
                              </p>
                            ) : null}
                          </>
                        ) : null}
                      </div>
                    ) : null}
                  </div>
                </div>

                <div className="data-sources-connect-form__grid">
                  <label className="dashboard-field">
                    <span className="dashboard-field__label">Meta OAuth</span>
                    <button
                      type="button"
                      className="button secondary"
                      onClick={() => void handleStartMetaOAuth()}
                      disabled={metaOAuthStarting || metaOAuthExchanging || metaOAuthSavingPage}
                      aria-busy={metaOAuthStarting || metaOAuthExchanging}
                    >
                      {metaOAuthStarting ? 'Redirecting…' : 'Connect with Facebook'}
                    </button>
                    <button
                      type="button"
                      className="button tertiary"
                      onClick={() => void handleRerequestMetaPermissions()}
                      disabled={metaOAuthStarting || metaOAuthExchanging || metaOAuthSavingPage}
                    >
                      Re-request permissions
                    </button>
                    <button
                      type="button"
                      className="button tertiary"
                      onClick={() => void handleDisconnectMetaOAuth()}
                      disabled={metaOAuthStarting || metaOAuthExchanging || metaOAuthSavingPage}
                    >
                      Disconnect Meta
                    </button>
                  </label>
                  <label className="dashboard-field">
                    <span className="dashboard-field__label">OAuth status</span>
                    <input type="text" value={metaConnectStep} readOnly aria-label="OAuth status" />
                  </label>
                </div>
                {metaPermissionDiagnostics.missingRequiredPermissions.length ? (
                  <div className="data-sources-connect-form__grid">
                    <div className="dashboard-field">
                      <span className="dashboard-field__label">Permission diagnostics</span>
                      <p className="status-message error">
                        Missing required permissions:{' '}
                        {metaPermissionDiagnostics.missingRequiredPermissions.join(', ')}
                      </p>
                      {metaPermissionDiagnostics.declinedPermissions.length ? (
                        <p className="status-message muted">
                          Declined permissions:{' '}
                          {metaPermissionDiagnostics.declinedPermissions.join(', ')}
                        </p>
                      ) : null}
                    </div>
                  </div>
                ) : null}

                {metaOAuthSelection.selectionToken ? (
                  <div className="data-sources-connect-form__grid">
                    <label className="dashboard-field">
                      <span className="dashboard-field__label">Business page</span>
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
                    <label className="dashboard-field">
                      <span className="dashboard-field__label">Ad account (for insights)</span>
                      <select
                        value={metaOAuthSelection.selectedAdAccountId}
                        onChange={(event) =>
                          setMetaOAuthSelection((previous) => ({
                            ...previous,
                            selectedAdAccountId: event.target.value,
                          }))
                        }
                      >
                        {metaOAuthSelection.adAccounts.map((account) => (
                          <option key={account.id} value={account.id}>
                            {account.name?.trim() ? `${account.name} (${account.id})` : account.id}
                          </option>
                        ))}
                      </select>
                    </label>
                    <label className="dashboard-field">
                      <span className="dashboard-field__label">
                        Instagram business account (optional)
                      </span>
                      <select
                        value={metaOAuthSelection.selectedInstagramAccountId}
                        onChange={(event) =>
                          setMetaOAuthSelection((previous) => ({
                            ...previous,
                            selectedInstagramAccountId: event.target.value,
                          }))
                        }
                      >
                        <option value="">No Instagram account selected</option>
                        {metaOAuthSelection.instagramAccounts.map((account) => (
                          <option key={account.id} value={account.id}>
                            {account.username?.trim()
                              ? `@${account.username} (${account.id})`
                              : account.name?.trim()
                                ? `${account.name} (${account.id})`
                                : account.id}
                          </option>
                        ))}
                      </select>
                    </label>
                    <label className="dashboard-field">
                      <span className="dashboard-field__label">Confirm selection</span>
                      <button
                        type="button"
                        className="button secondary"
                        onClick={() => void handleMetaPageConnect()}
                        disabled={
                          metaOAuthSavingPage ||
                          metaPermissionDiagnostics.missingRequiredPermissions.length > 0 ||
                          !metaOAuthSelection.selectedPageId ||
                          !metaOAuthSelection.selectedAdAccountId
                        }
                        aria-busy={metaOAuthSavingPage}
                      >
                        {metaOAuthSavingPage ? 'Saving…' : 'Save selected business page'}
                      </button>
                      {!metaOAuthSelection.selectedAdAccountId ? (
                        <p className="status-message error">
                          Meta Marketing API provisioning requires an ad account selection.
                        </p>
                      ) : null}
                    </label>
                  </div>
                ) : null}

                <div className="data-sources-connect-form__grid">
                  <label className="dashboard-field">
                    <span className="dashboard-field__label">Connected account ID</span>
                    <input
                      type="text"
                      value={metaConnectedCredential?.account_id ?? ''}
                      readOnly
                      placeholder="Complete OAuth to populate"
                    />
                  </label>
                  <label className="dashboard-field">
                    <span className="dashboard-field__label">Connected Instagram account</span>
                    <input
                      type="text"
                      value={
                        metaConnectedInstagramAccount?.username?.trim()
                          ? `@${metaConnectedInstagramAccount.username}`
                          : (metaConnectedInstagramAccount?.id ?? '')
                      }
                      readOnly
                      placeholder="Optional"
                    />
                  </label>
                  <label className="dashboard-field data-sources-checkbox-field">
                    <span className="dashboard-field__label">Auto-provision Airbyte</span>
                    <div className="data-sources-checkbox-row">
                      <input
                        type="checkbox"
                        checked={connectForm.linkConnection}
                        onChange={(event) =>
                          handleConnectFieldChange('linkConnection', event.target.checked)
                        }
                      />
                      <span>Create or reuse a Meta Airbyte source/connection now</span>
                    </div>
                  </label>
                </div>
              </>
            ) : (
              <div className="data-sources-connect-form__grid">
                <label className="dashboard-field">
                  <span className="dashboard-field__label">
                    {CONNECT_PROVIDER_ACCOUNT_LABELS[connectProvider]}
                  </span>
                  <input
                    type="text"
                    value={connectForm.accountId}
                    onChange={(event) => handleConnectFieldChange('accountId', event.target.value)}
                    placeholder="1234567890"
                    required
                  />
                </label>

                <label className="dashboard-field">
                  <span className="dashboard-field__label">Access token</span>
                  <input
                    type="password"
                    value={connectForm.accessToken}
                    onChange={(event) =>
                      handleConnectFieldChange('accessToken', event.target.value)
                    }
                    autoComplete="off"
                    required
                  />
                </label>

                <label className="dashboard-field">
                  <span className="dashboard-field__label">Refresh token (optional)</span>
                  <input
                    type="password"
                    value={connectForm.refreshToken}
                    onChange={(event) =>
                      handleConnectFieldChange('refreshToken', event.target.value)
                    }
                    autoComplete="off"
                  />
                </label>

                <label className="dashboard-field data-sources-checkbox-field">
                  <span className="dashboard-field__label">Also link Airbyte connection</span>
                  <div className="data-sources-checkbox-row">
                    <input
                      type="checkbox"
                      checked={connectForm.linkConnection}
                      onChange={(event) =>
                        handleConnectFieldChange('linkConnection', event.target.checked)
                      }
                    />
                    <span>Create/update a local Airbyte connection record now</span>
                  </div>
                </label>
              </div>
            )}

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
                {connectProvider === 'GOOGLE' ? (
                  <label className="dashboard-field">
                    <span className="dashboard-field__label">Airbyte connection UUID</span>
                    <input
                      type="text"
                      value={connectForm.connectionId}
                      onChange={(event) =>
                        handleConnectFieldChange('connectionId', event.target.value)
                      }
                      placeholder="11111111-1111-1111-1111-111111111111"
                      required
                    />
                  </label>
                ) : null}
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
                {connectProvider === 'META' ? (
                  <label className="dashboard-field">
                    <span className="dashboard-field__label">
                      Airbyte destination UUID (optional)
                    </span>
                    <input
                      type="text"
                      value={connectForm.destinationId}
                      onChange={(event) =>
                        handleConnectFieldChange('destinationId', event.target.value)
                      }
                      placeholder="bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb"
                    />
                  </label>
                ) : null}
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
