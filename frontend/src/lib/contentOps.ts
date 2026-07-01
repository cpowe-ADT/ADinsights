import apiClient, { appendQueryParams } from './apiClient';
import {
  channelLabel,
  contentOpsMockWorkspace,
  type ContentOpsApprovalSummary,
  type ContentOpsBrief,
  type ContentOpsChannel,
  type ContentOpsDraft,
  type ContentOpsDraftVariant,
  type ContentOpsGeneratedCandidate,
  type ContentOpsGenerationJob,
  type ContentOpsMockWorkspace,
  type ContentOpsQueueItem,
  type ContentOpsReadinessAxis,
} from './contentOpsMock';

type Paginated<T> = {
  results?: T[];
};

type BackendReadinessAxis = {
  state?: string | null;
  reason?: string | null;
  dataset_live_reason?: string | null;
  credential_count?: number;
  usable_credential_count?: number;
  active_page_connection_count?: number;
  page_count?: number;
  selected_page_count?: number;
  default_page_id?: string | null;
  linked_count?: number;
  identity_count?: number;
  missing_permissions?: unknown;
  required_permissions?: unknown;
  upstream_blockers?: unknown;
  identity_blockers?: unknown;
};

type BackendWorkspace = {
  id: string;
  name: string;
  timezone?: string | null;
};

export type ContentOpsUploadedAsset = {
  id: string;
  workspace: string;
  source: string;
  mime_type: string;
  width?: number | null;
  height?: number | null;
  duration_seconds?: number | null;
  alt_text: string;
  renditions?: Record<string, unknown>;
  status: string;
  download_url: string | null;
  created_at: string;
  updated_at: string;
};

export type ContentOpsDraftVersionPayload = {
  id: string;
  draft: string;
  version_number?: number;
  caption?: string;
  platform_overrides?: Record<string, unknown>;
  media_assets?: string[];
  change_note?: string;
};

export type ContentOpsCaptionGenerationRequest = {
  briefId: string;
  candidateCount: number;
  platforms: ContentOpsChannel[];
  toneOverride?: string;
  regionalAgentProfileId?: string;
};

export type ContentOpsRegion = 'caribbean' | 'peru_latam';

export type ContentOpsRegionalAgent = {
  id: string;
  workspaceId: string;
  name: string;
  region: ContentOpsRegion;
  locale: string;
  language: string;
  timezone: string;
  isActive: boolean;
};

export type ContentOpsRegionalAgentCreateRequest = {
  workspaceId: string;
  name: string;
  region: ContentOpsRegion;
  locale?: string;
  language?: string;
  timezone?: string;
};

export type ContentOpsWorkspaceSummary = {
  id: string;
  name: string;
  timezone: string;
};

export type ContentOpsImageGenerationRequest = {
  workspaceId: string;
  prompt: string;
  count?: number;
  size?: string;
  regionalAgentProfileId?: string;
};

export type ContentOpsBriefCreateRequest = {
  workspaceId: string;
  workspaceName: string;
  campaignTheme: string;
  audience: string;
  offer: string;
  tone: string;
  requiredTerms: string[];
  blockedTerms: string[];
  dateStart?: string;
  dateEnd?: string;
};

export type ContentOpsDraftCreateRequest = {
  workspaceId: string;
  briefId: string | null;
  title: string;
  channel: ContentOpsChannel;
  caption: string;
};

export type ContentOpsApprovalRequestPayload = {
  id: string;
  draft: string;
  version: string;
  reviewer_type: 'internal' | 'client' | string;
  status: string;
  requested_at?: string;
  due_at?: string | null;
};

export type ContentOpsApprovalDecisionPayload = {
  id: string;
  approval_request: string;
  decision: 'approved' | 'changes_requested' | 'rejected' | string;
  comment?: string;
  decided_at?: string;
};

export type ContentOpsSchedulePayload = {
  id: string;
  draft: string;
  version: string;
  scheduled_at: string;
  timezone: string;
  state: string;
  approval_snapshot?: Record<string, unknown>;
};

export type ContentOpsPublishAttemptPayload = {
  id: string;
  schedule: string;
  draft: string;
  version: string;
  channel: ContentOpsChannel;
  state: string;
  failure_code?: string;
  failure_detail_safe?: string;
  next_retry_at?: string | null;
};

export type ContentOpsPublishAttemptRetryPayload = {
  detail: string;
  reason: string;
  attempt_id: string;
  attempt: ContentOpsPublishAttemptPayload;
};

export type ContentOpsContentPlanExportPayload = {
  workspace: {
    id: string;
    name: string;
    timezone: string;
  };
  format: string;
  item_count: number;
  items: unknown[];
};

export type ContentOpsExportArtifact = {
  id: string;
  workspace: string;
  export_type: string;
  export_format: string;
  status: string;
  item_count: number;
  metadata?: Record<string, unknown>;
  requested_by?: string | null;
  completed_at?: string | null;
  download_url: string | null;
  created_at: string;
  updated_at: string;
};

export type ContentOpsMetricTotals = {
  impressions: number;
  reach: number;
  engagements: number;
  clicks: number;
  saves: number;
  shares: number;
  video_views: number;
};

export type ContentOpsReportOverviewPayload = {
  workspace_id: string | null;
  start_date: string | null;
  end_date: string | null;
  drafts_by_state: Record<string, number>;
  schedules_by_state: Record<string, number>;
  publish_attempts_by_state: Record<string, number>;
  published_posts_by_channel: Record<string, number>;
  metric_totals: ContentOpsMetricTotals;
};

export type ContentOpsReportPost = {
  id: string;
  workspace_id: string;
  draft_id: string;
  version_id: string;
  channel: ContentOpsChannel;
  meta_post_id: string;
  permalink: string;
  published_at: string;
  reporting_link_state: string;
  metrics: ContentOpsMetricTotals;
};

export type ContentOpsReportPostsPayload = {
  count: number;
  results: ContentOpsReportPost[];
};

type BackendBrief = {
  id: string;
  campaign_theme?: string;
  audience?: string;
  offer?: string;
  tone?: string;
  required_terms?: unknown;
  blocked_terms?: unknown;
  date_start?: string | null;
  date_end?: string | null;
};

type BackendGenerationJob = {
  id: string;
  job_type?: string;
  status?: string;
  provider?: string;
  prompt_policy_result?: Record<string, unknown>;
  result_summary?: Record<string, unknown>;
};

type BackendDraft = {
  id: string;
  title?: string;
  state?: string;
  active_version?: string | null;
  created_by?: string | null;
  owner?: string | null;
  approval_summary?: Record<string, BackendApprovalSummaryItem> | null;
  schedule_summary?: {
    state?: string | null;
    scheduled_at?: string | null;
  } | null;
};

type BackendApprovalSummaryItem = {
  id?: string | null;
  status?: string | null;
  version_id?: string | null;
};

type BackendDraftVersion = {
  id: string;
  version_number?: number;
  caption?: string;
  platform_overrides?: Record<string, unknown>;
  media_assets?: string[];
};

type BackendSchedule = {
  id: string;
  draft: string;
  scheduled_at?: string | null;
};

type BackendPublishAttempt = {
  id: string;
  draft: string;
  schedule: string;
  channel: ContentOpsChannel;
  state: ContentOpsQueueItem['state'] | string;
  failure_code?: string;
  failure_detail_safe?: string;
  next_retry_at?: string | null;
};

const READINESS_LABELS: Record<ContentOpsReadinessAxis['id'], string> = {
  meta_auth: 'Meta auth',
  page_selection: 'Page selection',
  instagram_linkage: 'Instagram linkage',
  facebook_page_publishing: 'Facebook publishing',
  instagram_publishing: 'Instagram publishing',
  reporting_readiness: 'Reporting readiness',
};

const READINESS_IDS = Object.keys(READINESS_LABELS) as ContentOpsReadinessAxis['id'][];

export type ContentOpsWorkspaceLoadResult = {
  workspace: ContentOpsMockWorkspace;
  source: 'api' | 'mock';
  warning?: string;
};

export { channelLabel };

export async function uploadContentOpsAsset({
  workspaceId,
  file,
  altText,
  signal,
}: {
  workspaceId: string;
  file: File;
  altText?: string;
  signal?: AbortSignal;
}): Promise<ContentOpsUploadedAsset> {
  const formData = new FormData();
  formData.set('workspace', workspaceId);
  formData.set('file', file);
  if (altText?.trim()) {
    formData.set('alt_text', altText.trim());
  }
  return apiClient.post<ContentOpsUploadedAsset>('/content-ops/assets/upload/', formData, {
    signal,
  });
}

export async function listContentOpsAssets(
  workspaceId: string,
  signal?: AbortSignal,
): Promise<ContentOpsUploadedAsset[]> {
  return getResults<ContentOpsUploadedAsset>(
    appendQueryParams('/content-ops/assets/', {
      workspace_id: workspaceId,
      status: 'available',
    }),
    signal,
  );
}

export async function createContentOpsVersionWithAsset({
  draftId,
  caption,
  channel,
  mediaAssetIds,
  assetId,
}: {
  draftId: string;
  caption: string;
  channel: ContentOpsChannel;
  mediaAssetIds: string[];
  assetId: string;
}): Promise<ContentOpsDraftVersionPayload> {
  const nextMediaAssets = Array.from(new Set([...mediaAssetIds, assetId]));
  return apiClient.post<ContentOpsDraftVersionPayload>(`/content-ops/drafts/${draftId}/versions/`, {
    caption,
    platform_overrides: { platform: channel },
    media_assets: nextMediaAssets,
    change_note: 'Attached media asset from Content Ops workspace.',
  });
}

export async function createContentOpsBrief({
  workspaceId,
  workspaceName,
  campaignTheme,
  audience,
  offer,
  tone,
  requiredTerms,
  blockedTerms,
  dateStart,
  dateEnd,
}: ContentOpsBriefCreateRequest): Promise<ContentOpsBrief> {
  const brief = await apiClient.post<BackendBrief>('/content-ops/briefs/', {
    workspace: workspaceId,
    campaign_theme: campaignTheme.trim(),
    audience: audience.trim(),
    offer: offer.trim(),
    tone: tone.trim(),
    required_terms: requiredTerms,
    blocked_terms: blockedTerms,
    date_start: dateStart || null,
    date_end: dateEnd || null,
    status: 'active',
  });
  return mapBrief(brief, workspaceName);
}

export async function createContentOpsDraftWithVersion({
  workspaceId,
  briefId,
  title,
  channel,
  caption,
}: ContentOpsDraftCreateRequest): Promise<ContentOpsDraft> {
  const draft = await apiClient.post<BackendDraft>('/content-ops/drafts/', {
    workspace: workspaceId,
    brief: briefId,
    title: title.trim(),
  });
  const version = await apiClient.post<BackendDraftVersion>(
    `/content-ops/drafts/${draft.id}/versions/`,
    {
      caption: caption.trim(),
      platform_overrides: { platform: channel },
      media_assets: [],
      change_note: 'Created draft caption from Content Ops workspace.',
    },
  );
  return mapDraft({ ...draft, state: 'generated' }, version);
}

export async function requestContentOpsCaptionGeneration({
  briefId,
  candidateCount,
  platforms,
  toneOverride,
  regionalAgentProfileId,
}: ContentOpsCaptionGenerationRequest): Promise<ContentOpsGenerationJob> {
  const job = await apiClient.post<BackendGenerationJob>(
    `/content-ops/briefs/${briefId}/captions/generate/`,
    {
      candidate_count: candidateCount,
      platforms,
      tone_override: toneOverride?.trim() ?? '',
      regional_agent_profile_id: regionalAgentProfileId || null,
    },
  );
  return mapGenerationJob(job);
}

type BackendRegionalAgent = {
  id: string;
  workspace: string;
  name: string;
  region: string;
  locale: string;
  language: string;
  timezone: string;
  is_active: boolean;
};

function mapRegionalAgent(agent: BackendRegionalAgent): ContentOpsRegionalAgent {
  return {
    id: agent.id,
    workspaceId: agent.workspace,
    name: agent.name,
    region: agent.region === 'peru_latam' ? 'peru_latam' : 'caribbean',
    locale: agent.locale,
    language: agent.language,
    timezone: agent.timezone,
    isActive: agent.is_active,
  };
}

export async function listContentOpsWorkspaces(
  signal?: AbortSignal,
): Promise<ContentOpsWorkspaceSummary[]> {
  const workspaces = await getAllResults<BackendWorkspace>('/content-ops/workspaces/', signal);
  return workspaces.map((workspace) => ({
    id: workspace.id,
    name: workspace.name,
    timezone: workspace.timezone || 'America/Jamaica',
  }));
}

export async function listContentOpsRegionalAgents(
  workspaceId?: string,
  signal?: AbortSignal,
): Promise<ContentOpsRegionalAgent[]> {
  const path = workspaceId
    ? appendQueryParams('/content-ops/regional-agents/', { workspace_id: workspaceId })
    : '/content-ops/regional-agents/';
  const agents = await getAllResults<BackendRegionalAgent>(path, signal);
  return agents.map(mapRegionalAgent);
}

export async function createContentOpsRegionalAgent({
  workspaceId,
  name,
  region,
  locale,
  language,
  timezone,
}: ContentOpsRegionalAgentCreateRequest): Promise<ContentOpsRegionalAgent> {
  const agent = await apiClient.post<BackendRegionalAgent>('/content-ops/regional-agents/', {
    workspace: workspaceId,
    name: name.trim(),
    region,
    locale: locale?.trim() || '',
    language: language?.trim() || '',
    timezone: timezone?.trim() || '',
  });
  return mapRegionalAgent(agent);
}

export async function requestContentOpsImageGeneration({
  workspaceId,
  prompt,
  count,
  size,
  regionalAgentProfileId,
}: ContentOpsImageGenerationRequest): Promise<ContentOpsGenerationJob> {
  const job = await apiClient.post<BackendGenerationJob>(
    `/content-ops/workspaces/${workspaceId}/images/generate/`,
    {
      prompt: prompt.trim(),
      count: count ?? 1,
      size: size?.trim() || '1024x1024',
      regional_agent_profile_id: regionalAgentProfileId || null,
    },
  );
  return mapGenerationJob(job);
}

export async function cancelContentOpsGenerationJob(
  jobId: string,
): Promise<ContentOpsGenerationJob> {
  const job = await apiClient.post<BackendGenerationJob>(
    `/content-ops/generation-jobs/${jobId}/cancel/`,
    {},
  );
  return mapGenerationJob(job);
}

export async function submitContentOpsInternalReview(
  draftId: string,
): Promise<ContentOpsApprovalRequestPayload> {
  return apiClient.post<ContentOpsApprovalRequestPayload>(
    `/content-ops/drafts/${draftId}/submit-internal-review/`,
    {},
  );
}

export async function submitContentOpsClientReview(
  draftId: string,
): Promise<ContentOpsApprovalRequestPayload> {
  return apiClient.post<ContentOpsApprovalRequestPayload>(
    `/content-ops/drafts/${draftId}/submit-client-review/`,
    {},
  );
}

export async function decideContentOpsApproval({
  approvalId,
  decision,
  comment,
}: {
  approvalId: string;
  decision: ContentOpsApprovalDecisionPayload['decision'];
  comment?: string;
}): Promise<ContentOpsApprovalDecisionPayload> {
  return apiClient.post<ContentOpsApprovalDecisionPayload>(
    `/content-ops/approval-requests/${approvalId}/decisions/`,
    {
      decision,
      comment: comment?.trim() ?? '',
    },
  );
}

export async function scheduleContentOpsDraft({
  draftId,
  scheduledAt,
  timezone,
}: {
  draftId: string;
  scheduledAt: string;
  timezone: string;
}): Promise<ContentOpsSchedulePayload> {
  return apiClient.post<ContentOpsSchedulePayload>(`/content-ops/drafts/${draftId}/schedule/`, {
    scheduled_at: scheduledAt,
    timezone,
  });
}

export async function retryContentOpsPublishAttempt(
  attemptId: string,
): Promise<ContentOpsPublishAttemptRetryPayload> {
  return apiClient.post<ContentOpsPublishAttemptRetryPayload>(
    `/content-ops/publishing/attempts/${attemptId}/retry/`,
    {},
  );
}

export type ContentOpsPublishTarget = {
  type: ContentOpsChannel;
  page_id?: string;
  ig_user_id?: string;
};

export type ContentOpsPublishNowResult = {
  schedule: ContentOpsSchedulePayload;
  attempts: ContentOpsPublishAttemptPayload[];
  dispatch: {
    scanned: number;
    schedules_dispatched?: number;
    attempts_created: number;
    attempts_existing: number;
    attempts_blocked: number;
  };
  approval_mode: string;
};

export async function publishContentOpsDraftNow({
  draftId,
  channels,
}: {
  draftId: string;
  channels?: ContentOpsPublishTarget[];
}): Promise<ContentOpsPublishNowResult> {
  return apiClient.post<ContentOpsPublishNowResult>(
    `/content-ops/drafts/${draftId}/publish-now/`,
    channels && channels.length > 0 ? { channels } : {},
  );
}

export type ContentOpsPublishingReadiness = {
  channel: ContentOpsChannel;
  label: string;
  ready: boolean;
  reason: string | null;
};

export async function fetchContentOpsPublishingReadiness(
  signal?: AbortSignal,
): Promise<ContentOpsPublishingReadiness[]> {
  const payload = await apiClient.get<Record<string, BackendReadinessAxis>>(
    '/content-ops/readiness/',
    { signal },
  );
  const axisFor = (key: string): BackendReadinessAxis => payload?.[key] ?? {};
  const facebook = axisFor('facebook_page_publishing');
  const instagram = axisFor('instagram_publishing');
  return [
    {
      channel: 'facebook_page',
      label: channelLabel('facebook_page'),
      ready: facebook.state === 'ready',
      reason: facebook.state === 'ready' ? null : facebook.reason ?? 'not_ready',
    },
    {
      channel: 'instagram',
      label: channelLabel('instagram'),
      ready: instagram.state === 'ready',
      reason: instagram.state === 'ready' ? null : instagram.reason ?? 'not_ready',
    },
  ];
}

export async function exportContentOpsPlan({
  workspaceId,
  states = [],
}: {
  workspaceId: string;
  states?: string[];
}): Promise<ContentOpsContentPlanExportPayload> {
  return apiClient.post<ContentOpsContentPlanExportPayload>('/content-ops/exports/content-plan/', {
    workspace_id: workspaceId,
    states,
  });
}

export async function listContentOpsExportArtifacts(
  workspaceId: string,
  signal?: AbortSignal,
): Promise<ContentOpsExportArtifact[]> {
  return getResults<ContentOpsExportArtifact>(
    appendQueryParams('/content-ops/exports/', {
      workspace_id: workspaceId,
      export_type: 'content_plan',
    }),
    signal,
  );
}

export async function createContentOpsExportArtifact({
  workspaceId,
  states = [],
}: {
  workspaceId: string;
  states?: string[];
}): Promise<ContentOpsExportArtifact> {
  return apiClient.post<ContentOpsExportArtifact>('/content-ops/exports/', {
    workspace_id: workspaceId,
    export_type: 'content_plan',
    export_format: 'json',
    states,
  });
}

export async function downloadContentOpsExportArtifact(
  artifact: Pick<ContentOpsExportArtifact, 'id' | 'download_url'>,
): Promise<{ blob: Blob; filename: string; contentType: string }> {
  return apiClient.download(contentOpsArtifactDownloadPath(artifact));
}

export async function fetchContentOpsReportOverview(
  workspaceId: string,
  signal?: AbortSignal,
): Promise<ContentOpsReportOverviewPayload> {
  return apiClient.get<ContentOpsReportOverviewPayload>(
    appendQueryParams('/content-ops/reports/overview/', { workspace_id: workspaceId }),
    { signal },
  );
}

export async function fetchContentOpsReportPosts(
  workspaceId: string,
  signal?: AbortSignal,
): Promise<ContentOpsReportPostsPayload> {
  return apiClient.get<ContentOpsReportPostsPayload>(
    appendQueryParams('/content-ops/reports/posts/', { workspace_id: workspaceId }),
    { signal },
  );
}

export function buildContentOpsExportFilename(
  workspaceName: string,
  exportedAt = new Date(),
): string {
  const workspaceSlug =
    workspaceName
      .trim()
      .toLowerCase()
      .replace(/[^a-z0-9]+/g, '-')
      .replace(/^-+|-+$/g, '') || 'workspace';
  const dateStamp = exportedAt.toISOString().slice(0, 10);
  return `content-plan-${workspaceSlug}-${dateStamp}.json`;
}

function contentOpsArtifactDownloadPath(
  artifact: Pick<ContentOpsExportArtifact, 'id' | 'download_url'>,
): string {
  const downloadUrl = artifact.download_url?.trim();
  if (!downloadUrl) {
    return `/content-ops/exports/${artifact.id}/download/`;
  }
  if (downloadUrl.startsWith('/api/')) {
    return downloadUrl.replace(/^\/api\//, '/');
  }
  return downloadUrl;
}

export async function fetchContentOpsWorkspace(
  signal?: AbortSignal,
): Promise<ContentOpsWorkspaceLoadResult> {
  try {
    const readinessPayload = await apiClient.get<Record<string, BackendReadinessAxis>>(
      '/content-ops/readiness/',
      { signal },
    );
    const workspaces = await getResults<BackendWorkspace>('/content-ops/workspaces/', signal);
    const workspace = workspaces[0];
    if (!workspace) {
      return {
        workspace: contentOpsMockWorkspace,
        source: 'mock',
        warning: 'No Content Ops workspaces have been created yet.',
      };
    }

    const [briefs, jobs, drafts, attempts, schedules] = await Promise.all([
      getResults<BackendBrief>(
        appendQueryParams('/content-ops/briefs/', { workspace_id: workspace.id }),
        signal,
      ),
      getResults<BackendGenerationJob>(
        appendQueryParams('/content-ops/generation-jobs/', { workspace_id: workspace.id }),
        signal,
      ),
      getResults<BackendDraft>(
        appendQueryParams('/content-ops/drafts/', { workspace_id: workspace.id }),
        signal,
      ),
      getResults<BackendPublishAttempt>('/content-ops/publishing/attempts/', signal),
      getResults<BackendSchedule>('/content-ops/schedules/', signal),
    ]);
    const versions = await loadActiveVersions(drafts, signal);
    const draftIds = new Set(drafts.map((draft) => draft.id));

    return {
      workspace: {
        id: workspace.id,
        name: workspace.name,
        timezone: workspace.timezone || 'America/Jamaica',
        calendarWindow: calendarWindow(briefs[0]),
        readiness: mapReadiness(readinessPayload),
        brief: mapBrief(briefs[0], workspace.name),
        generationJobs: jobs.map(mapGenerationJob),
        drafts: drafts.map((draft) => mapDraft(draft, versions.get(String(draft.active_version)))),
        queue: attempts
          .filter((attempt) => draftIds.has(attempt.draft))
          .map((attempt) => mapQueueItem(attempt, drafts, schedules, workspace.name)),
      },
      source: 'api',
    };
  } catch (error) {
    return {
      workspace: contentOpsMockWorkspace,
      source: 'mock',
      warning: error instanceof Error ? error.message : 'Content Ops API is unavailable.',
    };
  }
}

async function getResults<T>(path: string, signal?: AbortSignal): Promise<T[]> {
  const payload = await apiClient.get<T[] | Paginated<T>>(path, { signal });
  return Array.isArray(payload) ? payload : Array.isArray(payload.results) ? payload.results : [];
}

async function getAllResults<T>(path: string, signal?: AbortSignal): Promise<T[]> {
  const items: T[] = [];
  // Follow DRF page pagination; bounded to guard against a runaway loop.
  for (let page = 1; page <= 50; page += 1) {
    const separator = path.includes('?') ? '&' : '?';
    const payload = await apiClient.get<T[] | (Paginated<T> & { next?: string | null })>(
      `${path}${separator}page=${page}`,
      { signal },
    );
    if (Array.isArray(payload)) {
      items.push(...payload);
      break;
    }
    items.push(...(payload.results ?? []));
    if (!payload.next) {
      break;
    }
  }
  return items;
}

async function loadActiveVersions(
  drafts: BackendDraft[],
  signal?: AbortSignal,
): Promise<Map<string, BackendDraftVersion>> {
  const versionLists = await Promise.all(
    drafts.map(async (draft) => {
      if (!draft.active_version) {
        return [];
      }
      const payload = await apiClient.get<{ results?: BackendDraftVersion[] }>(
        `/content-ops/drafts/${draft.id}/versions/`,
        { signal },
      );
      return payload.results ?? [];
    }),
  );
  const versions = new Map<string, BackendDraftVersion>();
  versionLists.flat().forEach((version) => versions.set(version.id, version));
  return versions;
}

function mapReadiness(payload: Record<string, BackendReadinessAxis>): ContentOpsReadinessAxis[] {
  return READINESS_IDS.map((id) => {
    const axis = payload[id] ?? {};
    const state = axis.state || 'blocked';
    return {
      id,
      label: READINESS_LABELS[id],
      state,
      reason: axis.reason ?? axis.dataset_live_reason ?? null,
      actionLabel: readinessActionLabel(state),
      details: readinessDetails(id, axis),
    };
  });
}

function readinessActionLabel(value?: string | null): string {
  if (value === 'ready' || value === 'connected' || value === 'complete') {
    return 'Ready';
  }
  return 'Review';
}

function readinessDetails(id: ContentOpsReadinessAxis['id'], axis: BackendReadinessAxis): string[] {
  const details: string[] = [];
  if (id === 'meta_auth') {
    appendCountDetail(details, axis.usable_credential_count, 'usable credential');
    appendCountDetail(details, axis.active_page_connection_count, 'active Page connection');
  }
  if (id === 'page_selection') {
    appendCountDetail(details, axis.selected_page_count, 'selected Page');
    appendCountDetail(details, axis.page_count, 'available Page');
    if (axis.default_page_id) {
      details.push(`Default Page ${axis.default_page_id}`);
    }
  }
  if (id === 'instagram_linkage') {
    appendCountDetail(details, axis.linked_count, 'linked Instagram account');
  }
  if (id === 'facebook_page_publishing' || id === 'instagram_publishing') {
    appendCountDetail(details, axis.identity_count, 'selected publishing identity');
    appendListDetail(details, 'Missing', axis.missing_permissions);
    appendListDetail(details, 'Required', axis.required_permissions);
    appendListDetail(details, 'Upstream blockers', axis.upstream_blockers);
    appendListDetail(details, 'Identity blockers', axis.identity_blockers);
  }
  if (id === 'reporting_readiness' && axis.dataset_live_reason) {
    details.push(`Dataset live reason: ${axis.dataset_live_reason}`);
  }
  return details;
}

function mapBrief(brief: BackendBrief | undefined, workspaceName: string): ContentOpsBrief {
  if (!brief) {
    return {
      id: 'empty-brief',
      title: 'No active brief',
      client: workspaceName,
      audience: 'No audience defined',
      offer: 'No offer defined',
      tone: 'No tone defined',
      requiredTerms: [],
      blockedTerms: [],
      dateRange: 'No date range',
    };
  }
  return {
    id: brief.id,
    title: brief.campaign_theme || 'Untitled brief',
    client: workspaceName,
    audience: brief.audience || 'No audience defined',
    offer: brief.offer || 'No offer defined',
    tone: brief.tone || 'No tone defined',
    requiredTerms: stringList(brief.required_terms),
    blockedTerms: stringList(brief.blocked_terms),
    dateRange: dateRange(brief.date_start, brief.date_end),
  };
}

function mapGenerationJob(job: BackendGenerationJob): ContentOpsGenerationJob {
  const candidates = mapGenerationCandidates(job);
  const requestedCandidateCount = Number(
    job.prompt_policy_result?.candidate_count ?? job.result_summary?.candidate_count ?? 0,
  );
  const candidateCount =
    Number.isFinite(requestedCandidateCount) && requestedCandidateCount > 0
      ? requestedCandidateCount
      : candidates.length;
  return {
    id: job.id,
    label: stateLabel(job.job_type || 'generation job'),
    status: normalizeJobStatus(job.status),
    provider: job.provider === 'disabled' ? 'disabled' : 'mock',
    candidateCount,
    candidates,
  };
}

function mapGenerationCandidates(job: BackendGenerationJob): ContentOpsGeneratedCandidate[] {
  const rawCandidates = job.result_summary?.candidates;
  if (!Array.isArray(rawCandidates)) {
    return [];
  }
  return rawCandidates
    .map((candidate, index) => mapGenerationCandidate(job.id, candidate, index))
    .filter((candidate): candidate is ContentOpsGeneratedCandidate => Boolean(candidate));
}

function mapGenerationCandidate(
  jobId: string,
  value: unknown,
  index: number,
): ContentOpsGeneratedCandidate | null {
  if (!isRecord(value)) {
    return null;
  }
  const caption = stringValue(value.caption);
  if (!caption) {
    return null;
  }
  const platformOverrides = isRecord(value.platform_overrides) ? value.platform_overrides : {};
  const channel = normalizeChannel(value.channel ?? value.platform ?? platformOverrides.platform);
  const title =
    stringValue(value.title) ||
    stringValue(value.draft_title) ||
    `${channelLabel(channel)} caption option ${index + 1}`;
  const qualityScore = Number(value.quality_score ?? platformOverrides.quality_score);
  return {
    id: stringValue(value.id) || `${jobId}-candidate-${index + 1}`,
    title,
    channel,
    caption,
    hashtags: stringList(value.hashtags ?? platformOverrides.hashtags),
    cta: stringValue(value.cta ?? platformOverrides.cta),
    altText: stringValue(value.alt_text ?? platformOverrides.alt_text),
    riskFlags: stringList(value.risk_flags ?? platformOverrides.risk_flags),
    qualityScore: Number.isFinite(qualityScore) ? qualityScore : null,
  };
}

function mapDraft(draft: BackendDraft, version?: BackendDraftVersion): ContentOpsDraft {
  return {
    id: draft.id,
    title: draft.title || 'Untitled draft',
    state: draft.state || 'draft',
    activeVersionLabel: version?.version_number ? `v${version.version_number}` : 'No version',
    scheduledAt: formatDateTime(draft.schedule_summary?.scheduled_at ?? null),
    owner: draft.created_by ? 'Assigned user' : 'Unassigned',
    approvalSummary: mapApprovalSummary(draft.approval_summary),
    variants: version ? [mapVariant(version, draft.approval_summary)] : [],
  };
}

function mapVariant(
  version: BackendDraftVersion,
  approvalSummary?: Record<string, BackendApprovalSummaryItem> | null,
): ContentOpsDraftVariant {
  const platform = normalizeChannel(version.platform_overrides?.platform);
  const mediaAssetIds = Array.isArray(version.media_assets) ? version.media_assets : [];
  return {
    versionId: version.id,
    channel: platform,
    label: channelLabel(platform),
    caption: version.caption || 'No caption yet',
    mediaAssetIds,
    mediaLabel: mediaLabel(mediaAssetIds),
    approvalStatus: approvalStatusForVersion(version.id, approvalSummary),
  };
}

function mapQueueItem(
  attempt: BackendPublishAttempt,
  drafts: BackendDraft[],
  schedules: BackendSchedule[],
  workspaceName: string,
): ContentOpsQueueItem {
  const draft = drafts.find((item) => item.id === attempt.draft);
  const schedule = schedules.find((item) => item.id === attempt.schedule);
  return {
    id: attempt.id,
    draftTitle: draft?.title || 'Untitled draft',
    client: workspaceName,
    channel: normalizeChannel(attempt.channel),
    scheduledAt: formatDateTime(schedule?.scheduled_at ?? null) ?? 'Not scheduled',
    state: attempt.state || 'queued',
    blocker:
      attempt.failure_detail_safe ||
      attempt.failure_code ||
      (attempt.next_retry_at ? `Retry due ${formatDateTime(attempt.next_retry_at)}` : null),
  };
}

function normalizeChannel(value: unknown): ContentOpsChannel {
  return value === 'instagram' ? 'instagram' : 'facebook_page';
}

function normalizeJobStatus(value?: string): ContentOpsGenerationJob['status'] {
  if (value === 'running' || value === 'succeeded' || value === 'failed' || value === 'cancelled') {
    return value;
  }
  return 'queued';
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null && !Array.isArray(value);
}

function stringList(value: unknown): string[] {
  return Array.isArray(value) ? value.map((item) => String(item)) : [];
}

function stringValue(value: unknown): string {
  return typeof value === 'string' ? value.trim() : '';
}

function appendCountDetail(details: string[], value: number | undefined, label: string): void {
  if (typeof value !== 'number') {
    return;
  }
  details.push(`${value} ${label}${value === 1 ? '' : 's'}`);
}

function appendListDetail(details: string[], label: string, value: unknown): void {
  const items = stringList(value);
  if (items.length) {
    details.push(`${label}: ${items.join(', ')}`);
  }
}

function approvalStatusForVersion(
  versionId: string,
  approvalSummary?: Record<string, BackendApprovalSummaryItem> | null,
): string {
  const client = approvalSummary?.client;
  if (client?.version_id === versionId && client.status) {
    return `client_${client.status}`;
  }
  const internal = approvalSummary?.internal;
  if (internal?.version_id === versionId && internal.status) {
    return `internal_${internal.status}`;
  }
  return 'approval_not_requested';
}

function mapApprovalSummary(
  approvalSummary?: Record<string, BackendApprovalSummaryItem> | null,
): ContentOpsApprovalSummary {
  const summary: ContentOpsApprovalSummary = {};
  const internal = approvalSummary?.internal;
  if (internal?.id && internal.status && internal.version_id) {
    summary.internal = {
      id: internal.id,
      status: internal.status,
      versionId: internal.version_id,
    };
  }
  const client = approvalSummary?.client;
  if (client?.id && client.status && client.version_id) {
    summary.client = {
      id: client.id,
      status: client.status,
      versionId: client.version_id,
    };
  }
  return summary;
}

function calendarWindow(brief: BackendBrief | undefined): string {
  if (!brief) {
    return 'No active calendar window';
  }
  return dateRange(brief.date_start, brief.date_end);
}

function dateRange(start?: string | null, end?: string | null): string {
  if (start && end) {
    return `${formatDate(start)}-${formatDate(end)}`;
  }
  if (start) {
    return `From ${formatDate(start)}`;
  }
  if (end) {
    return `Until ${formatDate(end)}`;
  }
  return 'No date range';
}

function formatDate(value: string): string {
  const date = new Date(value);
  return Number.isNaN(date.getTime())
    ? value
    : date.toLocaleDateString(undefined, { month: 'short', day: 'numeric', year: 'numeric' });
}

function formatDateTime(value?: string | null): string | null {
  if (!value) {
    return null;
  }
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return value;
  }
  return date.toLocaleString(undefined, {
    weekday: 'short',
    month: 'short',
    day: 'numeric',
    hour: 'numeric',
    minute: '2-digit',
  });
}

function mediaLabel(mediaAssets?: string[]): string {
  const count = mediaAssets?.length ?? 0;
  if (!count) {
    return 'No media attached';
  }
  return count === 1 ? '1 attached asset' : `${count} attached assets`;
}

function stateLabel(value: string): string {
  return value
    .split('_')
    .map((token) => `${token.charAt(0).toUpperCase()}${token.slice(1)}`)
    .join(' ');
}
