import { render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import MetaCampaignOverviewPage from '../MetaCampaignOverviewPage';

const metaStoreMock = vi.hoisted(() => ({
  filters: { accountId: '', search: '', status: '', since: '', until: '' },
  setFilters: vi.fn(),
  accounts: { rows: [] as Array<{ id: string; external_id: string; name: string }> },
  campaigns: {
    status: 'loaded' as string,
    count: 0,
    rows: [] as Array<{
      id: string;
      name: string;
      external_id: string;
      status: string;
      objective: string;
      account_external_id: string;
      updated_time: string;
      updated_at: string;
    }>,
    error: undefined as string | undefined,
    errorCode: undefined as string | undefined,
  },
  loadAccounts: vi.fn(),
  loadCampaigns: vi.fn(),
}));

vi.mock('../../state/useMetaStore', () => {
  const fn = (selector?: (s: typeof metaStoreMock) => unknown) =>
    selector ? selector(metaStoreMock) : metaStoreMock;
  fn.getState = () => metaStoreMock;
  fn.subscribe = () => () => {};
  return { __esModule: true, default: fn };
});

vi.mock('../../components/EmptyState', () => ({
  __esModule: true,
  default: ({ title, message }: { title: string; message: string }) => (
    <div><h3>{title}</h3><p>{message}</p></div>
  ),
}));

describe('MetaCampaignOverviewPage', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    metaStoreMock.campaigns = { status: 'loaded', count: 0, rows: [], error: undefined, errorCode: undefined };
  });

  it('renders campaign overview heading', () => {
    render(
      <MemoryRouter>
        <MetaCampaignOverviewPage />
      </MemoryRouter>,
    );

    expect(screen.getByRole('heading', { name: 'Campaign overview' })).toBeInTheDocument();
  });

  it('shows no campaigns found when rows are empty', () => {
    render(
      <MemoryRouter>
        <MetaCampaignOverviewPage />
      </MemoryRouter>,
    );

    expect(screen.getByText('No campaigns found')).toBeInTheDocument();
  });

  it('shows error state when campaigns fail to load', () => {
    metaStoreMock.campaigns = {
      status: 'error',
      count: 0,
      rows: [],
      error: 'Network error',
      errorCode: undefined,
    };

    render(
      <MemoryRouter>
        <MetaCampaignOverviewPage />
      </MemoryRouter>,
    );

    expect(screen.getByText('Unable to load campaigns')).toBeInTheDocument();
  });
});
