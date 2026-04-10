import { render, screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter } from 'react-router-dom';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import { ApiError } from '../../lib/apiClient';
import DataSources from '../DataSources';

const addToast = vi.fn();

const airbyteMocks = vi.hoisted(() => ({
  loadAirbyteConnections: vi.fn(),
  loadAirbyteSummary: vi.fn(),
  triggerAirbyteSync: vi.fn(),
  loadGoogleAdsSetupStatus: vi.fn(),
  loadGoogleAdsStatus: vi.fn(),
  startGoogleAdsOAuth: vi.fn(),
  exchangeGoogleAdsOAuthCode: vi.fn(),
  provisionGoogleAds: vi.fn(),
  loadGoogleAnalyticsSetupStatus: vi.fn(),
  loadGoogleAnalyticsStatus: vi.fn(),
  startGoogleAnalyticsOAuth: vi.fn(),
  exchangeGoogleAnalyticsOAuthCode: vi.fn(),
  loadGoogleAnalyticsProperties: vi.fn(),
  provisionGoogleAnalytics: vi.fn(),
  startMetaOAuth: vi.fn(),
  exchangeMetaOAuthCode: vi.fn(),
  connectMetaPage: vi.fn(),
  provisionMetaIntegration: vi.fn(),
  syncMetaIntegration: vi.fn(),
  logoutMetaOAuth: vi.fn(),
  loadMetaSetupStatus: vi.fn(),
  loadSocialConnectionStatus: vi.fn(),
  previewMetaRecovery: vi.fn(),
}));
const metaPageInsightsMocks = vi.hoisted(() => ({
  callbackMetaOAuth: vi.fn(),
}));
const datasetStatusMocks = vi.hoisted(() => ({
  loadDatasetStatus: vi.fn(),
}));

vi.mock('../../stores/useToastStore', () => ({
  useToastStore: (selector: (state: { addToast: typeof addToast }) => unknown) =>
    selector({ addToast }),
}));

vi.mock('../../lib/airbyte', () => ({
  loadAirbyteConnections: airbyteMocks.loadAirbyteConnections,
  loadAirbyteSummary: airbyteMocks.loadAirbyteSummary,
  triggerAirbyteSync: airbyteMocks.triggerAirbyteSync,
  loadGoogleAdsSetupStatus: airbyteMocks.loadGoogleAdsSetupStatus,
  loadGoogleAdsStatus: airbyteMocks.loadGoogleAdsStatus,
  startGoogleAdsOAuth: airbyteMocks.startGoogleAdsOAuth,
  exchangeGoogleAdsOAuthCode: airbyteMocks.exchangeGoogleAdsOAuthCode,
  provisionGoogleAds: airbyteMocks.provisionGoogleAds,
  loadGoogleAnalyticsSetupStatus: airbyteMocks.loadGoogleAnalyticsSetupStatus,
  loadGoogleAnalyticsStatus: airbyteMocks.loadGoogleAnalyticsStatus,
  startGoogleAnalyticsOAuth: airbyteMocks.startGoogleAnalyticsOAuth,
  exchangeGoogleAnalyticsOAuthCode: airbyteMocks.exchangeGoogleAnalyticsOAuthCode,
  loadGoogleAnalyticsProperties: airbyteMocks.loadGoogleAnalyticsProperties,
  provisionGoogleAnalytics: airbyteMocks.provisionGoogleAnalytics,
  startMetaOAuth: airbyteMocks.startMetaOAuth,
  exchangeMetaOAuthCode: airbyteMocks.exchangeMetaOAuthCode,
  connectMetaPage: airbyteMocks.connectMetaPage,
  provisionMetaIntegration: airbyteMocks.provisionMetaIntegration,
  syncMetaIntegration: airbyteMocks.syncMetaIntegration,
  logoutMetaOAuth: airbyteMocks.logoutMetaOAuth,
  loadMetaSetupStatus: airbyteMocks.loadMetaSetupStatus,
  loadSocialConnectionStatus: airbyteMocks.loadSocialConnectionStatus,
  previewMetaRecovery: airbyteMocks.previewMetaRecovery,
}));
vi.mock('../../lib/metaPageInsights', () => ({
  META_OAUTH_FLOW_PAGE_INSIGHTS: 'page_insights',
  META_OAUTH_FLOW_SESSION_KEY: 'adinsights.meta.oauth.flow',
  callbackMetaOAuth: metaPageInsightsMocks.callbackMetaOAuth,
}));
vi.mock('../../lib/datasetStatus', () => ({
  loadDatasetStatus: datasetStatusMocks.loadDatasetStatus,
  messageForLiveDatasetReason: vi.fn((reason: string) => {
    const messages: Record<string, string> = {
      adapter_disabled: 'Live reporting is not enabled in this environment.',
      missing_snapshot: 'Meta is connected, but the first live warehouse snapshot has not been generated yet.',
      stale_snapshot: 'Live data is refreshing.',
      default_snapshot: 'Latest live snapshot is fallback data.',
      ready: 'Live reporting is ready.',
    };
    return messages[reason] ?? 'Live reporting status is unavailable.';
  }),
}));

const renderDataSources = () =>
  render(
    <MemoryRouter>
      <DataSources />
    </MemoryRouter>,
  );

describe('DataSources connect flow', () => {
  const findMetaConnectButton = async () => {
    const metaHeading = await screen.findByRole('heading', { name: 'Meta (Facebook)' });
    const metaCard = metaHeading.closest('article');
    expect(metaCard).not.toBeNull();
    return within(metaCard as HTMLElement).getByRole('button', {
      name: /connect with facebook/i,
    });
  };

  beforeEach(() => {
    vi.clearAllMocks();
    airbyteMocks.loadAirbyteConnections.mockResolvedValue([]);
    airbyteMocks.loadAirbyteSummary.mockResolvedValue({
      total: 0,
      active: 0,
      inactive: 0,
      due: 0,
      by_provider: {},
      latest_sync: null,
    });
    airbyteMocks.loadGoogleAdsSetupStatus.mockResolvedValue({
      provider: 'google_ads',
      ready_for_oauth: true,
      ready_for_provisioning_defaults: true,
      checks: [],
      oauth_scopes: ['https://www.googleapis.com/auth/adwords'],
      redirect_uri: 'http://localhost:5173/dashboards/data-sources',
      source_definition_id: '0b29e8f7-f64c-4a24-9e97-07c4603f8c04',
    });
    airbyteMocks.loadGoogleAdsStatus.mockResolvedValue({
      provider: 'google_ads',
      status: 'not_connected',
      reason: { message: 'Google Ads OAuth has not been connected.' },
      actions: ['connect_oauth'],
      last_checked_at: '2026-02-17T20:00:00Z',
      last_synced_at: null,
      sync_engine: 'airbyte',
      fallback_active: false,
      parity_state: 'unknown',
      last_parity_passed_at: null,
      metadata: { has_credential: false, has_connection: false },
    });
    airbyteMocks.startGoogleAdsOAuth.mockResolvedValue({
      authorize_url: 'https://accounts.google.com/o/oauth2/v2/auth?state=google-ads',
      state: 'google-ads-state-1',
      redirect_uri: 'http://localhost:5173/dashboards/data-sources',
      oauth_scopes: ['https://www.googleapis.com/auth/adwords'],
    });
    airbyteMocks.exchangeGoogleAdsOAuthCode.mockResolvedValue({
      credential: {
        id: 'google-ads-cred-1',
        provider: 'GOOGLE',
        account_id: '1234567890',
      },
      refresh_token_received: true,
      customer_id: '1234567890',
      login_customer_id: '0987654321',
    });
    airbyteMocks.provisionGoogleAds.mockResolvedValue({
      provider: 'google_ads',
      credential: {
        id: 'google-ads-cred-1',
        provider: 'GOOGLE',
        account_id: '1234567890',
      },
      connection: {
        id: 'gads-conn-1',
        name: 'Google Ads Metrics Connection',
        connection_id: '11111111-1111-4111-8111-111111111111',
        provider: 'GOOGLE',
      },
      sync_engine: 'sdk',
      fallback_active: false,
      source_reused: false,
      connection_reused: false,
    });
    airbyteMocks.loadGoogleAnalyticsSetupStatus.mockResolvedValue({
      provider: 'google_analytics',
      ready_for_oauth: true,
      oauth_scopes: ['https://www.googleapis.com/auth/analytics.readonly'],
      redirect_uri: 'http://localhost:5173/dashboards/data-sources',
      runtime_context: {
        redirect_uri: 'http://localhost:5173/dashboards/data-sources',
        redirect_source: 'explicit_redirect_uri',
        dataset_source: 'warehouse',
      },
    });
    airbyteMocks.loadGoogleAnalyticsStatus.mockResolvedValue({
      provider: 'google_analytics',
      status: 'not_connected',
      reason: { message: 'Google Analytics OAuth has not been connected.' },
      actions: ['connect_oauth'],
      last_checked_at: '2026-02-17T20:00:00Z',
      last_synced_at: null,
      metadata: { has_credential: false, has_connection: false },
    });
    airbyteMocks.startGoogleAnalyticsOAuth.mockResolvedValue({
      authorize_url: 'https://accounts.google.com/o/oauth2/v2/auth?state=ga4',
      state: 'ga4-state-1',
    });
    airbyteMocks.exchangeGoogleAnalyticsOAuthCode.mockResolvedValue({
      credential: {
        id: 'ga4-cred-1',
        provider: 'GOOGLE_ANALYTICS',
        account_id: 'ga4@example.com',
      },
      refresh_token_received: true,
    });
    airbyteMocks.loadGoogleAnalyticsProperties.mockResolvedValue({
      credential_id: 'ga4-cred-1',
      properties: [
        {
          property: 'properties/123456789',
          property_id: '123456789',
          property_name: 'Primary Property',
          account_name: 'Main Account',
        },
      ],
    });
    airbyteMocks.provisionGoogleAnalytics.mockResolvedValue({
      connection: {
        id: 'ga4-conn-1',
        credential_id: 'ga4-cred-1',
        property_id: '123456789',
        property_name: 'Primary Property',
        is_active: true,
        sync_frequency: 'daily',
      },
    });
    airbyteMocks.startMetaOAuth.mockResolvedValue({
      authorize_url: 'https://facebook.example/oauth',
      state: 'state-1',
      redirect_uri: 'http://localhost:5173/dashboards/data-sources',
    });
    airbyteMocks.exchangeMetaOAuthCode.mockResolvedValue({
      selection_token: 'selection-token-1',
      expires_in_seconds: 600,
      pages: [
        {
          id: 'page-1',
          name: 'Business Page',
          tasks: [],
          perms: [],
        },
      ],
      ad_accounts: [
        {
          id: 'act_123',
          account_id: '123',
          name: 'Primary Account',
        },
      ],
      instagram_accounts: [
        {
          id: 'ig-1',
          username: 'brandhandle',
          name: 'Brand Handle',
        },
      ],
      granted_permissions: ['ads_read', 'business_management'],
      declined_permissions: [],
      missing_required_permissions: [],
      token_debug_valid: true,
      oauth_connected_but_missing_permissions: false,
    });
    airbyteMocks.loadMetaSetupStatus.mockResolvedValue({
      provider: 'meta_ads',
      ready_for_oauth: true,
      ready_for_provisioning_defaults: true,
      checks: [
        {
          key: 'meta_runtime_redirect_origin',
          label: 'Open the app on the same host as the configured OAuth redirect',
          ok: false,
          details:
            'Open the app on http://localhost:5173 because the current frontend origin http://localhost:5175 does not match the configured OAuth redirect origin.',
        },
      ],
      oauth_scopes: ['ads_read'],
      graph_api_version: 'v24.0',
      redirect_uri: 'http://localhost:5173/dashboards/data-sources',
      source_definition_id: '778daa7c-feaf-4db6-96f3-70fd645acc77',
      login_configuration_id_configured: true,
      login_configuration_id: '2323589144820085',
      login_configuration_required: true,
      login_mode: 'facebook_login_for_business',
    });
    airbyteMocks.syncMetaIntegration.mockResolvedValue({
      provider: 'meta_ads',
      connection_id: 'conn-meta-1',
      job_id: '101',
    });
    airbyteMocks.logoutMetaOAuth.mockResolvedValue({
      provider: 'meta_ads',
      disconnected: true,
      deleted_credentials: 1,
    });
    airbyteMocks.connectMetaPage.mockResolvedValue({
      credential: {
        id: 'meta-cred-1',
        provider: 'META',
        account_id: 'act_123',
      },
      page: {
        id: 'page-1',
        name: 'Business Page',
        tasks: [],
        perms: [],
      },
      instagram_account: {
        id: 'ig-1',
        username: 'brandhandle',
      },
      granted_permissions: ['ads_read', 'business_management'],
      declined_permissions: [],
      missing_required_permissions: [],
    });
    airbyteMocks.loadSocialConnectionStatus.mockResolvedValue({
      generated_at: '2026-02-17T20:00:00Z',
      platforms: [
        {
          platform: 'meta',
          display_name: 'Meta (Facebook)',
          status: 'started_not_complete',
          reason: { code: 'provisioning_incomplete', message: 'Meta setup incomplete.' },
          last_checked_at: '2026-02-17T20:00:00Z',
          last_synced_at: null,
          actions: ['provision'],
          reporting_readiness: {
            stage: 'waiting_for_direct_sync',
            message: 'Meta setup incomplete.',
            auth_status: 'started_not_complete',
            direct_sync_status: 'blocked',
            warehouse_status: 'disabled',
            dataset_live_reason: 'adapter_disabled',
            warehouse_adapter_enabled: false,
            snapshot_generated_at: null,
          },
          metadata: {},
        },
        {
          platform: 'instagram',
          display_name: 'Instagram (Business)',
          status: 'not_connected',
          reason: {
            code: 'instagram_not_linked',
            message: 'Instagram business linking is optional and is completed inside the Meta asset-selection flow.',
          },
          last_checked_at: '2026-02-17T20:00:00Z',
          last_synced_at: null,
          actions: ['open_meta_setup'],
          metadata: {
            standalone_oauth_supported: false,
            connection_contract: 'linked_via_meta_setup',
          },
        },
      ],
    });
    airbyteMocks.previewMetaRecovery.mockResolvedValue({
      selection_token: 'recovery-token',
      expires_in_seconds: 600,
      pages: [{ id: 'page-1', name: 'Business Page', category: 'Business', tasks: [], perms: [] }],
      ad_accounts: [{ id: 'act_123', account_id: '123', name: 'Primary Account' }],
      instagram_accounts: [],
      granted_permissions: [
        'ads_read',
        'business_management',
        'pages_show_list',
        'pages_read_engagement',
      ],
      declined_permissions: [],
      missing_required_permissions: [],
      token_debug_valid: true,
      oauth_connected_but_missing_permissions: false,
      source: 'existing_meta_connection',
      recovered_from_existing_token: true,
      default_page_id: 'page-1',
      default_ad_account_id: 'act_123',
      default_instagram_account_id: null,
    });
    metaPageInsightsMocks.callbackMetaOAuth.mockResolvedValue({
      connection_id: 'meta-conn-1',
      pages: [
        {
          id: 'page-1',
          page_id: 'page-1',
          name: 'Business Page',
          can_analyze: true,
          is_default: true,
        },
      ],
      default_page_id: 'page-1',
      missing_required_permissions: [],
      oauth_connected_but_missing_permissions: false,
      tasks: {},
    });
    datasetStatusMocks.loadDatasetStatus.mockResolvedValue({
      live: {
        enabled: true,
        reason: 'ready',
        snapshot_generated_at: '2026-04-04T10:00:00Z',
      },
      demo: {
        enabled: true,
        source: 'fake',
        tenant_count: 0,
      },
      warehouse_adapter_enabled: true,
    });
    window.history.replaceState({}, '', '/');
    window.sessionStorage.clear();
  });

  it('shows connect buttons', async () => {
    renderDataSources();

    await waitFor(() => {
      expect(screen.getByRole('button', { name: 'Connect Meta' })).toBeInTheDocument();
      expect(screen.getByRole('button', { name: 'Connect Google Ads' })).toBeInTheDocument();
      expect(screen.getByRole('button', { name: 'Connect Google Analytics' })).toBeInTheDocument();
    });
  });

  it('does not crash when the connections payload is paginated', async () => {
    airbyteMocks.loadAirbyteConnections.mockResolvedValueOnce({
      count: 1,
      results: [
        {
          id: 'conn-1',
          name: 'Google Ads Metrics Connection',
          connection_id: '11111111-1111-1111-1111-111111111111',
          provider: 'GOOGLE',
        },
      ],
    });

    renderDataSources();

    expect(await screen.findByText('Google Ads Metrics Connection')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Connect Meta' })).toBeInTheDocument();
  });

  it('renders social connection statuses and social-focused mode', async () => {
    window.history.replaceState({}, '', '/dashboards/data-sources?sources=social');
    renderDataSources();

    expect(await screen.findByRole('heading', { name: /social connections/i })).toBeInTheDocument();
    expect(screen.getByText('Started, not complete')).toBeInTheDocument();
    expect(screen.getAllByText('Not connected').length).toBeGreaterThan(0);
    expect(screen.getAllByRole('button', { name: /continue setup/i }).length).toBeGreaterThan(0);
  });

  it('frames data sources as the canonical social setup hub', async () => {
    window.history.replaceState({}, '', '/dashboards/data-sources?sources=social');
    renderDataSources();

    expect(
      await screen.findByText(
        'Canonical setup and management hub for social, paid media, and web analytics connections.',
      ),
    ).toBeInTheDocument();
    expect(
      screen.getByText(
        'Connect and manage Meta here, then link Instagram inside the Meta asset-selection flow. There is no separate Instagram OAuth path in ADinsights.',
      ),
    ).toBeInTheDocument();
    expect(screen.getByRole('link', { name: 'Home' })).toHaveAttribute('href', '/');
    expect(screen.getByRole('link', { name: 'Facebook pages' })).toHaveAttribute(
      'href',
      '/dashboards/meta/pages',
    );
  });

  it('shows setup check details when runtime redirect diagnostics fail', async () => {
    const user = userEvent.setup();
    renderDataSources();

    await user.click(await screen.findByRole('button', { name: 'Connect Meta' }));

    expect(
      await screen.findByText(
        'Open the app on http://localhost:5173 because the current frontend origin http://localhost:5175 does not match the configured OAuth redirect origin.',
      ),
    ).toBeInTheDocument();
  });

  it('starts Meta OAuth directly from social connect action', async () => {
    const user = userEvent.setup();
    airbyteMocks.loadSocialConnectionStatus.mockResolvedValueOnce({
      generated_at: '2026-02-17T20:00:00Z',
      platforms: [
        {
          platform: 'meta',
          display_name: 'Meta (Facebook)',
          status: 'not_connected',
          reason: {
            code: 'missing_meta_credential',
            message: 'Meta OAuth has not been connected.',
          },
          last_checked_at: '2026-02-17T20:00:00Z',
          last_synced_at: null,
          actions: ['connect_oauth'],
          metadata: {},
        },
        {
          platform: 'instagram',
          display_name: 'Instagram (Business)',
          status: 'not_connected',
          reason: { code: 'missing_meta_credential', message: 'Connect Meta first.' },
          last_checked_at: '2026-02-17T20:00:00Z',
          last_synced_at: null,
          actions: ['open_meta_setup'],
          metadata: {
            standalone_oauth_supported: false,
          },
        },
      ],
    });

    renderDataSources();

    await user.click(await findMetaConnectButton());
    await waitFor(() => {
      expect(airbyteMocks.startMetaOAuth).toHaveBeenCalledTimes(1);
      expect(window.sessionStorage.getItem('adinsights.connect.oauth.provider')).toBe('META');
    });
    expect(screen.queryByRole('heading', { name: /connect meta/i })).not.toBeInTheDocument();
  });

  it('routes the Instagram CTA back into Meta setup instead of starting standalone OAuth', async () => {
    const user = userEvent.setup();
    renderDataSources();

    const instagramHeading = await screen.findByRole('heading', { name: 'Instagram (Business)' });
    const instagramCard = instagramHeading.closest('article');
    expect(instagramCard).not.toBeNull();

    await user.click(
      within(instagramCard as HTMLElement).getByRole('button', { name: 'Open Meta setup' }),
    );

    expect(airbyteMocks.startMetaOAuth).not.toHaveBeenCalled();
    expect(
      screen.getByRole('heading', { name: 'Connect Meta (Facebook & Instagram)' }),
    ).toBeInTheDocument();
  });

  it('shows the reporting stage separately from the Meta auth reason', async () => {
    renderDataSources();

    expect(await screen.findByText('Blocked')).toBeInTheDocument();
    expect(screen.getByText('Disabled')).toBeInTheDocument();
  });

  it('opens setup panel when direct social oauth start fails', async () => {
    const user = userEvent.setup();
    airbyteMocks.startMetaOAuth.mockRejectedValueOnce(
      new Error('META_APP_ID must be configured for Meta OAuth.'),
    );
    airbyteMocks.loadSocialConnectionStatus.mockResolvedValueOnce({
      generated_at: '2026-02-17T20:00:00Z',
      platforms: [
        {
          platform: 'meta',
          display_name: 'Meta (Facebook)',
          status: 'not_connected',
          reason: {
            code: 'missing_meta_credential',
            message: 'Meta OAuth has not been connected.',
          },
          last_checked_at: '2026-02-17T20:00:00Z',
          last_synced_at: null,
          actions: ['connect_oauth'],
          metadata: {},
        },
        {
          platform: 'instagram',
          display_name: 'Instagram (Business)',
          status: 'not_connected',
          reason: { code: 'missing_meta_credential', message: 'Connect Meta first.' },
          last_checked_at: '2026-02-17T20:00:00Z',
          last_synced_at: null,
          actions: ['open_meta_setup'],
          metadata: {
            standalone_oauth_supported: false,
          },
        },
      ],
    });

    renderDataSources();

    await user.click(await findMetaConnectButton());

    await waitFor(() => {
      expect(addToast).toHaveBeenCalledWith('META_APP_ID must be configured for Meta OAuth.', 'error');
      expect(screen.getByRole('heading', { name: /connect meta/i })).toBeInTheDocument();
    });
  });

  it('handles oauth callback without provider session marker and supports rerequest', async () => {
    const user = userEvent.setup();
    metaPageInsightsMocks.callbackMetaOAuth.mockRejectedValueOnce(
      new ApiError(
        'OAuth state belongs to the marketing flow. Use /api/integrations/meta/oauth/exchange/.',
        400,
        { detail: 'OAuth state belongs to the marketing flow.', code: 'wrong_oauth_flow' },
      ),
    );
    airbyteMocks.exchangeMetaOAuthCode.mockResolvedValueOnce({
      selection_token: 'selection-token-2',
      expires_in_seconds: 600,
      pages: [
        {
          id: 'page-1',
          name: 'Business Page',
          tasks: [],
          perms: [],
        },
      ],
      ad_accounts: [
        {
          id: 'act_123',
          account_id: '123',
          name: 'Primary Account',
        },
      ],
      instagram_accounts: [],
      granted_permissions: ['ads_read'],
      declined_permissions: ['business_management'],
      missing_required_permissions: ['business_management'],
      token_debug_valid: true,
      oauth_connected_but_missing_permissions: true,
    });
    window.history.replaceState(
      {},
      '',
      '/dashboards/data-sources?code=oauth-code&state=oauth-state',
    );
    window.sessionStorage.removeItem('adinsights.meta.oauth.provider');

    renderDataSources();

    expect(
      await screen.findByText(/Missing required permissions: business_management/i),
    ).toBeInTheDocument();

    const rerequestButton = screen.getByText('Re-request permissions', {
      selector: 'button',
    });
    await user.click(rerequestButton);
    await waitFor(() => {
      expect(airbyteMocks.startMetaOAuth).toHaveBeenCalledWith(
        expect.objectContaining({
          auth_type: 'rerequest',
          runtime_context: expect.any(Object),
        }),
      );
    });
  });

  it('handles page-insights callback even when oauth flow marker is missing', async () => {
    window.history.replaceState(
      {},
      '',
      '/dashboards/data-sources?code=oauth-code&state=oauth-state',
    );
    window.sessionStorage.removeItem('adinsights.meta.oauth.flow');

    renderDataSources();

    await waitFor(() => {
      expect(metaPageInsightsMocks.callbackMetaOAuth).toHaveBeenCalledWith('oauth-code', 'oauth-state');
    });
    expect(airbyteMocks.exchangeMetaOAuthCode).not.toHaveBeenCalled();
  });

  it('routes page-insights oauth callback to meta connect callback API', async () => {
    window.sessionStorage.setItem('adinsights.meta.oauth.flow', 'page_insights');
    window.history.replaceState(
      {},
      '',
      '/dashboards/data-sources?code=oauth-code&state=oauth-state',
    );
    renderDataSources();

    await waitFor(() => {
      expect(metaPageInsightsMocks.callbackMetaOAuth).toHaveBeenCalledWith('oauth-code', 'oauth-state');
    });
    await waitFor(() => {
      expect(addToast).toHaveBeenCalledWith('Meta Page Insights connected. Loading page dashboard.', 'success');
    });
  });

  it('requires Meta OAuth before saving connection', async () => {
    const user = userEvent.setup();
    renderDataSources();

    await user.click(await screen.findByRole('button', { name: 'Connect Meta' }));
    await user.click(screen.getByRole('button', { name: 'Save connection' }));

    expect(airbyteMocks.provisionMetaIntegration).not.toHaveBeenCalled();
    expect(addToast).toHaveBeenCalledWith('Complete Meta OAuth and save a business page first.', 'error');
  });

  it('treats restore as successful when sync succeeds even if provisioning fails', async () => {
    const user = userEvent.setup();
    airbyteMocks.loadSocialConnectionStatus.mockResolvedValue({
      generated_at: '2026-02-17T20:00:00Z',
      platforms: [
        {
          platform: 'meta',
          display_name: 'Meta (Facebook)',
          status: 'started_not_complete',
          reason: {
            code: 'orphaned_marketing_access',
            message: 'Restore Meta marketing access to resume reporting.',
          },
          last_checked_at: '2026-02-17T20:00:00Z',
          last_synced_at: null,
          actions: ['recover_marketing_access', 'view'],
          metadata: {
            has_recoverable_marketing_access: true,
            marketing_recovery_source: 'existing_meta_connection',
          },
        },
      ],
    });
    airbyteMocks.provisionMetaIntegration.mockRejectedValueOnce(
      new Error('Airbyte API /api/v1/sources/list request failed: connection refused'),
    );
    airbyteMocks.syncMetaIntegration.mockResolvedValueOnce({
      provider: 'meta_ads',
      connection_id: 'conn-meta-1',
      job_id: 'restore-101',
      task_dispatch_mode: 'inline',
    });

    renderDataSources();

    await user.click(await screen.findByRole('button', { name: 'Connect Meta' }));
    const saveButton = await screen.findByRole('button', { name: 'Save connection' });
    const connectForm = saveButton.closest('form');
    expect(connectForm).not.toBeNull();
    await user.click(
      within(connectForm as HTMLFormElement).getByRole('button', { name: 'Restore marketing access' }),
    );
    await waitFor(() => {
      expect(airbyteMocks.previewMetaRecovery).toHaveBeenCalledTimes(1);
    });
    await user.click(
      within(connectForm as HTMLFormElement).getByRole('button', { name: 'Confirm selection' }),
    );

    await waitFor(() => {
      expect(airbyteMocks.connectMetaPage).toHaveBeenCalledWith(
        expect.objectContaining({
        selection_token: 'recovery-token',
        page_id: 'page-1',
        ad_account_id: 'act_123',
        }),
      );
    });
    await waitFor(() => {
      expect(airbyteMocks.syncMetaIntegration).toHaveBeenCalledTimes(1);
    });
    expect(addToast).toHaveBeenCalledWith(
      'Meta restore completed and sync ran inline (job restore-101).',
      'success',
    );
    expect(addToast).toHaveBeenCalledWith(
      'Meta connected. Direct sync complete. Live reporting is ready.',
      'success',
    );
    expect(addToast).toHaveBeenCalledWith(
      expect.stringContaining('Meta marketing access restored; Airbyte connection was not provisioned.'),
      'info',
    );
  });

  it('completes Google Ads OAuth and provisions the connection', async () => {
    // Extended timeout for complex async mock chain (OAuth exchange + connection provisioning)
    const user = userEvent.setup();
    const view = renderDataSources();

    await user.click(await screen.findByRole('button', { name: 'Connect Google Ads' }));
    await user.type(screen.getByLabelText('Google Ads customer/account ID'), '1234567890');
    await user.type(screen.getByLabelText('Login customer ID (optional)'), '0987654321');
    const setupHeading = screen.getByRole('heading', { name: 'Connect Google Ads' });
    const setupForm = setupHeading.closest('form');
    expect(setupForm).not.toBeNull();
    await user.click(
      within(setupForm as HTMLFormElement).getByRole('button', { name: 'Connect Google Ads' }),
    );

    await waitFor(() => {
      expect(airbyteMocks.startGoogleAdsOAuth).toHaveBeenCalledWith({
        customer_id: '1234567890',
        login_customer_id: '0987654321',
        runtime_context: expect.any(Object),
      });
    });
    expect(window.sessionStorage.getItem('adinsights.connect.oauth.provider')).toBe('GOOGLE');

    window.history.replaceState(
      {},
      '',
      '/dashboards/data-sources?code=oauth-code&state=oauth-state',
    );
    view.unmount();
    renderDataSources();

    await waitFor(() => {
      expect(airbyteMocks.exchangeGoogleAdsOAuthCode).toHaveBeenCalledWith({
        code: 'oauth-code',
        state: 'oauth-state',
        runtime_context: expect.any(Object),
      });
    });

    await user.clear(screen.getByLabelText('Connection name'));
    await user.type(screen.getByLabelText('Connection name'), 'Google Ads Metrics');
    await user.type(
      screen.getByLabelText('Airbyte workspace UUID (optional)'),
      'aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa',
    );
    await user.type(
      screen.getByLabelText('Airbyte destination UUID (optional)'),
      'bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb',
    );

    await user.click(screen.getByRole('button', { name: 'Save connection' }));

    await waitFor(() => {
      expect(airbyteMocks.provisionGoogleAds).toHaveBeenCalledWith({
        external_account_id: '1234567890',
        login_customer_id: '0987654321',
        workspace_id: 'aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa',
        destination_id: 'bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb',
        connection_name: 'Google Ads Metrics',
        schedule_type: 'cron',
        is_active: true,
        interval_minutes: null,
        cron_expression: '0 6-22 * * *',
      });
    });
  }, 15000);

  it('starts Google Analytics OAuth from the setup panel', async () => {
    const user = userEvent.setup();
    renderDataSources();

    await user.click(await screen.findByRole('button', { name: 'Connect Google Analytics' }));
    const setupHeading = screen.getByRole('heading', { name: 'Connect Google Analytics 4' });
    const setupForm = setupHeading.closest('form');
    expect(setupForm).not.toBeNull();
    await user.click(
      within(setupForm as HTMLFormElement).getByRole('button', {
        name: 'Connect Google Analytics',
      }),
    );

    await waitFor(() => {
      expect(airbyteMocks.startGoogleAnalyticsOAuth).toHaveBeenCalled();
    });
  });

  it('shows separate Google Analytics and Google Ads cards with explicit setup labels', async () => {
    renderDataSources();

    expect(await screen.findByRole('heading', { name: 'Google Analytics 4' })).toBeInTheDocument();
    expect(screen.getByRole('heading', { name: 'Google Ads' })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Open GA4 setup' })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Open Google Ads setup' })).toBeInTheDocument();
    expect(screen.getByText(/website and app behavior/i)).toBeInTheDocument();
    expect(screen.getByText(/paid campaign performance/i)).toBeInTheDocument();
  });

  it('disables GA4 OAuth start when GA4 setup is not ready', async () => {
    const user = userEvent.setup();
    airbyteMocks.loadGoogleAnalyticsSetupStatus.mockResolvedValue({
      provider: 'google_analytics',
      ready_for_oauth: false,
      oauth_scopes: ['https://www.googleapis.com/auth/analytics.readonly'],
      redirect_uri: '',
      runtime_context: null,
    });

    renderDataSources();

    await user.click(await screen.findByRole('button', { name: 'Connect Google Analytics' }));
    const setupHeading = screen.getByRole('heading', { name: 'Connect Google Analytics 4' });
    const setupForm = setupHeading.closest('form');
    expect(setupForm).not.toBeNull();

    const oauthButton = within(setupForm as HTMLFormElement).getByRole('button', {
      name: 'Connect Google Analytics',
    });
    expect(oauthButton).toBeDisabled();
    expect(
      within(setupForm as HTMLFormElement).getByText(/GA4 OAuth is not ready/i),
    ).toBeInTheDocument();
    expect(airbyteMocks.startGoogleAnalyticsOAuth).not.toHaveBeenCalled();
  });

  it('loads GA4 properties for the exchanged credential after oauth callback', async () => {
    window.sessionStorage.setItem('adinsights.connect.oauth.provider', 'GA4');
    window.history.replaceState(
      {},
      '',
      '/dashboards/data-sources?code=oauth-code&state=oauth-state',
    );

    renderDataSources();

    await waitFor(() => {
      expect(airbyteMocks.exchangeGoogleAnalyticsOAuthCode).toHaveBeenCalledWith({
        code: 'oauth-code',
        state: 'oauth-state',
        runtime_context: expect.any(Object),
      });
    });
    await waitFor(() => {
      expect(airbyteMocks.loadGoogleAnalyticsProperties).toHaveBeenCalledWith({
        credential_id: 'ga4-cred-1',
      });
    });
    expect(await screen.findByDisplayValue('ga4@example.com')).toBeInTheDocument();
  });
});
