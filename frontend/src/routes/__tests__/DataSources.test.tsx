import { render, screen, waitFor } from '@testing-library/react';
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
  loadMetaSetupStatus: vi.fn(),
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
  loadMetaSetupStatus: airbyteMocks.loadMetaSetupStatus,
}));

describe('DataSources connect flow', () => {
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
    });
    airbyteMocks.syncMetaIntegration.mockResolvedValue({
      provider: 'meta_ads',
      connection_id: 'conn-meta-1',
      job_id: '101',
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
