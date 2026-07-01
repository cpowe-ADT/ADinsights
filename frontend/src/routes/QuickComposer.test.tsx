import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter } from 'react-router-dom';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

vi.mock('../lib/contentOps', async (importActual) => {
  const actual = await importActual<typeof import('../lib/contentOps')>();
  return {
    ...actual,
    listContentOpsWorkspaces: vi.fn(),
    fetchContentOpsPublishingReadiness: vi.fn(),
    createContentOpsDraftWithVersion: vi.fn(),
    publishContentOpsDraftNow: vi.fn(),
  };
});

import {
  createContentOpsDraftWithVersion,
  fetchContentOpsPublishingReadiness,
  listContentOpsWorkspaces,
  publishContentOpsDraftNow,
} from '../lib/contentOps';

import QuickComposer from './QuickComposer';

const listWorkspacesMock = vi.mocked(listContentOpsWorkspaces);
const readinessMock = vi.mocked(fetchContentOpsPublishingReadiness);
const createDraftMock = vi.mocked(createContentOpsDraftWithVersion);
const publishNowMock = vi.mocked(publishContentOpsDraftNow);

function renderComposer() {
  return render(
    <MemoryRouter>
      <QuickComposer />
    </MemoryRouter>,
  );
}

beforeEach(() => {
  listWorkspacesMock.mockResolvedValue([
    { id: 'ws1', name: 'Demo workspace', timezone: 'America/Jamaica' },
  ]);
  readinessMock.mockResolvedValue([
    { channel: 'facebook_page', label: 'Facebook Page', ready: true, reason: null },
    {
      channel: 'instagram',
      label: 'Instagram',
      ready: false,
      reason: 'missing_publishing_permissions',
    },
  ]);
  createDraftMock.mockResolvedValue({ id: 'draft-1' } as never);
  publishNowMock.mockResolvedValue({
    schedule: { id: 's1' } as never,
    attempts: [
      {
        id: 'a1',
        schedule: 's1',
        draft: 'draft-1',
        version: 'v1',
        channel: 'facebook_page',
        state: 'queued',
      },
    ],
    dispatch: { scanned: 1, attempts_created: 1, attempts_existing: 0, attempts_blocked: 0 },
    approval_mode: 'bypass',
  });
});

afterEach(() => vi.clearAllMocks());

describe('QuickComposer', () => {
  it('surfaces per-channel readiness after loading', async () => {
    renderComposer();

    expect(await screen.findByText('Ready')).toBeInTheDocument();
    expect(screen.getByText('Not live yet')).toBeInTheDocument();
    expect(
      screen.getByText(/awaiting publishing permissions/i),
    ).toBeInTheDocument();
  });

  it('creates a draft and publishes to the selected destination', async () => {
    const user = userEvent.setup();
    renderComposer();

    const captionField = await screen.findByPlaceholderText('What do you want to share?');
    await user.type(captionField, 'Hello Jamaica');
    await user.click(screen.getByRole('button', { name: /post now/i }));

    await waitFor(() => expect(publishNowMock).toHaveBeenCalledTimes(1));
    expect(createDraftMock).toHaveBeenCalledWith(
      expect.objectContaining({
        workspaceId: 'ws1',
        channel: 'facebook_page',
        caption: 'Hello Jamaica',
        briefId: null,
      }),
    );
    expect(publishNowMock).toHaveBeenCalledWith({
      draftId: 'draft-1',
      channels: [{ type: 'facebook_page' }],
    });
    expect(await screen.findByText('Publish status')).toBeInTheDocument();
    expect(screen.getByText('Queued')).toBeInTheDocument();
  });

  it('blocks submit until a caption is entered', async () => {
    renderComposer();
    await screen.findByPlaceholderText('What do you want to share?');

    expect(screen.getByRole('button', { name: /post now/i })).toBeDisabled();
  });
});
