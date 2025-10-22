import { useEffect } from 'react';

import { MOCK_MODE } from '../lib/apiClient';
import { useDatasetStore } from '../state/useDatasetStore';
import useDashboardStore from '../state/useDashboardStore';

const DATASET_LABELS: Record<'live' | 'dummy', string> = {
  live: 'Live data',
  dummy: 'Demo data',
};

const DatasetToggle = (): JSX.Element | null => {
  if (MOCK_MODE) {
    return null;
  }

  const mode = useDatasetStore((state) => state.mode);
  const status = useDatasetStore((state) => state.status);
  const adapters = useDatasetStore((state) => state.adapters);
  const error = useDatasetStore((state) => state.error);
  const source = useDatasetStore((state) => state.source);
  const loadAdapters = useDatasetStore((state) => state.loadAdapters);
  const toggleMode = useDatasetStore((state) => state.toggleMode);

  const activeTenantId = useDashboardStore((state) => state.activeTenantId);
  const loadAll = useDashboardStore((state) => state.loadAll);

  useEffect(() => {
    if (status === 'idle') {
      void loadAdapters();
    }
  }, [status, loadAdapters]);

  const hasDemoData = adapters.includes('fake');
  const hasLiveData = adapters.includes('warehouse');

  const nextMode = mode === 'live' ? 'dummy' : 'live';
  const nextLabel = mode === 'live' ? 'Use dummy data' : 'Use live data';
  const badge = DATASET_LABELS[mode];

  const disabled = (mode === 'dummy' && !hasLiveData) || (mode === 'live' && !hasDemoData);

  const handleClick = () => {
    if (mode === 'live' && !hasDemoData) {
      return;
    }
    if (mode === 'dummy' && !hasLiveData) {
      return;
    }
    toggleMode();
    void loadAll(activeTenantId, { force: true });
  };

  return (
    <div className="dataset-toggle">
      <span className="muted dataset-toggle__badge">{badge}</span>
      <button
        type="button"
        className="button secondary"
        onClick={handleClick}
        disabled={status === 'loading' || disabled}
      >
        {nextLabel}
      </button>
      {error ? (
        <span className="muted dataset-toggle__error" role="status">
          {error}
        </span>
      ) : null}
      {!hasLiveData && mode === 'dummy' ? (
        <span className="muted dataset-toggle__error" role="status">
          Live warehouse data unavailable.
        </span>
      ) : null}
      {!hasDemoData && mode === 'live' ? (
        <span className="muted dataset-toggle__error" role="status">
          Demo dataset unavailable.
        </span>
      ) : null}
      {!source ? (
        <span className="muted dataset-toggle__error" role="status">
          Dataset unavailable. Results may be empty.
        </span>
      ) : null}
    </div>
  );
};

export default DatasetToggle;
