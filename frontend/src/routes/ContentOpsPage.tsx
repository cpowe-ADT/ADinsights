import { type FormEvent, useEffect, useState } from 'react';
import { Link } from 'react-router-dom';

import { useAuth } from '../auth/AuthContext';
import DashboardState from '../components/DashboardState';
import {
  buildContentOpsExportFilename,
  cancelContentOpsGenerationJob,
  channelLabel,
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
  listContentOpsAssets,
  requestContentOpsCaptionGeneration,
  retryContentOpsPublishAttempt,
  scheduleContentOpsDraft,
  submitContentOpsClientReview,
  submitContentOpsInternalReview,
  type ContentOpsApprovalDecisionPayload,
  type ContentOpsApprovalRequestPayload,
  type ContentOpsExportArtifact,
  type ContentOpsReportOverviewPayload,
  type ContentOpsReportPost,
  type ContentOpsSchedulePayload,
  listContentOpsExportArtifacts,
  uploadContentOpsAsset,
  type ContentOpsUploadedAsset,
} from '../lib/contentOps';
import { saveBlobAsFile } from '../lib/download';
import { formatNumber } from '../lib/format';
import {
  contentOpsMockWorkspace,
  type ContentOpsChannel,
  type ContentOpsDraft,
  type ContentOpsDraftVariant,
  type ContentOpsGeneratedCandidate,
  type ContentOpsGenerationJob,
  type ContentOpsMockWorkspace,
  type ContentOpsQueueItem,
  type ContentOpsReadinessAxis,
} from '../lib/contentOpsMock';
import { canAccessCreatorUi } from '../lib/rbac';
import '../styles/dashboard.css';
import '../styles/contentOps.css';

const readinessTone = (state: ContentOpsReadinessAxis['state']) => {
  if (state === 'ready' || state === 'connected' || state === 'complete') {
    return 'ready';
  }
  if (state === 'partial' || state === 'page_insights_only') {
    return 'partial';
  }
  return 'blocked';
};

const livePublishingReadinessSummary = (readiness: ContentOpsReadinessAxis[]) => {
  const publishingAxes = readiness.filter((axis) =>
    ['facebook_page_publishing', 'instagram_publishing'].includes(axis.id),
  );
  const blockedAxes = publishingAxes.filter((axis) => readinessTone(axis.state) === 'blocked');
  const partialAxes = publishingAxes.filter((axis) => readinessTone(axis.state) === 'partial');
  if (blockedAxes.length === 0 && partialAxes.length === 0 && publishingAxes.length > 0) {
    return {
      tone: 'ready',
      title: 'Live publishing gates ready',
      detail: 'Facebook and Instagram publishing readiness are clear for this workspace.',
    };
  }
  const blockers = [...blockedAxes, ...partialAxes];
  return {
    tone: blockedAxes.length ? 'blocked' : 'partial',
    title: blockedAxes.length ? 'Live publishing gates blocked' : 'Live publishing gates partial',
    detail:
      blockers.map((axis) => `${axis.label}: ${axis.reason ?? axis.actionLabel}`).join(' · ') ||
      'Publishing readiness is still being checked.',
  };
};

const queueTone = (state: ContentOpsQueueItem['state']) => {
  if (
    state === 'queued' ||
    state === 'preflight' ||
    state === 'container_creating' ||
    state === 'container_pending' ||
    state === 'container_ready' ||
    state === 'publishing'
  ) {
    return 'queued';
  }
  if (state === 'published') {
    return 'ready';
  }
  if (state === 'failed_retryable') {
    return 'retry';
  }
  return 'blocked';
};

const queueDetailText = (item: ContentOpsQueueItem) => {
  if (item.blocker) {
    return item.blocker;
  }
  switch (item.state) {
    case 'queued':
      return 'Ready for dispatcher';
    case 'preflight':
      return 'Running preflight checks';
    case 'container_creating':
      return 'Creating Instagram media container';
    case 'container_pending':
      return 'Waiting for Instagram media container';
    case 'container_ready':
      return 'Instagram media container ready';
    case 'publishing':
      return 'Publishing through provider boundary';
    case 'published':
      return 'Published';
    case 'failed_retryable':
      return 'Retryable failure';
    case 'failed_terminal':
      return 'Terminal failure';
    case 'container_expired':
      return 'Instagram media container expired';
    case 'cancelled':
      return 'Cancelled';
    case 'blocked':
      return 'Blocked';
    default:
      return 'No detail available';
  }
};

const stateLabel = (value: string) =>
  value
    .split('_')
    .map((token) => `${token.charAt(0).toUpperCase()}${token.slice(1)}`)
    .join(' ');

const fileSummary = (file: File | null) => {
  if (!file) {
    return 'No file selected';
  }
  const sizeInMb = file.size / (1024 * 1024);
  return `${file.name} · ${sizeInMb.toFixed(sizeInMb >= 10 ? 0 : 1)} MB`;
};

const assetDisplayName = (asset: ContentOpsUploadedAsset) =>
  asset.alt_text?.trim() || asset.mime_type || asset.id;

const mediaLabelForAssets = (assetIds: string[]) => {
  if (assetIds.length === 0) {
    return 'No media attached';
  }
  return assetIds.length === 1 ? '1 attached asset' : `${assetIds.length} attached assets`;
};

const exportArtifactLabel = (artifact: ContentOpsExportArtifact) =>
  artifact.export_type === 'content_plan' ? 'Content plan' : stateLabel(artifact.export_type);

const exportArtifactCountLabel = (count: number) =>
  count === 1 ? '1 saved packet' : `${formatNumber(count)} saved packets`;

const hasActiveVersion = (draft: ContentOpsDraft) =>
  draft.variants.some((variant) => Boolean(variant.versionId));

const formatScheduleDisplay = (value: string) => {
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
};

const emptyReportOverview = (workspaceId: string | null): ContentOpsReportOverviewPayload => ({
  workspace_id: workspaceId,
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

const topBuckets = (buckets: Record<string, number>, limit = 3) =>
  Object.entries(buckets)
    .sort((left, right) => right[1] - left[1] || left[0].localeCompare(right[0]))
    .slice(0, limit);

const reportDateLabel = (value: string) => {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return value;
  }
  return date.toLocaleDateString(undefined, {
    month: 'short',
    day: 'numeric',
    year: 'numeric',
  });
};

const formatDateTimeDisplay = (value?: string | null) => {
  if (!value) {
    return 'Not available';
  }
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return value;
  }
  return date.toLocaleString(undefined, {
    month: 'short',
    day: 'numeric',
    year: 'numeric',
    hour: 'numeric',
    minute: '2-digit',
  });
};

const splitTerms = (value: string) =>
  value
    .split(',')
    .map((term) => term.trim())
    .filter(Boolean);

const captionPlatforms: ContentOpsChannel[] = ['facebook_page', 'instagram'];

const ReadinessItem = ({ axis }: { axis: ContentOpsReadinessAxis }) => (
  <li
    className={`content-ops-readiness__item content-ops-readiness__item--${readinessTone(axis.state)}`}
  >
    <div>
      <span className="content-ops-readiness__label">{axis.label}</span>
      <strong>{stateLabel(axis.state)}</strong>
    </div>
    <p>{axis.reason ?? axis.actionLabel}</p>
    {axis.details?.length ? (
      <ul className="content-ops-readiness__details">
        {axis.details.map((detail) => (
          <li key={detail}>{detail}</li>
        ))}
      </ul>
    ) : null}
  </li>
);

const ReadinessSummary = ({ readiness }: { readiness: ContentOpsReadinessAxis[] }) => {
  const summary = livePublishingReadinessSummary(readiness);
  return (
    <div
      className={`content-ops-readiness-summary content-ops-readiness-summary--${summary.tone}`}
      data-testid="content-ops-live-readiness-summary"
    >
      <strong>{summary.title}</strong>
      <span>{summary.detail}</span>
    </div>
  );
};

const DraftWorkflowControls = ({
  canWorkflow,
  draft,
  onDecideApproval,
  onScheduleDraft,
  onSubmitClientReview,
  onSubmitInternalReview,
}: {
  canWorkflow: boolean;
  draft: ContentOpsDraft;
  onDecideApproval: (
    draft: ContentOpsDraft,
    reviewerType: 'internal' | 'client',
    decision: ContentOpsApprovalDecisionPayload['decision'],
  ) => Promise<void>;
  onScheduleDraft: (draft: ContentOpsDraft, scheduledAt: string) => Promise<void>;
  onSubmitClientReview: (draft: ContentOpsDraft) => Promise<void>;
  onSubmitInternalReview: (draft: ContentOpsDraft) => Promise<void>;
}) => {
  const [status, setStatus] = useState<'idle' | 'submitting' | 'success' | 'error'>('idle');
  const [message, setMessage] = useState<string | null>(null);
  const [scheduledAtLocal, setScheduledAtLocal] = useState('');
  const [scheduleConfirmed, setScheduleConfirmed] = useState(false);
  const disabledReason = !canWorkflow
    ? 'Live creator access required.'
    : !hasActiveVersion(draft)
      ? 'Active version required.'
      : null;
  const isSubmitting = status === 'submitting';

  const runAction = async (action: () => Promise<void>, successMessage: string) => {
    setStatus('submitting');
    setMessage(null);
    try {
      await action();
      setStatus('success');
      setMessage(successMessage);
    } catch (error) {
      setStatus('error');
      setMessage(error instanceof Error ? error.message : 'Workflow action failed.');
    }
  };

  const baseDisabled = Boolean(disabledReason) || isSubmitting;
  const scheduleDisabled = baseDisabled || !scheduledAtLocal || !scheduleConfirmed;
  const internalApproval = draft.approvalSummary.internal;
  const clientApproval = draft.approvalSummary.client;
  const handleSchedule = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (!scheduledAtLocal) {
      setStatus('error');
      setMessage('Choose a schedule time.');
      return;
    }
    const scheduledAt = new Date(scheduledAtLocal);
    if (Number.isNaN(scheduledAt.getTime())) {
      setStatus('error');
      setMessage('Choose a valid schedule time.');
      return;
    }
    await runAction(() => onScheduleDraft(draft, scheduledAt.toISOString()), 'Draft scheduled.');
  };

  return (
    <div className="content-ops-workflow">
      {['draft', 'generated', 'internal_changes_requested', 'client_changes_requested'].includes(
        draft.state,
      ) ? (
        <button
          type="button"
          className="button secondary"
          disabled={baseDisabled}
          onClick={() =>
            void runAction(() => onSubmitInternalReview(draft), 'Internal review request created.')
          }
        >
          {isSubmitting ? 'Submitting...' : 'Submit internal review'}
        </button>
      ) : null}
      {draft.state === 'internal_review' && internalApproval ? (
        <>
          <button
            type="button"
            className="button secondary"
            disabled={baseDisabled}
            onClick={() =>
              void runAction(
                () => onDecideApproval(draft, 'internal', 'approved'),
                'Internal approval recorded.',
              )
            }
          >
            Approve internal
          </button>
          <button
            type="button"
            className="button tertiary"
            disabled={baseDisabled}
            onClick={() =>
              void runAction(
                () => onDecideApproval(draft, 'internal', 'changes_requested'),
                'Internal changes requested.',
              )
            }
          >
            Request internal changes
          </button>
        </>
      ) : null}
      {draft.state === 'internal_approved' ? (
        <button
          type="button"
          className="button secondary"
          disabled={baseDisabled}
          onClick={() =>
            void runAction(() => onSubmitClientReview(draft), 'Client review request created.')
          }
        >
          {isSubmitting ? 'Sending...' : 'Send client review'}
        </button>
      ) : null}
      {draft.state === 'client_review' && clientApproval ? (
        <>
          <button
            type="button"
            className="button secondary"
            disabled={baseDisabled}
            onClick={() =>
              void runAction(
                () => onDecideApproval(draft, 'client', 'approved'),
                'Client approval recorded.',
              )
            }
          >
            Approve client
          </button>
          <button
            type="button"
            className="button tertiary"
            disabled={baseDisabled}
            onClick={() =>
              void runAction(
                () => onDecideApproval(draft, 'client', 'changes_requested'),
                'Client changes requested.',
              )
            }
          >
            Request client changes
          </button>
        </>
      ) : null}
      {draft.state === 'client_approved' ? (
        <form className="content-ops-schedule-form" onSubmit={handleSchedule}>
          <label className="content-ops-field">
            <span>Schedule time</span>
            <input
              type="datetime-local"
              value={scheduledAtLocal}
              disabled={baseDisabled}
              onChange={(event) => {
                setScheduledAtLocal(event.target.value);
                setScheduleConfirmed(false);
                setStatus('idle');
                setMessage(null);
              }}
            />
          </label>
          <label className="content-ops-confirm">
            <input
              type="checkbox"
              checked={scheduleConfirmed}
              disabled={baseDisabled || !scheduledAtLocal}
              onChange={(event) => {
                setScheduleConfirmed(event.target.checked);
                setStatus('idle');
                setMessage(null);
              }}
            />
            <span>Confirm this approved version can enter the publish queue</span>
          </label>
          <button type="submit" className="button secondary" disabled={scheduleDisabled}>
            {isSubmitting ? 'Scheduling...' : 'Schedule'}
          </button>
        </form>
      ) : null}
      {draft.state === 'scheduled' ? (
        <span className="content-ops-workflow__state">Scheduled for dispatch</span>
      ) : null}
      {disabledReason ? (
        <span className="content-ops-workflow__state">{disabledReason}</span>
      ) : null}
      {message ? (
        <span className={`content-ops-workflow__message content-ops-workflow__message--${status}`}>
          {message}
        </span>
      ) : null}
    </div>
  );
};

const QueueRow = ({
  canRetry,
  item,
  onRetry,
}: {
  canRetry: boolean;
  item: ContentOpsQueueItem;
  onRetry: (item: ContentOpsQueueItem) => Promise<void>;
}) => {
  const [status, setStatus] = useState<'idle' | 'submitting' | 'success' | 'error'>('idle');
  const [message, setMessage] = useState<string | null>(null);
  const retryable = item.state === 'failed_retryable';

  const handleRetry = async () => {
    setStatus('submitting');
    setMessage(null);
    try {
      await onRetry(item);
      setStatus('success');
      setMessage('Requeued');
    } catch (error) {
      setStatus('error');
      setMessage(error instanceof Error ? error.message : 'Retry failed');
    }
  };

  return (
    <tr>
      <td>
        <strong>{item.draftTitle}</strong>
        <span>{item.client}</span>
      </td>
      <td>{channelLabel(item.channel)}</td>
      <td>{item.scheduledAt}</td>
      <td>
        <span className={`content-ops-status content-ops-status--${queueTone(item.state)}`}>
          {stateLabel(item.state)}
        </span>
      </td>
      <td>
        <span>{queueDetailText(item)}</span>
        {message ? (
          <span className={`content-ops-queue-message content-ops-queue-message--${status}`}>
            {message}
          </span>
        ) : null}
      </td>
      <td>
        {retryable ? (
          <button
            type="button"
            className="button secondary"
            disabled={!canRetry || status === 'submitting'}
            onClick={() => void handleRetry()}
          >
            {status === 'submitting' ? 'Retrying...' : 'Retry'}
          </button>
        ) : (
          <span className="content-ops-workflow__state">No action</span>
        )}
      </td>
    </tr>
  );
};

const AssetAttachControl = ({
  canCreate,
  assets,
  draft,
  variant,
  onAttach,
}: {
  canCreate: boolean;
  assets: ContentOpsUploadedAsset[];
  draft: ContentOpsDraft;
  variant: ContentOpsDraftVariant;
  onAttach: (
    draft: ContentOpsDraft,
    variant: ContentOpsDraftVariant,
    assetId: string,
  ) => Promise<void>;
}) => {
  const attachableAssets = assets.filter((asset) => !variant.mediaAssetIds.includes(asset.id));
  const [selectedAssetId, setSelectedAssetId] = useState('');
  const [status, setStatus] = useState<'idle' | 'submitting' | 'success' | 'error'>('idle');
  const [message, setMessage] = useState<string | null>(null);
  const disabledReason = !canCreate
    ? 'Viewer access cannot attach media.'
    : !variant.versionId
      ? 'Create a version before attaching media.'
      : attachableAssets.length === 0
        ? 'No unattached assets available.'
        : null;

  const handleAttach = async () => {
    if (!selectedAssetId) {
      setStatus('error');
      setMessage('Choose an uploaded asset to attach.');
      return;
    }
    setStatus('submitting');
    setMessage(null);
    try {
      await onAttach(draft, variant, selectedAssetId);
      setSelectedAssetId('');
      setStatus('success');
      setMessage('Media attached as a new draft version.');
    } catch (error) {
      setStatus('error');
      setMessage(error instanceof Error ? error.message : 'Unable to attach media.');
    }
  };

  return (
    <div className="content-ops-attach">
      <label className="content-ops-field">
        <span>Attach media</span>
        <select
          value={selectedAssetId}
          disabled={Boolean(disabledReason) || status === 'submitting'}
          aria-label={`Attach media to ${draft.title} ${variant.label}`}
          onChange={(event) => {
            setSelectedAssetId(event.target.value);
            setStatus('idle');
            setMessage(null);
          }}
        >
          <option value="">{disabledReason ?? 'Choose an uploaded asset'}</option>
          {attachableAssets.map((asset) => (
            <option value={asset.id} key={asset.id}>
              {assetDisplayName(asset)}
            </option>
          ))}
        </select>
      </label>
      <button
        type="button"
        className="button secondary"
        disabled={Boolean(disabledReason) || status === 'submitting'}
        onClick={() => void handleAttach()}
      >
        {status === 'submitting' ? 'Attaching...' : 'Attach'}
      </button>
      {message ? (
        <p className={`content-ops-upload-message content-ops-upload-message--${status}`}>
          {message}
        </p>
      ) : null}
    </div>
  );
};

const DraftPanel = ({
  assets,
  canCreate,
  canWorkflow,
  draft,
  onAttachAsset,
  onDecideApproval,
  onScheduleDraft,
  onSubmitClientReview,
  onSubmitInternalReview,
}: {
  assets: ContentOpsUploadedAsset[];
  canCreate: boolean;
  canWorkflow: boolean;
  draft: ContentOpsDraft;
  onAttachAsset: (
    draft: ContentOpsDraft,
    variant: ContentOpsDraftVariant,
    assetId: string,
  ) => Promise<void>;
  onDecideApproval: (
    draft: ContentOpsDraft,
    reviewerType: 'internal' | 'client',
    decision: ContentOpsApprovalDecisionPayload['decision'],
  ) => Promise<void>;
  onScheduleDraft: (draft: ContentOpsDraft, scheduledAt: string) => Promise<void>;
  onSubmitClientReview: (draft: ContentOpsDraft) => Promise<void>;
  onSubmitInternalReview: (draft: ContentOpsDraft) => Promise<void>;
}) => (
  <article className="content-ops-draft">
    <header className="content-ops-draft__header">
      <div>
        <h3>{draft.title}</h3>
        <p>
          {draft.activeVersionLabel} · {draft.owner}
        </p>
      </div>
      <span className="content-ops-status content-ops-status--draft">
        {stateLabel(draft.state)}
      </span>
    </header>

    <div className="content-ops-variant-grid">
      {draft.variants.map((variant) => (
        <section className="content-ops-variant" key={`${draft.id}-${variant.channel}`}>
          <header>
            <h4>{variant.label}</h4>
            <span>{stateLabel(variant.approvalStatus)}</span>
          </header>
          <p>{variant.caption}</p>
          <div className="content-ops-media-frame">
            <span>{variant.mediaLabel}</span>
          </div>
          <AssetAttachControl
            assets={assets}
            canCreate={canCreate}
            draft={draft}
            variant={variant}
            onAttach={onAttachAsset}
          />
        </section>
      ))}
    </div>

    <footer className="content-ops-draft__footer">
      <span>{draft.scheduledAt ? `Scheduled ${draft.scheduledAt}` : 'Not scheduled'}</span>
      <DraftWorkflowControls
        canWorkflow={canWorkflow}
        draft={draft}
        onDecideApproval={onDecideApproval}
        onScheduleDraft={onScheduleDraft}
        onSubmitClientReview={onSubmitClientReview}
        onSubmitInternalReview={onSubmitInternalReview}
      />
    </footer>
  </article>
);

const GenerationPanel = ({
  briefId,
  canGenerate,
  jobs,
  onCancelJob,
  onCreateCandidateDraft,
  onGenerateCaptions,
  source,
}: {
  briefId: string;
  canGenerate: boolean;
  jobs: ContentOpsGenerationJob[];
  onCancelJob: (job: ContentOpsGenerationJob) => Promise<void>;
  onCreateCandidateDraft: (payload: {
    title: string;
    channel: ContentOpsChannel;
    caption: string;
  }) => Promise<void>;
  onGenerateCaptions: (
    candidateCount: number,
    platforms: ContentOpsChannel[],
    toneOverride: string,
  ) => Promise<void>;
  source: 'api' | 'mock';
}) => {
  const [candidateCount, setCandidateCount] = useState(3);
  const [selectedPlatforms, setSelectedPlatforms] = useState<ContentOpsChannel[]>(captionPlatforms);
  const [toneOverride, setToneOverride] = useState('');
  const [status, setStatus] = useState<'idle' | 'submitting' | 'success' | 'error'>('idle');
  const [message, setMessage] = useState<string | null>(null);
  const isSubmitting = status === 'submitting';
  const disabledReason = !canGenerate
    ? source === 'api'
      ? 'Creator access required.'
      : 'Live workspace required.'
    : briefId === 'empty-brief'
      ? 'Create a brief before generating captions.'
      : null;

  const togglePlatform = (platform: ContentOpsChannel, checked: boolean) => {
    setSelectedPlatforms((current) => {
      if (checked) {
        return Array.from(new Set([...current, platform]));
      }
      return current.filter((item) => item !== platform);
    });
    setStatus('idle');
    setMessage(null);
  };

  const handleGenerate = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (selectedPlatforms.length === 0) {
      setStatus('error');
      setMessage('Choose at least one platform.');
      return;
    }
    setStatus('submitting');
    setMessage(null);
    try {
      await onGenerateCaptions(candidateCount, selectedPlatforms, toneOverride);
      setStatus('success');
      setMessage('Caption generation job queued.');
    } catch (error) {
      setStatus('error');
      setMessage(error instanceof Error ? error.message : 'Caption generation failed.');
    }
  };

  const handleCancel = async (job: ContentOpsGenerationJob) => {
    setStatus('submitting');
    setMessage(null);
    try {
      await onCancelJob(job);
      setStatus('success');
      setMessage('Generation job cancelled.');
    } catch (error) {
      setStatus('error');
      setMessage(error instanceof Error ? error.message : 'Unable to cancel generation job.');
    }
  };

  const handleCreateCandidateDraft = async (candidate: ContentOpsGeneratedCandidate) => {
    setStatus('submitting');
    setMessage(null);
    try {
      await onCreateCandidateDraft({
        title: candidate.title,
        channel: candidate.channel,
        caption: candidate.caption,
      });
      setStatus('success');
      setMessage('Draft created from generated candidate.');
    } catch (error) {
      setStatus('error');
      setMessage(error instanceof Error ? error.message : 'Draft creation failed.');
    }
  };

  return (
    <section className="content-ops-section" aria-labelledby="generation-title">
      <div className="content-ops-section__header">
        <h2 id="generation-title">Generation</h2>
        <span>{source === 'api' ? 'Queued caption jobs' : 'Provider status'}</span>
      </div>
      <form className="content-ops-generation-form" onSubmit={handleGenerate}>
        <label className="content-ops-field">
          <span>Candidates</span>
          <input
            type="number"
            min={1}
            max={10}
            value={candidateCount}
            disabled={Boolean(disabledReason) || isSubmitting}
            onChange={(event) => {
              setCandidateCount(Number(event.target.value) || 1);
              setStatus('idle');
              setMessage(null);
            }}
          />
        </label>
        <fieldset className="content-ops-platform-field">
          <legend>Platforms</legend>
          {captionPlatforms.map((platform) => (
            <label key={platform}>
              <input
                type="checkbox"
                checked={selectedPlatforms.includes(platform)}
                disabled={Boolean(disabledReason) || isSubmitting}
                onChange={(event) => togglePlatform(platform, event.target.checked)}
              />
              <span>{channelLabel(platform)}</span>
            </label>
          ))}
        </fieldset>
        <label className="content-ops-field">
          <span>Tone override</span>
          <input
            type="text"
            value={toneOverride}
            maxLength={128}
            disabled={Boolean(disabledReason) || isSubmitting}
            placeholder="Optional"
            onChange={(event) => {
              setToneOverride(event.target.value);
              setStatus('idle');
              setMessage(null);
            }}
          />
        </label>
        <div className="content-ops-generation-form__footer">
          <span>{disabledReason ?? 'Caption jobs stay review-only until approved.'}</span>
          <button
            type="submit"
            className="button secondary"
            disabled={Boolean(disabledReason) || isSubmitting}
          >
            {isSubmitting ? 'Queuing...' : 'Generate captions'}
          </button>
        </div>
        {message ? (
          <p className={`content-ops-upload-message content-ops-upload-message--${status}`}>
            {message}
          </p>
        ) : null}
      </form>
      <div className="content-ops-job-list">
        {jobs.map((job) => {
          const cancellable = job.status === 'queued' || job.status === 'running';
          const candidates = job.candidates ?? [];
          return (
            <article className="content-ops-job" key={job.id}>
              <div>
                <h3>{job.label}</h3>
                <p>
                  {job.provider} · {job.candidateCount} candidates
                </p>
              </div>
              <div className="content-ops-job__actions">
                <span className={`content-ops-status content-ops-status--${job.status}`}>
                  {stateLabel(job.status)}
                </span>
                {cancellable ? (
                  <button
                    type="button"
                    className="button tertiary"
                    disabled={!canGenerate || isSubmitting}
                    onClick={() => void handleCancel(job)}
                  >
                    Cancel
                  </button>
                ) : null}
              </div>
              {candidates.length ? (
                <div className="content-ops-candidate-list">
                  {candidates.map((candidate) => (
                    <section className="content-ops-candidate" key={candidate.id}>
                      <div>
                        <h4>{candidate.title}</h4>
                        <p>{candidate.caption}</p>
                        <dl>
                          <div>
                            <dt>Channel</dt>
                            <dd>{channelLabel(candidate.channel)}</dd>
                          </div>
                          {candidate.qualityScore !== null ? (
                            <div>
                              <dt>Quality</dt>
                              <dd>{Math.round(candidate.qualityScore * 100)}%</dd>
                            </div>
                          ) : null}
                          {candidate.riskFlags.length ? (
                            <div>
                              <dt>Risk flags</dt>
                              <dd>{candidate.riskFlags.join(', ')}</dd>
                            </div>
                          ) : null}
                          {candidate.cta ? (
                            <div>
                              <dt>CTA</dt>
                              <dd>{candidate.cta}</dd>
                            </div>
                          ) : null}
                          {candidate.hashtags.length ? (
                            <div>
                              <dt>Hashtags</dt>
                              <dd>{candidate.hashtags.join(', ')}</dd>
                            </div>
                          ) : null}
                          {candidate.altText ? (
                            <div>
                              <dt>Alt text</dt>
                              <dd>{candidate.altText}</dd>
                            </div>
                          ) : null}
                        </dl>
                      </div>
                      <button
                        type="button"
                        className="button secondary"
                        aria-label={`Create draft from ${candidate.title}`}
                        disabled={!canGenerate || isSubmitting}
                        onClick={() => void handleCreateCandidateDraft(candidate)}
                      >
                        Create draft
                      </button>
                    </section>
                  ))}
                </div>
              ) : null}
            </article>
          );
        })}
      </div>
    </section>
  );
};

const BriefCreatePanel = ({
  onCreateBrief,
  onDismiss,
}: {
  onCreateBrief: (payload: {
    campaignTheme: string;
    audience: string;
    offer: string;
    tone: string;
    requiredTerms: string[];
    blockedTerms: string[];
    dateStart: string;
    dateEnd: string;
  }) => Promise<void>;
  onDismiss: () => void;
}) => {
  const [campaignTheme, setCampaignTheme] = useState('');
  const [audience, setAudience] = useState('');
  const [offer, setOffer] = useState('');
  const [tone, setTone] = useState('');
  const [requiredTerms, setRequiredTerms] = useState('');
  const [blockedTerms, setBlockedTerms] = useState('');
  const [dateStart, setDateStart] = useState('');
  const [dateEnd, setDateEnd] = useState('');
  const [status, setStatus] = useState<'idle' | 'submitting' | 'success' | 'error'>('idle');
  const [message, setMessage] = useState<string | null>(null);

  const handleSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (!campaignTheme.trim()) {
      setStatus('error');
      setMessage('Campaign theme is required.');
      return;
    }
    setStatus('submitting');
    setMessage(null);
    try {
      await onCreateBrief({
        campaignTheme,
        audience,
        offer,
        tone,
        requiredTerms: splitTerms(requiredTerms),
        blockedTerms: splitTerms(blockedTerms),
        dateStart,
        dateEnd,
      });
      setStatus('success');
      setMessage('Brief created.');
    } catch (error) {
      setStatus('error');
      setMessage(error instanceof Error ? error.message : 'Brief creation failed.');
    }
  };

  return (
    <section className="content-ops-section" aria-labelledby="new-brief-title">
      <div className="content-ops-section__header">
        <h2 id="new-brief-title">New Brief</h2>
        <button type="button" className="button tertiary" onClick={onDismiss}>
          Close
        </button>
      </div>
      <form className="content-ops-brief-form" onSubmit={handleSubmit}>
        <label className="content-ops-field">
          <span>Campaign theme</span>
          <input
            type="text"
            value={campaignTheme}
            maxLength={255}
            onChange={(event) => setCampaignTheme(event.target.value)}
          />
        </label>
        <label className="content-ops-field">
          <span>Audience</span>
          <textarea value={audience} onChange={(event) => setAudience(event.target.value)} />
        </label>
        <label className="content-ops-field">
          <span>Offer</span>
          <textarea value={offer} onChange={(event) => setOffer(event.target.value)} />
        </label>
        <label className="content-ops-field">
          <span>Tone</span>
          <input
            type="text"
            value={tone}
            maxLength={128}
            onChange={(event) => setTone(event.target.value)}
          />
        </label>
        <label className="content-ops-field">
          <span>Required terms</span>
          <input
            type="text"
            value={requiredTerms}
            placeholder="Comma-separated"
            onChange={(event) => setRequiredTerms(event.target.value)}
          />
        </label>
        <label className="content-ops-field">
          <span>Blocked terms</span>
          <input
            type="text"
            value={blockedTerms}
            placeholder="Comma-separated"
            onChange={(event) => setBlockedTerms(event.target.value)}
          />
        </label>
        <label className="content-ops-field">
          <span>Start date</span>
          <input
            type="date"
            value={dateStart}
            onChange={(event) => setDateStart(event.target.value)}
          />
        </label>
        <label className="content-ops-field">
          <span>End date</span>
          <input type="date" value={dateEnd} onChange={(event) => setDateEnd(event.target.value)} />
        </label>
        <div className="content-ops-brief-form__footer">
          <span>New briefs stay in Content Ops until drafts are reviewed and approved.</span>
          <button type="submit" className="button primary" disabled={status === 'submitting'}>
            {status === 'submitting' ? 'Creating...' : 'Create brief'}
          </button>
        </div>
        {message ? (
          <p className={`content-ops-upload-message content-ops-upload-message--${status}`}>
            {message}
          </p>
        ) : null}
      </form>
    </section>
  );
};

const DraftCreatePanel = ({
  onCreateDraft,
  onDismiss,
}: {
  onCreateDraft: (payload: {
    title: string;
    channel: ContentOpsChannel;
    caption: string;
  }) => Promise<void>;
  onDismiss: () => void;
}) => {
  const [title, setTitle] = useState('');
  const [channel, setChannel] = useState<ContentOpsChannel>('facebook_page');
  const [caption, setCaption] = useState('');
  const [status, setStatus] = useState<'idle' | 'submitting' | 'success' | 'error'>('idle');
  const [message, setMessage] = useState<string | null>(null);

  const handleSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (!title.trim()) {
      setStatus('error');
      setMessage('Draft title is required.');
      return;
    }
    if (!caption.trim()) {
      setStatus('error');
      setMessage('Caption is required.');
      return;
    }
    setStatus('submitting');
    setMessage(null);
    try {
      await onCreateDraft({
        title,
        channel,
        caption,
      });
      setStatus('success');
      setMessage('Draft created.');
    } catch (error) {
      setStatus('error');
      setMessage(error instanceof Error ? error.message : 'Draft creation failed.');
    }
  };

  return (
    <section className="content-ops-section" aria-labelledby="new-draft-title">
      <div className="content-ops-section__header">
        <h2 id="new-draft-title">New Draft</h2>
        <button type="button" className="button tertiary" onClick={onDismiss}>
          Close
        </button>
      </div>
      <form className="content-ops-draft-form" onSubmit={handleSubmit}>
        <label className="content-ops-field">
          <span>Draft title</span>
          <input
            type="text"
            value={title}
            maxLength={255}
            onChange={(event) => setTitle(event.target.value)}
          />
        </label>
        <label className="content-ops-field">
          <span>Channel</span>
          <select
            value={channel}
            onChange={(event) => setChannel(event.target.value as ContentOpsChannel)}
          >
            {captionPlatforms.map((platform) => (
              <option key={platform} value={platform}>
                {channelLabel(platform)}
              </option>
            ))}
          </select>
        </label>
        <label className="content-ops-field content-ops-field--wide">
          <span>Caption</span>
          <textarea value={caption} onChange={(event) => setCaption(event.target.value)} />
        </label>
        <div className="content-ops-draft-form__footer">
          <span>Drafts must still pass internal and client approval before scheduling.</span>
          <button type="submit" className="button primary" disabled={status === 'submitting'}>
            {status === 'submitting' ? 'Creating...' : 'Create draft'}
          </button>
        </div>
        {message ? (
          <p className={`content-ops-upload-message content-ops-upload-message--${status}`}>
            {message}
          </p>
        ) : null}
      </form>
    </section>
  );
};

const MediaUploadPanel = ({
  canCreate,
  workspaceId,
  uploadedAssets,
  onUploaded,
}: {
  canCreate: boolean;
  workspaceId: string | null;
  uploadedAssets: ContentOpsUploadedAsset[];
  onUploaded: (asset: ContentOpsUploadedAsset) => void;
}) => {
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [altText, setAltText] = useState('');
  const [status, setStatus] = useState<'idle' | 'submitting' | 'success' | 'error'>('idle');
  const [message, setMessage] = useState<string | null>(null);
  const canUpload = canCreate && Boolean(workspaceId);
  const disabledReason = !canCreate
    ? 'Viewer access can review media but cannot upload assets.'
    : !workspaceId
      ? 'Upload requires a live Content Ops workspace.'
      : null;

  const handleSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (!workspaceId) {
      setStatus('error');
      setMessage('Upload requires a live Content Ops workspace.');
      return;
    }
    if (!selectedFile) {
      setStatus('error');
      setMessage('Choose an image or video file before uploading.');
      return;
    }
    setStatus('submitting');
    setMessage(null);
    try {
      const asset = await uploadContentOpsAsset({
        workspaceId,
        file: selectedFile,
        altText,
      });
      onUploaded(asset);
      setSelectedFile(null);
      setAltText('');
      setStatus('success');
      setMessage('Asset uploaded and is available for draft versions.');
    } catch (error) {
      setStatus('error');
      setMessage(error instanceof Error ? error.message : 'Asset upload failed.');
    }
  };

  return (
    <section className="content-ops-section" aria-labelledby="media-upload-title">
      <div className="content-ops-section__header">
        <h2 id="media-upload-title">Media Library</h2>
        <span>Upload image or video assets</span>
      </div>
      <form className="content-ops-upload-panel" onSubmit={handleSubmit}>
        <label className="content-ops-field">
          <span>Asset file</span>
          <input
            type="file"
            accept="image/*,video/*"
            disabled={!canUpload || status === 'submitting'}
            onChange={(event) => {
              setSelectedFile(event.target.files?.[0] ?? null);
              setStatus('idle');
              setMessage(null);
            }}
          />
        </label>
        <label className="content-ops-field">
          <span>Alt text</span>
          <input
            type="text"
            value={altText}
            disabled={!canUpload || status === 'submitting'}
            maxLength={1000}
            placeholder="Describe the visual for review and accessibility"
            onChange={(event) => setAltText(event.target.value)}
          />
        </label>
        <div className="content-ops-upload-panel__footer">
          <span>{disabledReason ?? fileSummary(selectedFile)}</span>
          <button
            type="submit"
            className="button primary"
            disabled={!canUpload || status === 'submitting'}
          >
            {status === 'submitting' ? 'Uploading...' : 'Upload asset'}
          </button>
        </div>
        {message ? (
          <p className={`content-ops-upload-message content-ops-upload-message--${status}`}>
            {message}
          </p>
        ) : null}
      </form>
      {uploadedAssets.length ? (
        <ul className="content-ops-asset-list" aria-label="Recently uploaded assets">
          {uploadedAssets.map((asset) => (
            <li key={asset.id}>
              <div>
                <strong>{asset.alt_text || asset.mime_type}</strong>
                <span>
                  {asset.mime_type} · {stateLabel(asset.status)}
                </span>
              </div>
              {asset.download_url ? (
                <a href={asset.download_url} className="button tertiary">
                  Preview
                </a>
              ) : null}
            </li>
          ))}
        </ul>
      ) : null}
    </section>
  );
};

const CalendarPanel = ({
  drafts,
  queue,
  timezone,
}: {
  drafts: ContentOpsDraft[];
  queue: ContentOpsQueueItem[];
  timezone: string;
}) => {
  const scheduledDrafts = drafts.filter((draft) => Boolean(draft.scheduledAt));
  const unscheduledCount = drafts.length - scheduledDrafts.length;
  const blockedCount = queue.filter(
    (item) => item.blocker || queueTone(item.state) === 'blocked',
  ).length;

  return (
    <section className="content-ops-section" aria-labelledby="calendar-title">
      <div className="content-ops-section__header">
        <h2 id="calendar-title">Calendar</h2>
        <span>{timezone}</span>
      </div>
      <div className="content-ops-calendar-summary">
        <article>
          <span>Scheduled drafts</span>
          <strong>{formatNumber(scheduledDrafts.length)}</strong>
        </article>
        <article>
          <span>Unscheduled drafts</span>
          <strong>{formatNumber(unscheduledCount)}</strong>
        </article>
        <article>
          <span>Blocked queue rows</span>
          <strong>{formatNumber(blockedCount)}</strong>
        </article>
      </div>
      <div className="content-ops-timeline" aria-label="Content calendar timeline">
        {scheduledDrafts.length ? (
          scheduledDrafts.map((draft) => (
            <article className="content-ops-timeline__item" key={draft.id}>
              <div>
                <strong>{draft.scheduledAt}</strong>
                <span>{draft.title}</span>
              </div>
              <span className="content-ops-status content-ops-status--queued">
                {stateLabel(draft.state)}
              </span>
            </article>
          ))
        ) : (
          <p>No scheduled drafts yet.</p>
        )}
      </div>
    </section>
  );
};

const ClientReviewPanel = ({ drafts }: { drafts: ContentOpsDraft[] }) => {
  const reviewDrafts = drafts.filter((draft) =>
    ['client_review', 'client_changes_requested', 'client_approved'].includes(draft.state),
  );

  return (
    <section className="content-ops-section" aria-labelledby="client-review-title">
      <div className="content-ops-section__header">
        <h2 id="client-review-title">Client Review</h2>
        <span>{reviewDrafts.length} client-facing drafts</span>
      </div>
      <div className="content-ops-client-review-list">
        {reviewDrafts.length ? (
          reviewDrafts.map((draft) => {
            const clientApproval = draft.approvalSummary.client;
            return (
              <article className="content-ops-client-review" key={draft.id}>
                <div>
                  <strong>{draft.title}</strong>
                  <span>
                    {clientApproval
                      ? `${stateLabel(clientApproval.status)} · ${draft.activeVersionLabel}`
                      : `No client request · ${draft.activeVersionLabel}`}
                  </span>
                </div>
                <span className="content-ops-status content-ops-status--draft">
                  {stateLabel(draft.state)}
                </span>
              </article>
            );
          })
        ) : (
          <p>No drafts are waiting on client review.</p>
        )}
      </div>
    </section>
  );
};

const ExportHistoryPanel = ({
  artifacts,
  canExport,
  onCreateArtifact,
  onDownloadArtifact,
}: {
  artifacts: ContentOpsExportArtifact[];
  canExport: boolean;
  onCreateArtifact: () => Promise<void>;
  onDownloadArtifact: (artifact: ContentOpsExportArtifact) => Promise<void>;
}) => {
  const [status, setStatus] = useState<'idle' | 'submitting' | 'success' | 'error'>('idle');
  const [message, setMessage] = useState<string | null>(null);
  const isSubmitting = status === 'submitting';

  const run = async (action: () => Promise<void>, successMessage: string) => {
    setStatus('submitting');
    setMessage(null);
    try {
      await action();
      setStatus('success');
      setMessage(successMessage);
    } catch (error) {
      setStatus('error');
      setMessage(error instanceof Error ? error.message : 'Export action failed.');
    }
  };

  return (
    <section className="content-ops-section" aria-labelledby="export-history-title">
      <div className="content-ops-section__header">
        <div>
          <h2 id="export-history-title">Export History</h2>
          <span>{exportArtifactCountLabel(artifacts.length)}</span>
        </div>
        <button
          type="button"
          className="button secondary"
          disabled={!canExport || isSubmitting}
          onClick={() => void run(onCreateArtifact, 'Saved export created.')}
        >
          {isSubmitting ? 'Saving...' : 'Save export'}
        </button>
      </div>
      {message ? (
        <p className={`content-ops-export-message content-ops-export-message--${status}`}>
          {message}
        </p>
      ) : null}
      <div className="content-ops-table-wrap">
        <table className="content-ops-table content-ops-export-table">
          <thead>
            <tr>
              <th scope="col">Packet</th>
              <th scope="col">Created</th>
              <th scope="col">Items</th>
              <th scope="col">Status</th>
              <th scope="col">Action</th>
            </tr>
          </thead>
          <tbody>
            {artifacts.length ? (
              artifacts.map((artifact) => (
                <tr key={artifact.id}>
                  <td>
                    <strong>{exportArtifactLabel(artifact)}</strong>
                    <span>{artifact.export_format.toUpperCase()}</span>
                  </td>
                  <td>{formatDateTimeDisplay(artifact.completed_at ?? artifact.created_at)}</td>
                  <td>{formatNumber(artifact.item_count)}</td>
                  <td>
                    <span className={`content-ops-status content-ops-status--${artifact.status}`}>
                      {stateLabel(artifact.status)}
                    </span>
                  </td>
                  <td>
                    <button
                      type="button"
                      className="button tertiary"
                      disabled={!artifact.download_url || isSubmitting}
                      onClick={() =>
                        void run(() => onDownloadArtifact(artifact), 'Saved export downloaded.')
                      }
                    >
                      Download
                    </button>
                  </td>
                </tr>
              ))
            ) : (
              <tr>
                <td colSpan={5}>
                  <span>No saved exports yet.</span>
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </section>
  );
};

const ContentReportPanel = ({
  overview,
  posts,
  source,
}: {
  overview: ContentOpsReportOverviewPayload | null;
  posts: ContentOpsReportPost[];
  source: 'api' | 'mock';
}) => {
  const report = overview ?? emptyReportOverview(null);
  const totals = report.metric_totals;
  const postCount = Object.values(report.published_posts_by_channel).reduce(
    (sum, count) => sum + Number(count || 0),
    0,
  );
  const statusBuckets = topBuckets(report.publish_attempts_by_state);

  return (
    <section className="content-ops-section" aria-labelledby="reports-title">
      <div className="content-ops-section__header">
        <h2 id="reports-title">Organic Report</h2>
        <span>
          {source === 'api' ? 'Stored aggregate snapshots' : 'Waiting for live report data'}
        </span>
      </div>
      <div className="content-ops-report-grid">
        <article className="content-ops-report-card">
          <span>Published posts</span>
          <strong>{formatNumber(postCount)}</strong>
          <p>
            {topBuckets(report.published_posts_by_channel)
              .map(
                ([channel, count]) =>
                  `${channelLabel(channel as ContentOpsQueueItem['channel'])}: ${formatNumber(count)}`,
              )
              .join(' · ') || 'No published posts yet'}
          </p>
        </article>
        <article className="content-ops-report-card">
          <span>Engagements</span>
          <strong>{formatNumber(totals.engagements)}</strong>
          <p>
            {formatNumber(totals.impressions)} impressions · {formatNumber(totals.reach)} reach
          </p>
        </article>
        <article className="content-ops-report-card">
          <span>Post actions</span>
          <strong>{formatNumber(totals.clicks)}</strong>
          <p>
            {formatNumber(totals.saves)} saves · {formatNumber(totals.shares)} shares ·{' '}
            {formatNumber(totals.video_views)} video views
          </p>
        </article>
        <article className="content-ops-report-card">
          <span>Queue health</span>
          <strong>
            {formatNumber(
              Object.values(report.publish_attempts_by_state).reduce(
                (sum, count) => sum + Number(count || 0),
                0,
              ),
            )}
          </strong>
          <p>
            {statusBuckets
              .map(([state, count]) => `${stateLabel(state)}: ${formatNumber(count)}`)
              .join(' · ') || 'No publish attempts yet'}
          </p>
        </article>
      </div>
      <div className="content-ops-table-wrap">
        <table className="content-ops-table content-ops-report-table">
          <thead>
            <tr>
              <th scope="col">Published post</th>
              <th scope="col">Channel</th>
              <th scope="col">Published</th>
              <th scope="col">Reporting</th>
              <th scope="col">Engagements</th>
              <th scope="col">Actions</th>
            </tr>
          </thead>
          <tbody>
            {posts.length ? (
              posts.map((post) => (
                <tr key={post.id}>
                  <td>
                    <strong>{post.meta_post_id || post.id}</strong>
                    {post.permalink ? (
                      <a href={post.permalink} rel="noreferrer" target="_blank">
                        Open post
                      </a>
                    ) : (
                      <span>No permalink</span>
                    )}
                  </td>
                  <td>{channelLabel(post.channel)}</td>
                  <td>{reportDateLabel(post.published_at)}</td>
                  <td>
                    <span className="content-ops-status content-ops-status--ready">
                      {stateLabel(post.reporting_link_state)}
                    </span>
                  </td>
                  <td>{formatNumber(post.metrics.engagements)}</td>
                  <td>
                    {formatNumber(post.metrics.clicks)} clicks · {formatNumber(post.metrics.saves)}{' '}
                    saves
                  </td>
                </tr>
              ))
            ) : (
              <tr>
                <td colSpan={6}>
                  <span>No published post metrics have been linked yet.</span>
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </section>
  );
};

const ContentOpsPage = () => {
  const { user } = useAuth();
  const canCreate = canAccessCreatorUi(user);
  const [workspace, setWorkspace] = useState<ContentOpsMockWorkspace>(contentOpsMockWorkspace);
  const [source, setSource] = useState<'api' | 'mock'>('mock');
  const [warning, setWarning] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [uploadedAssets, setUploadedAssets] = useState<ContentOpsUploadedAsset[]>([]);
  const [exportArtifacts, setExportArtifacts] = useState<ContentOpsExportArtifact[]>([]);
  const [reportOverview, setReportOverview] = useState<ContentOpsReportOverviewPayload | null>(
    null,
  );
  const [reportPosts, setReportPosts] = useState<ContentOpsReportPost[]>([]);
  const [showBriefForm, setShowBriefForm] = useState(false);
  const [showDraftForm, setShowDraftForm] = useState(false);
  const [exportStatus, setExportStatus] = useState<'idle' | 'submitting' | 'success' | 'error'>(
    'idle',
  );
  const [exportMessage, setExportMessage] = useState<string | null>(null);

  useEffect(() => {
    const controller = new AbortController();
    setIsLoading(true);
    fetchContentOpsWorkspace(controller.signal)
      .then(async (result) => {
        let assets: ContentOpsUploadedAsset[] = [];
        let artifacts: ContentOpsExportArtifact[] = [];
        let overview: ContentOpsReportOverviewPayload | null = null;
        let posts: ContentOpsReportPost[] = [];
        let assetWarning: string | null = null;
        let exportWarning: string | null = null;
        let reportWarning: string | null = null;
        if (result.source === 'api' && result.workspace.id) {
          const [assetResult, exportResult, overviewResult, postsResult] = await Promise.allSettled(
            [
              listContentOpsAssets(result.workspace.id, controller.signal),
              listContentOpsExportArtifacts(result.workspace.id, controller.signal),
              fetchContentOpsReportOverview(result.workspace.id, controller.signal),
              fetchContentOpsReportPosts(result.workspace.id, controller.signal),
            ],
          );
          if (assetResult.status === 'fulfilled') {
            assets = assetResult.value;
          } else {
            assetWarning =
              assetResult.reason instanceof Error
                ? assetResult.reason.message
                : 'Content Ops media library is unavailable.';
          }
          if (exportResult.status === 'fulfilled') {
            artifacts = exportResult.value;
          } else {
            exportWarning =
              exportResult.reason instanceof Error
                ? exportResult.reason.message
                : 'Content Ops export history is unavailable.';
          }
          if (overviewResult.status === 'fulfilled') {
            overview = overviewResult.value;
          } else {
            reportWarning =
              overviewResult.reason instanceof Error
                ? overviewResult.reason.message
                : 'Content Ops reports are unavailable.';
          }
          if (postsResult.status === 'fulfilled') {
            posts = postsResult.value.results;
          } else {
            reportWarning =
              postsResult.reason instanceof Error
                ? postsResult.reason.message
                : 'Content Ops reports are unavailable.';
          }
        }
        setWorkspace(result.workspace);
        setSource(result.source);
        setWarning(result.warning ?? assetWarning ?? exportWarning ?? reportWarning);
        setUploadedAssets(assets);
        setExportArtifacts(artifacts);
        setReportOverview(overview);
        setReportPosts(posts);
      })
      .catch((error) => {
        if (!controller.signal.aborted) {
          setWorkspace(contentOpsMockWorkspace);
          setSource('mock');
          setWarning(error instanceof Error ? error.message : 'Content Ops API is unavailable.');
          setUploadedAssets([]);
          setExportArtifacts([]);
          setReportOverview(null);
          setReportPosts([]);
        }
      })
      .finally(() => {
        if (!controller.signal.aborted) {
          setIsLoading(false);
        }
      });
    return () => controller.abort();
  }, []);

  const handleAttachAsset = async (
    draft: ContentOpsDraft,
    variant: ContentOpsDraftVariant,
    assetId: string,
  ) => {
    const version = await createContentOpsVersionWithAsset({
      draftId: draft.id,
      caption: variant.caption,
      channel: variant.channel,
      mediaAssetIds: variant.mediaAssetIds,
      assetId,
    });
    const nextMediaAssets =
      version.media_assets ?? Array.from(new Set([...variant.mediaAssetIds, assetId]));
    setWorkspace((current) => ({
      ...current,
      drafts: current.drafts.map((currentDraft) => {
        if (currentDraft.id !== draft.id) {
          return currentDraft;
        }
        return {
          ...currentDraft,
          activeVersionLabel: version.version_number
            ? `v${version.version_number}`
            : currentDraft.activeVersionLabel,
          variants: currentDraft.variants.map((currentVariant) => {
            if (
              currentVariant.versionId !== variant.versionId ||
              currentVariant.channel !== variant.channel
            ) {
              return currentVariant;
            }
            return {
              ...currentVariant,
              versionId: version.id,
              mediaAssetIds: nextMediaAssets,
              mediaLabel: mediaLabelForAssets(nextMediaAssets),
            };
          }),
        };
      }),
    }));
  };

  const applyApprovalRequest = (
    draft: ContentOpsDraft,
    approval: ContentOpsApprovalRequestPayload,
    nextState: string,
  ) => {
    setWorkspace((current) => ({
      ...current,
      drafts: current.drafts.map((currentDraft) => {
        if (currentDraft.id !== draft.id) {
          return currentDraft;
        }
        const reviewerType = approval.reviewer_type === 'client' ? 'client' : 'internal';
        return {
          ...currentDraft,
          state: nextState,
          approvalSummary: {
            ...currentDraft.approvalSummary,
            [reviewerType]: {
              id: approval.id,
              status: approval.status,
              versionId: approval.version,
            },
          },
          variants: currentDraft.variants.map((variant) =>
            variant.versionId === approval.version
              ? {
                  ...variant,
                  approvalStatus: `${reviewerType}_${approval.status}`,
                }
              : variant,
          ),
        };
      }),
    }));
  };

  const handleSubmitInternalReview = async (draft: ContentOpsDraft) => {
    const approval = await submitContentOpsInternalReview(draft.id);
    applyApprovalRequest(draft, approval, 'internal_review');
  };

  const handleSubmitClientReview = async (draft: ContentOpsDraft) => {
    const approval = await submitContentOpsClientReview(draft.id);
    applyApprovalRequest(draft, approval, 'client_review');
  };

  const handleDecideApproval = async (
    draft: ContentOpsDraft,
    reviewerType: 'internal' | 'client',
    decision: ContentOpsApprovalDecisionPayload['decision'],
  ) => {
    const approval = draft.approvalSummary[reviewerType];
    if (!approval) {
      throw new Error('No pending approval request is available for this draft.');
    }
    const result = await decideContentOpsApproval({
      approvalId: approval.id,
      decision,
    });
    const nextState =
      reviewerType === 'internal'
        ? result.decision === 'approved'
          ? 'internal_approved'
          : 'internal_changes_requested'
        : result.decision === 'approved'
          ? 'client_approved'
          : 'client_changes_requested';
    setWorkspace((current) => ({
      ...current,
      drafts: current.drafts.map((currentDraft) => {
        if (currentDraft.id !== draft.id) {
          return currentDraft;
        }
        return {
          ...currentDraft,
          state: nextState,
          approvalSummary: {
            ...currentDraft.approvalSummary,
            [reviewerType]: {
              ...approval,
              status: result.decision,
            },
          },
          variants: currentDraft.variants.map((variant) =>
            variant.versionId === approval.versionId
              ? {
                  ...variant,
                  approvalStatus: `${reviewerType}_${result.decision}`,
                }
              : variant,
          ),
        };
      }),
    }));
  };

  const handleScheduleDraft = async (draft: ContentOpsDraft, scheduledAt: string) => {
    const schedule = await scheduleContentOpsDraft({
      draftId: draft.id,
      scheduledAt,
      timezone: workspace.timezone,
    });
    applySchedule(draft, schedule);
  };

  const applySchedule = (draft: ContentOpsDraft, schedule: ContentOpsSchedulePayload) => {
    setWorkspace((current) => ({
      ...current,
      drafts: current.drafts.map((currentDraft) =>
        currentDraft.id === draft.id
          ? {
              ...currentDraft,
              state: 'scheduled',
              scheduledAt: formatScheduleDisplay(schedule.scheduled_at),
            }
          : currentDraft,
      ),
    }));
  };

  const handleGenerateCaptions = async (
    candidateCount: number,
    platforms: ContentOpsChannel[],
    toneOverride: string,
  ) => {
    const job = await requestContentOpsCaptionGeneration({
      briefId: workspace.brief.id,
      candidateCount,
      platforms,
      toneOverride,
    });
    setWorkspace((current) => ({
      ...current,
      generationJobs: [job, ...current.generationJobs.filter((item) => item.id !== job.id)],
    }));
  };

  const handleCancelGenerationJob = async (job: ContentOpsGenerationJob) => {
    const cancelled = await cancelContentOpsGenerationJob(job.id);
    setWorkspace((current) => ({
      ...current,
      generationJobs: current.generationJobs.map((item) => (item.id === job.id ? cancelled : item)),
    }));
  };

  const handleCreateBrief = async (payload: {
    campaignTheme: string;
    audience: string;
    offer: string;
    tone: string;
    requiredTerms: string[];
    blockedTerms: string[];
    dateStart: string;
    dateEnd: string;
  }) => {
    if (!workspace.id) {
      throw new Error('Brief creation requires a live Content Ops workspace.');
    }
    const brief = await createContentOpsBrief({
      workspaceId: workspace.id,
      workspaceName: workspace.name,
      ...payload,
    });
    setWorkspace((current) => ({
      ...current,
      calendarWindow: brief.dateRange,
      brief,
    }));
    setShowBriefForm(false);
  };

  const handleCreateDraft = async (payload: {
    title: string;
    channel: ContentOpsChannel;
    caption: string;
  }) => {
    if (!workspace.id) {
      throw new Error('Draft creation requires a live Content Ops workspace.');
    }
    const draft = await createContentOpsDraftWithVersion({
      workspaceId: workspace.id,
      briefId: workspace.brief.id === 'empty-brief' ? null : workspace.brief.id,
      ...payload,
    });
    setWorkspace((current) => ({
      ...current,
      drafts: [draft, ...current.drafts.filter((item) => item.id !== draft.id)],
    }));
    setShowDraftForm(false);
  };

  const handleRetryQueueItem = async (item: ContentOpsQueueItem) => {
    const result = await retryContentOpsPublishAttempt(item.id);
    setWorkspace((current) => ({
      ...current,
      queue: current.queue.map((queueItem) =>
        queueItem.id === item.id
          ? {
              ...queueItem,
              state: result.attempt.state,
              blocker: result.attempt.failure_detail_safe || result.attempt.failure_code || null,
            }
          : queueItem,
      ),
    }));
  };

  const handleExportPlan = async () => {
    if (!workspace.id) {
      setExportStatus('error');
      setExportMessage('Export requires a live Content Ops workspace.');
      return;
    }
    setExportStatus('submitting');
    setExportMessage(null);
    try {
      const payload = await exportContentOpsPlan({
        workspaceId: workspace.id,
        states: [],
      });
      const blob = new Blob([JSON.stringify(payload, null, 2)], {
        type: 'application/json',
      });
      saveBlobAsFile(blob, buildContentOpsExportFilename(workspace.name));
      setExportStatus('success');
      setExportMessage('Content plan export downloaded.');
    } catch (error) {
      setExportStatus('error');
      setExportMessage(error instanceof Error ? error.message : 'Content plan export failed.');
    }
  };

  const handleCreateExportArtifact = async () => {
    if (!workspace.id) {
      throw new Error('Export history requires a live Content Ops workspace.');
    }
    const artifact = await createContentOpsExportArtifact({
      workspaceId: workspace.id,
      states: [],
    });
    setExportArtifacts((artifacts) => [
      artifact,
      ...artifacts.filter((current) => current.id !== artifact.id),
    ]);
  };

  const handleDownloadExportArtifact = async (artifact: ContentOpsExportArtifact) => {
    const download = await downloadContentOpsExportArtifact(artifact);
    saveBlobAsFile(
      download.blob,
      download.filename || buildContentOpsExportFilename(workspace.name),
    );
  };

  if (isLoading) {
    return (
      <section className="content-ops-page" aria-labelledby="content-ops-title">
        <header className="content-ops-header">
          <div>
            <p className="dashboardEyebrow">Content Ops</p>
            <h1 id="content-ops-title">Loading content workspace</h1>
          </div>
        </header>
        <DashboardState
          variant="loading"
          layout="page"
          message="Loading Content Ops workspace..."
        />
      </section>
    );
  }

  const visibleWarning =
    warning ??
    (source === 'mock'
      ? 'Showing mock Content Ops data. Live workspace actions are disabled until API data loads.'
      : null);
  const canExportPlan = canCreate && source === 'api' && Boolean(workspace.id);
  const canGenerateCaptions = canCreate && source === 'api' && Boolean(workspace.id);
  const canCreateBrief = canCreate && source === 'api' && Boolean(workspace.id);
  const canCreateDraft = canCreate && source === 'api' && Boolean(workspace.id);

  return (
    <section className="content-ops-page" aria-labelledby="content-ops-title">
      <header className="content-ops-header">
        <div>
          <p className="dashboardEyebrow">Content Ops</p>
          <h1 id="content-ops-title">{workspace.name}</h1>
          <p>
            {workspace.calendarWindow} · {workspace.timezone}
          </p>
        </div>
        <div className="content-ops-header__actions">
          <span
            className={`content-ops-source content-ops-source--${source}`}
            title={visibleWarning ?? undefined}
          >
            {source === 'api' ? 'Live API' : 'Mock fallback - not live data'}
          </span>
          <Link to="/dashboards/meta/pages" className="button tertiary">
            Meta pages
          </Link>
          <button
            type="button"
            className="button secondary"
            disabled={!canExportPlan || exportStatus === 'submitting'}
            onClick={() => void handleExportPlan()}
          >
            {exportStatus === 'submitting' ? 'Exporting...' : 'Export plan'}
          </button>
          <button
            type="button"
            className="button primary"
            disabled={!canCreateBrief}
            onClick={() => setShowBriefForm((value) => !value)}
          >
            New brief
          </button>
        </div>
      </header>

      {visibleWarning ? <p className="content-ops-warning">{visibleWarning}</p> : null}
      {exportMessage ? (
        <p className={`content-ops-export-message content-ops-export-message--${exportStatus}`}>
          {exportMessage}
        </p>
      ) : null}

      {showBriefForm ? (
        <BriefCreatePanel
          onCreateBrief={handleCreateBrief}
          onDismiss={() => setShowBriefForm(false)}
        />
      ) : null}

      {showDraftForm ? (
        <DraftCreatePanel
          onCreateDraft={handleCreateDraft}
          onDismiss={() => setShowDraftForm(false)}
        />
      ) : null}

      <section className="content-ops-section" aria-labelledby="readiness-title">
        <div className="content-ops-section__header">
          <h2 id="readiness-title">Readiness</h2>
          <span>Current gates</span>
        </div>
        <ReadinessSummary readiness={workspace.readiness} />
        <ul className="content-ops-readiness" data-testid="content-ops-readiness">
          {workspace.readiness.map((axis) => (
            <ReadinessItem axis={axis} key={axis.id} />
          ))}
        </ul>
      </section>

      <div className="content-ops-main-grid">
        <section className="content-ops-section" aria-labelledby="brief-title">
          <div className="content-ops-section__header">
            <h2 id="brief-title">Brief</h2>
            <span>{workspace.brief.client}</span>
          </div>
          <div className="content-ops-brief">
            <h3>{workspace.brief.title}</h3>
            <dl>
              <div>
                <dt>Audience</dt>
                <dd>{workspace.brief.audience}</dd>
              </div>
              <div>
                <dt>Offer</dt>
                <dd>{workspace.brief.offer}</dd>
              </div>
              <div>
                <dt>Tone</dt>
                <dd>{workspace.brief.tone}</dd>
              </div>
              <div>
                <dt>Required terms</dt>
                <dd>{workspace.brief.requiredTerms.join(', ')}</dd>
              </div>
              <div>
                <dt>Blocked terms</dt>
                <dd>{workspace.brief.blockedTerms.join(', ')}</dd>
              </div>
            </dl>
          </div>
        </section>
        <GenerationPanel
          briefId={workspace.brief.id}
          canGenerate={canGenerateCaptions}
          jobs={workspace.generationJobs}
          onCancelJob={handleCancelGenerationJob}
          onCreateCandidateDraft={handleCreateDraft}
          onGenerateCaptions={handleGenerateCaptions}
          source={source}
        />
      </div>

      <MediaUploadPanel
        canCreate={canCreate}
        workspaceId={workspace.id}
        uploadedAssets={uploadedAssets}
        onUploaded={(asset) => setUploadedAssets((assets) => [asset, ...assets])}
      />

      <div className="content-ops-main-grid">
        <CalendarPanel
          drafts={workspace.drafts}
          queue={workspace.queue}
          timezone={workspace.timezone}
        />
        <ClientReviewPanel drafts={workspace.drafts} />
      </div>

      <ContentReportPanel overview={reportOverview} posts={reportPosts} source={source} />

      <ExportHistoryPanel
        artifacts={exportArtifacts}
        canExport={canExportPlan}
        onCreateArtifact={handleCreateExportArtifact}
        onDownloadArtifact={handleDownloadExportArtifact}
      />

      <section className="content-ops-section" aria-labelledby="queue-title">
        <div className="content-ops-section__header">
          <h2 id="queue-title">Production Queue</h2>
          <span>{workspace.queue.length} scheduled channel rows</span>
        </div>
        <div className="content-ops-table-wrap">
          <table className="content-ops-table">
            <thead>
              <tr>
                <th scope="col">Draft</th>
                <th scope="col">Channel</th>
                <th scope="col">Due</th>
                <th scope="col">State</th>
                <th scope="col">Detail</th>
                <th scope="col">Action</th>
              </tr>
            </thead>
            <tbody>
              {workspace.queue.map((item) => (
                <QueueRow
                  canRetry={canCreate && source === 'api'}
                  item={item}
                  key={item.id}
                  onRetry={handleRetryQueueItem}
                />
              ))}
            </tbody>
          </table>
        </div>
      </section>

      <section className="content-ops-section" aria-labelledby="drafts-title">
        <div className="content-ops-section__header">
          <h2 id="drafts-title">Draft Editor</h2>
          <button
            type="button"
            className="button secondary"
            disabled={!canCreateDraft}
            onClick={() => setShowDraftForm((value) => !value)}
          >
            New draft
          </button>
        </div>
        <div className="content-ops-draft-list">
          {workspace.drafts.map((draft) => (
            <DraftPanel
              assets={uploadedAssets}
              canCreate={canCreate}
              canWorkflow={canCreate && source === 'api' && Boolean(workspace.id)}
              draft={draft}
              key={draft.id}
              onAttachAsset={handleAttachAsset}
              onDecideApproval={handleDecideApproval}
              onScheduleDraft={handleScheduleDraft}
              onSubmitClientReview={handleSubmitClientReview}
              onSubmitInternalReview={handleSubmitInternalReview}
            />
          ))}
        </div>
      </section>
    </section>
  );
};

export default ContentOpsPage;
