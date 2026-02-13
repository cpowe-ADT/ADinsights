import { render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import userEvent from '@testing-library/user-event';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import DataSources from '../DataSources';

const pushToast = vi.fn();

const airbyteMocks = vi.hoisted(() => ({
  loadAirbyteConnections: vi.fn(),
  loadAirbyteSummary: vi.fn(),
  triggerAirbyteSync: vi.fn(),
  startMetaOAuth: vi.fn(),
  exchangeMetaOAuthCode: vi.fn(),
  connectMetaPage: vi.fn(),
  startIntegrationOAuth: vi.fn(),
  callbackIntegrationOAuth: vi.fn(),
  provisionIntegration: vi.fn(),
  syncIntegration: vi.fn(),
  loadIntegrationStatus: vi.fn(),
}));

vi.mock('../../components/ToastProvider', () => ({
  useToast: () => ({ pushToast }),
}));

vi.mock('../../lib/airbyte', () => ({
  loadAirbyteConnections: airbyteMocks.loadAirbyteConnections,
  loadAirbyteSummary: airbyteMocks.loadAirbyteSummary,
  triggerAirbyteSync: airbyteMocks.triggerAirbyteSync,
  startMetaOAuth: airbyteMocks.startMetaOAuth,
  exchangeMetaOAuthCode: airbyteMocks.exchangeMetaOAuthCode,
  connectMetaPage: airbyteMocks.connectMetaPage,
  startIntegrationOAuth: airbyteMocks.startIntegrationOAuth,
  callbackIntegrationOAuth: airbyteMocks.callbackIntegrationOAuth,
  provisionIntegration: airbyteMocks.provisionIntegration,
  syncIntegration: airbyteMocks.syncIntegration,
  loadIntegrationStatus: airbyteMocks.loadIntegrationStatus,
}));

describe('DataSources connector flow', () => {
  const renderPage = () =>
    render(
      <MemoryRouter initialEntries={[window.location.pathname + window.location.search]}>
        <DataSources />
      </MemoryRouter>,
    );

  beforeEach(() => {
    vi.clearAllMocks();
    window.history.pushState({}, '', '/dashboards/data-sources');
    window.sessionStorage.clear();
    airbyteMocks.loadAirbyteConnections.mockResolvedValue([]);
    airbyteMocks.loadAirbyteSummary.mockResolvedValue({
      total: 0,
      active: 0,
      inactive: 0,
      due: 0,
      by_provider: {},
      latest_sync: null,
    });
    airbyteMocks.loadIntegrationStatus.mockImplementation(async (provider: string) => ({
      provider,
      label: provider,
      state: 'not_connected',
      credentials: [],
      connections: [],
      latest_connection_id: null,
    }));
    airbyteMocks.startMetaOAuth.mockResolvedValue({
      provider: 'facebook_pages',
      authorize_url: 'https://facebook.example/oauth',
      state: 'state',
      redirect_uri: 'http://localhost:5173/dashboards/data-sources',
    });
    airbyteMocks.startIntegrationOAuth.mockResolvedValue({
      provider: 'google_ads',
      authorize_url: 'https://accounts.google.com/o/oauth2/auth',
      state: 'state',
      redirect_uri: 'http://localhost:5173/dashboards/data-sources',
    });
    airbyteMocks.exchangeMetaOAuthCode.mockResolvedValue({
      selection_token: 'selection-token-1',
      expires_in_seconds: 600,
      pages: [
        {
          id: 'page-1',
          name: 'Primary Page',
          category: 'Business',
          tasks: ['CREATE_CONTENT'],
          perms: ['ADMINISTER'],
        },
      ],
    });
    airbyteMocks.connectMetaPage.mockResolvedValue({
      credential: { id: 'cred-1', provider: 'META', account_id: 'page-1' },
      page: {
        id: 'page-1',
        name: 'Primary Page',
        category: 'Business',
        tasks: ['CREATE_CONTENT'],
        perms: ['ADMINISTER'],
      },
    });
    airbyteMocks.provisionIntegration.mockResolvedValue({
      provider: 'ga4',
      credential: { id: 'cred-1', provider: 'GA4', account_id: '123' },
      connection: {
        id: 'conn-1',
        name: 'GA4 Reporting',
        connection_id: '11111111-1111-4111-8111-111111111111',
        provider: 'GA4',
      },
      source: { source_id: 'source-1', name: 'GA4 source' },
      source_reused: false,
      connection_reused: false,
    });
    airbyteMocks.syncIntegration.mockResolvedValue({
      provider: 'google_ads',
      connection_id: 'conn-id',
      job_id: '101',
    });
  });

  it('renders all connector buttons', async () => {
    renderPage();

    await waitFor(() => {
      expect(screen.getByRole('button', { name: 'Connect Facebook Page' })).toBeInTheDocument();
      expect(screen.getByRole('button', { name: 'Connect Google Ads' })).toBeInTheDocument();
      expect(screen.getByRole('button', { name: 'Connect Google Analytics 4' })).toBeInTheDocument();
      expect(screen.getByRole('button', { name: 'Connect Google Search Console' })).toBeInTheDocument();
    });
  });

  it('starts Google OAuth from the connect panel', async () => {
    const user = userEvent.setup();
    renderPage();

    await user.click(await screen.findByRole('button', { name: 'Connect Google Ads' }));
    await user.type(screen.getByLabelText('Google Ads customer/account ID'), '1234567890');
    await user.click(screen.getByRole('button', { name: 'Connect with Google' }));

    await waitFor(() => {
      expect(airbyteMocks.startIntegrationOAuth).toHaveBeenCalledWith('google_ads');
      expect(window.sessionStorage.getItem('adinsights.integration.oauth.provider')).toBe('google_ads');
      expect(window.sessionStorage.getItem('adinsights.integration.oauth.account')).toBe('1234567890');
    });
  });

  it('handles Meta callback and saves selected page', async () => {
    const user = userEvent.setup();
    window.history.pushState({}, '', '/dashboards/data-sources?code=oauth-code&state=oauth-state');
    renderPage();

    await waitFor(() => {
      expect(airbyteMocks.exchangeMetaOAuthCode).toHaveBeenCalledWith({
        code: 'oauth-code',
        state: 'oauth-state',
      });
    });

    await user.click(screen.getByRole('button', { name: 'Save selected page' }));

    await waitFor(() => {
      expect(airbyteMocks.connectMetaPage).toHaveBeenCalledWith({
        selection_token: 'selection-token-1',
        page_id: 'page-1',
      });
    });
  });

  it('provisions connector from panel submit', async () => {
    const user = userEvent.setup();
    renderPage();

    await user.click(await screen.findByRole('button', { name: 'Connect Google Analytics 4' }));
    await user.type(screen.getByLabelText('GA4 property ID'), '123456789');
    await user.click(screen.getByRole('button', { name: 'Save connection' }));

    await waitFor(() => {
      expect(airbyteMocks.provisionIntegration).toHaveBeenCalledWith(
        'ga4',
        expect.objectContaining({
          external_account_id: '123456789',
          connection_name: 'GA4 Reporting',
          schedule_type: 'cron',
        }),
      );
    });
  });
});
