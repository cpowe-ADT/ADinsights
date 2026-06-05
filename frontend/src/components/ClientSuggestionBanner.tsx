/**
 * Sprint 9b: dashboard banner surfacing unacknowledged cross-platform client
 * suggestions. Reads the `ClientSuggestionSnapshot` built by the post-OAuth
 * Celery task and prompts the user to review them on /clients/suggest.
 *
 * Kept thin — self-fetches so DashboardLayout stays lean. Silent on fetch
 * failure (banner is a nice-to-have; no need to raise an error banner for it).
 */

import { useCallback, useEffect, useState } from 'react';
import { Link } from 'react-router-dom';

import {
  acknowledgeClientSuggestionSnapshot,
  getClientSuggestionSnapshot,
  type ClientSuggestionSnapshot,
} from '../lib/clients';

const triggerLabel = (reason: ClientSuggestionSnapshot['trigger_reason']): string => {
  switch (reason) {
    case 'meta_sync':
      return 'after your Meta sync';
    case 'google_sync':
      return 'after your Google Ads sync';
    default:
      return '';
  }
};

interface ClientSuggestionBannerProps {
  /** Only render when true — the dashboard gates on live-data readiness. */
  enabled: boolean;
}

export const ClientSuggestionBanner = ({ enabled }: ClientSuggestionBannerProps) => {
  const [snapshot, setSnapshot] = useState<ClientSuggestionSnapshot | null>(null);
  const [dismissed, setDismissed] = useState(false);
  const [working, setWorking] = useState(false);

  useEffect(() => {
    if (!enabled) {
      return;
    }
    let cancelled = false;
    void (async () => {
      try {
        const response = await getClientSuggestionSnapshot();
        if (cancelled) {
          return;
        }
        setSnapshot(response.snapshot);
      } catch {
        // Silent: banner is optional.
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [enabled]);

  const handleDismiss = useCallback(async () => {
    setWorking(true);
    try {
      await acknowledgeClientSuggestionSnapshot();
    } catch {
      // Silent — still hide locally so the user can move on.
    } finally {
      setDismissed(true);
      setWorking(false);
    }
  }, []);

  if (!enabled || dismissed || !snapshot || !snapshot.is_unacknowledged) {
    return null;
  }

  const count = snapshot.suggestion_count;
  const reasonText = triggerLabel(snapshot.trigger_reason);

  return (
    <div className="dashboard-status">
      <div className="dashboard-boundary">
        <div
          className="client-suggestion-banner"
          role="status"
          aria-live="polite"
          aria-label="New client suggestions"
        >
          <div className="client-suggestion-banner__body">
            <strong className="client-suggestion-banner__title">
              {count} new client suggestion{count === 1 ? '' : 's'}
            </strong>
            <span className="client-suggestion-banner__detail">
              We found accounts that look like they belong to the same Client
              {reasonText ? ` ${reasonText}` : ''}. Review and group them to see combined reporting.
            </span>
          </div>
          <div className="client-suggestion-banner__actions">
            <Link to="/clients/suggest" className="client-suggestion-banner__review">
              Review suggestions
            </Link>
            <button
              type="button"
              className="client-suggestion-banner__dismiss"
              onClick={handleDismiss}
              disabled={working}
            >
              Dismiss
            </button>
          </div>
        </div>
      </div>
    </div>
  );
};

export default ClientSuggestionBanner;
