import { beforeEach, describe, expect, it, vi } from 'vitest';

import {
  buildContentOpsExportFilename,
  cancelContentOpsGenerationJob,
  createContentOpsExportArtifact,
  createContentOpsBrief,
  createContentOpsDraftWithVersion,
  createContentOpsVersionWithAsset,
  decideContentOpsApproval,
  downloadContentOpsExportArtifact,
  exportContentOpsPlan,
  fetchContentOpsReportOverview,
  fetchContentOpsReportPosts,
  fetchContentOpsWorkspace,
  listContentOpsExportArtifacts,
  listContentOpsAssets,
  requestContentOpsCaptionGeneration,
  retryContentOpsPublishAttempt,
  scheduleContentOpsDraft,
  submitContentOpsClientReview,
  submitContentOpsInternalReview,
  uploadContentOpsAsset,
} from './contentOps';

const apiClientMock = vi.hoisted(() => ({
  download: vi.fn(),
  get: vi.fn(),
  post: vi.fn(),
}));

vi.mock('./apiClient', () => ({
  default: apiClientMock,
  appendQueryParams: (path: string, params: Record<string, string>) => {
    const search = new URLSearchParams(params).toString();
    return search ? `${path}?${search}` : path;
  },
}));

describe('fetchContentOpsWorkspace', () => {
  beforeEach(() => {
    apiClientMock.get.mockReset();
    apiClientMock.post.mockReset();
    apiClientMock.download.mockReset();
  });

  it('maps backend Content Ops payloads into the workspace view model', async () => {
    apiClientMock.get.mockImplementation(async (path: string) => {
      if (path === '/content-ops/readiness/') {
        return {
          meta_auth: {
            state: 'connected',
            reason: null,
            usable_credential_count: 1,
            active_page_connection_count: 2,
          },
          page_selection: {
            state: 'complete',
            reason: null,
            selected_page_count: 1,
            page_count: 3,
            default_page_id: 'page-1',
          },
          instagram_linkage: { state: 'blocked', reason: 'instagram_not_linked' },
          facebook_page_publishing: { state: 'ready', reason: null },
          instagram_publishing: {
            state: 'blocked',
            reason: 'missing_permissions',
            identity_count: 1,
            missing_permissions: ['instagram_content_publish'],
            required_permissions: ['instagram_basic', 'instagram_content_publish'],
            upstream_blockers: ['instagram_not_linked'],
            identity_blockers: ['unknown'],
          },
          reporting_readiness: { state: 'ready', dataset_live_reason: 'ready' },
        };
      }
      if (path === '/content-ops/workspaces/') {
        return { results: [{ id: 'workspace-1', name: 'Live Workspace', timezone: 'America/Jamaica' }] };
      }
      if (path === '/content-ops/briefs/?workspace_id=workspace-1') {
        return {
          results: [
            {
              id: 'brief-1',
              campaign_theme: 'Live brief',
              audience: 'Owners',
              offer: 'Launch offer',
              tone: 'Practical',
              required_terms: ['Terms apply'],
              blocked_terms: ['guaranteed'],
              date_start: '2026-06-10',
              date_end: '2026-06-20',
            },
          ],
        };
      }
      if (path === '/content-ops/generation-jobs/?workspace_id=workspace-1') {
        return {
          results: [
            {
              id: 'job-1',
              job_type: 'caption',
              status: 'succeeded',
              provider: 'disabled',
              prompt_policy_result: { candidate_count: 3 },
              result_summary: {
                candidates: [
                  {
                    id: 'candidate-1',
                    title: 'Live brief - Instagram option',
                    platform: 'instagram',
                    caption: 'Generated Instagram caption. Terms apply.',
                    hashtags: ['Launch'],
                    cta: 'Plan your visit',
                    alt_text: 'Product bundle arranged for a social post.',
                    risk_flags: [],
                    quality_score: 0.91,
                  },
                ],
              },
            },
          ],
        };
      }
      if (path === '/content-ops/drafts/?workspace_id=workspace-1') {
        return {
          results: [
            {
              id: 'draft-1',
              title: 'Live draft',
              state: 'publishing',
              active_version: 'version-1',
              approval_summary: {
                internal: {
                  id: 'approval-internal',
                  status: 'approved',
                  version_id: 'version-1',
                },
                client: {
                  id: 'approval-client',
                  status: 'pending',
                  version_id: 'version-1',
                },
              },
              schedule_summary: { scheduled_at: '2026-06-12T14:00:00Z' },
            },
          ],
        };
      }
      if (path === '/content-ops/publishing/attempts/') {
        return {
          results: [
            {
              id: 'attempt-1',
              draft: 'draft-1',
              schedule: 'schedule-1',
              channel: 'facebook_page',
              state: 'container_pending',
              failure_code: '',
              failure_detail_safe: '',
            },
          ],
        };
      }
      if (path === '/content-ops/schedules/') {
        return {
          results: [{ id: 'schedule-1', draft: 'draft-1', scheduled_at: '2026-06-12T14:00:00Z' }],
        };
      }
      if (path === '/content-ops/drafts/draft-1/versions/') {
        return {
          results: [
            {
              id: 'version-1',
              version_number: 2,
              caption: 'Live caption',
              platform_overrides: { platform: 'facebook_page' },
              media_assets: ['asset-1'],
            },
          ],
        };
      }
      throw new Error(`Unexpected path ${path}`);
    });

    const result = await fetchContentOpsWorkspace();

    expect(result.source).toBe('api');
    expect(result.workspace.id).toBe('workspace-1');
    expect(result.workspace.name).toBe('Live Workspace');
    expect(result.workspace.readiness).toHaveLength(6);
    expect(result.workspace.readiness[0]).toMatchObject({
      id: 'meta_auth',
      state: 'connected',
      details: ['1 usable credential', '2 active Page connections'],
    });
    expect(result.workspace.readiness[1]).toMatchObject({
      id: 'page_selection',
      state: 'complete',
      details: ['1 selected Page', '3 available Pages', 'Default Page page-1'],
    });
    expect(result.workspace.readiness[4]).toMatchObject({
      id: 'instagram_publishing',
      details: [
        '1 selected publishing identity',
        'Missing: instagram_content_publish',
        'Required: instagram_basic, instagram_content_publish',
        'Upstream blockers: instagram_not_linked',
        'Identity blockers: unknown',
      ],
    });
    expect(result.workspace.brief.title).toBe('Live brief');
    expect(result.workspace.generationJobs[0]).toMatchObject({
      id: 'job-1',
      status: 'succeeded',
      candidateCount: 3,
      candidates: [
        {
          id: 'candidate-1',
          title: 'Live brief - Instagram option',
          channel: 'instagram',
          caption: 'Generated Instagram caption. Terms apply.',
          hashtags: ['Launch'],
          cta: 'Plan your visit',
          altText: 'Product bundle arranged for a social post.',
          riskFlags: [],
          qualityScore: 0.91,
        },
      ],
    });
    expect(result.workspace.drafts[0].variants[0]).toMatchObject({
      versionId: 'version-1',
      label: 'Facebook Page',
      caption: 'Live caption',
      mediaAssetIds: ['asset-1'],
      mediaLabel: '1 attached asset',
      approvalStatus: 'client_pending',
    });
    expect(result.workspace.drafts[0].approvalSummary).toMatchObject({
      internal: {
        id: 'approval-internal',
        status: 'approved',
        versionId: 'version-1',
      },
      client: {
        id: 'approval-client',
        status: 'pending',
        versionId: 'version-1',
      },
    });
    expect(result.workspace.drafts[0].state).toBe('publishing');
    expect(result.workspace.queue[0]).toMatchObject({
      draftTitle: 'Live draft',
      state: 'container_pending',
    });
  });

  it('falls back to the mock workspace when no backend workspace exists', async () => {
    apiClientMock.get.mockImplementation(async (path: string) => {
      if (path === '/content-ops/readiness/') {
        return {};
      }
      if (path === '/content-ops/workspaces/') {
        return { results: [] };
      }
      throw new Error(`Unexpected path ${path}`);
    });

    const result = await fetchContentOpsWorkspace();

    expect(result.source).toBe('mock');
    expect(result.warning).toContain('No Content Ops workspaces');
    expect(result.workspace.name).toBe('June Meta content plan');
    expect(result.workspace.id).toBeNull();
  });

  it('uploads assets with multipart form data', async () => {
    apiClientMock.post.mockResolvedValue({
      id: 'asset-1',
      workspace: 'workspace-1',
      source: 'uploaded',
      mime_type: 'image/png',
      alt_text: 'Hero visual',
      status: 'available',
      download_url: '/api/content-ops/assets/asset-1/download/',
      created_at: '2026-06-10T12:00:00Z',
      updated_at: '2026-06-10T12:00:00Z',
    });
    const file = new File(['image-bytes'], 'hero.png', { type: 'image/png' });

    const result = await uploadContentOpsAsset({
      workspaceId: 'workspace-1',
      file,
      altText: 'Hero visual',
    });

    expect(apiClientMock.post).toHaveBeenCalledWith(
      '/content-ops/assets/upload/',
      expect.any(FormData),
      { signal: undefined },
    );
    const formData = apiClientMock.post.mock.calls[0][1] as FormData;
    expect(formData.get('workspace')).toBe('workspace-1');
    expect(formData.get('file')).toBe(file);
    expect(formData.get('alt_text')).toBe('Hero visual');
    expect(result.download_url).toBe('/api/content-ops/assets/asset-1/download/');
  });

  it('lists available workspace assets', async () => {
    apiClientMock.get.mockResolvedValue({
      results: [
        {
          id: 'asset-1',
          workspace: 'workspace-1',
          source: 'uploaded',
          mime_type: 'image/png',
          alt_text: 'Hero visual',
          status: 'available',
          download_url: '/api/content-ops/assets/asset-1/download/',
          created_at: '2026-06-10T12:00:00Z',
          updated_at: '2026-06-10T12:00:00Z',
        },
      ],
    });

    const result = await listContentOpsAssets('workspace-1');

    expect(apiClientMock.get).toHaveBeenCalledWith(
      '/content-ops/assets/?workspace_id=workspace-1&status=available',
      { signal: undefined },
    );
    expect(result[0].id).toBe('asset-1');
  });

  it('creates a new draft version when attaching an asset', async () => {
    apiClientMock.post.mockResolvedValue({
      id: 'version-2',
      draft: 'draft-1',
      version_number: 2,
      caption: 'Caption',
      platform_overrides: { platform: 'instagram' },
      media_assets: ['asset-existing', 'asset-new'],
    });

    const result = await createContentOpsVersionWithAsset({
      draftId: 'draft-1',
      caption: 'Caption',
      channel: 'instagram',
      mediaAssetIds: ['asset-existing'],
      assetId: 'asset-new',
    });

    expect(apiClientMock.post).toHaveBeenCalledWith('/content-ops/drafts/draft-1/versions/', {
      caption: 'Caption',
      platform_overrides: { platform: 'instagram' },
      media_assets: ['asset-existing', 'asset-new'],
      change_note: 'Attached media asset from Content Ops workspace.',
    });
    expect(result.id).toBe('version-2');
  });

  it('creates active content briefs with structured terms', async () => {
    apiClientMock.post.mockResolvedValue({
      id: 'brief-new',
      workspace: 'workspace-1',
      campaign_theme: 'Holiday launch',
      audience: 'Gift buyers',
      offer: 'Bundle savings',
      tone: 'Warm',
      required_terms: ['Terms apply'],
      blocked_terms: ['guaranteed'],
      date_start: '2026-06-10',
      date_end: '2026-06-20',
      status: 'active',
    });

    const result = await createContentOpsBrief({
      workspaceId: 'workspace-1',
      workspaceName: 'Live Workspace',
      campaignTheme: ' Holiday launch ',
      audience: ' Gift buyers ',
      offer: ' Bundle savings ',
      tone: ' Warm ',
      requiredTerms: ['Terms apply'],
      blockedTerms: ['guaranteed'],
      dateStart: '2026-06-10',
      dateEnd: '2026-06-20',
    });

    expect(apiClientMock.post).toHaveBeenCalledWith('/content-ops/briefs/', {
      workspace: 'workspace-1',
      campaign_theme: 'Holiday launch',
      audience: 'Gift buyers',
      offer: 'Bundle savings',
      tone: 'Warm',
      required_terms: ['Terms apply'],
      blocked_terms: ['guaranteed'],
      date_start: '2026-06-10',
      date_end: '2026-06-20',
      status: 'active',
    });
    expect(result).toMatchObject({
      id: 'brief-new',
      title: 'Holiday launch',
      client: 'Live Workspace',
      requiredTerms: ['Terms apply'],
      blockedTerms: ['guaranteed'],
    });
    expect(result.dateRange).toContain('2026');
  });

  it('creates a draft and first active version from manual captions', async () => {
    apiClientMock.post
      .mockResolvedValueOnce({
        id: 'draft-new',
        workspace: 'workspace-1',
        brief: 'brief-1',
        title: 'Manual launch post',
        state: 'draft',
        active_version: null,
        approval_summary: {},
      })
      .mockResolvedValueOnce({
        id: 'version-new',
        draft: 'draft-new',
        version_number: 1,
        caption: 'Manual caption',
        platform_overrides: { platform: 'instagram' },
        media_assets: [],
      });

    const result = await createContentOpsDraftWithVersion({
      workspaceId: 'workspace-1',
      briefId: 'brief-1',
      title: ' Manual launch post ',
      channel: 'instagram',
      caption: ' Manual caption ',
    });

    expect(apiClientMock.post).toHaveBeenNthCalledWith(1, '/content-ops/drafts/', {
      workspace: 'workspace-1',
      brief: 'brief-1',
      title: 'Manual launch post',
    });
    expect(apiClientMock.post).toHaveBeenNthCalledWith(
      2,
      '/content-ops/drafts/draft-new/versions/',
      {
        caption: 'Manual caption',
        platform_overrides: { platform: 'instagram' },
        media_assets: [],
        change_note: 'Created draft caption from Content Ops workspace.',
      },
    );
    expect(result).toMatchObject({
      id: 'draft-new',
      title: 'Manual launch post',
      state: 'generated',
      activeVersionLabel: 'v1',
      variants: [
        {
          versionId: 'version-new',
          channel: 'instagram',
          caption: 'Manual caption',
          approvalStatus: 'approval_not_requested',
        },
      ],
    });
  });

  it('queues caption generation jobs with platform and tone controls', async () => {
    apiClientMock.post.mockResolvedValue({
      id: 'job-caption-live',
      workspace: 'workspace-1',
      brief: 'brief-1',
      job_type: 'caption',
      provider: 'disabled',
      status: 'queued',
      prompt_policy_result: {
        candidate_count: 4,
        platforms: ['facebook_page', 'instagram'],
      },
      result_summary: {
        candidates: [
          {
            channel: 'facebook_page',
            caption: 'Generated Facebook caption. Terms apply.',
            platform_overrides: {
              hashtags: ['Sale'],
              quality_score: 0.84,
            },
          },
        ],
      },
    });

    const result = await requestContentOpsCaptionGeneration({
      briefId: 'brief-1',
      candidateCount: 4,
      platforms: ['facebook_page', 'instagram'],
      toneOverride: ' Warmer ',
    });

    expect(apiClientMock.post).toHaveBeenCalledWith(
      '/content-ops/briefs/brief-1/captions/generate/',
      {
        candidate_count: 4,
        platforms: ['facebook_page', 'instagram'],
        tone_override: 'Warmer',
      },
    );
    expect(result).toMatchObject({
      id: 'job-caption-live',
      label: 'Caption',
      status: 'queued',
      provider: 'disabled',
      candidateCount: 4,
      candidates: [
        {
          id: 'job-caption-live-candidate-1',
          title: 'Facebook Page caption option 1',
          channel: 'facebook_page',
          caption: 'Generated Facebook caption. Terms apply.',
          hashtags: ['Sale'],
          qualityScore: 0.84,
        },
      ],
    });
  });

  it('cancels queued or running generation jobs', async () => {
    apiClientMock.post.mockResolvedValue({
      id: 'job-caption-live',
      workspace: 'workspace-1',
      brief: 'brief-1',
      job_type: 'caption',
      provider: 'disabled',
      status: 'cancelled',
      prompt_policy_result: {
        candidate_count: 4,
      },
    });

    const result = await cancelContentOpsGenerationJob('job-caption-live');

    expect(apiClientMock.post).toHaveBeenCalledWith(
      '/content-ops/generation-jobs/job-caption-live/cancel/',
      {},
    );
    expect(result.status).toBe('cancelled');
  });

  it('submits draft approval workflow actions', async () => {
    apiClientMock.post
      .mockResolvedValueOnce({
        id: 'approval-internal',
        draft: 'draft-1',
        version: 'version-1',
        reviewer_type: 'internal',
        status: 'pending',
      })
      .mockResolvedValueOnce({
        id: 'approval-client',
        draft: 'draft-1',
        version: 'version-1',
        reviewer_type: 'client',
        status: 'pending',
      });

    const internal = await submitContentOpsInternalReview('draft-1');
    const client = await submitContentOpsClientReview('draft-1');

    expect(apiClientMock.post).toHaveBeenNthCalledWith(
      1,
      '/content-ops/drafts/draft-1/submit-internal-review/',
      {},
    );
    expect(apiClientMock.post).toHaveBeenNthCalledWith(
      2,
      '/content-ops/drafts/draft-1/submit-client-review/',
      {},
    );
    expect(internal.reviewer_type).toBe('internal');
    expect(client.reviewer_type).toBe('client');
  });

  it('posts approval decisions with trimmed safe comments', async () => {
    apiClientMock.post.mockResolvedValue({
      id: 'decision-1',
      approval_request: 'approval-1',
      decision: 'approved',
      comment: 'Ready',
    });

    const result = await decideContentOpsApproval({
      approvalId: 'approval-1',
      decision: 'approved',
      comment: ' Ready ',
    });

    expect(apiClientMock.post).toHaveBeenCalledWith(
      '/content-ops/approval-requests/approval-1/decisions/',
      {
        decision: 'approved',
        comment: 'Ready',
      },
    );
    expect(result.decision).toBe('approved');
  });

  it('schedules client-approved drafts with workspace timezone', async () => {
    apiClientMock.post.mockResolvedValue({
      id: 'schedule-1',
      draft: 'draft-1',
      version: 'version-1',
      scheduled_at: '2026-06-18T14:30:00Z',
      timezone: 'America/Jamaica',
      state: 'scheduled',
    });

    const result = await scheduleContentOpsDraft({
      draftId: 'draft-1',
      scheduledAt: '2026-06-18T14:30:00Z',
      timezone: 'America/Jamaica',
    });

    expect(apiClientMock.post).toHaveBeenCalledWith('/content-ops/drafts/draft-1/schedule/', {
      scheduled_at: '2026-06-18T14:30:00Z',
      timezone: 'America/Jamaica',
    });
    expect(result.state).toBe('scheduled');
  });

  it('requeues retryable publish attempts', async () => {
    apiClientMock.post.mockResolvedValue({
      detail: 'Publish attempt requeued.',
      reason: 'requeued',
      attempt_id: 'attempt-1',
      attempt: {
        id: 'attempt-1',
        schedule: 'schedule-1',
        draft: 'draft-1',
        version: 'version-1',
        channel: 'facebook_page',
        state: 'queued',
        failure_code: '',
        failure_detail_safe: '',
        next_retry_at: null,
      },
    });

    const result = await retryContentOpsPublishAttempt('attempt-1');

    expect(apiClientMock.post).toHaveBeenCalledWith(
      '/content-ops/publishing/attempts/attempt-1/retry/',
      {},
    );
    expect(result.attempt.state).toBe('queued');
  });

  it('exports a client-safe content plan snapshot', async () => {
    apiClientMock.post.mockResolvedValue({
      workspace: {
        id: 'workspace-1',
        name: 'Live Workspace',
        timezone: 'America/Jamaica',
      },
      format: 'json',
      item_count: 1,
      items: [{ draft_id: 'draft-1', title: 'Live draft' }],
    });

    const result = await exportContentOpsPlan({
      workspaceId: 'workspace-1',
      states: ['client_approved', 'scheduled'],
    });

    expect(apiClientMock.post).toHaveBeenCalledWith('/content-ops/exports/content-plan/', {
      workspace_id: 'workspace-1',
      states: ['client_approved', 'scheduled'],
    });
    expect(result.item_count).toBe(1);
  });

  it('lists and creates persisted content export artifacts', async () => {
    apiClientMock.get.mockResolvedValue({
      results: [
        {
          id: 'export-1',
          workspace: 'workspace-1',
          export_type: 'content_plan',
          export_format: 'json',
          status: 'completed',
          item_count: 2,
          metadata: {},
          requested_by: null,
          completed_at: '2026-06-10T12:30:00Z',
          download_url: '/api/content-ops/exports/export-1/download/',
          created_at: '2026-06-10T12:30:00Z',
          updated_at: '2026-06-10T12:30:00Z',
        },
      ],
    });
    apiClientMock.post.mockResolvedValue({
      id: 'export-2',
      workspace: 'workspace-1',
      export_type: 'content_plan',
      export_format: 'json',
      status: 'completed',
      item_count: 3,
      metadata: {},
      requested_by: null,
      completed_at: '2026-06-10T12:35:00Z',
      download_url: '/api/content-ops/exports/export-2/download/',
      created_at: '2026-06-10T12:35:00Z',
      updated_at: '2026-06-10T12:35:00Z',
    });

    const artifacts = await listContentOpsExportArtifacts('workspace-1');
    const artifact = await createContentOpsExportArtifact({
      workspaceId: 'workspace-1',
      states: ['client_approved'],
    });

    expect(apiClientMock.get).toHaveBeenCalledWith(
      '/content-ops/exports/?workspace_id=workspace-1&export_type=content_plan',
      { signal: undefined },
    );
    expect(apiClientMock.post).toHaveBeenCalledWith('/content-ops/exports/', {
      workspace_id: 'workspace-1',
      export_type: 'content_plan',
      export_format: 'json',
      states: ['client_approved'],
    });
    expect(artifacts).toHaveLength(1);
    expect(artifact.item_count).toBe(3);
  });

  it('downloads persisted export artifacts without duplicating the API prefix', async () => {
    apiClientMock.download.mockResolvedValue({
      blob: new Blob(['{}'], { type: 'application/json' }),
      filename: 'content-plan.json',
      contentType: 'application/json',
    });

    const result = await downloadContentOpsExportArtifact({
      id: 'export-1',
      download_url: '/api/content-ops/exports/export-1/download/',
    });

    expect(apiClientMock.download).toHaveBeenCalledWith(
      '/content-ops/exports/export-1/download/',
    );
    expect(result.filename).toBe('content-plan.json');
  });

  it('fetches aggregate-only content report payloads for a workspace', async () => {
    apiClientMock.get
      .mockResolvedValueOnce({
        workspace_id: 'workspace-1',
        start_date: null,
        end_date: null,
        drafts_by_state: { published: 1 },
        schedules_by_state: { published: 1 },
        publish_attempts_by_state: { published: 1 },
        published_posts_by_channel: { facebook_page: 1 },
        metric_totals: {
          impressions: 1200,
          reach: 900,
          engagements: 80,
          clicks: 20,
          saves: 4,
          shares: 3,
          video_views: 0,
        },
      })
      .mockResolvedValueOnce({
        count: 1,
        results: [
          {
            id: 'post-1',
            workspace_id: 'workspace-1',
            draft_id: 'draft-1',
            version_id: 'version-1',
            channel: 'facebook_page',
            meta_post_id: 'meta-post-1',
            permalink: 'https://facebook.example/post-1',
            published_at: '2026-06-10T12:00:00Z',
            reporting_link_state: 'linked',
            metrics: {
              impressions: 1200,
              reach: 900,
              engagements: 80,
              clicks: 20,
              saves: 4,
              shares: 3,
              video_views: 0,
            },
          },
        ],
      });

    const overview = await fetchContentOpsReportOverview('workspace-1');
    const posts = await fetchContentOpsReportPosts('workspace-1');

    expect(apiClientMock.get).toHaveBeenNthCalledWith(
      1,
      '/content-ops/reports/overview/?workspace_id=workspace-1',
      { signal: undefined },
    );
    expect(apiClientMock.get).toHaveBeenNthCalledWith(
      2,
      '/content-ops/reports/posts/?workspace_id=workspace-1',
      { signal: undefined },
    );
    expect(overview.metric_totals.engagements).toBe(80);
    expect(posts.results[0].meta_post_id).toBe('meta-post-1');
  });

  it('builds stable content plan export filenames', () => {
    expect(
      buildContentOpsExportFilename(
        'Live Agency Content Workspace',
        new Date('2026-06-10T12:00:00Z'),
      ),
    ).toBe('content-plan-live-agency-content-workspace-2026-06-10.json');
    expect(buildContentOpsExportFilename(' ', new Date('2026-06-10T12:00:00Z'))).toBe(
      'content-plan-workspace-2026-06-10.json',
    );
  });
});
