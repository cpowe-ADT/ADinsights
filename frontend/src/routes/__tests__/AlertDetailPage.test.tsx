import { render, screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import AlertDetailPage from '../AlertDetailPage';
import type { AlertRule } from '../../lib/phase2Api';

const phase2ApiMock = vi.hoisted(() => ({
  getAlert: vi.fn(),
  deleteAlert: vi.fn(),
  updateAlert: vi.fn(),
  pauseAlert: vi.fn(),
  resumeAlert: vi.fn(),
  listNotificationChannels: vi.fn(),
}));

const toastMock = vi.hoisted(() => ({
  addToast: vi.fn(),
  removeToast: vi.fn(),
  toasts: [] as Array<{ id: string; message: string; variant: string }>,
}));

vi.mock('../../lib/phase2Api', () => ({
  getAlert: phase2ApiMock.getAlert,
  deleteAlert: phase2ApiMock.deleteAlert,
  updateAlert: phase2ApiMock.updateAlert,
  pauseAlert: phase2ApiMock.pauseAlert,
  resumeAlert: phase2ApiMock.resumeAlert,
  listNotificationChannels: phase2ApiMock.listNotificationChannels,
}));

vi.mock('../../stores/useToastStore', () => ({
  useToastStore: (selector: (state: typeof toastMock) => unknown) => selector(toastMock),
}));

const sampleAlert: AlertRule = {
  id: '1',
  name: 'High CPC Alert',
  metric: 'cpc',
  comparison_operator: '>',
  threshold: '5.00',
  lookback_hours: 24,
  severity: 'medium',
  is_active: true,
  notification_channels: [],
  created_at: '2026-04-01T10:00:00Z',
  updated_at: '2026-04-05T14:30:00Z',
};

function renderPage(alertId = '1') {
  return render(
    <MemoryRouter initialEntries={[`/alerts/${alertId}`]}>
      <Routes>
        <Route path="/alerts/:alertId" element={<AlertDetailPage />} />
      </Routes>
    </MemoryRouter>,
  );
}

describe('AlertDetailPage', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    phase2ApiMock.getAlert.mockResolvedValue(sampleAlert);
    phase2ApiMock.listNotificationChannels.mockResolvedValue([]);
    phase2ApiMock.updateAlert.mockResolvedValue(sampleAlert);
    phase2ApiMock.deleteAlert.mockResolvedValue(undefined);
    phase2ApiMock.pauseAlert.mockResolvedValue({ ...sampleAlert, is_active: false });
    phase2ApiMock.resumeAlert.mockResolvedValue({ ...sampleAlert, is_active: true });
  });

  it('renders alert rule details after loading', async () => {
    renderPage();

    await waitFor(() => expect(phase2ApiMock.getAlert).toHaveBeenCalledWith('1'));
    expect(await screen.findByRole('heading', { name: 'High CPC Alert' })).toBeInTheDocument();
    expect(screen.getByText('cpc')).toBeInTheDocument();
    expect(screen.getByText('>')).toBeInTheDocument();
    expect(screen.getByText('5.00')).toBeInTheDocument();
    // The pause-duration dropdown also exposes "24 hours", so anchor on the
    // <strong> element that lives inside the Lookback paragraph.
    expect(
      screen.getByText('24 hours', { selector: 'strong' }),
    ).toBeInTheDocument();
    expect(screen.getByText('medium')).toBeInTheDocument();
  });

  it('renders severity pill with correct class', async () => {
    renderPage();

    const pill = await screen.findByText('medium');
    expect(pill).toHaveClass('phase2-pill--medium');
  });

  it('shows error state when API fails', async () => {
    phase2ApiMock.getAlert.mockRejectedValue(new Error('Network error'));

    renderPage();

    await waitFor(() => expect(screen.getByText('Alert unavailable')).toBeInTheDocument());
    expect(screen.getByText('Network error')).toBeInTheDocument();
  });

  it('refreshes alert data when Refresh button is clicked', async () => {
    renderPage();

    await screen.findByRole('heading', { name: 'High CPC Alert' });

    const updatedAlert = { ...sampleAlert, name: 'Updated Alert' };
    phase2ApiMock.getAlert.mockResolvedValue(updatedAlert);

    const user = userEvent.setup();
    await user.click(screen.getByRole('button', { name: /refresh/i }));

    await waitFor(() => expect(phase2ApiMock.getAlert).toHaveBeenCalledTimes(2));
    expect(await screen.findByRole('heading', { name: 'Updated Alert' })).toBeInTheDocument();
  });

  it('renders back to alerts link', async () => {
    renderPage();

    await screen.findByRole('heading', { name: 'High CPC Alert' });

    const backLink = screen.getByRole('link', { name: /back to alerts/i });
    expect(backLink).toHaveAttribute('href', '/alerts');
  });

  it('shows active state with pause button', async () => {
    renderPage();
    await screen.findByRole('heading', { name: 'High CPC Alert' });
    expect(screen.getByText('Active')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Pause' })).toBeInTheDocument();
  });

  it('shows paused state with resume button when inactive', async () => {
    phase2ApiMock.getAlert.mockResolvedValue({ ...sampleAlert, is_active: false });
    renderPage();
    await waitFor(() => expect(screen.getByText('Paused')).toBeInTheDocument());
    expect(screen.getByRole('button', { name: 'Resume' })).toBeInTheDocument();
  });

  it('renders five pause duration preset options when active with Indefinite default', async () => {
    renderPage();
    await screen.findByRole('heading', { name: 'High CPC Alert' });

    const dropdown = screen.getByLabelText('Pause duration') as HTMLSelectElement;
    const options = within(dropdown).getAllByRole('option');
    const labels = options.map((opt) => opt.textContent);
    expect(labels).toEqual(['1 hour', '4 hours', '24 hours', '7 days', 'Indefinite']);
    expect(dropdown.value).toBe('indefinite');
  });

  it('hides the pause duration dropdown when alert is paused', async () => {
    phase2ApiMock.getAlert.mockResolvedValue({ ...sampleAlert, is_active: false });
    renderPage();

    await waitFor(() => expect(screen.getByText('Paused')).toBeInTheDocument());
    expect(screen.queryByLabelText('Pause duration')).not.toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Resume' })).toBeInTheDocument();
  });

  it('selecting 24 hours and clicking Pause calls pauseAlert with duration_hours: 24', async () => {
    renderPage();
    await screen.findByRole('heading', { name: 'High CPC Alert' });

    const user = userEvent.setup();
    const dropdown = screen.getByLabelText('Pause duration');
    await user.selectOptions(dropdown, '24h');
    await user.click(screen.getByRole('button', { name: 'Pause' }));

    await waitFor(() =>
      expect(phase2ApiMock.pauseAlert).toHaveBeenCalledWith('1', { duration_hours: 24 }),
    );
  });

  it('clicking Pause with the Indefinite default calls pauseAlert with empty body', async () => {
    renderPage();
    await screen.findByRole('heading', { name: 'High CPC Alert' });

    const user = userEvent.setup();
    await user.click(screen.getByRole('button', { name: 'Pause' }));

    await waitFor(() => expect(phase2ApiMock.pauseAlert).toHaveBeenCalledWith('1', {}));
  });

  it('clicking Resume calls resumeAlert and does not call updateAlert', async () => {
    phase2ApiMock.getAlert.mockResolvedValue({ ...sampleAlert, is_active: false });
    renderPage();
    await waitFor(() => expect(screen.getByText('Paused')).toBeInTheDocument());

    const user = userEvent.setup();
    await user.click(screen.getByRole('button', { name: 'Resume' }));

    await waitFor(() => expect(phase2ApiMock.resumeAlert).toHaveBeenCalledTimes(1));
    expect(phase2ApiMock.resumeAlert).toHaveBeenCalledWith('1');
    expect(phase2ApiMock.updateAlert).not.toHaveBeenCalled();
  });

  it('shows the auto-resume line when paused_until is set', async () => {
    const future = new Date(Date.now() + 60 * 60 * 1000).toISOString();
    phase2ApiMock.getAlert.mockResolvedValue({
      ...sampleAlert,
      is_active: false,
      paused_until: future,
    });

    renderPage();

    expect(await screen.findByText(/Auto-resumes/i)).toBeInTheDocument();
  });

  it('fires success toast referencing pause time when pauseAlert resolves with paused_until', async () => {
    const future = new Date(Date.now() + 60 * 60 * 1000).toISOString();
    phase2ApiMock.pauseAlert.mockResolvedValue({
      ...sampleAlert,
      is_active: false,
      paused_until: future,
    });

    renderPage();
    await screen.findByRole('heading', { name: 'High CPC Alert' });

    const user = userEvent.setup();
    await user.click(screen.getByRole('button', { name: 'Pause' }));

    await waitFor(() => expect(toastMock.addToast).toHaveBeenCalled());
    const messages = toastMock.addToast.mock.calls.map((c) => String(c[0]));
    expect(messages.some((msg) => /paused/i.test(msg) && /until/i.test(msg))).toBe(true);
  });

  it('fires error toast on pause failure and does not flip alert to paused state', async () => {
    phase2ApiMock.pauseAlert.mockRejectedValue(new Error('boom'));

    renderPage();
    await screen.findByRole('heading', { name: 'High CPC Alert' });

    const user = userEvent.setup();
    await user.click(screen.getByRole('button', { name: 'Pause' }));

    await waitFor(() => expect(phase2ApiMock.pauseAlert).toHaveBeenCalled());
    await waitFor(() =>
      expect(
        toastMock.addToast.mock.calls.some(
          (call) => call[1] === 'error' && /failed/i.test(String(call[0])),
        ),
      ).toBe(true),
    );
    // Status should remain Active because we never called setAlert with a paused row.
    expect(screen.getByText('Active')).toBeInTheDocument();
    expect(screen.queryByText('Paused')).not.toBeInTheDocument();
  });

  it('clicking Edit reveals editable rule form fields', async () => {
    renderPage();
    await screen.findByRole('heading', { name: 'High CPC Alert' });

    const user = userEvent.setup();
    await user.click(screen.getByRole('button', { name: 'Edit' }));

    expect(screen.getByLabelText('Name')).toBeInTheDocument();
    expect(screen.getByLabelText('Metric')).toBeInTheDocument();
    expect(screen.getByLabelText('Threshold')).toBeInTheDocument();
    expect(screen.getByLabelText('Lookback (hours)')).toBeInTheDocument();
    expect(screen.getByLabelText('Operator')).toBeInTheDocument();
    expect(screen.getByLabelText('Severity')).toBeInTheDocument();
  });

  it('Save in edit form calls updateAlert with the changed threshold and toasts success', async () => {
    phase2ApiMock.updateAlert.mockResolvedValue({ ...sampleAlert, threshold: '12' });

    renderPage();
    await screen.findByRole('heading', { name: 'High CPC Alert' });

    const user = userEvent.setup();
    await user.click(screen.getByRole('button', { name: 'Edit' }));

    const thresholdInput = screen.getByLabelText('Threshold');
    await user.clear(thresholdInput);
    await user.type(thresholdInput, '12');

    await user.click(screen.getByRole('button', { name: 'Save' }));

    await waitFor(() => expect(phase2ApiMock.updateAlert).toHaveBeenCalledTimes(1));
    const [calledId, calledPayload] = phase2ApiMock.updateAlert.mock.calls[0];
    expect(calledId).toBe('1');
    expect(calledPayload).toMatchObject({ threshold: '12' });
    await waitFor(() =>
      expect(
        toastMock.addToast.mock.calls.some((call) => String(call[0]) === 'Alert rule updated'),
      ).toBe(true),
    );
  });

  it('Cancel in edit form discards changes and does not mutate alert state', async () => {
    renderPage();
    await screen.findByRole('heading', { name: 'High CPC Alert' });

    const user = userEvent.setup();
    await user.click(screen.getByRole('button', { name: 'Edit' }));

    const nameInput = screen.getByLabelText('Name') as HTMLInputElement;
    await user.clear(nameInput);
    await user.type(nameInput, 'Renamed Alert');

    await user.click(screen.getByRole('button', { name: 'Cancel' }));

    // Form fields are gone and the original heading is intact.
    expect(screen.queryByLabelText('Name')).not.toBeInTheDocument();
    expect(screen.getByRole('heading', { name: 'High CPC Alert' })).toBeInTheDocument();
    expect(phase2ApiMock.updateAlert).not.toHaveBeenCalled();
  });

  it('Save error keeps the edit form open and fires error toast', async () => {
    phase2ApiMock.updateAlert.mockRejectedValue(new Error('nope'));

    renderPage();
    await screen.findByRole('heading', { name: 'High CPC Alert' });

    const user = userEvent.setup();
    await user.click(screen.getByRole('button', { name: 'Edit' }));

    const thresholdInput = screen.getByLabelText('Threshold');
    await user.clear(thresholdInput);
    await user.type(thresholdInput, '9.99');

    await user.click(screen.getByRole('button', { name: 'Save' }));

    await waitFor(() => expect(phase2ApiMock.updateAlert).toHaveBeenCalled());
    await waitFor(() =>
      expect(
        toastMock.addToast.mock.calls.some(
          (call) => call[1] === 'error' && /failed/i.test(String(call[0])),
        ),
      ).toBe(true),
    );
    // Form should still be visible.
    expect(screen.getByLabelText('Threshold')).toBeInTheDocument();
    expect(screen.getByLabelText('Name')).toBeInTheDocument();
  });
});
