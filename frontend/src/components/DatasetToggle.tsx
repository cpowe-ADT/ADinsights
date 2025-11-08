import { useEffect, type ChangeEvent } from 'react';

import { MOCK_MODE } from '../lib/apiClient';
import { useDatasetStore } from '../state/useDatasetStore';
import useDashboardStore from '../state/useDashboardStore';

const DATASET_LABELS: Record<'live' | 'dummy', string> = {
  live: 'Live data',
  dummy: 'Demo data',
};

const DatasetToggle = (): JSX.Element | null => {
  const {
    mode,
    status,
    adapters,
    error,
    source,
    loadAdapters,
    toggleMode,
    demoTenants,
    demoTenantId,
    setDemoTenantId,
  } = useDatasetStore((state) => ({
    mode: state.mode,
    status: state.status,
    adapters: state.adapters,
    error: state.error,
    source: state.source,
    loadAdapters: state.loadAdapters,
    toggleMode: state.toggleMode,
    demoTenants: state.demoTenants,
    demoTenantId: state.demoTenantId,
    setDemoTenantId: state.setDemoTenantId,
  }));

  const { activeTenantId, loadAll } = useDashboardStore((state) => ({
    activeTenantId: state.activeTenantId,
    loadAll: state.loadAll,
  }));

  const isLoading = status === 'loading';
  useEffect(() => {
    if (MOCK_MODE || status !== 'idle') {
      return;
    }

    void loadAdapters();
  }, [status, loadAdapters]);

  if (MOCK_MODE) {
    return null;
  }

  const hasDemoData = adapters.includes('demo') || adapters.includes('fake');
  const hasLiveData = adapters.includes('warehouse');

  const nextLabel = mode === 'live' ? 'Use dummy data' : 'Use live data';
  const badge = DATASET_LABELS[mode];

  const disabled = isLoading || (mode === 'dummy' && !hasLiveData) || (mode === 'live' && !hasDemoData);

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

  const handleDemoTenantChange = (event: ChangeEvent<HTMLSelectElement>) => {
    const nextTenant = event.target.value;
    setDemoTenantId(nextTenant);
    void loadAll(activeTenantId, { force: true });
  };

  return (
    <div className="dataset-toggle">
      <span className="muted dataset-toggle__badge">{badge}</span>
      <button
        type="button"
        className="button secondary"
        onClick={handleClick}
        disabled={disabled}
      >
        {isLoading ? 'Checking datasets…' : nextLabel}
      </button>
      {mode === 'dummy' && demoTenants.length > 0 ? (
        <label className="muted dataset-toggle__selector">
          Demo tenant
          <select
            value={demoTenantId ?? demoTenants[0]?.id}
            onChange={handleDemoTenantChange}
            className="dataset-toggle__select"
          >
            {demoTenants.map((tenant) => (
              <option key={tenant.id} value={tenant.id}>
                {tenant.label}
              </option>
            ))}
          </select>
        </label>
      ) : null}
      {isLoading ? (
        <span className="muted dataset-toggle__error" role="status">
          Loading dataset availability…
        </span>
      ) : null}
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
