import { render, screen, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter } from 'react-router-dom';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import { contentOpsMockWorkspace, type ContentOpsMockWorkspace } from '../../lib/contentOpsMock';
import ContentOpsPage from '../ContentOpsPage';

const authMock = vi.hoisted(() => ({
  user: { email: 'admin@example.com', roles: ['ADMIN'] } as Record<string, unknown>,
}));

const contentOpsApiMock = vi.hoisted(() => ({
  buildContentOpsExportFilename: vi.fn(),
  cancelContentOpsGenerationJob: vi.fn(),
  createContentOpsExportArtifact: vi.fn(),
  createContentOpsBrief: vi.fn(),
  createContentOpsDraftWithVersion: vi.fn(),
  createContentOpsVersionWithAsset: vi.fn(),
  decideContentOpsApproval: vi.fn(),
  downloadContentOpsExportArtifact: vi.fn(),
  exportContentOpsPlan: vi.fn(),
  fetchContentOpsReportOverview: vi.fn(),
  fetchContentOpsReportPosts: vi.fn(),
  fetchContentOpsWorkspace: vi.fn(),
  listContentOpsExportArtifacts: vi.fn(),
  listContentOpsAssets: vi.fn(),
  requestContentOpsCaptionGeneration: vi.fn(),
  retryContentOpsPublishAttempt: vi.fn(),
  scheduleContentOpsDraft: vi.fn(),
  submitContentOpsClientReview: vi.fn(),
  submitContentOpsInternalReview: vi.fn(),
  uploadContentOpsAsset: vi.fn(),
}));

const downloadMock = vi.hoisted(() => ({
  saveBlobAsFile: vi.fn(),
}));

vi.mock('../../auth/AuthContext', () => ({
  useAuth: () => ({
    user: authMock.user,
  }),
}));

vi.mock('../../lib/contentOps', () => ({
  buildContentOpsExportFilename: contentOpsApiMock.buildContentOpsExportFilename,
  cancelContentOpsGenerationJob: contentOpsApiMock.cancelContentOpsGenerationJob,
  channelLabel: (channel: string) => (channel === 'instagram' ? 'Instagram' : 'Facebook Page'),
  createContentOpsExportArtifact: contentOpsApiMock.createContentOpsExportArtifact,
  createContentOpsBrief: contentOpsApiMock.createContentOpsBrief,
  createContentOpsDraftWithVersion: contentOpsApiMock.createContentOpsDraftWithVersion,
  createContentOpsVersionWithAsset: contentOpsApiMock.createContentOpsVersionWithAsset,
  decideContentOpsApproval: contentOpsApiMock.decideContentOpsApproval,
  downloadContentOpsExportArtifact: contentOpsApiMock.downloadContentOpsExportArtifact,
  exportContentOpsPlan: contentOpsApiMock.exportContentOpsPlan,
  fetchContentOpsReportOverview: contentOpsApiMock.fetchContentOpsReportOverview,
  fetchContentOpsReportPosts: contentOpsApiMock.fetchContentOpsReportPosts,
  fetchContentOpsWorkspace: contentOpsApiMock.fetchContentOpsWorkspace,
  listContentOpsExportArtifacts: contentOpsApiMock.listContentOpsExportArtifacts,
  listContentOpsAssets: contentOpsApiMock.listContentOpsAssets,
  requestContentOpsCaptionGeneration: contentOpsApiMock.requestContentOpsCaptionGeneration,
  retryContentOpsPublishAttempt: contentOpsApiMock.retryContentOpsPublishAttempt,
  scheduleContentOpsDraft: contentOpsApiMock.scheduleContentOpsDraft,
  submitContentOpsClientReview: contentOpsApiMock.submitContentOpsClientReview,
  submitContentOpsInternalReview: contentOpsApiMock.submitContentOpsInternalReview,
  uploadContentOpsAsset: contentOpsApiMock.uploadContentOpsAsset,
}));

vi.mock('../../lib/download', () => ({
  saveBlobAsFile: downloadMock.saveBlobAsFile,
}));

const renderPage = () =>
  render(
    <MemoryRouter>
      <ContentOpsPage />
    </MemoryRouter>,
  );

describe('ContentOpsPage', () => {
  beforeEach(() => {
    authMock.user = { email: 'admin@example.com', roles: ['ADMIN'] };
    contentOpsApiMock.buildContentOpsExportFilename.mockReset();
    contentOpsApiMock.cancelContentOpsGenerationJob.mockReset();
    contentOpsApiMock.createContentOpsExportArtifact.mockReset();
    contentOpsApiMock.createContentOpsBrief.mockReset();
    contentOpsApiMock.createContentOpsDraftWithVersion.mockReset();
    contentOpsApiMock.createContentOpsVersionWithAsset.mockReset();
    contentOpsApiMock.decideContentOpsApproval.mockReset();
    contentOpsApiMock.downloadContentOpsExportArtifact.mockReset();
    contentOpsApiMock.exportContentOpsPlan.mockReset();
    contentOpsApiMock.fetchContentOpsReportOverview.mockReset();
    contentOpsApiMock.fetchContentOpsReportPosts.mockReset();
    contentOpsApiMock.fetchContentOpsWorkspace.mockReset();
    contentOpsApiMock.listContentOpsAssets.mockReset();
    contentOpsApiMock.listContentOpsExportArtifacts.mockReset();
    contentOpsApiMock.requestContentOpsCaptionGeneration.mockReset();
    contentOpsApiMock.retryContentOpsPublishAttempt.mockReset();
    contentOpsApiMock.scheduleContentOpsDraft.mockReset();
    contentOpsApiMock.submitContentOpsClientReview.mockReset();
    contentOpsApiMock.submitContentOpsInternalReview.mockReset();
    contentOpsApiMock.uploadContentOpsAsset.mockReset();
    downloadMock.saveBlobAsFile.mockReset();
    contentOpsApiMock.buildContentOpsExportFilename.mockReturnValue('content-plan-live.json');
    contentOpsApiMock.createContentOpsExportArtifact.mockResolvedValue({
      id: 'export-created',
      workspace: 'workspace-live',
      export_type: 'content_plan',
      export_format: 'json',
      status: 'completed',
      item_count: 2,
      metadata: {},
      requested_by: null,
      completed_at: '2026-06-10T12:30:00Z',
      download_url: '/api/content-ops/exports/export-created/download/',
      created_at: '2026-06-10T12:30:00Z',
      updated_at: '2026-06-10T12:30:00Z',
    });
    contentOpsApiMock.downloadContentOpsExportArtifact.mockResolvedValue({
      blob: new Blob(['{}'], { type: 'application/json' }),
      filename: 'saved-content-plan.json',
      contentType: 'application/json',
    });
    contentOpsApiMock.fetchContentOpsWorkspace.mockResolvedValue({
      workspace: contentOpsMockWorkspace,
      source: 'mock',
    });
    contentOpsApiMock.listContentOpsAssets.mockResolvedValue([]);
    contentOpsApiMock.listContentOpsExportArtifacts.mockResolvedValue([]);
    contentOpsApiMock.fetchContentOpsReportOverview.mockResolvedValue({
      workspace_id: 'workspace-live',
      start_date: null,
      end_date: null,
      drafts_by_state: {},
      schedules_by_state: {},
      publish_attempts_by_state: {},
      published_posts_by_channel: {},
      metric_totals: {
        impressions: 0,
        reach: 0,
        engagements: 0,
        clicks: 0,
        saves: 0,
        shares: 0,
        video_views: 0,
      },
    });
    contentOpsApiMock.fetchContentOpsReportPosts.mockResolvedValue({
      count: 0,
      results: [],
    });
  });

  it('renders the mocked Content Ops workspace shell', async () => {
    renderPage();

    expect(
      await screen.findByRole('heading', { name: 'June Meta content plan', level: 1 }),
    ).toBeInTheDocument();
    expect(screen.getByRole('heading', { name: 'Production Queue' })).toBeInTheDocument();
    expect(screen.getByRole('heading', { name: 'Draft Editor' })).toBeInTheDocument();
    expect(screen.getByText('Mock fallback - not live data')).toBeInTheDocument();
    expect(
      screen.getByText(
        'Showing mock Content Ops data. Live workspace actions are disabled until API data loads.',
      ),
    ).toBeInTheDocument();
  });

  it('renders live API workspace data when available', async () => {
    const liveWorkspace: ContentOpsMockWorkspace = {
      ...contentOpsMockWorkspace,
      id: 'workspace-live',
      name: 'Live agency content workspace',
      timezone: 'America/Jamaica',
      brief: {
        ...contentOpsMockWorkspace.brief,
        title: 'Live launch brief',
        client: 'Live agency content workspace',
      },
      readiness: contentOpsMockWorkspace.readiness.map((axis) =>
        axis.id === 'meta_auth'
          ? {
              ...axis,
              state: 'connected',
              details: ['1 usable credential', '2 active Page connections'],
            }
          : axis,
      ),
      queue: [
        {
          id: 'attempt-live',
          draftTitle: 'Live approved post',
          client: 'Live agency content workspace',
          channel: 'facebook_page',
          scheduledAt: 'Tue Jun 16, 10:00 AM',
          state: 'container_pending',
          blocker: null,
        },
      ],
    };
    contentOpsApiMock.fetchContentOpsWorkspace.mockResolvedValue({
      workspace: liveWorkspace,
      source: 'api',
    });

    renderPage();

    expect(
      await screen.findByRole('heading', { name: 'Live agency content workspace', level: 1 }),
    ).toBeInTheDocument();
    expect(screen.getByText('Live API')).toBeInTheDocument();
    expect(screen.getByRole('heading', { name: 'Live launch brief' })).toBeInTheDocument();
    expect(screen.getByText('Live approved post')).toBeInTheDocument();
    expect(screen.getByText('Container Pending')).toBeInTheDocument();
    expect(screen.getByText('Waiting for Instagram media container')).toBeInTheDocument();
    expect(screen.getByText('1 usable credential')).toBeInTheDocument();
    expect(screen.getByText('2 active Page connections')).toBeInTheDocument();
    expect(screen.getByText('Live publishing gates blocked')).toBeInTheDocument();
  });

  it('creates a live content brief and updates the active brief panel', async () => {
    const user = userEvent.setup();
    contentOpsApiMock.fetchContentOpsWorkspace.mockResolvedValue({
      workspace: {
        ...contentOpsMockWorkspace,
        id: 'workspace-live',
        name: 'Live agency content workspace',
      },
      source: 'api',
    });
    contentOpsApiMock.createContentOpsBrief.mockResolvedValue({
      id: 'brief-holiday',
      title: 'Holiday launch',
      client: 'Live agency content workspace',
      audience: 'Gift buyers',
      offer: 'Bundle savings',
      tone: 'Warm',
      requiredTerms: ['Terms apply'],
      blockedTerms: ['guaranteed'],
      dateRange: 'Jun 10, 2026-Jun 20, 2026',
    });

    renderPage();

    await screen.findByText('Live API');
    await user.click(screen.getByRole('button', { name: 'New brief' }));
    await user.type(screen.getByLabelText('Campaign theme'), 'Holiday launch');
    await user.type(screen.getByLabelText('Audience'), 'Gift buyers');
    await user.type(screen.getByLabelText('Offer'), 'Bundle savings');
    await user.type(screen.getByLabelText('Tone'), 'Warm');
    await user.type(screen.getByLabelText('Required terms'), 'Terms apply');
    await user.type(screen.getByLabelText('Blocked terms'), 'guaranteed');
    await user.type(screen.getByLabelText('Start date'), '2026-06-10');
    await user.type(screen.getByLabelText('End date'), '2026-06-20');
    await user.click(screen.getByRole('button', { name: 'Create brief' }));

    expect(contentOpsApiMock.createContentOpsBrief).toHaveBeenCalledWith({
      workspaceId: 'workspace-live',
      workspaceName: 'Live agency content workspace',
      campaignTheme: 'Holiday launch',
      audience: 'Gift buyers',
      offer: 'Bundle savings',
      tone: 'Warm',
      requiredTerms: ['Terms apply'],
      blockedTerms: ['guaranteed'],
      dateStart: '2026-06-10',
      dateEnd: '2026-06-20',
    });
    expect(await screen.findByRole('heading', { name: 'Holiday launch' })).toBeInTheDocument();
    expect(screen.getByText('Gift buyers')).toBeInTheDocument();
    expect(screen.queryByRole('heading', { name: 'New Brief' })).not.toBeInTheDocument();
  }, 15000);

  it('creates a live draft with an initial caption version', async () => {
    const user = userEvent.setup();
    contentOpsApiMock.fetchContentOpsWorkspace.mockResolvedValue({
      workspace: {
        ...contentOpsMockWorkspace,
        id: 'workspace-live',
        name: 'Live agency content workspace',
      },
      source: 'api',
    });
    contentOpsApiMock.createContentOpsDraftWithVersion.mockResolvedValue({
      id: 'draft-new',
      title: 'Manual launch post',
      state: 'generated',
      activeVersionLabel: 'v1',
      scheduledAt: null,
      owner: 'Unassigned',
      approvalSummary: {},
      variants: [
        {
          versionId: 'version-new',
          channel: 'instagram',
          label: 'Instagram',
          caption: 'Manual caption for Instagram.',
          mediaAssetIds: [],
          mediaLabel: 'No media attached',
          approvalStatus: 'approval_not_requested',
        },
      ],
    });

    renderPage();

    await screen.findByText('Live API');
    await user.click(screen.getByRole('button', { name: 'New draft' }));
    await user.type(screen.getByLabelText('Draft title'), 'Manual launch post');
    await user.selectOptions(screen.getByLabelText('Channel'), 'instagram');
    await user.type(screen.getByLabelText('Caption'), 'Manual caption for Instagram.');
    await user.click(screen.getByRole('button', { name: 'Create draft' }));

    expect(contentOpsApiMock.createContentOpsDraftWithVersion).toHaveBeenCalledWith({
      workspaceId: 'workspace-live',
      briefId: 'brief-june',
      title: 'Manual launch post',
      channel: 'instagram',
      caption: 'Manual caption for Instagram.',
    });
    expect(await screen.findByRole('heading', { name: 'Manual launch post' })).toBeInTheDocument();
    const draft = screen.getByRole('heading', { name: 'Manual launch post' }).closest('article');
    expect(draft).not.toBeNull();
    expect(within(draft as HTMLElement).getByText('Generated')).toBeInTheDocument();
    expect(within(draft as HTMLElement).getByText('Manual caption for Instagram.')).toBeInTheDocument();
    expect(within(draft as HTMLElement).getByRole('button', { name: 'Submit internal review' })).toBeInTheDocument();
  }, 15000);

  it('downloads a live workspace content plan export', async () => {
    const user = userEvent.setup();
    const liveWorkspace: ContentOpsMockWorkspace = {
      ...contentOpsMockWorkspace,
      id: 'workspace-live',
      name: 'Live agency content workspace',
    };
    contentOpsApiMock.fetchContentOpsWorkspace.mockResolvedValue({
      workspace: liveWorkspace,
      source: 'api',
    });
    contentOpsApiMock.exportContentOpsPlan.mockResolvedValue({
      workspace: {
        id: 'workspace-live',
        name: 'Live agency content workspace',
        timezone: 'America/Jamaica',
      },
      format: 'json',
      item_count: 1,
      items: [{ draft_id: 'draft-weekend-bundle', title: 'Weekend bundle announcement' }],
    });

    renderPage();

    await screen.findByRole('heading', { name: 'Live agency content workspace', level: 1 });
    await user.click(screen.getByRole('button', { name: 'Export plan' }));

    expect(contentOpsApiMock.exportContentOpsPlan).toHaveBeenCalledWith({
      workspaceId: 'workspace-live',
      states: [],
    });
    expect(contentOpsApiMock.buildContentOpsExportFilename).toHaveBeenCalledWith(
      'Live agency content workspace',
    );
    expect(downloadMock.saveBlobAsFile).toHaveBeenCalledWith(
      expect.any(Blob),
      'content-plan-live.json',
    );
    expect(await screen.findByText('Content plan export downloaded.')).toBeInTheDocument();
  });

  it('renders, creates, and downloads persisted export history', async () => {
    const user = userEvent.setup();
    const liveWorkspace: ContentOpsMockWorkspace = {
      ...contentOpsMockWorkspace,
      id: 'workspace-live',
      name: 'Live agency content workspace',
    };
    const existingArtifact = {
      id: 'export-existing',
      workspace: 'workspace-live',
      export_type: 'content_plan',
      export_format: 'json',
      status: 'completed',
      item_count: 2,
      metadata: {},
      requested_by: null,
      completed_at: '2026-06-10T12:00:00Z',
      download_url: '/api/content-ops/exports/export-existing/download/',
      created_at: '2026-06-10T12:00:00Z',
      updated_at: '2026-06-10T12:00:00Z',
    };
    contentOpsApiMock.fetchContentOpsWorkspace.mockResolvedValue({
      workspace: liveWorkspace,
      source: 'api',
    });
    contentOpsApiMock.listContentOpsExportArtifacts.mockResolvedValue([existingArtifact]);

    renderPage();

    const exportHistory = (
      await screen.findByRole('heading', { name: 'Export History' })
    ).closest('section');
    expect(exportHistory).not.toBeNull();
    expect(contentOpsApiMock.listContentOpsExportArtifacts).toHaveBeenCalledWith(
      'workspace-live',
      expect.any(AbortSignal),
    );
    expect(within(exportHistory as HTMLElement).getByText('1 saved packet')).toBeInTheDocument();
    expect(within(exportHistory as HTMLElement).getByText('Content plan')).toBeInTheDocument();
    expect(within(exportHistory as HTMLElement).getByText('JSON')).toBeInTheDocument();

    await user.click(within(exportHistory as HTMLElement).getByRole('button', { name: 'Download' }));

    expect(contentOpsApiMock.downloadContentOpsExportArtifact).toHaveBeenCalledWith(
      existingArtifact,
    );
    expect(downloadMock.saveBlobAsFile).toHaveBeenCalledWith(
      expect.any(Blob),
      'saved-content-plan.json',
    );
    expect(
      await within(exportHistory as HTMLElement).findByText('Saved export downloaded.'),
    ).toBeInTheDocument();

    await user.click(within(exportHistory as HTMLElement).getByRole('button', { name: 'Save export' }));

    expect(contentOpsApiMock.createContentOpsExportArtifact).toHaveBeenCalledWith({
      workspaceId: 'workspace-live',
      states: [],
    });
    expect(
      await within(exportHistory as HTMLElement).findByText('Saved export created.'),
    ).toBeInTheDocument();
    expect(within(exportHistory as HTMLElement).getByText('2 saved packets')).toBeInTheDocument();
  }, 15000);

  it('renders calendar and client review workflow summaries', async () => {
    renderPage();

    const calendar = (await screen.findByRole('heading', { name: 'Calendar' })).closest('section');
    const clientReview = screen.getByRole('heading', { name: 'Client Review' }).closest('section');

    expect(calendar).not.toBeNull();
    expect(clientReview).not.toBeNull();
    expect(within(calendar as HTMLElement).getByText('Scheduled drafts')).toBeInTheDocument();
    expect(within(calendar as HTMLElement).getByText('Weekend bundle announcement')).toBeInTheDocument();
    expect(within(calendar as HTMLElement).getByText('Unscheduled drafts')).toBeInTheDocument();
    expect(
      within(clientReview as HTMLElement).getByText('1 client-facing drafts'),
    ).toBeInTheDocument();
    expect(
      within(clientReview as HTMLElement).getByText('Pending · v3'),
    ).toBeInTheDocument();
  });

  it('renders aggregate organic report data from live API endpoints', async () => {
    const liveWorkspace: ContentOpsMockWorkspace = {
      ...contentOpsMockWorkspace,
      id: 'workspace-live',
      name: 'Live agency content workspace',
    };
    contentOpsApiMock.fetchContentOpsWorkspace.mockResolvedValue({
      workspace: liveWorkspace,
      source: 'api',
    });
    contentOpsApiMock.fetchContentOpsReportOverview.mockResolvedValue({
      workspace_id: 'workspace-live',
      start_date: null,
      end_date: null,
      drafts_by_state: { published: 1 },
      schedules_by_state: { published: 1 },
      publish_attempts_by_state: { published: 1, failed_retryable: 1 },
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
    });
    contentOpsApiMock.fetchContentOpsReportPosts.mockResolvedValue({
      count: 1,
      results: [
        {
          id: 'post-1',
          workspace_id: 'workspace-live',
          draft_id: 'draft-weekend-bundle',
          version_id: 'version-weekend-facebook',
          channel: 'facebook_page',
          meta_post_id: 'fb-post-1',
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

    renderPage();

    expect(await screen.findByRole('heading', { name: 'Organic Report' })).toBeInTheDocument();
    expect(contentOpsApiMock.fetchContentOpsReportOverview).toHaveBeenCalledWith(
      'workspace-live',
      expect.any(AbortSignal),
    );
    expect(contentOpsApiMock.fetchContentOpsReportPosts).toHaveBeenCalledWith(
      'workspace-live',
      expect.any(AbortSignal),
    );
    expect(screen.getAllByText('80').length).toBeGreaterThan(0);
    expect(screen.getByText('1,200 impressions · 900 reach')).toBeInTheDocument();
    expect(screen.getByText('fb-post-1')).toBeInTheDocument();
    expect(screen.getByRole('link', { name: 'Open post' })).toHaveAttribute(
      'href',
      'https://facebook.example/post-1',
    );
    expect(screen.getByText('20 clicks · 4 saves')).toBeInTheDocument();
  });

  it('queues caption generation for live creator workspaces', async () => {
    const user = userEvent.setup();
    contentOpsApiMock.fetchContentOpsWorkspace.mockResolvedValue({
      workspace: {
        ...contentOpsMockWorkspace,
        id: 'workspace-live',
      },
      source: 'api',
    });
    contentOpsApiMock.requestContentOpsCaptionGeneration.mockResolvedValue({
      id: 'job-caption-live',
      label: 'Caption',
      status: 'queued',
      provider: 'disabled',
      candidateCount: 4,
    });

    renderPage();

    await screen.findByText('Live API');
    await user.type(screen.getByLabelText('Tone override'), 'Warmer');
    await user.click(screen.getByRole('button', { name: 'Generate captions' }));

    expect(contentOpsApiMock.requestContentOpsCaptionGeneration).toHaveBeenCalledWith({
      briefId: 'brief-june',
      candidateCount: 3,
      platforms: ['facebook_page', 'instagram'],
      toneOverride: 'Warmer',
    });
    expect(await screen.findByText('Caption generation job queued.')).toBeInTheDocument();
    expect(screen.getByRole('heading', { name: 'Caption' })).toBeInTheDocument();
    expect(screen.getByText('disabled · 4 candidates')).toBeInTheDocument();
  });

  it('cancels queued generation jobs and updates their state', async () => {
    const user = userEvent.setup();
    contentOpsApiMock.fetchContentOpsWorkspace.mockResolvedValue({
      workspace: {
        ...contentOpsMockWorkspace,
        id: 'workspace-live',
        generationJobs: [
          {
            id: 'job-caption-live',
            label: 'Caption',
            status: 'running',
            provider: 'disabled',
            candidateCount: 3,
          },
        ],
      },
      source: 'api',
    });
    contentOpsApiMock.cancelContentOpsGenerationJob.mockResolvedValue({
      id: 'job-caption-live',
      label: 'Caption',
      status: 'cancelled',
      provider: 'disabled',
      candidateCount: 3,
    });

    renderPage();

    const generation = (await screen.findByRole('heading', { name: 'Generation' })).closest(
      'section',
    );
    expect(generation).not.toBeNull();
    await user.click(within(generation as HTMLElement).getByRole('button', { name: 'Cancel' }));

    expect(contentOpsApiMock.cancelContentOpsGenerationJob).toHaveBeenCalledWith(
      'job-caption-live',
    );
    expect(
      await within(generation as HTMLElement).findByText('Generation job cancelled.'),
    ).toBeInTheDocument();
    expect(within(generation as HTMLElement).getByText('Cancelled')).toBeInTheDocument();
  });

  it('creates a draft from a generated caption candidate', async () => {
    const user = userEvent.setup();
    contentOpsApiMock.fetchContentOpsWorkspace.mockResolvedValue({
      workspace: {
        ...contentOpsMockWorkspace,
        id: 'workspace-live',
        generationJobs: [
          {
            id: 'job-caption-live',
            label: 'Caption',
            status: 'succeeded',
            provider: 'mock',
            candidateCount: 1,
            candidates: [
              {
                id: 'candidate-instagram',
                title: 'Launch reminder - Instagram option',
                channel: 'instagram',
                caption: 'Generated candidate caption for Instagram. Terms apply.',
                hashtags: ['Launch'],
                cta: 'Plan your visit',
                altText: 'Lifestyle product arrangement for Instagram.',
                riskFlags: [],
                qualityScore: 0.93,
              },
            ],
          },
        ],
      },
      source: 'api',
    });
    contentOpsApiMock.createContentOpsDraftWithVersion.mockResolvedValue({
      id: 'draft-candidate',
      title: 'Launch reminder - Instagram option',
      state: 'generated',
      activeVersionLabel: 'v1',
      scheduledAt: null,
      owner: 'Unassigned',
      approvalSummary: {},
      variants: [
        {
          versionId: 'version-candidate',
          channel: 'instagram',
          label: 'Instagram',
          caption: 'Generated candidate caption for Instagram. Terms apply.',
          mediaAssetIds: [],
          mediaLabel: 'No media attached',
          approvalStatus: 'approval_not_requested',
        },
      ],
    });

    renderPage();

    const candidate = (
      await screen.findByRole('heading', { name: 'Launch reminder - Instagram option' })
    ).closest('section');
    expect(candidate).not.toBeNull();
    expect(within(candidate as HTMLElement).getByText('Instagram')).toBeInTheDocument();
    expect(within(candidate as HTMLElement).getByText('93%')).toBeInTheDocument();
    expect(within(candidate as HTMLElement).getByText('Plan your visit')).toBeInTheDocument();
    expect(within(candidate as HTMLElement).getByText('Launch')).toBeInTheDocument();
    expect(
      within(candidate as HTMLElement).getByText('Lifestyle product arrangement for Instagram.'),
    ).toBeInTheDocument();
    await user.click(
      within(candidate as HTMLElement).getByRole('button', {
        name: 'Create draft from Launch reminder - Instagram option',
      }),
    );

    expect(contentOpsApiMock.createContentOpsDraftWithVersion).toHaveBeenCalledWith({
      workspaceId: 'workspace-live',
      briefId: 'brief-june',
      title: 'Launch reminder - Instagram option',
      channel: 'instagram',
      caption: 'Generated candidate caption for Instagram. Terms apply.',
    });
    expect(await screen.findByText('Draft created from generated candidate.')).toBeInTheDocument();
    expect(
      screen.getByRole('heading', { name: 'Launch reminder - Instagram option', level: 3 }),
    ).toBeInTheDocument();
  });

  it('shows fallback warning when the API mapper falls back to mock data', async () => {
    contentOpsApiMock.fetchContentOpsWorkspace.mockResolvedValue({
      workspace: contentOpsMockWorkspace,
      source: 'mock',
      warning: 'No Content Ops workspaces have been created yet.',
    });

    renderPage();

    expect(await screen.findByText('Mock fallback - not live data')).toBeInTheDocument();
    expect(screen.getByText('No Content Ops workspaces have been created yet.')).toBeInTheDocument();
  });

  it('keeps readiness blockers as six separate axes', async () => {
    renderPage();

    const readiness = await screen.findByTestId('content-ops-readiness');
    const axes = within(readiness).getAllByRole('listitem');

    expect(axes).toHaveLength(6);
    expect(within(readiness).getByText('Meta auth')).toBeInTheDocument();
    expect(within(readiness).getByText('Page selection')).toBeInTheDocument();
    expect(within(readiness).getByText('Instagram linkage')).toBeInTheDocument();
    expect(within(readiness).getByText('Facebook publishing')).toBeInTheDocument();
    expect(within(readiness).getByText('Instagram publishing')).toBeInTheDocument();
    expect(within(readiness).getByText('Reporting readiness')).toBeInTheDocument();
    expect(
      within(readiness).getByText('Instagram publishing permission family is not confirmed.'),
    ).toBeInTheDocument();
    const summary = screen.getByTestId('content-ops-live-readiness-summary');
    expect(within(summary).getByText('Live publishing gates blocked')).toBeInTheDocument();
    expect(
      within(summary).getByText(
        /Facebook publishing: pages_manage_posts App Review evidence is not complete/,
      ),
    ).toBeInTheDocument();
  });

  it('renders Facebook and Instagram draft variants independently', async () => {
    renderPage();

    const draft = (await screen.findByRole('heading', { name: 'Weekend bundle announcement' }))
      .closest('article');

    expect(draft).not.toBeNull();
    expect(
      within(draft as HTMLElement).getByRole('heading', { name: 'Facebook Page' }),
    ).toBeInTheDocument();
    expect(
      within(draft as HTMLElement).getByRole('heading', { name: 'Instagram' }),
    ).toBeInTheDocument();
    expect(within(draft as HTMLElement).getByText('Landscape product collage')).toBeInTheDocument();
    expect(within(draft as HTMLElement).getByText('Square carousel cover')).toBeInTheDocument();
  });

  it('disables brief creation for viewer-only users', async () => {
    authMock.user = { email: 'viewer@example.com', roles: ['VIEWER'] };

    renderPage();

    expect(await screen.findByRole('button', { name: 'New brief' })).toBeDisabled();
  });

  it('uploads media assets for live creator workspaces', async () => {
    const user = userEvent.setup();
    contentOpsApiMock.fetchContentOpsWorkspace.mockResolvedValue({
      workspace: { ...contentOpsMockWorkspace, id: 'workspace-live' },
      source: 'api',
    });
    contentOpsApiMock.uploadContentOpsAsset.mockResolvedValue({
      id: 'asset-live',
      workspace: 'workspace-live',
      source: 'uploaded',
      mime_type: 'image/png',
      alt_text: 'Hero product visual',
      status: 'available',
      download_url: '/api/content-ops/assets/asset-live/download/',
      created_at: '2026-06-10T12:00:00Z',
      updated_at: '2026-06-10T12:00:00Z',
    });

    renderPage();

    const file = new File(['image-bytes'], 'hero.png', { type: 'image/png' });
    await user.upload(await screen.findByLabelText('Asset file'), file);
    await user.type(screen.getByLabelText('Alt text'), 'Hero product visual');
    await user.click(screen.getByRole('button', { name: 'Upload asset' }));

    expect(contentOpsApiMock.uploadContentOpsAsset).toHaveBeenCalledWith({
      workspaceId: 'workspace-live',
      file,
      altText: 'Hero product visual',
    });
    expect(await screen.findByText('Asset uploaded and is available for draft versions.')).toBeInTheDocument();
    expect(screen.getAllByText('Hero product visual').length).toBeGreaterThan(0);
    expect(screen.getByRole('link', { name: 'Preview' })).toHaveAttribute(
      'href',
      '/api/content-ops/assets/asset-live/download/',
    );
  });

  it('surfaces upload failures without clearing the live workspace', async () => {
    const user = userEvent.setup();
    contentOpsApiMock.fetchContentOpsWorkspace.mockResolvedValue({
      workspace: { ...contentOpsMockWorkspace, id: 'workspace-live' },
      source: 'api',
    });
    contentOpsApiMock.uploadContentOpsAsset.mockRejectedValue(
      new Error('Asset MIME type is not supported.'),
    );

    renderPage();

    await user.upload(
      await screen.findByLabelText('Asset file'),
      new File(['image-bytes'], 'bad-image.png', { type: 'image/png' }),
    );
    await user.click(screen.getByRole('button', { name: 'Upload asset' }));

    expect(await screen.findByText('Asset MIME type is not supported.')).toBeInTheDocument();
    expect(screen.getByRole('heading', { name: 'June Meta content plan', level: 1 })).toBeInTheDocument();
  });

  it('disables media upload for viewer-only users', async () => {
    authMock.user = { email: 'viewer@example.com', roles: ['VIEWER'] };
    contentOpsApiMock.fetchContentOpsWorkspace.mockResolvedValue({
      workspace: { ...contentOpsMockWorkspace, id: 'workspace-live' },
      source: 'api',
    });

    renderPage();

    expect(await screen.findByText('Viewer access can review media but cannot upload assets.')).toBeInTheDocument();
    expect(screen.getByLabelText('Asset file')).toBeDisabled();
    expect(screen.getByRole('button', { name: 'Upload asset' })).toBeDisabled();
  });

  it('attaches uploaded media to a draft by creating a new version', async () => {
    const user = userEvent.setup();
    contentOpsApiMock.fetchContentOpsWorkspace.mockResolvedValue({
      workspace: { ...contentOpsMockWorkspace, id: 'workspace-live' },
      source: 'api',
    });
    contentOpsApiMock.listContentOpsAssets.mockResolvedValue([
      {
        id: 'asset-live',
        workspace: 'workspace-live',
        source: 'uploaded',
        mime_type: 'image/png',
        alt_text: 'Hero product visual',
        status: 'available',
        download_url: '/api/content-ops/assets/asset-live/download/',
        created_at: '2026-06-10T12:00:00Z',
        updated_at: '2026-06-10T12:00:00Z',
      },
    ]);
    contentOpsApiMock.createContentOpsVersionWithAsset.mockResolvedValue({
      id: 'version-weekend-facebook-next',
      draft: 'draft-weekend-bundle',
      version_number: 4,
      caption:
        'Weekend plans, simplified. Shop bundled home and lifestyle picks for a cleaner, faster checkout. Terms apply.',
      platform_overrides: { platform: 'facebook_page' },
      media_assets: ['asset-live'],
    });

    renderPage();

    const selector = await screen.findByLabelText(
      'Attach media to Weekend bundle announcement Facebook Page',
    );
    await user.selectOptions(selector, 'asset-live');
    const attachControl = selector.closest('.content-ops-attach');
    expect(attachControl).not.toBeNull();
    await user.click(within(attachControl as HTMLElement).getByRole('button', { name: 'Attach' }));

    expect(contentOpsApiMock.createContentOpsVersionWithAsset).toHaveBeenCalledWith({
      draftId: 'draft-weekend-bundle',
      caption:
        'Weekend plans, simplified. Shop bundled home and lifestyle picks for a cleaner, faster checkout. Terms apply.',
      channel: 'facebook_page',
      mediaAssetIds: [],
      assetId: 'asset-live',
    });
    expect(await screen.findByText('Media attached as a new draft version.')).toBeInTheDocument();
    const draft = screen
      .getByRole('heading', { name: 'Weekend bundle announcement' })
      .closest('article');
    expect(draft).not.toBeNull();
    expect(within(draft as HTMLElement).getByText('v4 · A. Strategist')).toBeInTheDocument();
    expect(within(draft as HTMLElement).getByText('1 attached asset')).toBeInTheDocument();
  });

  it('submits a generated draft for internal review', async () => {
    const user = userEvent.setup();
    contentOpsApiMock.fetchContentOpsWorkspace.mockResolvedValue({
      workspace: { ...contentOpsMockWorkspace, id: 'workspace-live' },
      source: 'api',
    });
    contentOpsApiMock.submitContentOpsInternalReview.mockResolvedValue({
      id: 'approval-payday-internal',
      draft: 'draft-payday-reminder',
      version: 'version-payday-facebook',
      reviewer_type: 'internal',
      status: 'pending',
    });

    renderPage();

    const draft = (await screen.findByRole('heading', { name: 'Payday reminder' })).closest(
      'article',
    );
    expect(draft).not.toBeNull();
    await user.click(
      within(draft as HTMLElement).getByRole('button', { name: 'Submit internal review' }),
    );

    expect(contentOpsApiMock.submitContentOpsInternalReview).toHaveBeenCalledWith(
      'draft-payday-reminder',
    );
    expect(
      await within(draft as HTMLElement).findByText('Internal review request created.'),
    ).toBeInTheDocument();
    expect(within(draft as HTMLElement).getByText('Internal Review')).toBeInTheDocument();
    expect(within(draft as HTMLElement).getByText('Internal Pending')).toBeInTheDocument();
  });

  it('records client approval and marks the draft ready for scheduling', async () => {
    const user = userEvent.setup();
    contentOpsApiMock.fetchContentOpsWorkspace.mockResolvedValue({
      workspace: { ...contentOpsMockWorkspace, id: 'workspace-live' },
      source: 'api',
    });
    contentOpsApiMock.decideContentOpsApproval.mockResolvedValue({
      id: 'decision-client',
      approval_request: 'approval-weekend-client',
      decision: 'approved',
      comment: '',
    });

    renderPage();

    const draft = (
      await screen.findByRole('heading', { name: 'Weekend bundle announcement' })
    ).closest('article');
    expect(draft).not.toBeNull();
    await user.click(within(draft as HTMLElement).getByRole('button', { name: 'Approve client' }));

    expect(contentOpsApiMock.decideContentOpsApproval).toHaveBeenCalledWith({
      approvalId: 'approval-weekend-client',
      decision: 'approved',
    });
    expect(
      await within(draft as HTMLElement).findByText('Client approval recorded.'),
    ).toBeInTheDocument();
    expect(within(draft as HTMLElement).getAllByText('Client Approved')).toHaveLength(2);
    expect(within(draft as HTMLElement).getByLabelText('Schedule time')).toBeInTheDocument();
    expect(
      within(draft as HTMLElement).getByLabelText(
        'Confirm this approved version can enter the publish queue',
      ),
    ).toBeDisabled();
  });

  it('schedules a client-approved draft with the workspace timezone', async () => {
    const user = userEvent.setup();
    contentOpsApiMock.fetchContentOpsWorkspace.mockResolvedValue({
      workspace: { ...contentOpsMockWorkspace, id: 'workspace-live' },
      source: 'api',
    });
    contentOpsApiMock.decideContentOpsApproval.mockResolvedValue({
      id: 'decision-client',
      approval_request: 'approval-weekend-client',
      decision: 'approved',
      comment: '',
    });
    contentOpsApiMock.scheduleContentOpsDraft.mockResolvedValue({
      id: 'schedule-live',
      draft: 'draft-weekend-bundle',
      version: 'version-weekend-instagram',
      scheduled_at: '2026-06-18T14:30:00Z',
      timezone: 'America/Jamaica',
      state: 'scheduled',
    });

    renderPage();

    const draft = (
      await screen.findByRole('heading', { name: 'Weekend bundle announcement' })
    ).closest('article');
    expect(draft).not.toBeNull();
    await user.click(within(draft as HTMLElement).getByRole('button', { name: 'Approve client' }));
    const scheduleButton = within(draft as HTMLElement).getByRole('button', { name: 'Schedule' });
    expect(scheduleButton).toBeDisabled();
    await user.type(await within(draft as HTMLElement).findByLabelText('Schedule time'), '2026-06-18T09:30');
    expect(scheduleButton).toBeDisabled();
    await user.click(
      within(draft as HTMLElement).getByLabelText(
        'Confirm this approved version can enter the publish queue',
      ),
    );
    await user.click(scheduleButton);

    expect(contentOpsApiMock.scheduleContentOpsDraft).toHaveBeenCalledWith({
      draftId: 'draft-weekend-bundle',
      scheduledAt: expect.any(String),
      timezone: 'America/Jamaica',
    });
    expect(await within(draft as HTMLElement).findByText('Draft scheduled.')).toBeInTheDocument();
    expect(within(draft as HTMLElement).getByText('Scheduled')).toBeInTheDocument();
    expect(within(draft as HTMLElement).getByText('Scheduled for dispatch')).toBeInTheDocument();
  });

  it('retries retryable publish queue rows and updates the row state', async () => {
    const user = userEvent.setup();
    const liveWorkspace: ContentOpsMockWorkspace = {
      ...contentOpsMockWorkspace,
      id: 'workspace-live',
      queue: [
        {
          id: 'attempt-retry',
          draftTitle: 'Retryable post',
          client: 'North Coast Retail Group',
          channel: 'facebook_page',
          scheduledAt: 'Thu Jun 18, 9:30 AM',
          state: 'failed_retryable',
          blocker: 'Provider timeout',
        },
      ],
    };
    contentOpsApiMock.fetchContentOpsWorkspace.mockResolvedValue({
      workspace: liveWorkspace,
      source: 'api',
    });
    contentOpsApiMock.retryContentOpsPublishAttempt.mockResolvedValue({
      detail: 'Publish attempt requeued.',
      reason: 'requeued',
      attempt_id: 'attempt-retry',
      attempt: {
        id: 'attempt-retry',
        schedule: 'schedule-live',
        draft: 'draft-weekend-bundle',
        version: 'version-weekend-instagram',
        channel: 'facebook_page',
        state: 'queued',
        failure_code: '',
        failure_detail_safe: '',
        next_retry_at: null,
      },
    });

    renderPage();

    const row = (await screen.findByText('Retryable post')).closest('tr');
    expect(row).not.toBeNull();
    expect(within(row as HTMLElement).getByText('Failed Retryable')).toBeInTheDocument();
    await user.click(within(row as HTMLElement).getByRole('button', { name: 'Retry' }));

    expect(contentOpsApiMock.retryContentOpsPublishAttempt).toHaveBeenCalledWith('attempt-retry');
    expect(await within(row as HTMLElement).findByText('Requeued')).toBeInTheDocument();
    expect(within(row as HTMLElement).getByText('Queued')).toBeInTheDocument();
    expect(within(row as HTMLElement).getByText('Ready for dispatcher')).toBeInTheDocument();
  });

  it('renders live publish attempt lifecycle details without retrying terminal rows', async () => {
    const liveWorkspace: ContentOpsMockWorkspace = {
      ...contentOpsMockWorkspace,
      id: 'workspace-live',
      queue: [
        {
          id: 'attempt-preflight',
          draftTitle: 'Preflight post',
          client: 'North Coast Retail Group',
          channel: 'facebook_page',
          scheduledAt: 'Thu Jun 18, 9:30 AM',
          state: 'preflight',
          blocker: null,
        },
        {
          id: 'attempt-container-creating',
          draftTitle: 'Container creating post',
          client: 'North Coast Retail Group',
          channel: 'instagram',
          scheduledAt: 'Thu Jun 18, 9:31 AM',
          state: 'container_creating',
          blocker: null,
        },
        {
          id: 'attempt-container-pending',
          draftTitle: 'Container pending post',
          client: 'North Coast Retail Group',
          channel: 'instagram',
          scheduledAt: 'Thu Jun 18, 9:32 AM',
          state: 'container_pending',
          blocker: null,
        },
        {
          id: 'attempt-container-ready',
          draftTitle: 'Container ready post',
          client: 'North Coast Retail Group',
          channel: 'instagram',
          scheduledAt: 'Thu Jun 18, 9:33 AM',
          state: 'container_ready',
          blocker: null,
        },
        {
          id: 'attempt-publishing',
          draftTitle: 'Publishing post',
          client: 'North Coast Retail Group',
          channel: 'facebook_page',
          scheduledAt: 'Thu Jun 18, 9:34 AM',
          state: 'publishing',
          blocker: null,
        },
        {
          id: 'attempt-terminal',
          draftTitle: 'Terminal post',
          client: 'North Coast Retail Group',
          channel: 'facebook_page',
          scheduledAt: 'Thu Jun 18, 9:35 AM',
          state: 'failed_terminal',
          blocker: 'Permission missing',
        },
        {
          id: 'attempt-expired',
          draftTitle: 'Expired container post',
          client: 'North Coast Retail Group',
          channel: 'instagram',
          scheduledAt: 'Thu Jun 18, 9:36 AM',
          state: 'container_expired',
          blocker: null,
        },
        {
          id: 'attempt-cancelled',
          draftTitle: 'Cancelled post',
          client: 'North Coast Retail Group',
          channel: 'facebook_page',
          scheduledAt: 'Thu Jun 18, 9:37 AM',
          state: 'cancelled',
          blocker: null,
        },
      ],
    };
    contentOpsApiMock.fetchContentOpsWorkspace.mockResolvedValue({
      workspace: liveWorkspace,
      source: 'api',
    });

    renderPage();

    await screen.findByText('Preflight post');
    expect(screen.getByText('Running preflight checks')).toBeInTheDocument();
    expect(screen.getByText('Creating Instagram media container')).toBeInTheDocument();
    expect(screen.getByText('Waiting for Instagram media container')).toBeInTheDocument();
    expect(screen.getByText('Instagram media container ready')).toBeInTheDocument();
    expect(screen.getByText('Publishing through provider boundary')).toBeInTheDocument();
    expect(screen.getByText('Permission missing')).toBeInTheDocument();
    expect(screen.getByText('Instagram media container expired')).toBeInTheDocument();
    const cancelledRow = screen.getByText('Cancelled post').closest('tr');
    expect(cancelledRow).not.toBeNull();
    expect(within(cancelledRow as HTMLElement).getAllByText('Cancelled')).toHaveLength(2);
    expect(screen.queryByRole('button', { name: 'Retry' })).not.toBeInTheDocument();
    expect(contentOpsApiMock.retryContentOpsPublishAttempt).not.toHaveBeenCalled();
  });
});
