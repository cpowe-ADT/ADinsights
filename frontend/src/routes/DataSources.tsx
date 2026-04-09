import { useCallback, useEffect, useMemo, useRef, useState, type FormEvent } from 'react';
import { Link } from 'react-router-dom';

import EmptyState from '../components/EmptyState';
import { useToast } from '../components/ToastProvider';
import { ApiError } from '../lib/apiClient';
import {
  connectMetaPage,
  exchangeGoogleAdsOAuthCode,
  exchangeGoogleAnalyticsOAuthCode,
  exchangeMetaOAuthCode,
  loadGoogleAdsSetupStatus,
  loadGoogleAdsStatus,
  loadGoogleAnalyticsProperties,
  loadGoogleAnalyticsSetupStatus,
  loadGoogleAnalyticsStatus,
  loadAirbyteConnections,
  loadAirbyteSummary,
  loadMetaSetupStatus,
  logoutMetaOAuth,
  loadSocialConnectionStatus,
  previewMetaRecovery,
  provisionGoogleAds,
  provisionGoogleAnalytics,
  provisionMetaIntegration,
  startGoogleAdsOAuth,
  startGoogleAnalyticsOAuth,
  syncMetaIntegration,
  startMetaOAuth,
  triggerAirbyteSync,
  type AirbyteConnectionRecord,
  type AirbyteConnectionsSummary,
  type GoogleAdsSetupStatusResponse,
  type GoogleAdsStatusResponse,
  type GoogleAnalyticsPropertyRecord,
  type GoogleAnalyticsSetupStatusResponse,
  type GoogleAnalyticsStatusResponse,
  type MetaAdAccount,
  type MetaInstagramAccount,
  type MetaOAuthExchangeResponse,
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
import {
  loadDatasetStatus,
  type DatasetLiveReason,
} from '../lib/datasetStatus';
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
  GA4: 'Google Analytics 4',
  LINKEDIN: 'LinkedIn',
  TIKTOK: 'TikTok',
  UNKNOWN: 'Unknown provider',
};

const FAILURE_STATUSES = new Set(['failed', 'error', 'cancelled']);
const RUNNING_STATUSES = new Set(['running', 'pending', 'in_progress']);

type LoadStatus = 'loading' | 'loaded' | 'error';

type ConnectionState = 'healthy' | 'stale' | 'paused' | 'needs-attention' | 'syncing';
type ConnectProvider = 'META' | 'GOOGLE' | 'GA4';
type MetaConnectStep = 'idle' | 'oauth-pending' | 'page-selection' | 'credential-connected';
type GoogleAdsConnectStep = 'idle' | 'oauth-pending' | 'connected';
type Ga4ConnectStep = 'idle' | 'oauth-pending' | 'property-selection' | 'connected';
type SocialStatusLoad = 'loading' | 'loaded' | 'error';
type MetaReportingNoteTone = 'success' | 'info' | 'warning';

interface ConnectFormState {
  accountId: string;
  loginCustomerId: string;
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
  source: string | null;
  recoveredFromExistingToken: boolean;
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

const CONNECT_OAUTH_PROVIDER_KEY = 'adinsights.connect.oauth.provider';
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
  GA4: 'Google Analytics 4',
};

const CONNECT_PROVIDER_ACCOUNT_LABELS: Record<'GOOGLE', string> = {
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
  loginCustomerId: '',
  accessToken: '',
  refreshToken: '',
  linkConnection: provider === 'META' || provider === 'GOOGLE',
  connectionName:
    provider === 'META'
      ? 'Meta Metrics Connection'
      : provider === 'GA4'
        ? 'Google Analytics Property Connection'
        : 'Google Ads Metrics Connection',
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

const ensureConnectionsArray = (value: unknown): AirbyteConnectionRecord[] => {
  if (Array.isArray(value)) {
    return value;
  }
  if (
    value &&
    typeof value === 'object' &&
    'results' in value &&
    Array.isArray((value as { results?: unknown }).results)
  ) {
    return (value as { results: AirbyteConnectionRecord[] }).results;
  }
  return [];
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

const resolveSocialPrimaryAction = (platformStatus: SocialPlatformCard): string => {
  const { platform, status, actions } = platformStatus;
  if (platform === 'instagram') {
    if (actions.includes('open_meta_setup')) {
      return status === 'not_connected' ? 'Open Meta setup' : 'Link in Meta setup';
    }
    if (actions.includes('view')) {
      return 'View Meta status';
    }
  }
  if (actions.includes('recover_marketing_access')) {
    return 'Restore Meta marketing access';
  }
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

const resolveDirectSyncStatusLabel = (value?: string): string => {
  if (value === 'blocked') {
    return 'Blocked';
  }
  if (value === 'pending') {
    return 'Pending';
  }
  if (value === 'running') {
    return 'Running';
  }
  if (value === 'failed') {
    return 'Failed';
  }
  if (value === 'paused') {
    return 'Paused';
  }
  if (value === 'complete_no_data') {
    return 'Complete (no data)';
  }
  if (value === 'complete') {
    return 'Complete';
  }
  return 'Unknown';
};

const resolveWarehouseStatusLabel = (value?: string): string => {
  if (value === 'disabled') {
    return 'Disabled';
  }
  if (value === 'waiting_snapshot') {
    return 'Waiting snapshot';
  }
  if (value === 'refreshing_snapshot') {
    return 'Refreshing';
  }
  if (value === 'fallback_snapshot') {
    return 'Fallback';
  }
  if (value === 'ready') {
    return 'Ready';
  }
  return 'Unknown';
};

const resolveGa4PrimaryAction = (status: GoogleAnalyticsStatusResponse['status']): string => {
  if (status === 'not_connected') {
    return 'Open GA4 setup';
  }
  if (status === 'started_not_complete') {
    return 'Continue GA4 setup';
  }
  if (status === 'complete') {
    return 'Open GA4 setup';
  }
  return 'Manage GA4';
};

const resolveGoogleAdsPrimaryAction = (
  status: GoogleAdsStatusResponse['status'],
  actions: string[],
): string => {
  if (actions.includes('connect_oauth') || status === 'not_connected') {
    return 'Open Google Ads setup';
  }
  if (actions.includes('provision') || status === 'started_not_complete') {
    return 'Continue Google Ads setup';
  }
  if (actions.includes('sync_now')) {
    return 'Run Google Ads sync';
  }
  if (status === 'complete') {
    return 'Open Google Ads setup';
  }
  return 'Manage Google Ads';
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
    source: null,
    recoveredFromExistingToken: false,
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
  const [metaReportingStatusNote, setMetaReportingStatusNote] = useState<{
    tone: MetaReportingNoteTone;
    message: string;
  } | null>(null);
  const [googleAdsConnectStep, setGoogleAdsConnectStep] =
    useState<GoogleAdsConnectStep>('idle');
  const [googleAdsCredential, setGoogleAdsCredential] =
    useState<PlatformCredentialRecord | null>(null);
  const [googleAdsSetupStatus, setGoogleAdsSetupStatus] =
    useState<GoogleAdsSetupStatusResponse | null>(null);
  const [googleAdsSetupLoading, setGoogleAdsSetupLoading] = useState(false);
  const [googleAdsStatus, setGoogleAdsStatus] = useState<GoogleAdsStatusResponse | null>(null);
  const [googleAdsStatusLoad, setGoogleAdsStatusLoad] = useState<LoadStatus>('loading');
  const [googleAdsStatusError, setGoogleAdsStatusError] = useState<string | null>(null);
  const [googleAdsOAuthStarting, setGoogleAdsOAuthStarting] = useState(false);
  const [googleAdsOAuthExchanging, setGoogleAdsOAuthExchanging] = useState(false);
  const [ga4ConnectStep, setGa4ConnectStep] = useState<Ga4ConnectStep>('idle');
  const [ga4Credential, setGa4Credential] = useState<PlatformCredentialRecord | null>(null);
  const [ga4Properties, setGa4Properties] = useState<GoogleAnalyticsPropertyRecord[]>([]);
  const [ga4SelectedPropertyId, setGa4SelectedPropertyId] = useState('');
  const [ga4SetupStatus, setGa4SetupStatus] = useState<GoogleAnalyticsSetupStatusResponse | null>(
    null,
  );
  const [ga4SetupLoading, setGa4SetupLoading] = useState(false);
  const [ga4Status, setGa4Status] = useState<GoogleAnalyticsStatusResponse | null>(null);
  const [ga4StatusLoad, setGa4StatusLoad] = useState<LoadStatus>('loading');
  const [ga4StatusError, setGa4StatusError] = useState<string | null>(null);
  const [ga4OAuthStarting, setGa4OAuthStarting] = useState(false);
  const [ga4OAuthExchanging, setGa4OAuthExchanging] = useState(false);
  const [ga4PropertiesLoading, setGa4PropertiesLoading] = useState(false);
  const [socialStatus, setSocialStatus] = useState<SocialPlatformStatusRecord[]>([]);
  const [socialStatusLoad, setSocialStatusLoad] = useState<SocialStatusLoad>('loading');
  const [socialStatusError, setSocialStatusError] = useState<string | null>(null);
  const [socialActionPendingPlatform, setSocialActionPendingPlatform] = useState<string | null>(
    null,
  );
  const normalizedConnections = ensureConnectionsArray(connections);
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
    setGoogleAdsStatusLoad('loading');
    setGoogleAdsStatusError(null);
    setGa4StatusLoad('loading');
    setGa4StatusError(null);
    try {
      const [connectionsPayload, summaryPayload] = await Promise.all([
        loadAirbyteConnections(),
        loadAirbyteSummary(),
      ]);
      setConnections(ensureConnectionsArray(connectionsPayload));
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

      try {
        const googleAdsPayload = await loadGoogleAdsStatus();
        setGoogleAdsStatus(googleAdsPayload);
        setGoogleAdsStatusLoad('loaded');
      } catch (googleAdsError) {
        const googleAdsMessage =
          googleAdsError instanceof Error ? googleAdsError.message : 'Unable to load Google Ads status.';
        setGoogleAdsStatus(null);
        setGoogleAdsStatusLoad('error');
        setGoogleAdsStatusError(googleAdsMessage);
      }

      try {
        const ga4Payload = await loadGoogleAnalyticsStatus();
        setGa4Status(ga4Payload);
        setGa4StatusLoad('loaded');
      } catch (ga4Error) {
        const ga4Message =
          ga4Error instanceof Error ? ga4Error.message : 'Unable to load Google Analytics status.';
        setGa4Status(null);
        setGa4StatusLoad('error');
        setGa4StatusError(ga4Message);
      }
    } catch (loadError) {
      const message =
        loadError instanceof Error ? loadError.message : 'Unable to load data sources.';
      setError(message);
      setSocialStatus([]);
      setSocialStatusLoad('loaded');
      setSocialStatusError(null);
      setGoogleAdsStatus(null);
      setGoogleAdsStatusLoad('loaded');
      setGoogleAdsStatusError(null);
      setGa4Status(null);
      setGa4StatusLoad('loaded');
      setGa4StatusError(null);
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

  useEffect(() => {
    if (connectProvider !== 'GA4') {
      return;
    }
    let cancelled = false;
    setGa4SetupLoading(true);
    void loadGoogleAnalyticsSetupStatus(runtimeContext)
      .then((payload) => {
        if (cancelled) {
          return;
        }
        setGa4SetupStatus(payload);
      })
      .catch(() => {
        if (cancelled) {
          return;
        }
        setGa4SetupStatus(null);
      })
      .finally(() => {
        if (!cancelled) {
          setGa4SetupLoading(false);
        }
      });

    return () => {
      cancelled = true;
    };
  }, [connectProvider, runtimeContext]);

  useEffect(() => {
    if (connectProvider !== 'GOOGLE') {
      return;
    }
    let cancelled = false;
    setGoogleAdsSetupLoading(true);
    void loadGoogleAdsSetupStatus(runtimeContext)
      .then((payload) => {
        if (cancelled) {
          return;
        }
        setGoogleAdsSetupStatus(payload);
      })
      .catch(() => {
        if (cancelled) {
          return;
        }
        setGoogleAdsSetupStatus(null);
      })
      .finally(() => {
        if (!cancelled) {
          setGoogleAdsSetupLoading(false);
        }
      });

    return () => {
      cancelled = true;
    };
  }, [connectProvider, runtimeContext]);

  useEffect(() => {
    if (connectProvider !== 'GOOGLE') {
      return;
    }
    const storedAccountId =
      typeof googleAdsStatus?.metadata?.credential_account_id === 'string'
        ? googleAdsStatus.metadata.credential_account_id
        : '';
    if (!storedAccountId) {
      return;
    }
    setGoogleAdsConnectStep((previous) => (previous === 'idle' ? 'connected' : previous));
    setConnectForm((previous) =>
      previous.accountId.trim()
        ? previous
        : {
            ...previous,
            accountId: storedAccountId,
          },
    );
  }, [connectProvider, googleAdsStatus]);

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
      source: null,
      recoveredFromExistingToken: false,
    });
    setMetaConnectedCredential(null);
    setMetaConnectedInstagramAccount(null);
    setMetaPermissionDiagnostics(EMPTY_META_PERMISSION_DIAGNOSTICS);
    setMetaOAuthStarting(false);
    setMetaOAuthExchanging(false);
    setMetaOAuthSavingPage(false);
  }, []);

  const resetGoogleAdsState = useCallback(() => {
    setGoogleAdsConnectStep('idle');
    setGoogleAdsCredential(null);
    setGoogleAdsOAuthStarting(false);
    setGoogleAdsOAuthExchanging(false);
  }, []);

  const resetGa4State = useCallback(() => {
    setGa4ConnectStep('idle');
    setGa4Credential(null);
    setGa4Properties([]);
    setGa4SelectedPropertyId('');
    setGa4OAuthStarting(false);
    setGa4OAuthExchanging(false);
    setGa4PropertiesLoading(false);
  }, []);

  const applyMetaOAuthSelectionResponse = useCallback(
    (
      response: MetaOAuthExchangeResponse,
      options?: { successMessage?: string; missingPermissionsMessage?: string },
    ) => {
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
          options?.missingPermissionsMessage ??
            'Meta OAuth connected, but required permissions are missing. Re-request permissions and reconnect.',
          { tone: 'error' },
        );
        return false;
      }
      const selectedPageId = response.default_page_id || response.pages[0]?.id || '';
      const selectedAdAccountId =
        response.default_ad_account_id ||
        response.ad_accounts.find((account) => account.id)?.id ||
        response.ad_accounts[0]?.id ||
        '';
      const selectedInstagramAccountId =
        response.default_instagram_account_id || response.instagram_accounts[0]?.id || '';
      setMetaOAuthSelection({
        selectionToken: response.selection_token,
        pages: response.pages,
        adAccounts: response.ad_accounts,
        instagramAccounts: response.instagram_accounts,
        selectedPageId,
        selectedAdAccountId,
        selectedInstagramAccountId,
        source: response.source ?? null,
        recoveredFromExistingToken: Boolean(response.recovered_from_existing_token),
      });
      if (!response.ad_accounts.length) {
        setMetaConnectStep('oauth-pending');
        pushToast(
          'Meta OAuth complete, but no ad accounts were returned. Add ad account access in Meta Business Manager and reconnect.',
          { tone: 'error' },
        );
        return false;
      }
      setMetaConnectStep('page-selection');
      pushToast(
        options?.successMessage ??
          'Meta OAuth complete. Select your business page and ad account to finish setup.',
        {
          tone: 'success',
        },
      );
      return true;
    },
    [pushToast],
  );

  const applyGa4Properties = useCallback((properties: GoogleAnalyticsPropertyRecord[]) => {
    setGa4Properties(properties);
    setGa4SelectedPropertyId((previous) => {
      if (previous && properties.some((row) => row.property_id === previous)) {
        return previous;
      }
      return properties[0]?.property_id ?? '';
    });
  }, []);

  const handleLoadGa4Properties = useCallback(
    async (options?: {
      credentialId?: string;
      silentError?: boolean;
      showToastOnEmpty?: boolean;
    }) => {
      setGa4PropertiesLoading(true);
      try {
        const payload = await loadGoogleAnalyticsProperties(
          options?.credentialId ? { credential_id: options.credentialId } : undefined,
        );
        setGa4Credential((previous) =>
          previous ?? {
            id: payload.credential_id,
            provider: 'GOOGLE_ANALYTICS',
            account_id: '',
          },
        );
        applyGa4Properties(payload.properties ?? []);
        if ((payload.properties ?? []).length > 0) {
          setGa4ConnectStep('property-selection');
        } else if (options?.showToastOnEmpty) {
          pushToast('Google Analytics connected, but no GA4 properties were returned.', {
            tone: 'error',
          });
        }
      } catch (ga4PropertiesError) {
        applyGa4Properties([]);
        if (!options?.silentError) {
          const message =
            ga4PropertiesError instanceof Error
              ? ga4PropertiesError.message
              : 'Unable to load GA4 properties.';
          pushToast(message, { tone: 'error' });
        }
      } finally {
        setGa4PropertiesLoading(false);
      }
    },
    [applyGa4Properties, pushToast],
  );

  const handleStartGoogleAdsOAuth = useCallback(async () => {
    if (googleAdsOAuthStarting || googleAdsOAuthExchanging) {
      return;
    }
    const customerId = connectForm.accountId.trim();
    if (!customerId) {
      pushToast('Google Ads customer/account ID is required before OAuth.', { tone: 'error' });
      return;
    }
    setGoogleAdsOAuthStarting(true);
    try {
      if (typeof window !== 'undefined') {
        window.sessionStorage.setItem(CONNECT_OAUTH_PROVIDER_KEY, 'GOOGLE');
      }
      const hasRuntimeContext = Boolean(
        runtimeContext.client_origin || runtimeContext.client_port || runtimeContext.dataset_source,
      );
      const response = await startGoogleAdsOAuth(
        {
          customer_id: customerId,
          login_customer_id: connectForm.loginCustomerId.trim() || undefined,
          ...(hasRuntimeContext ? { runtime_context: runtimeContext } : {}),
        },
      );
      if (typeof window !== 'undefined') {
        if (import.meta.env.MODE === 'test') {
          return;
        }
        window.location.assign(response.authorize_url);
      }
    } catch (googleAdsStartError) {
      const message =
        googleAdsStartError instanceof Error
          ? googleAdsStartError.message
          : 'Unable to start Google Ads OAuth.';
      pushToast(message, { tone: 'error' });
      setConnectProvider('GOOGLE');
      resetGoogleAdsState();
    } finally {
      setGoogleAdsOAuthStarting(false);
    }
  }, [
    connectForm,
    googleAdsOAuthExchanging,
    googleAdsOAuthStarting,
    pushToast,
    resetGoogleAdsState,
    runtimeContext,
  ]);

  const handleStartGoogleAnalyticsOAuth = useCallback(async () => {
    if (ga4OAuthStarting || ga4OAuthExchanging) {
      return;
    }
    setGa4OAuthStarting(true);
    try {
      if (typeof window !== 'undefined') {
        window.sessionStorage.setItem(CONNECT_OAUTH_PROVIDER_KEY, 'GA4');
      }
      const hasRuntimeContext = Boolean(
        runtimeContext.client_origin || runtimeContext.client_port || runtimeContext.dataset_source,
      );
      const response = await startGoogleAnalyticsOAuth(
        hasRuntimeContext ? { runtime_context: runtimeContext } : undefined,
      );
      if (typeof window !== 'undefined') {
        if (import.meta.env.MODE === 'test') {
          return;
        }
        window.location.assign(response.authorize_url);
      }
    } catch (ga4StartError) {
      const message =
        ga4StartError instanceof Error ? ga4StartError.message : 'Unable to start GA4 OAuth.';
      pushToast(message, { tone: 'error' });
      setConnectProvider('GA4');
      setConnectForm(buildInitialConnectForm('GA4'));
      resetGa4State();
    } finally {
      setGa4OAuthStarting(false);
    }
  }, [ga4OAuthExchanging, ga4OAuthStarting, pushToast, resetGa4State, runtimeContext]);

  useEffect(() => {
    if (connectProvider !== 'GA4') {
      return;
    }
    if (ga4Properties.length > 0 || ga4PropertiesLoading) {
      return;
    }
    const hasStoredCredential =
      Boolean(ga4Credential?.id) || Boolean(ga4Status?.metadata?.has_credential);
    if (!hasStoredCredential) {
      return;
    }
    void handleLoadGa4Properties({
      credentialId: ga4Credential?.id,
      silentError: true,
    });
  }, [
    connectProvider,
    ga4Credential?.id,
    ga4Properties.length,
    ga4PropertiesLoading,
    ga4Status?.metadata,
    handleLoadGa4Properties,
  ]);

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
      window.sessionStorage.removeItem(CONNECT_OAUTH_PROVIDER_KEY);
      const nextUrl = `${window.location.pathname}${window.location.hash}`;
      window.history.replaceState({}, document.title, nextUrl);
    };
    const clearOAuthMarkers = () => {
      window.sessionStorage.removeItem(META_OAUTH_FLOW_SESSION_KEY);
      clearOAuthParams();
    };
    const oauthFlow = window.sessionStorage.getItem(META_OAUTH_FLOW_SESSION_KEY);
    const oauthProvider = window.sessionStorage.getItem(CONNECT_OAUTH_PROVIDER_KEY);

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

    const handleGoogleAnalyticsCallback = async () => {
      setConnectProvider('GA4');
      setConnectForm(buildInitialConnectForm('GA4'));
      setGa4ConnectStep('oauth-pending');

      const response = await exchangeGoogleAnalyticsOAuthCode({
        code: code ?? '',
        state: state ?? '',
        runtime_context: runtimeContext,
      });
      setGa4Credential(response.credential);
      setGa4ConnectStep('property-selection');
      await handleLoadGa4Properties({
        credentialId: response.credential.id,
        showToastOnEmpty: true,
      });
      pushToast('Google Analytics connected. Select a GA4 property to finish setup.', {
        tone: 'success',
      });
    };

    const handleGoogleAdsCallback = async () => {
      const nextForm = buildInitialConnectForm('GOOGLE');
      setConnectProvider('GOOGLE');
      setGoogleAdsConnectStep('oauth-pending');

      const response = await exchangeGoogleAdsOAuthCode({
        code: code ?? '',
        state: state ?? '',
        runtime_context: runtimeContext,
      });
      setGoogleAdsCredential(response.credential);
      setGoogleAdsConnectStep('connected');
      Object.assign(nextForm, {
        accountId: response.customer_id || response.credential.account_id,
        loginCustomerId: response.login_customer_id || '',
      });
      setConnectForm(nextForm);
      pushToast(
        response.refresh_token_received
          ? 'Google Ads connected. Save the connection to finish provisioning.'
          : 'Google Ads connected, but no refresh token was returned. Reconnect if sync fails.',
        {
          tone: response.refresh_token_received ? 'success' : 'error',
        },
      );
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
      applyMetaOAuthSelectionResponse(response);
    };

    if (oauthError) {
      const providerLabel =
        oauthProvider === 'GA4'
          ? 'Google Analytics'
          : oauthProvider === 'GOOGLE'
            ? 'Google Ads'
            : 'OAuth';
      pushToast(
        oauthErrorDescription?.trim()
          ? `${providerLabel} failed: ${oauthErrorDescription}`
          : `${providerLabel} failed: ${oauthError}`,
        { tone: 'error' },
      );
      if (oauthProvider === 'GA4') {
        clearOAuthParams();
      } else {
        clearOAuthMarkers();
      }
      return;
    }

    if (oauthProvider === 'GOOGLE') {
      setGoogleAdsOAuthExchanging(true);
      void (async () => {
        try {
          await handleGoogleAdsCallback();
        } catch (googleAdsExchangeError) {
          const message =
            googleAdsExchangeError instanceof Error
              ? googleAdsExchangeError.message
              : 'Google Ads OAuth callback failed.';
          pushToast(message, { tone: 'error' });
        } finally {
          setGoogleAdsOAuthExchanging(false);
          clearOAuthParams();
        }
      })();
      return;
    }

    if (oauthProvider === 'GA4') {
      setGa4OAuthExchanging(true);
      void (async () => {
        try {
          await handleGoogleAnalyticsCallback();
        } catch (ga4ExchangeError) {
          const message =
            ga4ExchangeError instanceof Error
              ? ga4ExchangeError.message
              : 'Google Analytics OAuth callback failed.';
          pushToast(message, { tone: 'error' });
        } finally {
          setGa4OAuthExchanging(false);
          clearOAuthParams();
        }
      })();
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
  }, [applyMetaOAuthSelectionResponse, handleLoadGa4Properties, pushToast, runtimeContext]);

  const handleStartMetaOAuth = useCallback(
    async (options?: { openPanelOnError?: boolean; authType?: 'rerequest' }) => {
      if (metaOAuthStarting || metaOAuthExchanging) {
        return;
      }
      setMetaOAuthStarting(true);
      try {
        if (typeof window !== 'undefined') {
          window.sessionStorage.setItem(CONNECT_OAUTH_PROVIDER_KEY, 'META');
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

  const handleStartMetaRecovery = useCallback(async () => {
    if (metaOAuthStarting || metaOAuthExchanging || metaOAuthSavingPage) {
      return;
    }
    setSocialActionPendingPlatform('meta');
    setConnectProvider('META');
    setConnectForm(buildInitialConnectForm('META'));
    setMetaReportingStatusNote(null);
    setMetaConnectStep('oauth-pending');
    try {
      const response = await previewMetaRecovery();
      applyMetaOAuthSelectionResponse(response, {
        successMessage:
          'Recovered Meta marketing access from the stored Meta token. Confirm the assets to restore reporting.',
        missingPermissionsMessage:
          'Stored Meta connection is missing required marketing permissions. Reconnect Meta with Facebook to continue.',
      });
    } catch (recoveryError) {
      const message =
        recoveryError instanceof Error
          ? recoveryError.message
          : 'Unable to recover Meta marketing access from the stored connection.';
      pushToast(message, { tone: 'error' });
    } finally {
      setSocialActionPendingPlatform(null);
    }
  }, [
    applyMetaOAuthSelectionResponse,
    metaOAuthExchanging,
    metaOAuthSavingPage,
    metaOAuthStarting,
    pushToast,
  ]);

  const applyMetaReportingStatusNote = useCallback(
    async (options?: { syncCompleted?: boolean }) => {
      if (!options?.syncCompleted) {
        setMetaReportingStatusNote(null);
        return;
      }
      try {
        const datasetStatus = await loadDatasetStatus();
        const liveReason = datasetStatus.live.reason;
        const messages: Record<DatasetLiveReason, string> = {
          adapter_disabled:
            'Meta connected. Direct sync complete. Live reporting is not enabled in this environment.',
          missing_snapshot:
            'Meta connected. Direct sync complete. Waiting for the first warehouse snapshot.',
          stale_snapshot: 'Meta connected. Direct sync complete. Live data is refreshing.',
          default_snapshot:
            'Meta connected. Direct sync complete. The latest warehouse snapshot is fallback data.',
          ready: 'Meta connected. Direct sync complete. Live reporting is ready.',
        };
        const tone: MetaReportingNoteTone =
          liveReason === 'ready'
            ? 'success'
            : liveReason === 'default_snapshot'
              ? 'warning'
              : 'info';
        const message =
          (typeof datasetStatus.live.detail === 'string' && datasetStatus.live.detail.trim()) ||
          messages[liveReason];
        setMetaReportingStatusNote({ tone, message });
        pushToast(message, { tone: tone === 'warning' ? 'info' : tone });
      } catch (reportingError) {
        const message =
          reportingError instanceof Error
            ? reportingError.message
            : 'Meta connected, but reporting readiness could not be verified.';
        setMetaReportingStatusNote({ tone: 'warning', message });
        pushToast(message, { tone: 'info' });
      }
    },
    [pushToast],
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
      if (metaOAuthSelection.recoveredFromExistingToken) {
        let provisionError: string | null = null;
        let syncCompleted = false;
        try {
          if (connectForm.linkConnection) {
            const scheduleType = connectForm.scheduleType;
            await provisionMetaIntegration({
              external_account_id: response.credential.account_id,
              workspace_id: connectForm.workspaceId.trim() || null,
              destination_id: connectForm.destinationId.trim() || null,
              connection_name: connectForm.connectionName.trim(),
              schedule_type: scheduleType,
              is_active: connectForm.isActive,
              interval_minutes:
                scheduleType === 'interval' ? Number(connectForm.intervalMinutes) : null,
              cron_expression:
                scheduleType === 'cron' ? connectForm.cronExpression.trim() : '',
            });
          }
        } catch (error) {
          provisionError =
            error instanceof Error
              ? error.message
              : 'Unable to reprovision the Meta connection automatically.';
        }

        try {
          const syncPayload = await syncMetaIntegration();
          syncCompleted = true;
          if (syncPayload.job_id) {
            pushToast(
              syncPayload.task_dispatch_mode === 'inline'
                ? `Meta restore completed and sync ran inline (job ${syncPayload.job_id}).`
                : `Meta restore completed and sync started (job ${syncPayload.job_id}).`,
              { tone: 'success' },
            );
          }
        } catch (error) {
          const message =
            error instanceof Error ? error.message : 'Unable to start Meta sync after restore.';
          pushToast(message, { tone: 'error' });
        }

        await applyMetaReportingStatusNote({ syncCompleted });

        if (provisionError !== null && syncCompleted) {
          pushToast(
            `Meta marketing access restored; Airbyte connection was not provisioned. ${provisionError}`,
            { tone: 'info' },
          );
        } else if (provisionError === null) {
          pushToast('Meta marketing access restored.', {
            tone: 'success',
          });
        }
        void loadData();
      }
    } catch (metaConnectError) {
      const message =
        metaConnectError instanceof Error
          ? metaConnectError.message
          : 'Unable to connect selected Meta page.';
      pushToast(message, { tone: 'error' });
    } finally {
      setMetaOAuthSavingPage(false);
    }
  }, [
    applyMetaReportingStatusNote,
    connectForm,
    loadData,
    metaOAuthSavingPage,
    metaOAuthSelection,
    metaPermissionDiagnostics,
    pushToast,
  ]);

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
      setMetaReportingStatusNote(null);
      resetGoogleAdsState();
      resetMetaOAuthState();
      resetGa4State();
    },
    [resetGa4State, resetGoogleAdsState, resetMetaOAuthState],
  );

  const closeConnectPanel = useCallback(() => {
    setConnectProvider(null);
    setSavingConnect(false);
    setMetaReportingStatusNote(null);
    resetGoogleAdsState();
    resetMetaOAuthState();
    resetGa4State();
  }, [resetGa4State, resetGoogleAdsState, resetMetaOAuthState]);

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
      if (platformStatus.actions.includes('open_meta_setup')) {
        openConnectPanel('META');
        return;
      }
      if (platformStatus.actions.includes('recover_marketing_access')) {
        await handleStartMetaRecovery();
        return;
      }
      if (platformStatus.actions.includes('connect_oauth')) {
        if (platformStatus.platform === 'instagram') {
          openConnectPanel('META');
          return;
        }
        setSocialActionPendingPlatform(platformStatus.platform);
        try {
          await handleStartMetaOAuth({ openPanelOnError: true });
        } finally {
          setSocialActionPendingPlatform(null);
        }
        return;
      }
      if (platformStatus.actions.includes('sync_now')) {
        const metaConnection = normalizedConnections
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
    [
      handleRunNow,
      handleStartMetaOAuth,
      handleStartMetaRecovery,
      normalizedConnections,
      openConnectPanel,
    ],
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
            await applyMetaReportingStatusNote({ syncCompleted: true });
          }
        } else if (connectProvider === 'GA4') {
          if (!ga4Credential?.id) {
            pushToast('Complete Google OAuth first.', { tone: 'error' });
            return;
          }
          const selectedProperty = ga4Properties.find(
            (property) => property.property_id === ga4SelectedPropertyId,
          );
          if (!selectedProperty) {
            pushToast('Select a GA4 property first.', { tone: 'error' });
            return;
          }

          await provisionGoogleAnalytics({
            credential_id: ga4Credential.id,
            property_id: selectedProperty.property_id,
            property_name: selectedProperty.property_name,
            is_active: true,
            sync_frequency: 'daily',
          });
          setGa4ConnectStep('connected');
        } else {
          const accountId = connectForm.accountId.trim();
          const hasGoogleAdsCredential = Boolean(
            googleAdsCredential || googleAdsStatus?.metadata?.has_credential,
          );
          if (!accountId) {
            pushToast('Google Ads customer/account ID is required.', { tone: 'error' });
            return;
          }
          if (!hasGoogleAdsCredential) {
            pushToast('Complete Google Ads OAuth first.', { tone: 'error' });
            return;
          }

          if (connectForm.linkConnection) {
            const scheduleType = connectForm.scheduleType;
            await provisionGoogleAds({
              external_account_id: accountId,
              login_customer_id: connectForm.loginCustomerId.trim() || undefined,
              workspace_id: connectForm.workspaceId.trim() || null,
              destination_id: connectForm.destinationId.trim() || null,
              connection_name: connectForm.connectionName.trim(),
              is_active: connectForm.isActive,
              schedule_type: scheduleType,
              interval_minutes:
                scheduleType === 'interval' ? Number(connectForm.intervalMinutes) : null,
              cron_expression: scheduleType === 'cron' ? connectForm.cronExpression.trim() : '',
            });
            setGoogleAdsConnectStep('connected');
          }
        }

        pushToast(
          connectProvider === 'GA4'
            ? 'Google Analytics 4 property connected.'
            : connectProvider === 'GOOGLE'
              ? connectForm.linkConnection
                ? 'Google Ads connected and provisioned.'
                : 'Google Ads OAuth connected.'
            : connectForm.linkConnection
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
      applyMetaReportingStatusNote,
      closeConnectPanel,
      connectForm,
      connectProvider,
      loadData,
      metaConnectedCredential,
      metaPermissionDiagnostics,
      googleAdsCredential,
      googleAdsStatus?.metadata,
      ga4Credential,
      ga4Properties,
      ga4SelectedPropertyId,
      pushToast,
      savingConnect,
    ],
  );

  const providerOptions = useMemo(() => {
    const providers = new Set<string>();
    normalizedConnections.forEach((connection) => {
      providers.add(connection.provider ?? 'UNKNOWN');
    });
    return Array.from(providers)
      .map((provider) => ({
        value: provider,
        label: resolveProviderLabel(provider),
      }))
      .sort((a, b) => a.label.localeCompare(b.label, undefined, { sensitivity: 'base' }));
  }, [normalizedConnections]);

  const filteredConnections = useMemo(() => {
    const normalizedQuery = query.trim().toLowerCase();
    return normalizedConnections.filter((connection) => {
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
  }, [normalizedConnections, providerFilter, query, statusFilter]);

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
          reason:
            platform === 'meta'
              ? { code: 'missing_status_payload', message: 'Status has not been loaded yet.' }
              : {
                  code: 'missing_status_payload',
                  message: 'Instagram business linking is handled inside Meta setup.',
                },
          last_checked_at: null,
          last_synced_at: null,
          actions: platform === 'meta' ? ['connect_oauth'] : ['open_meta_setup'],
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
  const metaSocialStatus = useMemo(
    () => socialCards.find((row) => row.platform === 'meta') ?? null,
    [socialCards],
  );

  const handleGa4PrimaryAction = useCallback(() => {
    openConnectPanel('GA4');
  }, [openConnectPanel]);

  const handleGoogleAdsPrimaryAction = useCallback(() => {
    openConnectPanel('GOOGLE');
  }, [openConnectPanel]);

  const ga4StatusValue: GoogleAnalyticsStatusResponse['status'] =
    ga4Status?.status ?? 'not_connected';
  const ga4StatusLabel = resolveSocialStatusLabel(ga4StatusValue);
  const ga4StatusTone = resolveSocialStatusTone(ga4StatusValue);
  const ga4PrimaryActionLabel = resolveGa4PrimaryAction(ga4StatusValue);
  const ga4LastCheckedLabel = formatRelativeTime(ga4Status?.last_checked_at ?? null) ?? '—';
  const ga4LastSyncedLabel = formatRelativeTime(ga4Status?.last_synced_at ?? null) ?? 'Never';
  const ga4OauthReady = Boolean(ga4SetupStatus?.ready_for_oauth);

  const googleAdsStatusValue: GoogleAdsStatusResponse['status'] =
    googleAdsStatus?.status ?? 'not_connected';
  const googleAdsStatusLabel = resolveSocialStatusLabel(googleAdsStatusValue);
  const googleAdsStatusTone = resolveSocialStatusTone(googleAdsStatusValue);
  const googleAdsPrimaryActionLabel = resolveGoogleAdsPrimaryAction(
    googleAdsStatusValue,
    googleAdsStatus?.actions ?? [],
  );
  const googleAdsLastCheckedLabel =
    formatRelativeTime(googleAdsStatus?.last_checked_at ?? null) ?? '—';
  const googleAdsLastSyncedLabel =
    formatRelativeTime(googleAdsStatus?.last_synced_at ?? null) ?? 'Never';
  const googleAdsOauthReady = Boolean(googleAdsSetupStatus?.ready_for_oauth);

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
    const total = normalizedConnections.length;
    const active = normalizedConnections.filter((connection) => connection.is_active !== false).length;
    return {
      total,
      active,
      inactive: total - active,
      due: normalizedConnections.filter((connection) => resolveConnectionState(connection) === 'stale')
        .length,
      by_provider: {},
    };
  }, [normalizedConnections, summary]);

  const hasConnections = normalizedConnections.length > 0;
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
            Canonical setup and management hub for social, paid media, and web analytics connections.
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
            Connect and manage Meta here, then link Instagram inside the Meta asset-selection flow. There is no separate Instagram OAuth path in ADinsights.
          </p>
          <div className="dashboard-header__actions-row" style={{ marginBottom: '0.75rem' }}>
            <Link className="button tertiary" to="/">
              Home
            </Link>
            <Link className="button tertiary" to="/dashboards/meta/pages">
              Facebook pages
            </Link>
            <Link className="button tertiary" to="/dashboards/meta/accounts">
              Meta accounts
            </Link>
            <Link className="button tertiary" to="/dashboards/meta/campaigns">
              Campaign overview
            </Link>
            <Link className="button tertiary" to="/dashboards/meta/insights">
              Insights dashboard
            </Link>
            <Link className="button tertiary" to="/dashboards/meta/status">
              Connection status
            </Link>
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
              const primaryActionLabel = resolveSocialPrimaryAction(platformStatus);
              const checkedLabel = formatRelativeTime(platformStatus.last_checked_at ?? null);
              const syncedLabel = formatRelativeTime(platformStatus.last_synced_at ?? null);
              const reportingMessage =
                platformStatus.reporting_readiness &&
                platformStatus.reporting_readiness.message !== platformStatus.reason.message
                  ? platformStatus.reporting_readiness.message
                  : null;
              return (
                <article key={platformStatus.platform} className="social-connection-card">
                  <div className="social-connection-card__header">
                    <h4>{platformStatus.display_name}</h4>
                    <span className={`status-pill ${statusTone}`}>{statusLabel}</span>
                  </div>
                  <p className="status-message muted">{platformStatus.reason.message}</p>
                  {reportingMessage ? (
                    <p className="status-message muted">
                      <strong>Reporting stage:</strong> {reportingMessage}
                    </p>
                  ) : null}
                  {platformStatus.platform === 'instagram' ? (
                    <p className="status-message muted">
                      Instagram business linking is completed in Meta setup, not through a
                      separate Instagram login.
                    </p>
                  ) : null}
                  <dl className="social-connection-card__meta">
                    <div>
                      <dt>Checked</dt>
                      <dd>{checkedLabel ?? '—'}</dd>
                    </div>
                    <div>
                      <dt>Last sync</dt>
                      <dd>{syncedLabel ?? 'Never'}</dd>
                    </div>
                    {platformStatus.reporting_readiness ? (
                      <>
                        <div>
                          <dt>Direct sync</dt>
                          <dd>
                            {resolveDirectSyncStatusLabel(
                              platformStatus.reporting_readiness.direct_sync_status,
                            )}
                          </dd>
                        </div>
                        <div>
                          <dt>Warehouse</dt>
                          <dd>
                            {resolveWarehouseStatusLabel(
                              platformStatus.reporting_readiness.warehouse_status,
                            )}
                          </dd>
                        </div>
                      </>
                    ) : null}
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

        <section className="social-connections-panel" aria-labelledby="web-analytics-title">
          <div className="panel-header__title-row">
            <h3 id="web-analytics-title">Web analytics</h3>
            <span className={`status-pill ${ga4StatusLoad === 'loaded' ? ga4StatusTone : 'muted'}`}>
              {ga4StatusLoad === 'loaded' ? ga4StatusLabel : 'Checking status'}
            </span>
          </div>
          <p className="status-message muted">
            Use Google Analytics 4 for website and app behavior. Connect a GA4 property when you
            want sessions, engagement, on-site conversions, and revenue reporting by property.
          </p>
          {ga4StatusLoad === 'loading' ? (
            <p className="status-message muted">Loading Google Analytics status…</p>
          ) : null}
          {ga4StatusLoad === 'error' ? (
            <p className="status-message error">
              {ga4StatusError ?? 'Could not load Google Analytics status.'}
            </p>
          ) : null}
          <div className="social-connections-grid">
            <article className="social-connection-card">
              <div className="social-connection-card__header">
                <h4>Google Analytics 4</h4>
                <span className={`status-pill ${ga4StatusTone}`}>{ga4StatusLabel}</span>
              </div>
              <p className="status-message muted">
                {ga4Status?.reason?.message ??
                  'Choose this when you need website analytics. It does not import ad spend or campaign delivery from Google Ads.'}
              </p>
              <dl className="social-connection-card__meta">
                <div>
                  <dt>Checked</dt>
                  <dd>{ga4LastCheckedLabel}</dd>
                </div>
                <div>
                  <dt>Last sync</dt>
                  <dd>{ga4LastSyncedLabel}</dd>
                </div>
              </dl>
              <div className="social-connection-card__actions">
                <button
                  type="button"
                  className="button secondary"
                  onClick={handleGa4PrimaryAction}
                  disabled={ga4OAuthStarting || ga4OAuthExchanging}
                >
                  {ga4OAuthStarting ? 'Redirecting…' : ga4PrimaryActionLabel}
                </button>
                {(ga4Status?.status === 'complete' || ga4Status?.status === 'active') && (
                  <a className="button tertiary" href="/dashboards/web/ga4">
                    Open dashboard
                  </a>
                )}
              </div>
            </article>
          </div>
        </section>

        <section className="social-connections-panel" aria-labelledby="paid-media-title">
          <div className="panel-header__title-row">
            <h3 id="paid-media-title">Paid media</h3>
            <span
              className={`status-pill ${googleAdsStatusLoad === 'loaded' ? googleAdsStatusTone : 'muted'}`}
            >
              {googleAdsStatusLoad === 'loaded' ? googleAdsStatusLabel : 'Checking status'}
            </span>
          </div>
          <p className="status-message muted">
            Use Google Ads for paid campaign performance. Connect a Google Ads account when you
            want spend, clicks, impressions, conversions, and campaign-level delivery metrics.
          </p>
          {googleAdsStatusLoad === 'loading' ? (
            <p className="status-message muted">Loading Google Ads status…</p>
          ) : null}
          {googleAdsStatusLoad === 'error' ? (
            <p className="status-message error">
              {googleAdsStatusError ?? 'Could not load Google Ads status.'}
            </p>
          ) : null}
          <div className="social-connections-grid">
            <article className="social-connection-card">
              <div className="social-connection-card__header">
                <h4>Google Ads</h4>
                <span className={`status-pill ${googleAdsStatusTone}`}>{googleAdsStatusLabel}</span>
              </div>
              <p className="status-message muted">
                {googleAdsStatus?.reason?.message ??
                  'Choose this when you need paid media performance. It does not replace GA4 website analytics or property reporting.'}
              </p>
              <dl className="social-connection-card__meta">
                <div>
                  <dt>Checked</dt>
                  <dd>{googleAdsLastCheckedLabel}</dd>
                </div>
                <div>
                  <dt>Last sync</dt>
                  <dd>{googleAdsLastSyncedLabel}</dd>
                </div>
              </dl>
              <div className="social-connection-card__actions">
                <button
                  type="button"
                  className="button secondary"
                  onClick={handleGoogleAdsPrimaryAction}
                  disabled={googleAdsOAuthStarting || googleAdsOAuthExchanging}
                >
                  {googleAdsOAuthStarting ? 'Redirecting…' : googleAdsPrimaryActionLabel}
                </button>
                {(googleAdsStatus?.status === 'complete' || googleAdsStatus?.status === 'active') && (
                  <a className="button tertiary" href="/dashboards/google-ads">
                    Open dashboard
                  </a>
                )}
              </div>
            </article>
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
            <button
              type="button"
              className="button secondary"
              onClick={() => openConnectPanel('GA4')}
            >
              Connect Google Analytics
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
          optional Instagram business account, then provision insights sync. Google Analytics 4
          handles website analytics at the property level. Google Ads handles paid media
          performance at the ad account level. They both use Google OAuth but remain separate
          integrations because they serve different reporting jobs.
        </p>

        {connectProvider ? (
          <form className="data-sources-connect-form" onSubmit={handleConnectSubmit}>
            <header className="data-sources-connect-form__header">
              <div>
                <h3>{`Connect ${CONNECT_PROVIDER_LABELS[connectProvider]}`}</h3>
                <p className="status-message muted">
                  {connectProvider === 'META'
                    ? 'Complete Facebook OAuth, pick business assets, and optionally auto-provision the sync.'
                    : connectProvider === 'GOOGLE'
                      ? 'Use this flow for Google Ads campaign performance. Enter a Google Ads customer ID, complete Google OAuth, then optionally provision the sync connection.'
                    : connectProvider === 'GA4'
                      ? 'Use this flow for website analytics. Complete Google OAuth, select the GA4 property that owns your site data, and save the tenant-scoped analytics connection.'
                      : 'Save API credentials and optionally link an existing Airbyte connection record.'}
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

            {connectProvider === 'META' && metaReportingStatusNote ? (
              <p
                className={`status-message ${
                  metaReportingStatusNote.tone === 'warning'
                    ? 'warning'
                    : metaReportingStatusNote.tone === 'info'
                      ? 'muted'
                      : 'success'
                }`}
              >
                {metaReportingStatusNote.message}
              </p>
            ) : null}

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
                              {check.details ? (
                                <div className={`status-message ${check.ok ? 'muted' : 'error'}`}>
                                  {check.details}
                                </div>
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
                    {metaSocialStatus?.reason.code === 'orphaned_marketing_access' ? (
                      <p className="status-message warning">
                        Stored Meta Page Insights access is recoverable. Use restore to recover ad
                        accounts and reporting without another Facebook OAuth roundtrip.
                      </p>
                    ) : null}
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
                      onClick={() => void handleStartMetaRecovery()}
                      disabled={metaOAuthStarting || metaOAuthExchanging || metaOAuthSavingPage}
                    >
                      Restore marketing access
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
                  <>
                    {metaOAuthSelection.recoveredFromExistingToken ? (
                      <div className="data-sources-connect-form__grid">
                        <div className="dashboard-field">
                          <span className="dashboard-field__label">Recovery mode</span>
                          <p className="status-message muted">
                            These assets were rediscovered from the stored Meta Page Insights token.
                            Saving will restore the marketing credential, repopulate ad accounts,
                            and start sync.
                          </p>
                        </div>
                      </div>
                    ) : null}
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
                          {(metaOAuthSelection.pages ?? []).map((page) => (
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
                          {(metaOAuthSelection.adAccounts ?? []).map((account) => (
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
                          {(metaOAuthSelection.instagramAccounts ?? []).map((account) => (
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
                          {metaOAuthSavingPage
                            ? 'Saving…'
                            : metaOAuthSelection.recoveredFromExistingToken
                              ? 'Restore Meta marketing access'
                              : 'Save selected business page'}
                        </button>
                        {!metaOAuthSelection.selectedAdAccountId ? (
                          <p className="status-message error">
                            Meta Marketing API provisioning requires an ad account selection.
                          </p>
                        ) : null}
                      </label>
                    </div>
                  </>
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
            ) : connectProvider === 'GA4' ? (
              <>
                <div className="data-sources-connect-form__grid">
                  <div className="dashboard-field">
                    <span className="dashboard-field__label">GA4 setup checklist</span>
                    {ga4SetupLoading ? (
                      <p className="status-message muted">Checking backend setup…</p>
                    ) : null}
                    {!ga4SetupLoading && !ga4SetupStatus ? (
                      <p className="status-message error">
                        Could not load GA4 setup status. Confirm backend is running and authenticated.
                      </p>
                    ) : null}
                    {ga4SetupStatus ? (
                      <>
                        <p className="status-message muted">
                          OAuth ready:{' '}
                          <span
                            className={`status-pill ${ga4SetupStatus.ready_for_oauth ? 'success' : 'error'}`}
                          >
                            {ga4SetupStatus.ready_for_oauth ? 'Yes' : 'No'}
                          </span>
                        </p>
                        <p className="status-message muted">
                          Redirect URI: {ga4SetupStatus.redirect_uri || 'Not configured'}
                        </p>
                        <p className="status-message muted">
                          OAuth scopes: {ga4SetupStatus.oauth_scopes.join(', ') || '—'}
                        </p>
                        {ga4SetupStatus.checks?.length ? (
                          <ul className="status-message muted">
                            {ga4SetupStatus.checks.map((check) => (
                              <li key={check.key}>
                                <span className={`status-pill ${check.ok ? 'success' : 'error'}`}>
                                  {check.ok ? 'OK' : 'Missing'}
                                </span>{' '}
                                {check.label}
                                {check.details ? (
                                  <div className={`status-message ${check.ok ? 'muted' : 'error'}`}>
                                    {check.details}
                                  </div>
                                ) : null}
                              </li>
                            ))}
                          </ul>
                        ) : null}
                      </>
                    ) : null}
                  </div>
                </div>

                <div className="data-sources-connect-form__grid">
                  <div className="dashboard-field">
                    <span className="dashboard-field__label">Google OAuth</span>
                    <button
                      type="button"
                      className="button secondary"
                      onClick={() => void handleStartGoogleAnalyticsOAuth()}
                      disabled={
                        ga4OAuthStarting ||
                        ga4OAuthExchanging ||
                        ga4SetupLoading ||
                        !ga4OauthReady
                      }
                      aria-busy={ga4OAuthStarting || ga4OAuthExchanging}
                    >
                      {ga4OAuthStarting ? 'Redirecting…' : 'Connect Google Analytics'}
                    </button>
                    {!ga4SetupLoading && !ga4OauthReady ? (
                      <p className="status-message error">
                        GA4 OAuth is not ready. Configure the GA4 client ID, client secret, and
                        redirect URI first.
                      </p>
                    ) : null}
                  </div>
                  <label className="dashboard-field">
                    <span className="dashboard-field__label">OAuth status</span>
                    <input type="text" value={ga4ConnectStep} readOnly aria-label="GA4 OAuth status" />
                  </label>
                </div>

                <div className="data-sources-connect-form__grid">
                  <label className="dashboard-field">
                    <span className="dashboard-field__label">Connected account</span>
                    <input
                      type="text"
                      value={ga4Credential?.account_id ?? ''}
                      readOnly
                      placeholder="Connect with Google to populate"
                    />
                  </label>
                  <label className="dashboard-field">
                    <span className="dashboard-field__label">GA4 property</span>
                    {ga4PropertiesLoading ? (
                      <p className="status-message muted">Loading available properties…</p>
                    ) : ga4Properties.length > 0 ? (
                      <select
                        value={ga4SelectedPropertyId}
                        onChange={(event) => setGa4SelectedPropertyId(event.target.value)}
                      >
                        {ga4Properties.map((property) => (
                          <option key={property.property_id} value={property.property_id}>
                            {`${property.property_name} (${property.account_name || property.property_id})`}
                          </option>
                        ))}
                      </select>
                    ) : (
                      <p className="status-message muted">
                        Connect Google OAuth to load your available GA4 properties.
                      </p>
                    )}
                  </label>
                  <div className="dashboard-field">
                    <span className="dashboard-field__label">Dashboard</span>
                    <a className="button tertiary" href="/dashboards/web/ga4">
                      Open GA4 dashboard
                    </a>
                  </div>
                </div>
              </>
            ) : connectProvider === 'GOOGLE' ? (
              <>
                <div className="data-sources-connect-form__grid">
                  <div className="dashboard-field">
                    <span className="dashboard-field__label">Google Ads setup checklist</span>
                    {googleAdsSetupLoading ? (
                      <p className="status-message muted">Checking backend setup…</p>
                    ) : null}
                    {!googleAdsSetupLoading && !googleAdsSetupStatus ? (
                      <p className="status-message error">
                        Could not load Google Ads setup status. Confirm backend is running and authenticated.
                      </p>
                    ) : null}
                    {googleAdsSetupStatus ? (
                      <>
                        <p className="status-message muted">
                          OAuth ready:{' '}
                          <span
                            className={`status-pill ${googleAdsSetupStatus.ready_for_oauth ? 'success' : 'error'}`}
                          >
                            {googleAdsSetupStatus.ready_for_oauth ? 'Yes' : 'No'}
                          </span>
                        </p>
                        <p className="status-message muted">
                          Provisioning defaults:{' '}
                          <span
                            className={`status-pill ${googleAdsSetupStatus.ready_for_provisioning_defaults ? 'success' : 'error'}`}
                          >
                            {googleAdsSetupStatus.ready_for_provisioning_defaults ? 'Ready' : 'Needs config'}
                          </span>
                        </p>
                        <p className="status-message muted">
                          Redirect URI: {googleAdsSetupStatus.redirect_uri || 'Not configured'}
                        </p>
                        <p className="status-message muted">
                          OAuth scopes: {googleAdsSetupStatus.oauth_scopes.join(', ') || '—'}
                        </p>
                        {googleAdsSetupStatus.checks?.length ? (
                          <ul className="status-message muted">
                            {googleAdsSetupStatus.checks.map((check) => (
                              <li key={check.key}>
                                <span className={`status-pill ${check.ok ? 'success' : 'error'}`}>
                                  {check.ok ? 'OK' : 'Missing'}
                                </span>{' '}
                                {check.label}
                                {check.details ? (
                                  <div className={`status-message ${check.ok ? 'muted' : 'error'}`}>
                                    {check.details}
                                  </div>
                                ) : null}
                              </li>
                            ))}
                          </ul>
                        ) : null}
                      </>
                    ) : null}
                    {googleAdsStatusLoad === 'error' ? (
                      <p className="status-message error">
                        {googleAdsStatusError ?? 'Could not load Google Ads status.'}
                      </p>
                    ) : null}
                    {googleAdsStatus ? (
                      <p className="status-message muted">
                        Current status: {googleAdsStatus.reason?.message ?? googleAdsStatus.status}
                      </p>
                    ) : null}
                  </div>
                </div>

                <div className="data-sources-connect-form__grid">
                  <label className="dashboard-field">
                    <span className="dashboard-field__label">Google Ads customer/account ID</span>
                    <input
                      type="text"
                      value={connectForm.accountId}
                      onChange={(event) => handleConnectFieldChange('accountId', event.target.value)}
                      placeholder="1234567890"
                      required
                    />
                  </label>
                  <label className="dashboard-field">
                    <span className="dashboard-field__label">Login customer ID (optional)</span>
                    <input
                      type="text"
                      value={connectForm.loginCustomerId}
                      onChange={(event) =>
                        handleConnectFieldChange('loginCustomerId', event.target.value)
                      }
                      placeholder="1234567890"
                    />
                  </label>
                  <div className="dashboard-field">
                    <span className="dashboard-field__label">Google OAuth</span>
                    <button
                      type="button"
                      className="button secondary"
                      onClick={() => void handleStartGoogleAdsOAuth()}
                      disabled={
                        googleAdsOAuthStarting ||
                        googleAdsOAuthExchanging ||
                        googleAdsSetupLoading ||
                        !googleAdsOauthReady
                      }
                      aria-busy={googleAdsOAuthStarting || googleAdsOAuthExchanging}
                    >
                      {googleAdsOAuthStarting ? 'Redirecting…' : 'Connect Google Ads'}
                    </button>
                    {!googleAdsSetupLoading && !googleAdsOauthReady ? (
                      <p className="status-message error">
                        Google Ads OAuth is not ready. Configure the Google Ads OAuth client and
                        redirect URI first.
                      </p>
                    ) : null}
                  </div>
                  <label className="dashboard-field">
                    <span className="dashboard-field__label">OAuth status</span>
                    <input
                      type="text"
                      value={googleAdsConnectStep}
                      readOnly
                      aria-label="Google Ads OAuth status"
                    />
                  </label>
                </div>

                <div className="data-sources-connect-form__grid">
                  <label className="dashboard-field">
                    <span className="dashboard-field__label">Connected account</span>
                    <input
                      type="text"
                      value={
                        googleAdsCredential?.account_id ??
                        (typeof googleAdsStatus?.metadata?.credential_account_id === 'string'
                          ? googleAdsStatus.metadata.credential_account_id
                          : '')
                      }
                      readOnly
                      placeholder="Connect with Google to populate"
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
                      <span>Create or reuse a Google Ads Airbyte source/connection now</span>
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

            {connectProvider !== 'GA4' && connectForm.linkConnection ? (
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
                {connectProvider === 'META' || connectProvider === 'GOOGLE' ? (
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
                {savingConnect
                  ? 'Saving…'
                  : connectProvider === 'GA4'
                    ? 'Save GA4 property'
                    : 'Save connection'}
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
