import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { MemoryRouter } from 'react-router-dom';

const clientsMock = vi.hoisted(() => ({
  getClientSuggestionSnapshot: vi.fn(),
  acknowledgeClientSuggestionSnapshot: vi.fn(),
}));

vi.mock('../../lib/clients', async () => {
  const actual = await vi.importActual<typeof import('../../lib/clients')>('../../lib/clients');
  return {
    ...actual,
    getClientSuggestionSnapshot: clientsMock.getClientSuggestionSnapshot,
    acknowledgeClientSuggestionSnapshot: clientsMock.acknowledgeClientSuggestionSnapshot,
  };
});

import ClientSuggestionBanner from '../ClientSuggestionBanner';

const renderWithRouter = (ui: React.ReactElement) => render(<MemoryRouter>{ui}</MemoryRouter>);

describe('ClientSuggestionBanner', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('renders nothing when disabled', async () => {
    const { container } = renderWithRouter(<ClientSuggestionBanner enabled={false} />);
    expect(container.firstChild).toBeNull();
    expect(clientsMock.getClientSuggestionSnapshot).not.toHaveBeenCalled();
  });

  it('renders nothing when snapshot is null', async () => {
    clientsMock.getClientSuggestionSnapshot.mockResolvedValue({
      snapshot: null,
    });
    const { container } = renderWithRouter(<ClientSuggestionBanner enabled />);
    await waitFor(() => {
      expect(clientsMock.getClientSuggestionSnapshot).toHaveBeenCalled();
    });
    expect(container.firstChild).toBeNull();
  });

  it('renders unacknowledged suggestions with a review link', async () => {
    clientsMock.getClientSuggestionSnapshot.mockResolvedValue({
      snapshot: {
        id: 'snap-1',
        trigger_reason: 'meta_sync',
        threshold: 0.7,
        suggestion_count: 3,
        payload: [],
        generated_at: '2026-04-13T01:00:00Z',
        acknowledged_at: null,
        is_unacknowledged: true,
      },
    });
    renderWithRouter(<ClientSuggestionBanner enabled />);

    expect(await screen.findByText(/3 new client suggestions/i)).toBeInTheDocument();
    expect(screen.getByRole('link', { name: /review suggestions/i })).toHaveAttribute(
      'href',
      '/clients/suggest',
    );
    expect(screen.getByText(/after your meta sync/i)).toBeInTheDocument();
  });

  it('uses singular copy for exactly one suggestion', async () => {
    clientsMock.getClientSuggestionSnapshot.mockResolvedValue({
      snapshot: {
        id: 'snap-1',
        trigger_reason: 'manual',
        threshold: 0.7,
        suggestion_count: 1,
        payload: [],
        generated_at: '2026-04-13T01:00:00Z',
        acknowledged_at: null,
        is_unacknowledged: true,
      },
    });
    renderWithRouter(<ClientSuggestionBanner enabled />);
    expect(await screen.findByText(/1 new client suggestion\b/i)).toBeInTheDocument();
  });

  it('hides itself after dismiss and calls acknowledge', async () => {
    clientsMock.getClientSuggestionSnapshot.mockResolvedValue({
      snapshot: {
        id: 'snap-1',
        trigger_reason: 'google_sync',
        threshold: 0.7,
        suggestion_count: 2,
        payload: [],
        generated_at: '2026-04-13T01:00:00Z',
        acknowledged_at: null,
        is_unacknowledged: true,
      },
    });
    clientsMock.acknowledgeClientSuggestionSnapshot.mockResolvedValue({
      snapshot: { id: 'snap-1', is_unacknowledged: false },
    });

    renderWithRouter(<ClientSuggestionBanner enabled />);

    const dismissButton = await screen.findByRole('button', {
      name: /dismiss/i,
    });
    fireEvent.click(dismissButton);

    await waitFor(() => {
      expect(clientsMock.acknowledgeClientSuggestionSnapshot).toHaveBeenCalled();
    });
    await waitFor(() => {
      expect(screen.queryByText(/new client suggestion/i)).not.toBeInTheDocument();
    });
  });

  it('hides when snapshot is already acknowledged', async () => {
    clientsMock.getClientSuggestionSnapshot.mockResolvedValue({
      snapshot: {
        id: 'snap-1',
        trigger_reason: 'manual',
        threshold: 0.7,
        suggestion_count: 5,
        payload: [],
        generated_at: '2026-04-13T01:00:00Z',
        acknowledged_at: '2026-04-13T02:00:00Z',
        is_unacknowledged: false,
      },
    });
    const { container } = renderWithRouter(<ClientSuggestionBanner enabled />);
    await waitFor(() => {
      expect(clientsMock.getClientSuggestionSnapshot).toHaveBeenCalled();
    });
    expect(container.firstChild).toBeNull();
  });
});
