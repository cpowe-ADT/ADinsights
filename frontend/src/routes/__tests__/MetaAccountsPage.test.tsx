import { render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { beforeEach, describe, expect, it, vi } from 'vitest';

const storeMock = vi.hoisted(() => ({
  state: {
    accounts: {
      status: 'loaded' as const,
      rows: [
        {
          id: 'acct-1',
          name: 'Primary Account',
          external_id: 'act_123',
          account_id: '123',
          currency: 'USD',
          status: '1',
          business_name: 'Demo Biz',
        },
      ],
      count: 1,
      error: '',
      errorCode: '',
    },
    filters: {
      search: '',
      status: '',
      since: '',
      until: '',
    },
    setFilters: vi.fn(),
    loadAccounts: vi.fn().mockResolvedValue(undefined),
  },
}));

const airbyteMocks = vi.hoisted(() => ({
  loadSocialConnectionStatus: vi.fn(),
  previewMetaRecovery: vi.fn(),
}));

import MetaAccountsPage from '../MetaAccountsPage';

vi.mock('../../state/useMetaStore', () => ({
  default: (selector: (state: typeof storeMock.state) => unknown) => selector(storeMock.state),
}));

vi.mock('../../lib/airbyte', () => ({
  loadSocialConnectionStatus: airbyteMocks.loadSocialConnectionStatus,
  previewMetaRecovery: airbyteMocks.previewMetaRecovery,
}));

describe('MetaAccountsPage', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    airbyteMocks.loadSocialConnectionStatus.mockResolvedValue({
      generated_at: '2026-04-04T15:00:00Z',
      platforms: [],
    });
  });

  it('explains that Meta accounts and Facebook pages are separate assets', async () => {
    render(
      <MemoryRouter>
        <MetaAccountsPage />
      </MemoryRouter>,
    );

    expect(
      await screen.findByText(/Meta ad accounts and Facebook Pages are separate assets\./i),
    ).toBeInTheDocument();
    expect(screen.getByRole('link', { name: 'Facebook pages' })).toHaveAttribute(
      'href',
      '/dashboards/meta/pages',
    );
  });
});
