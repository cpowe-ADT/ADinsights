import { useCallback, useEffect, useState } from 'react';

import {
  disconnectIntegration,
  loadIntegrationJobs,
  reconnectIntegration,
  type IntegrationJobRecord,
  type IntegrationProviderSlug,
} from '../lib/airbyte';
import { useToastStore } from '../stores/useToastStore';

interface ConnectorLifecycleControlsProps {
  provider: IntegrationProviderSlug;
  label: string;
  /** Notify the parent (e.g. to refresh connection status) after a disconnect. */
  onChanged?: () => void;
}

/**
 * Provider-agnostic connector lifecycle controls (salvaged from PR #339).
 *
 * Renders Reconnect / Disconnect actions plus a recent sync-job history for any
 * provider, driven entirely by the generic `api/integrations/<provider>/*`
 * endpoints. Self-contained so it can drop into any connector card without
 * entangling the host route's state.
 */
export function ConnectorLifecycleControls({
  provider,
  label,
  onChanged,
}: ConnectorLifecycleControlsProps) {
  const addToast = useToastStore((s) => s.addToast);
  const [jobs, setJobs] = useState<IntegrationJobRecord[]>([]);
  const [loadingJobs, setLoadingJobs] = useState(false);
  const [disconnecting, setDisconnecting] = useState(false);
  const [reconnecting, setReconnecting] = useState(false);

  const refreshJobs = useCallback(
    async (signal?: AbortSignal) => {
      setLoadingJobs(true);
      try {
        const payload = await loadIntegrationJobs(provider, 5, signal);
        setJobs(payload.jobs ?? []);
      } catch {
        // Job history is best-effort; never block the card on it.
        if (!signal?.aborted) {
          setJobs([]);
        }
      } finally {
        if (!signal?.aborted) {
          setLoadingJobs(false);
        }
      }
    },
    [provider],
  );

  useEffect(() => {
    const controller = new AbortController();
    void refreshJobs(controller.signal);
    return () => controller.abort();
  }, [refreshJobs]);

  const handleReconnect = useCallback(async () => {
    if (reconnecting) {
      return;
    }
    setReconnecting(true);
    try {
      const response = await reconnectIntegration(provider);
      if (response.authorize_url) {
        window.location.assign(response.authorize_url);
        return;
      }
      addToast(`${label} reconnect started.`, 'info');
    } catch (error) {
      const message = error instanceof Error ? error.message : 'Reconnect failed.';
      addToast(message, 'error');
      setReconnecting(false);
    }
  }, [addToast, label, provider, reconnecting]);

  const handleDisconnect = useCallback(async () => {
    if (disconnecting) {
      return;
    }
    setDisconnecting(true);
    try {
      await disconnectIntegration(provider);
      addToast(`${label} disconnected.`, 'success');
      onChanged?.();
      void refreshJobs();
    } catch (error) {
      const message = error instanceof Error ? error.message : 'Disconnect failed.';
      addToast(message, 'error');
    } finally {
      setDisconnecting(false);
    }
  }, [addToast, disconnecting, label, onChanged, provider, refreshJobs]);

  return (
    <div className="connector-lifecycle" data-provider={provider}>
      <div className="connector-lifecycle__actions">
        <button
          type="button"
          className="button tertiary"
          onClick={() => void handleReconnect()}
          disabled={reconnecting || disconnecting}
          aria-busy={reconnecting}
        >
          {reconnecting ? 'Redirecting…' : 'Reconnect'}
        </button>
        <button
          type="button"
          className="button tertiary"
          onClick={() => void handleDisconnect()}
          disabled={reconnecting || disconnecting}
          aria-busy={disconnecting}
        >
          {disconnecting ? 'Disconnecting…' : 'Disconnect'}
        </button>
      </div>
      <div className="connector-lifecycle__jobs">
        <span className="dashboard-field__label">
          {loadingJobs
            ? 'Loading sync jobs…'
            : jobs.length
              ? 'Recent sync jobs'
              : 'No sync jobs recorded yet.'}
        </span>
        {jobs.length ? (
          <ul className="connector-lifecycle__job-list">
            {jobs.slice(0, 3).map((job) => (
              <li key={job.job_id} className="connector-lifecycle__job">
                <span className="connector-lifecycle__job-status">{job.status}</span>
                <span className="connector-lifecycle__job-meta">
                  {new Date(job.started_at).toLocaleString()}
                  {typeof job.records_synced === 'number'
                    ? ` · ${job.records_synced.toLocaleString()} records`
                    : ''}
                </span>
              </li>
            ))}
          </ul>
        ) : null}
      </div>
    </div>
  );
}

export default ConnectorLifecycleControls;
