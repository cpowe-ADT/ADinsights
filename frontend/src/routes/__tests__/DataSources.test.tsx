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
  });

  it('shows connect buttons', async () => {
    render(<DataSources />);

    await waitFor(() => {
      expect(screen.getByRole('button', { name: 'Connect Meta' })).toBeInTheDocument();
      expect(screen.getByRole('button', { name: 'Connect Google Ads' })).toBeInTheDocument();
    });
  });

  it('creates Meta credential from connect form', async () => {
    const user = userEvent.setup();
    render(<DataSources />);

    await user.click(await screen.findByRole('button', { name: 'Connect Meta' }));
    await user.type(screen.getByLabelText('Meta ad account ID'), 'act_123456789');
    await user.type(screen.getByLabelText('Access token'), 'meta-token');
    await user.click(screen.getByRole('button', { name: 'Save connection' }));

    await waitFor(() => {
      expect(airbyteMocks.createPlatformCredential).toHaveBeenCalledWith({
        provider: 'META',
        account_id: 'act_123456789',
        access_token: 'meta-token',
        refresh_token: null,
      });
    });
    expect(airbyteMocks.createAirbyteConnection).not.toHaveBeenCalled();
    expect(pushToast).toHaveBeenCalledWith('Meta (Facebook & Instagram) credentials saved.', {
      tone: 'success',
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

