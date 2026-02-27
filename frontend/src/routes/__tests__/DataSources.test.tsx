import { render, screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import DataSources from '../DataSources';

const pushToast = vi.fn();

const airbyteMocks = vi.hoisted(() => ({
  loadAirbyteConnections: vi.fn(),
  loadAirbyteSummary: vi.fn(),
  triggerAirbyteSync: vi.fn(),
  createPlatformCredential: vi.fn(),
  createAirbyteConnection: vi.fn(),
  startMetaOAuth: vi.fn(),
  exchangeMetaOAuthCode: vi.fn(),
  connectMetaPage: vi.fn(),
  provisionMetaIntegration: vi.fn(),
  syncMetaIntegration: vi.fn(),
  logoutMetaOAuth: vi.fn(),
  loadMetaSetupStatus: vi.fn(),
  loadSocialConnectionStatus: vi.fn(),
}));
const metaPageInsightsMocks = vi.hoisted(() => ({
  callbackMetaOAuth: vi.fn(),
}));

vi.mock('../../components/ToastProvider', () => ({
  useToast: () => ({ pushToast }),
}));

vi.mock('../../lib/airbyte', () => ({
  loadAirbyteConnections: airbyteMocks.loadAirbyteConnections,
  loadAirbyteSummary: airbyteMocks.loadAirbyteSummary,
  triggerAirbyteSync: airbyteMocks.triggerAirbyteSync,
  createPlatformCredential: airbyteMocks.createPlatformCredential,
  createAirbyteConnection: airbyteMocks.createAirbyteConnection,
  startMetaOAuth: airbyteMocks.startMetaOAuth,
  exchangeMetaOAuthCode: airbyteMocks.exchangeMetaOAuthCode,
  connectMetaPage: airbyteMocks.connectMetaPage,
  provisionMetaIntegration: airbyteMocks.provisionMetaIntegration,
  syncMetaIntegration: airbyteMocks.syncMetaIntegration,
  logoutMetaOAuth: airbyteMocks.logoutMetaOAuth,
  loadMetaSetupStatus: airbyteMocks.loadMetaSetupStatus,
  loadSocialConnectionStatus: airbyteMocks.loadSocialConnectionStatus,
}));
vi.mock('../../lib/metaPageInsights', () => ({
  META_OAUTH_FLOW_PAGE_INSIGHTS: 'page_insights',
  META_OAUTH_FLOW_SESSION_KEY: 'adinsights.meta.oauth.flow',
  callbackMetaOAuth: metaPageInsightsMocks.callbackMetaOAuth,
}));

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
    airbyteMocks.createPlatformCredential.mockResolvedValue({
      id: 'cred-1',
      provider: 'META',
      account_id: 'act_123',
    });
    airbyteMocks.createAirbyteConnection.mockResolvedValue({
      id: 'conn-local-1',
      name: 'Meta Metrics Connection',
      connection_id: '11111111-1111-1111-1111-111111111111',
      provider: 'META',
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
      checks: [],
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
          metadata: {},
        },
        {
          platform: 'instagram',
          display_name: 'Instagram (Business)',
          status: 'not_connected',
          reason: {
            code: 'instagram_not_linked',
            message: 'Instagram is not linked yet.',
          },
          last_checked_at: '2026-02-17T20:00:00Z',
          last_synced_at: null,
          actions: ['select_assets'],
          metadata: {},
        },
      ],
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
    window.history.replaceState({}, '', '/');
    window.sessionStorage.clear();
  });

  it('shows connect buttons', async () => {
    render(<DataSources />);

    await waitFor(() => {
      expect(screen.getByRole('button', { name: 'Connect Meta' })).toBeInTheDocument();
      expect(screen.getByRole('button', { name: 'Connect Google Ads' })).toBeInTheDocument();
    });
  });

  it('renders social connection statuses and social-focused mode', async () => {
    window.history.replaceState({}, '', '/dashboards/data-sources?sources=social');
    render(<DataSources />);

    expect(await screen.findByRole('heading', { name: /social connections/i })).toBeInTheDocument();
    expect(screen.getByText('Started, not complete')).toBeInTheDocument();
    expect(screen.getAllByText('Not connected').length).toBeGreaterThan(0);
    expect(screen.getAllByRole('button', { name: /continue setup/i }).length).toBeGreaterThan(0);
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
          actions: ['connect_oauth'],
          metadata: {},
        },
      ],
    });

    render(<DataSources />);

    await user.click(await findMetaConnectButton());
    await waitFor(() => {
      expect(airbyteMocks.startMetaOAuth).toHaveBeenCalledTimes(1);
      expect(window.sessionStorage.getItem('adinsights.meta.oauth.provider')).toBe('META');
    });
    expect(screen.queryByRole('heading', { name: /connect meta/i })).not.toBeInTheDocument();
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
          actions: ['connect_oauth'],
          metadata: {},
        },
      ],
    });

    render(<DataSources />);

    await user.click(await findMetaConnectButton());

    await waitFor(() => {
      expect(pushToast).toHaveBeenCalledWith('META_APP_ID must be configured for Meta OAuth.', {
        tone: 'error',
      });
      expect(screen.getByRole('heading', { name: /connect meta/i })).toBeInTheDocument();
    });
  });

  it('handles oauth callback without provider session marker and supports rerequest', async () => {
    const user = userEvent.setup();
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

    render(<DataSources />);

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

  it('routes page-insights oauth callback to meta connect callback API', async () => {
    window.sessionStorage.setItem('adinsights.meta.oauth.flow', 'page_insights');
    window.history.replaceState(
      {},
      '',
      '/dashboards/data-sources?code=oauth-code&state=oauth-state',
    );
    render(<DataSources />);

    await waitFor(() => {
      expect(metaPageInsightsMocks.callbackMetaOAuth).toHaveBeenCalledWith('oauth-code', 'oauth-state');
    });
    await waitFor(() => {
      expect(pushToast).toHaveBeenCalledWith('Meta Page Insights connected. Loading page dashboard.', {
        tone: 'success',
      });
    });
  });

  it('requires Meta OAuth before saving connection', async () => {
    const user = userEvent.setup();
    render(<DataSources />);

    await user.click(await screen.findByRole('button', { name: 'Connect Meta' }));
    await user.click(screen.getByRole('button', { name: 'Save connection' }));

    expect(airbyteMocks.createPlatformCredential).not.toHaveBeenCalled();
    expect(pushToast).toHaveBeenCalledWith('Complete Meta OAuth and save a business page first.', {
      tone: 'error',
    });
  });

  it('creates Google credential and links Airbyte connection when enabled', async () => {
    const user = userEvent.setup();
    render(<DataSources />);

    await user.click(await screen.findByRole('button', { name: 'Connect Google Ads' }));
    await user.type(screen.getByLabelText('Google Ads customer/account ID'), '1234567890');
    await user.type(screen.getByLabelText('Access token'), 'google-access-token');
    await user.click(screen.getByRole('checkbox', { name: /Also link Airbyte connection/i }));
    await user.clear(screen.getByLabelText('Connection name'));
    await user.type(screen.getByLabelText('Connection name'), 'Google Ads Metrics');
    await user.type(
      screen.getByLabelText('Airbyte connection UUID'),
      '11111111-1111-4111-8111-111111111111',
    );
    await user.type(
      screen.getByLabelText('Airbyte workspace UUID (optional)'),
      'aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa',
    );

    await user.click(screen.getByRole('button', { name: 'Save connection' }));

    await waitFor(() => {
      expect(airbyteMocks.createPlatformCredential).toHaveBeenCalledWith({
        provider: 'GOOGLE',
        account_id: '1234567890',
        access_token: 'google-access-token',
        refresh_token: null,
      });
      expect(airbyteMocks.createAirbyteConnection).toHaveBeenCalledWith({
        name: 'Google Ads Metrics',
        connection_id: '11111111-1111-4111-8111-111111111111',
        workspace_id: 'aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa',
        provider: 'GOOGLE',
        schedule_type: 'cron',
        is_active: true,
        interval_minutes: null,
        cron_expression: '0 6-22 * * *',
      });
    });
  });
});
