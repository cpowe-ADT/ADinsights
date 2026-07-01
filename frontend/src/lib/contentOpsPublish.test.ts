import { afterEach, describe, expect, it, vi } from 'vitest';

import apiClient from './apiClient';
import {
  fetchContentOpsPublishingReadiness,
  publishContentOpsDraftNow,
} from './contentOps';

describe('publishContentOpsDraftNow', () => {
  afterEach(() => vi.restoreAllMocks());

  it('posts to the publish-now endpoint with the selected channels', async () => {
    const response = {
      schedule: { id: 's1', draft: 'draft-1' },
      attempts: [{ id: 'a1', channel: 'facebook_page', state: 'queued' }],
      dispatch: { scanned: 1, attempts_created: 1, attempts_existing: 0, attempts_blocked: 0 },
      approval_mode: 'bypass',
    };
    const post = vi.spyOn(apiClient, 'post').mockResolvedValue(response as never);

    const result = await publishContentOpsDraftNow({
      draftId: 'draft-1',
      channels: [{ type: 'facebook_page' }, { type: 'instagram' }],
    });

    expect(post).toHaveBeenCalledWith('/content-ops/drafts/draft-1/publish-now/', {
      channels: [{ type: 'facebook_page' }, { type: 'instagram' }],
    });
    expect(result.approval_mode).toBe('bypass');
    expect(result.attempts).toHaveLength(1);
  });

  it('sends an empty body when no channels are supplied', async () => {
    const post = vi.spyOn(apiClient, 'post').mockResolvedValue({} as never);

    await publishContentOpsDraftNow({ draftId: 'draft-2' });

    expect(post).toHaveBeenCalledWith('/content-ops/drafts/draft-2/publish-now/', {});
  });
});

describe('fetchContentOpsPublishingReadiness', () => {
  afterEach(() => vi.restoreAllMocks());

  it('maps the facebook and instagram publishing axes', async () => {
    vi.spyOn(apiClient, 'get').mockResolvedValue({
      facebook_page_publishing: { state: 'ready', reason: null },
      instagram_publishing: { state: 'blocked', reason: 'missing_publishing_permissions' },
    } as never);

    const readiness = await fetchContentOpsPublishingReadiness();

    expect(readiness).toEqual([
      { channel: 'facebook_page', label: expect.any(String), ready: true, reason: null },
      {
        channel: 'instagram',
        label: expect.any(String),
        ready: false,
        reason: 'missing_publishing_permissions',
      },
    ]);
  });

  it('treats a missing axis as not ready', async () => {
    vi.spyOn(apiClient, 'get').mockResolvedValue({} as never);

    const readiness = await fetchContentOpsPublishingReadiness();

    expect(readiness.every((axis) => axis.ready === false)).toBe(true);
    expect(readiness.map((axis) => axis.channel)).toEqual(['facebook_page', 'instagram']);
  });
});
