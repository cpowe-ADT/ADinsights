import '@testing-library/jest-dom';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import DashboardLibrary from '../DashboardLibrary';

const apiMocks = vi.hoisted(() => ({
  fetchDashboardLibrary: vi.fn(),
  updateDashboardDefinition: vi.fn(),
  duplicateDashboardDefinition: vi.fn(),
  deleteDashboardDefinition: vi.fn(),
}));

vi.mock('../../auth/AuthContext', () => ({
  useAuth: () => ({
    user: { email: 'admin@example.com', roles: ['ADMIN'] },
    tenantId: 'tenant-1',
  }),
}));

vi.mock('../../lib/rbac', () => ({
  canAccessCreatorUi: () => true,
}));

vi.mock('../../lib/dashboardLibrary', () => ({
  fetchDashboardLibrary: apiMocks.fetchDashboardLibrary,
}));

vi.mock('../../lib/phase2Api', async () => {
  const actual = await vi.importActual('../../lib/phase2Api');
  return {
    ...actual,
    updateDashboardDefinition: apiMocks.updateDashboardDefinition,
    duplicateDashboardDefinition: apiMocks.duplicateDashboardDefinition,
    deleteDashboardDefinition: apiMocks.deleteDashboardDefinition,
  };
});

function renderLibrary() {
  return render(
    <MemoryRouter initialEntries={['/dashboards']}>
      <Routes>
        <Route path="/dashboards" element={<DashboardLibrary />} />
        <Route path="/dashboards/create" element={<div>Builder route</div>} />
        <Route path="/dashboards/saved/:dashboardId" element={<div>Saved route</div>} />
      </Routes>
    </MemoryRouter>,
  );
}

describe('DashboardLibrary', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    apiMocks.fetchDashboardLibrary.mockResolvedValue({
      generatedAt: '2026-03-30T12:00:00Z',
      systemTemplates: [
        {
          id: 'meta_campaign_performance',
          kind: 'system_template',
          templateKey: 'meta_campaign_performance',
          name: 'Meta campaign performance',
          type: 'Campaigns',
          owner: 'System',
          updatedAt: '2026-03-30',
          tags: ['Meta Ads', 'ROAS'],
          description: 'Campaign template',
          route: '/dashboards/create?template=meta_campaign_performance',
        },
      ],
      savedDashboards: [
        {
          id: 'dash-1',
          kind: 'saved_dashboard',
          templateKey: 'meta_creative_insights',
          name: 'JDIC creative review',
          type: 'Meta creative insights',
          owner: 'admin@example.com',
          updatedAt: '2026-03-30',
          tags: ['CTR', 'Meta Ads'],
          description: 'Saved creative dashboard',
          route: '/dashboards/saved/dash-1',
          defaultMetric: 'ctr',
          isActive: true,
        },
      ],
    });
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it('calls fetchDashboardLibrary API on mount', async () => {
    renderLibrary();

    await waitFor(() => {
      expect(apiMocks.fetchDashboardLibrary).toHaveBeenCalledTimes(1);
    });
  });

  it('renders split system-template and saved-dashboard sections', async () => {
    renderLibrary();

    expect(await screen.findByRole('heading', { name: 'System templates' })).toBeInTheDocument();
    expect(screen.getByRole('heading', { name: 'Saved dashboards' })).toBeInTheDocument();
    expect(screen.getByText('Meta campaign performance')).toBeInTheDocument();
    expect(screen.getByText('JDIC creative review')).toBeInTheDocument();
    expect(screen.getByRole('link', { name: 'Use template' })).toHaveAttribute(
      'href',
      '/dashboards/create?template=meta_campaign_performance',
    );
  });

  it('renames, duplicates, archives, and deletes saved dashboards', async () => {
    const promptSpy = vi.spyOn(window, 'prompt').mockReturnValue('JDIC renamed');
    const confirmSpy = vi.spyOn(window, 'confirm').mockReturnValue(true);
    apiMocks.updateDashboardDefinition
      .mockResolvedValueOnce({
        id: 'dash-1',
        name: 'JDIC renamed',
        description: 'Saved creative dashboard',
        template_key: 'meta_creative_insights',
        filters: { accountId: 'act_697812007883214' },
        layout: { widgets: ['creative_table'] },
        default_metric: 'ctr',
        is_active: true,
        owner_email: 'admin@example.com',
        created_at: '2026-03-30T12:00:00Z',
        updated_at: '2026-03-30T12:05:00Z',
      })
      .mockResolvedValueOnce({
        id: 'dash-1',
        name: 'JDIC renamed',
        description: 'Saved creative dashboard',
        template_key: 'meta_creative_insights',
        filters: { accountId: 'act_697812007883214' },
        layout: { widgets: ['creative_table'] },
        default_metric: 'ctr',
        is_active: false,
        owner_email: 'admin@example.com',
        created_at: '2026-03-30T12:00:00Z',
        updated_at: '2026-03-30T12:10:00Z',
      });
    apiMocks.duplicateDashboardDefinition.mockResolvedValue({
      id: 'dash-2',
      name: 'JDIC renamed Copy',
      description: 'Saved creative dashboard',
      template_key: 'meta_creative_insights',
      filters: { accountId: 'act_697812007883214' },
      layout: { widgets: ['creative_table'] },
      default_metric: 'ctr',
      is_active: true,
      owner_email: 'admin@example.com',
      created_at: '2026-03-30T12:00:00Z',
      updated_at: '2026-03-30T12:06:00Z',
    });
    apiMocks.deleteDashboardDefinition.mockResolvedValue(undefined);

    renderLibrary();

    const user = userEvent.setup();

    await user.click(await screen.findByRole('button', { name: 'Rename' }));
    await waitFor(() =>
      expect(apiMocks.updateDashboardDefinition).toHaveBeenCalledWith('dash-1', {
        name: 'JDIC renamed',
      }),
    );
    expect(await screen.findByText('JDIC renamed')).toBeInTheDocument();

    await user.click(screen.getByRole('button', { name: 'Duplicate' }));
    await waitFor(() =>
      expect(apiMocks.duplicateDashboardDefinition).toHaveBeenCalledWith('dash-1'),
    );
    expect(await screen.findByText('JDIC renamed Copy')).toBeInTheDocument();

    await user.click(screen.getAllByRole('button', { name: 'Archive' })[0]);
    await waitFor(() =>
      expect(apiMocks.updateDashboardDefinition).toHaveBeenCalledWith('dash-1', {
        name: 'JDIC renamed',
      }),
    );
    await waitFor(() =>
      expect(apiMocks.updateDashboardDefinition).toHaveBeenCalledWith('dash-2', {
        is_active: false,
      }),
    );
    expect(screen.queryByText('JDIC renamed Copy')).not.toBeInTheDocument();

    await user.click(screen.getByRole('button', { name: 'Delete' }));
    await waitFor(() =>
      expect(apiMocks.deleteDashboardDefinition).toHaveBeenCalledWith('dash-1'),
    );
    expect(screen.queryByText('JDIC renamed')).not.toBeInTheDocument();

    expect(promptSpy).toHaveBeenCalled();
    expect(confirmSpy).toHaveBeenCalledTimes(2);
  });
});
