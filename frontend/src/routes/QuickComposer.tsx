import {
  type ChangeEvent,
  type FormEvent,
  useEffect,
  useMemo,
  useRef,
  useState,
} from 'react';
import { Link } from 'react-router-dom';

import { ApiError } from '../lib/apiClient';
import {
  channelLabel,
  createContentOpsDraft,
  createContentOpsDraftWithVersion,
  createContentOpsVersionWithAsset,
  fetchContentOpsPublishingReadiness,
  listContentOpsWorkspaces,
  publishContentOpsDraftNow,
  uploadContentOpsAsset,
  type ContentOpsPublishingReadiness,
  type ContentOpsPublishNowResult,
  type ContentOpsWorkspaceSummary,
} from '../lib/contentOps';
import { type ContentOpsChannel } from '../lib/contentOpsMock';
import { useToastStore } from '../stores/useToastStore';
import './QuickComposer.css';

const CHANNELS: ContentOpsChannel[] = ['facebook_page', 'instagram'];
const CAPTION_MAX = 2200;
const IMAGE_MAX_BYTES = 8 * 1024 * 1024;
const IMAGE_ACCEPT = 'image/jpeg,image/png,image/webp';

const REASON_LABELS: Record<string, string> = {
  publishing_identity_missing: 'No destination is connected for this channel yet.',
  missing_publishing_permissions:
    'The Meta app is awaiting publishing permissions (Meta App Review).',
  upstream_readiness_blocked: 'Connect a Meta account and select a page first.',
  publishing_identity_blocked: 'This destination needs re-authentication.',
  instagram_not_linked: 'No Instagram business account is linked to the page.',
  meta_auth_required: 'Connect your Meta account first.',
  not_ready: 'Not ready for live publishing yet.',
};

const ATTEMPT_STATE_LABELS: Record<string, string> = {
  queued: 'Queued',
  preflight: 'Preparing',
  container_creating: 'Preparing media',
  container_pending: 'Processing media',
  container_ready: 'Ready',
  publishing: 'Publishing',
  published: 'Published',
  blocked: 'Blocked',
  failed_retryable: 'Failed — will retry',
  failed_terminal: 'Failed',
};

function humanizeReason(reason: string | null | undefined): string {
  if (!reason) return '';
  return REASON_LABELS[reason] ?? reason.replace(/_/g, ' ');
}

function attemptStateLabel(state: string): string {
  return ATTEMPT_STATE_LABELS[state] ?? state.replace(/_/g, ' ');
}

function badgeToneForState(state: string): 'ready' | 'blocked' | 'pending' {
  if (state === 'published') return 'ready';
  if (state === 'blocked' || state === 'failed_terminal' || state === 'failed_retryable') {
    return 'blocked';
  }
  return 'pending';
}

function describeError(error: unknown, fallback: string): string {
  if (error instanceof ApiError && error.payload) {
    const payload = error.payload as Record<string, unknown>;
    const fieldMessages = Object.entries(payload)
      .filter(([key]) => key !== 'detail' && key !== 'message')
      .flatMap(([, value]) => (Array.isArray(value) ? value : [value]))
      .map((value) => String(value))
      .filter(Boolean);
    if (fieldMessages.length > 0) return fieldMessages.join(' ');
  }
  return error instanceof Error && error.message ? error.message : fallback;
}

function deriveTitle(caption: string): string {
  const firstLine = caption
    .split('\n')
    .map((line) => line.trim())
    .find(Boolean);
  return (firstLine ?? '').slice(0, 80).trim() || 'Untitled post';
}

export default function QuickComposer() {
  const addToast = useToastStore((store) => store.addToast);

  const [workspaces, setWorkspaces] = useState<ContentOpsWorkspaceSummary[]>([]);
  const [workspaceId, setWorkspaceId] = useState('');
  const [readiness, setReadiness] = useState<ContentOpsPublishingReadiness[]>([]);
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState<string | null>(null);

  const [caption, setCaption] = useState('');
  const [selected, setSelected] = useState<Record<ContentOpsChannel, boolean>>({
    facebook_page: true,
    instagram: false,
  });
  const [submitting, setSubmitting] = useState(false);
  const [result, setResult] = useState<ContentOpsPublishNowResult | null>(null);
  const [imageFile, setImageFile] = useState<File | null>(null);
  const [imagePreview, setImagePreview] = useState<string | null>(null);
  const fileInputRef = useRef<HTMLInputElement | null>(null);

  useEffect(() => {
    const controller = new AbortController();
    setLoading(true);
    Promise.all([
      listContentOpsWorkspaces(controller.signal),
      fetchContentOpsPublishingReadiness(controller.signal),
    ])
      .then(([workspaceList, readinessList]) => {
        setWorkspaces(workspaceList);
        setWorkspaceId((current) => current || workspaceList[0]?.id || '');
        setReadiness(readinessList);
        const readyByChannel = new Map(readinessList.map((axis) => [axis.channel, axis.ready]));
        setSelected({
          facebook_page: readyByChannel.get('facebook_page') ?? true,
          instagram: readyByChannel.get('instagram') ?? false,
        });
        setLoadError(null);
      })
      .catch((error) => {
        if (controller.signal.aborted) return;
        setLoadError(describeError(error, 'Unable to load the composer.'));
      })
      .finally(() => {
        if (!controller.signal.aborted) setLoading(false);
      });
    return () => controller.abort();
  }, []);

  useEffect(() => {
    if (!imageFile) {
      setImagePreview(null);
      return;
    }
    const url = URL.createObjectURL(imageFile);
    setImagePreview(url);
    return () => URL.revokeObjectURL(url);
  }, [imageFile]);

  const readinessByChannel = useMemo(
    () => new Map(readiness.map((axis) => [axis.channel, axis])),
    [readiness],
  );

  const selectedChannels = CHANNELS.filter((channel) => selected[channel]);
  const instagramNeedsImage = selected.instagram && !imageFile;
  const canSubmit =
    !submitting &&
    Boolean(workspaceId) &&
    caption.trim().length > 0 &&
    selectedChannels.length > 0 &&
    !instagramNeedsImage;

  const toggleChannel = (channel: ContentOpsChannel) => {
    setSelected((current) => ({ ...current, [channel]: !current[channel] }));
  };

  const handleImageChange = (event: ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0] ?? null;
    if (file && file.size > IMAGE_MAX_BYTES) {
      addToast('That image is larger than 8 MB — please choose a smaller file.', 'error');
      return;
    }
    setImageFile(file);
  };

  const clearImage = () => {
    setImageFile(null);
    if (fileInputRef.current) {
      fileInputRef.current.value = '';
    }
  };

  const handleSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (!canSubmit) return;
    setSubmitting(true);
    setResult(null);
    try {
      const title = deriveTitle(caption);
      const primaryChannel = selectedChannels[0];
      let draftId: string;
      if (imageFile) {
        const draft = await createContentOpsDraft({ workspaceId, title });
        const asset = await uploadContentOpsAsset({
          workspaceId,
          file: imageFile,
          altText: caption.slice(0, 120),
        });
        await createContentOpsVersionWithAsset({
          draftId: draft.id,
          caption,
          channel: primaryChannel,
          mediaAssetIds: [],
          assetId: asset.id,
        });
        draftId = draft.id;
      } else {
        const draft = await createContentOpsDraftWithVersion({
          workspaceId,
          briefId: null,
          title,
          channel: primaryChannel,
          caption,
        });
        draftId = draft.id;
      }
      const publishResult = await publishContentOpsDraftNow({
        draftId,
        channels: selectedChannels.map((channel) => ({ type: channel })),
      });
      setResult(publishResult);
      const states = publishResult.attempts.map((attempt) => attempt.state);
      if (states.includes('published')) {
        addToast('Your post is live.', 'success');
      } else if (states.length > 0 && states.every((state) => state === 'blocked')) {
        addToast('Queued, but live publishing is not enabled yet — see status below.', 'info');
      } else {
        addToast('Post queued for publishing.', 'info');
      }
      setCaption('');
      clearImage();
    } catch (error) {
      addToast(describeError(error, 'Could not publish the post.'), 'error');
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <section className="composer">
      <header className="composer__header">
        <div>
          <h1 className="composer__title">Create post</h1>
          <p className="composer__subtitle">
            Write once and publish to your connected Facebook Page and Instagram.
          </p>
        </div>
        <Link className="button tertiary" to="/content">
          Open content studio
        </Link>
      </header>

      {loading ? (
        <p className="composer__muted">Loading composer…</p>
      ) : loadError ? (
        <div className="composer__banner composer__banner--error" role="alert">
          {loadError}
        </div>
      ) : workspaces.length === 0 ? (
        <div className="composer__banner">
          You need a content workspace before you can post.{' '}
          <Link to="/content">Create one in the content studio</Link>.
        </div>
      ) : (
        <form className="composer__form" onSubmit={handleSubmit}>
          {workspaces.length > 1 && (
            <label className="composer__field">
              <span className="composer__label">Workspace</span>
              <select
                className="composer__input"
                value={workspaceId}
                onChange={(event) => setWorkspaceId(event.target.value)}
              >
                {workspaces.map((workspace) => (
                  <option key={workspace.id} value={workspace.id}>
                    {workspace.name}
                  </option>
                ))}
              </select>
            </label>
          )}

          <label className="composer__field">
            <span className="composer__label">Caption</span>
            <textarea
              className="composer__input composer__textarea"
              value={caption}
              onChange={(event) => setCaption(event.target.value)}
              placeholder="What do you want to share?"
              rows={6}
              maxLength={CAPTION_MAX}
            />
            <span className="composer__hint">
              {caption.trim().length}/{CAPTION_MAX}
            </span>
          </label>

          <div className="composer__field">
            <span className="composer__label">Image (optional)</span>
            {imagePreview ? (
              <div className="composer__image-preview">
                <img src={imagePreview} alt="Selected post media preview" />
                <button type="button" className="button tertiary" onClick={clearImage}>
                  Remove image
                </button>
              </div>
            ) : (
              <input
                ref={fileInputRef}
                className="composer__input"
                type="file"
                accept={IMAGE_ACCEPT}
                aria-label="Attach an image"
                onChange={handleImageChange}
              />
            )}
            <span className="composer__hint">
              JPEG, PNG or WebP up to 8&nbsp;MB. Required for Instagram.
            </span>
          </div>

          <fieldset className="composer__field composer__destinations">
            <legend className="composer__label">Destinations</legend>
            {CHANNELS.map((channel) => {
              const axis = readinessByChannel.get(channel);
              const ready = axis?.ready ?? false;
              return (
                <label key={channel} className="composer__destination">
                  <input
                    type="checkbox"
                    checked={selected[channel]}
                    onChange={() => toggleChannel(channel)}
                  />
                  <span className="composer__destination-name">
                    {axis?.label ?? channelLabel(channel)}
                  </span>
                  <span
                    className={`composer__badge composer__badge--${ready ? 'ready' : 'blocked'}`}
                  >
                    {ready ? 'Ready' : 'Not live yet'}
                  </span>
                  {!ready && axis?.reason ? (
                    <span className="composer__destination-reason">
                      {humanizeReason(axis.reason)}
                    </span>
                  ) : null}
                </label>
              );
            })}
          </fieldset>

          {instagramNeedsImage ? (
            <p className="composer__warning" role="alert">
              Instagram posts require an image — attach one above, or unselect Instagram.
            </p>
          ) : null}

          <div className="composer__actions">
            <button className="button primary" type="submit" disabled={!canSubmit}>
              {submitting ? 'Posting…' : 'Post now'}
            </button>
            <span className="composer__hint">Scheduling is coming next.</span>
          </div>
        </form>
      )}

      {result ? (
        <div className="composer__result">
          <h2 className="composer__result-title">Publish status</h2>
          <ul className="composer__attempts">
            {result.attempts.map((attempt) => (
              <li key={attempt.id} className="composer__attempt">
                <span className="composer__attempt-channel">{channelLabel(attempt.channel)}</span>
                <span
                  className={`composer__badge composer__badge--${badgeToneForState(attempt.state)}`}
                >
                  {attemptStateLabel(attempt.state)}
                </span>
                {attempt.failure_detail_safe || attempt.failure_code ? (
                  <span className="composer__attempt-detail">
                    {attempt.failure_detail_safe || humanizeReason(attempt.failure_code)}
                  </span>
                ) : null}
              </li>
            ))}
            {result.attempts.length === 0 ? (
              <li className="composer__attempt composer__muted">
                No publish attempts were created — check that a destination is connected.
              </li>
            ) : null}
          </ul>
        </div>
      ) : null}
    </section>
  );
}
