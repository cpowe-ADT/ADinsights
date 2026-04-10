import { render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import MetaIntegrationPage from '../MetaIntegrationPage';

const pageInsightsStoreMock = vi.hoisted(() => ({
  pagesStatus: 'loaded' as string,
  oauthStatus: 'idle' as string,
  pages: [] as Array<{ id: string; page_id: string; name: string; can_analyze: boolean; is_default: boolean }>,
  error: null as string | null,
  missingRequiredPermissions: [] as string[],
  selectedPageId: null as string | null,
  connectOAuthStart: vi.fn(),
  connectOAuthCallback: vi.fn(),
  loadPages: vi.fn(),
  selectDefaultPage: vi.fn(),
}));

vi.mock('../../state/useMetaPageInsightsStore', () => {
  const fn = (selector?: (s: typeof pageInsightsStoreMock) => unknown) =>
    selector ? selector(pageInsightsStoreMock) : pageInsightsStoreMock;
  fn.getState = () => pageInsightsStoreMock;
  fn.subscribe = () => () => {};
  return { __esModule: true, default: fn };
});

vi.mock('../../lib/airbyte', () => ({
  loadSocialConnectionStatus: vi.fn().mockResolvedValue({ platforms: [] }),
}));

vi.mock('../../components/EmptyState', () => ({
  __esModule: true,
  default: ({ title, message }: { title: string; message: string }) => (
    <div><h3>{title}</h3><p>{message}</p></div>
  ),
}));

describe('MetaIntegrationPage', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    pageInsightsStoreMock.pages = [];
    pageInsightsStoreMock.pagesStatus = 'loaded';
    pageInsightsStoreMock.error = null;
    pageInsightsStoreMock.missingRequiredPermissions = [];
  });

  it('renders Meta heading', () => {
    render(
      <MemoryRouter>
        <MetaIntegrationPage />
      </MemoryRouter>,
    );

    expect(screen.getByRole('heading', { name: 'Meta' })).toBeInTheDocument();
  });

  it('shows no pages found when pages list is empty', () => {
    render(
      <MemoryRouter>
        <MetaIntegrationPage />
      </MemoryRouter>,
    );

    expect(screen.getByText('No pages found')).toBeInTheDocument();
  });

  it('shows connect button', () => {
    render(
      <MemoryRouter>
        <MetaIntegrationPage />
      </MemoryRouter>,
    );

    expect(screen.getByRole('button', { name: 'Connect for Page Insights' })).toBeInTheDocument();
  });
});
