export type ContentOpsChannel = 'facebook_page' | 'instagram';

export type ContentOpsReadinessTone = 'ready' | 'blocked' | 'partial';

export type ContentOpsReadinessAxis = {
  id:
    | 'meta_auth'
    | 'page_selection'
    | 'instagram_linkage'
    | 'facebook_page_publishing'
    | 'instagram_publishing'
    | 'reporting_readiness';
  label: string;
  state: string;
  reason: string | null;
  actionLabel: string;
  details?: string[];
};

export type ContentOpsBrief = {
  id: string;
  title: string;
  client: string;
  audience: string;
  offer: string;
  tone: string;
  requiredTerms: string[];
  blockedTerms: string[];
  dateRange: string;
};

export type ContentOpsDraftVariant = {
  versionId: string | null;
  channel: ContentOpsChannel;
  label: string;
  caption: string;
  mediaAssetIds: string[];
  mediaLabel: string;
  approvalStatus: string;
};

export type ContentOpsApprovalSummaryItem = {
  id: string;
  status: string;
  versionId: string;
};

export type ContentOpsApprovalSummary = {
  internal?: ContentOpsApprovalSummaryItem;
  client?: ContentOpsApprovalSummaryItem;
};

export type ContentOpsDraft = {
  id: string;
  title: string;
  state: string;
  activeVersionLabel: string;
  scheduledAt: string | null;
  owner: string;
  approvalSummary: ContentOpsApprovalSummary;
  variants: ContentOpsDraftVariant[];
};

export type ContentOpsQueueItem = {
  id: string;
  draftTitle: string;
  client: string;
  channel: ContentOpsChannel;
  scheduledAt: string;
  state: string;
  blocker: string | null;
};

export type ContentOpsGenerationJob = {
  id: string;
  label: string;
  status: 'queued' | 'running' | 'succeeded' | 'failed' | 'cancelled';
  provider: 'disabled' | 'mock';
  candidateCount: number;
  candidates: ContentOpsGeneratedCandidate[];
};

export type ContentOpsGeneratedCandidate = {
  id: string;
  title: string;
  channel: ContentOpsChannel;
  caption: string;
  hashtags: string[];
  cta: string;
  altText: string;
  riskFlags: string[];
  qualityScore: number | null;
};

export type ContentOpsMockWorkspace = {
  id: string | null;
  name: string;
  timezone: string;
  calendarWindow: string;
  readiness: ContentOpsReadinessAxis[];
  brief: ContentOpsBrief;
  drafts: ContentOpsDraft[];
  queue: ContentOpsQueueItem[];
  generationJobs: ContentOpsGenerationJob[];
};

export const contentOpsMockWorkspace: ContentOpsMockWorkspace = {
  id: null,
  name: 'June Meta content plan',
  timezone: 'America/Jamaica',
  calendarWindow: 'June 10-24, 2026',
  readiness: [
    {
      id: 'meta_auth',
      label: 'Meta auth',
      state: 'ready',
      reason: null,
      actionLabel: 'Connected',
    },
    {
      id: 'page_selection',
      label: 'Page selection',
      state: 'ready',
      reason: null,
      actionLabel: 'Selected',
    },
    {
      id: 'instagram_linkage',
      label: 'Instagram linkage',
      state: 'partial',
      reason: 'One selected Page has no linked professional account.',
      actionLabel: 'Review linkage',
    },
    {
      id: 'facebook_page_publishing',
      label: 'Facebook publishing',
      state: 'blocked',
      reason: 'pages_manage_posts App Review evidence is not complete.',
      actionLabel: 'Evidence needed',
    },
    {
      id: 'instagram_publishing',
      label: 'Instagram publishing',
      state: 'blocked',
      reason: 'Instagram publishing permission family is not confirmed.',
      actionLabel: 'Permission review',
    },
    {
      id: 'reporting_readiness',
      label: 'Reporting readiness',
      state: 'ready',
      reason: null,
      actionLabel: 'Aggregate snapshots',
    },
  ],
  brief: {
    id: 'brief-june',
    title: 'Mid-month awareness push',
    client: 'North Coast Retail Group',
    audience: 'Young professionals planning weekend shopping trips',
    offer: 'Limited-time bundled savings across home and lifestyle categories',
    tone: 'Clear, premium, practical',
    requiredTerms: ['Terms apply', 'Available while stocks last'],
    blockedTerms: ['guaranteed', 'free money'],
    dateRange: 'June 10-24, 2026',
  },
  drafts: [
    {
      id: 'draft-weekend-bundle',
      title: 'Weekend bundle announcement',
      state: 'client_review',
      activeVersionLabel: 'v3',
      scheduledAt: 'Fri Jun 12, 9:30 AM',
      owner: 'A. Strategist',
      approvalSummary: {
        internal: {
          id: 'approval-weekend-internal',
          status: 'approved',
          versionId: 'version-weekend-facebook',
        },
        client: {
          id: 'approval-weekend-client',
          status: 'pending',
          versionId: 'version-weekend-instagram',
        },
      },
      variants: [
        {
          versionId: 'version-weekend-facebook',
          channel: 'facebook_page',
          label: 'Facebook Page',
          caption:
            'Weekend plans, simplified. Shop bundled home and lifestyle picks for a cleaner, faster checkout. Terms apply.',
          mediaAssetIds: [],
          mediaLabel: 'Landscape product collage',
          approvalStatus: 'internal_approved',
        },
        {
          versionId: 'version-weekend-instagram',
          channel: 'instagram',
          label: 'Instagram',
          caption:
            'Weekend picks are ready. Browse the bundle edit and plan your stop before Friday. Terms apply. #NorthCoastFinds',
          mediaAssetIds: [],
          mediaLabel: 'Square carousel cover',
          approvalStatus: 'client_review',
        },
      ],
    },
    {
      id: 'draft-payday-reminder',
      title: 'Payday reminder',
      state: 'generated',
      activeVersionLabel: 'v1',
      scheduledAt: null,
      owner: 'J. Content Lead',
      approvalSummary: {},
      variants: [
        {
          versionId: 'version-payday-facebook',
          channel: 'facebook_page',
          label: 'Facebook Page',
          caption:
            'A practical payday checklist for the home upgrades you have been putting off. Available while stocks last.',
          mediaAssetIds: [],
          mediaLabel: 'Static checklist graphic',
          approvalStatus: 'internal_approved',
        },
        {
          versionId: 'version-payday-instagram',
          channel: 'instagram',
          label: 'Instagram',
          caption:
            'Payday checklist: refresh the essentials, compare your bundle, keep the weekend simple.',
          mediaAssetIds: [],
          mediaLabel: 'Portrait story-safe graphic',
          approvalStatus: 'internal_approved',
        },
      ],
    },
  ],
  queue: [
    {
      id: 'queue-facebook-1',
      draftTitle: 'Weekend bundle announcement',
      client: 'North Coast Retail Group',
      channel: 'facebook_page',
      scheduledAt: 'Fri Jun 12, 9:30 AM',
      state: 'blocked',
      blocker: 'Facebook publishing permission evidence needed',
    },
    {
      id: 'queue-instagram-1',
      draftTitle: 'Weekend bundle announcement',
      client: 'North Coast Retail Group',
      channel: 'instagram',
      scheduledAt: 'Fri Jun 12, 9:30 AM',
      state: 'blocked',
      blocker: 'Instagram permission family not confirmed',
    },
    {
      id: 'queue-facebook-2',
      draftTitle: 'Payday reminder',
      client: 'North Coast Retail Group',
      channel: 'facebook_page',
      scheduledAt: 'Wed Jun 17, 8:00 AM',
      state: 'failed_retryable',
      blocker: null,
    },
  ],
  generationJobs: [
    {
      id: 'job-caption-1',
      label: 'Caption candidates',
      status: 'succeeded',
      provider: 'mock',
      candidateCount: 5,
      candidates: [
        {
          id: 'candidate-weekend-facebook',
          title: 'Mid-month awareness push - Facebook Page option',
          channel: 'facebook_page',
          caption:
            'Weekend plans, simplified. Shop bundled home and lifestyle picks before Friday. Terms apply.',
          hashtags: [],
          cta: 'Shop the bundle edit',
          altText: 'Lifestyle product bundle arranged for a weekend shopping post.',
          riskFlags: [],
          qualityScore: 0.92,
        },
        {
          id: 'candidate-weekend-instagram',
          title: 'Mid-month awareness push - Instagram option',
          channel: 'instagram',
          caption:
            'Weekend picks are ready. Browse the bundle edit and plan your stop before Friday. Terms apply. #NorthCoastFinds',
          hashtags: ['NorthCoastFinds'],
          cta: 'Plan your stop',
          altText: 'Square carousel cover with home and lifestyle bundle items.',
          riskFlags: [],
          qualityScore: 0.89,
        },
      ],
    },
    {
      id: 'job-graphic-1',
      label: 'Graphic batch',
      status: 'queued',
      provider: 'disabled',
      candidateCount: 0,
      candidates: [],
    },
  ],
};

export function channelLabel(channel: ContentOpsChannel): string {
  return channel === 'facebook_page' ? 'Facebook Page' : 'Instagram';
}
