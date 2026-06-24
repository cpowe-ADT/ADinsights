import { render, screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter } from 'react-router-dom';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import RegionalAgentsPage from '../RegionalAgentsPage';

const addToast = vi.fn();

const contentOpsMocks = vi.hoisted(() => ({
  listContentOpsWorkspaces: vi.fn(),
  listContentOpsRegionalAgents: vi.fn(),
  createContentOpsRegionalAgent: vi.fn(),
  requestContentOpsImageGeneration: vi.fn(),
}));

vi.mock('../../stores/useToastStore', () => ({
  useToastStore: (selector: (state: { addToast: typeof addToast }) => unknown) =>
    selector({ addToast }),
}));

vi.mock('../../lib/contentOps', () => ({
  listContentOpsWorkspaces: contentOpsMocks.listContentOpsWorkspaces,
  listContentOpsRegionalAgents: contentOpsMocks.listContentOpsRegionalAgents,
  createContentOpsRegionalAgent: contentOpsMocks.createContentOpsRegionalAgent,
  requestContentOpsImageGeneration: contentOpsMocks.requestContentOpsImageGeneration,
}));

const workspace = { id: 'ws-1', name: 'Acme Caribbean', timezone: 'America/Jamaica' };
const peruAgent = {
  id: 'agent-1',
  workspaceId: 'ws-1',
  name: 'Peru agent',
  region: 'peru_latam' as const,
  locale: 'es-PE',
  language: 'Spanish',
  timezone: 'America/Lima',
  isActive: true,
};

const renderPage = () =>
  render(
    <MemoryRouter>
      <RegionalAgentsPage />
    </MemoryRouter>,
  );

describe('RegionalAgentsPage', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    contentOpsMocks.listContentOpsWorkspaces.mockResolvedValue([workspace]);
    contentOpsMocks.listContentOpsRegionalAgents.mockResolvedValue([peruAgent]);
    contentOpsMocks.createContentOpsRegionalAgent.mockResolvedValue({
      id: 'agent-2',
      workspaceId: 'ws-1',
      name: 'Caribbean agent',
      region: 'caribbean',
      locale: 'en-JM',
      language: 'English',
      timezone: 'America/Jamaica',
      isActive: true,
    });
    contentOpsMocks.requestContentOpsImageGeneration.mockResolvedValue({ id: 'job-1' });
  });

  it('loads workspaces and lists regional agents', async () => {
    renderPage();

    const table = await screen.findByRole('table', { name: 'Regional agents' });
    expect(within(table).getByText('Peru agent')).toBeInTheDocument();
    expect(within(table).getByText('es-PE')).toBeInTheDocument();
    expect(contentOpsMocks.listContentOpsRegionalAgents).toHaveBeenCalledWith('ws-1');
  });

  it('creates a regional agent with the chosen region', async () => {
    const user = userEvent.setup();
    renderPage();
    await screen.findByRole('table', { name: 'Regional agents' });

    await user.type(screen.getByLabelText('Name'), 'Caribbean agent');
    await user.click(screen.getByRole('button', { name: 'Create agent' }));

    await waitFor(() => {
      expect(contentOpsMocks.createContentOpsRegionalAgent).toHaveBeenCalledWith({
        workspaceId: 'ws-1',
        name: 'Caribbean agent',
        region: 'caribbean',
      });
    });
    expect(addToast).toHaveBeenCalledWith(expect.stringContaining('Created'), 'success');
  });

  it('queues an image generation job', async () => {
    const user = userEvent.setup();
    renderPage();
    await screen.findByRole('table', { name: 'Regional agents' });

    await user.type(screen.getByLabelText('Prompt'), 'Sunset over Kingston');
    await user.click(screen.getByRole('button', { name: 'Queue image job' }));

    await waitFor(() => {
      expect(contentOpsMocks.requestContentOpsImageGeneration).toHaveBeenCalledWith(
        expect.objectContaining({
          workspaceId: 'ws-1',
          prompt: 'Sunset over Kingston',
          count: 1,
        }),
      );
    });
    expect(addToast).toHaveBeenCalledWith(expect.stringContaining('Image job queued'), 'success');
  });
});
