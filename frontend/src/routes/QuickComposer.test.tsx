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
    createContentOpsDraft: vi.fn(),
    createContentOpsDraftWithVersion: vi.fn(),
    createContentOpsVersionWithAsset: vi.fn(),
    uploadContentOpsAsset: vi.fn(),
    publishContentOpsDraftNow: vi.fn(),
  };
});

import {
  createContentOpsDraft,
  createContentOpsDraftWithVersion,
  createContentOpsVersionWithAsset,
  fetchContentOpsPublishingReadiness,
  listContentOpsWorkspaces,
  publishContentOpsDraftNow,
  uploadContentOpsAsset,
} from '../lib/contentOps';

import QuickComposer from './QuickComposer';

const listWorkspacesMock = vi.mocked(listContentOpsWorkspaces);
const readinessMock = vi.mocked(fetchContentOpsPublishingReadiness);
const createDraftMock = vi.mocked(createContentOpsDraft);
const createDraftWithVersionMock = vi.mocked(createContentOpsDraftWithVersion);
const versionWithAssetMock = vi.mocked(createContentOpsVersionWithAsset);
const uploadAssetMock = vi.mocked(uploadContentOpsAsset);
const publishNowMock = vi.mocked(publishContentOpsDraftNow);

Object.defineProperty(window.URL, 'createObjectURL', {
  writable: true,
  value: vi.fn(() => 'blob:preview'),
});
Object.defineProperty(window.URL, 'revokeObjectURL', {
  writable: true,
  value: vi.fn(),
});

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
  createDraftMock.mockResolvedValue({ id: 'draft-1' });
  createDraftWithVersionMock.mockResolvedValue({ id: 'draft-1' } as never);
  versionWithAssetMock.mockResolvedValue({ id: 'v1', draft: 'draft-1' } as never);
  uploadAssetMock.mockResolvedValue({ id: 'asset-1' } as never);
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
    expect(screen.getByText(/awaiting publishing permissions/i)).toBeInTheDocument();
  });

  it('publishes a text post via the create-draft-with-version path', async () => {
    const user = userEvent.setup();
    renderComposer();

    const captionField = await screen.findByPlaceholderText('What do you want to share?');
    await user.type(captionField, 'Hello Jamaica');
    await user.click(screen.getByRole('button', { name: /post now/i }));

    await waitFor(() => expect(publishNowMock).toHaveBeenCalledTimes(1));
    expect(createDraftWithVersionMock).toHaveBeenCalledWith(
      expect.objectContaining({
        workspaceId: 'ws1',
        channel: 'facebook_page',
        caption: 'Hello Jamaica',
        briefId: null,
      }),
    );
    expect(uploadAssetMock).not.toHaveBeenCalled();
    expect(publishNowMock).toHaveBeenCalledWith({
      draftId: 'draft-1',
      channels: [{ type: 'facebook_page' }],
    });
    expect(await screen.findByText('Publish status')).toBeInTheDocument();
  });

  it('uploads an image and attaches it before publishing', async () => {
    const user = userEvent.setup();
    renderComposer();

    const captionField = await screen.findByPlaceholderText('What do you want to share?');
    await user.type(captionField, 'Photo post');
    const file = new File(['bytes'], 'photo.png', { type: 'image/png' });
    await user.upload(screen.getByLabelText(/attach an image/i), file);
    await user.click(screen.getByRole('button', { name: /post now/i }));

    await waitFor(() => expect(publishNowMock).toHaveBeenCalledTimes(1));
    expect(createDraftMock).toHaveBeenCalledWith(expect.objectContaining({ workspaceId: 'ws1' }));
    expect(uploadAssetMock).toHaveBeenCalledWith(
      expect.objectContaining({ workspaceId: 'ws1', file }),
    );
    expect(versionWithAssetMock).toHaveBeenCalledWith(
      expect.objectContaining({
        draftId: 'draft-1',
        assetId: 'asset-1',
        channel: 'facebook_page',
        caption: 'Photo post',
      }),
    );
    expect(createDraftWithVersionMock).not.toHaveBeenCalled();
  });

  it('requires an image when Instagram is selected', async () => {
    const user = userEvent.setup();
    renderComposer();

    const captionField = await screen.findByPlaceholderText('What do you want to share?');
    await user.type(captionField, 'IG post');
    await user.click(screen.getByRole('checkbox', { name: /instagram/i }));

    expect(screen.getByText(/Instagram posts require an image/i)).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /post now/i })).toBeDisabled();
  });

  it('blocks submit until a caption is entered', async () => {
    renderComposer();
    await screen.findByPlaceholderText('What do you want to share?');

    expect(screen.getByRole('button', { name: /post now/i })).toBeDisabled();
  });
});
