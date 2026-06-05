import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import { ConnectorLifecycleControls } from '../ConnectorLifecycleControls';

const addToast = vi.fn();
const loadIntegrationJobs = vi.fn();
const disconnectIntegration = vi.fn();
const reconnectIntegration = vi.fn();

vi.mock('../../stores/useToastStore', () => ({
  useToastStore: (selector: (state: { addToast: typeof addToast }) => unknown) =>
    selector({ addToast }),
}));

vi.mock('../../lib/airbyte', () => ({
  loadIntegrationJobs: (...args: unknown[]) => loadIntegrationJobs(...args),
  disconnectIntegration: (...args: unknown[]) => disconnectIntegration(...args),
  reconnectIntegration: (...args: unknown[]) => reconnectIntegration(...args),
}));

describe('ConnectorLifecycleControls', () => {
  beforeEach(() => {
    addToast.mockReset();
    loadIntegrationJobs.mockReset();
    disconnectIntegration.mockReset();
    reconnectIntegration.mockReset();
    loadIntegrationJobs.mockResolvedValue({ provider: 'google_ads', count: 0, jobs: [] });
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it('renders recent sync jobs returned by the API', async () => {
    loadIntegrationJobs.mockResolvedValue({
      provider: 'google_ads',
      count: 1,
      jobs: [
        {
          job_id: 'job-1',
          status: 'succeeded',
          started_at: '2026-06-01T10:00:00Z',
          records_synced: 1234,
          connection: { id: 'c1', name: 'Google Ads', connection_id: 'conn-1' },
        },
      ],
    });

    render(<ConnectorLifecycleControls provider="google_ads" label="Google Ads" />);

    expect(await screen.findByText('Recent sync jobs')).toBeInTheDocument();
    expect(screen.getByText('succeeded')).toBeInTheDocument();
    expect(screen.getByText(/1,234 records/)).toBeInTheDocument();
    expect(loadIntegrationJobs).toHaveBeenCalledWith('google_ads', 5, expect.anything());
  });

  it('disconnects the provider and notifies the parent', async () => {
    disconnectIntegration.mockResolvedValue({ provider: 'google_ads', state: 'not_connected' });
    const onChanged = vi.fn();
    const user = userEvent.setup();

    render(
      <ConnectorLifecycleControls provider="google_ads" label="Google Ads" onChanged={onChanged} />,
    );

    await user.click(await screen.findByRole('button', { name: /disconnect/i }));

    await waitFor(() => expect(disconnectIntegration).toHaveBeenCalledWith('google_ads'));
    expect(onChanged).toHaveBeenCalledTimes(1);
    expect(addToast).toHaveBeenCalledWith('Google Ads disconnected.', 'success');
  });

  it('redirects the browser to the reconnect authorize URL', async () => {
    reconnectIntegration.mockResolvedValue({
      provider: 'google_ads',
      authorize_url: 'https://auth.example.com/go',
      state: 'state-1',
      redirect_uri: 'https://app.example.com/cb',
    });
    const assign = vi.fn();
    const originalLocation = window.location;
    Object.defineProperty(window, 'location', {
      configurable: true,
      value: { ...originalLocation, assign },
    });
    const user = userEvent.setup();

    render(<ConnectorLifecycleControls provider="google_ads" label="Google Ads" />);

    await user.click(await screen.findByRole('button', { name: /reconnect/i }));

    await waitFor(() =>
      expect(reconnectIntegration).toHaveBeenCalledWith('google_ads'),
    );
    expect(assign).toHaveBeenCalledWith('https://auth.example.com/go');
  });
});
