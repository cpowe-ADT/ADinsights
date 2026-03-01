import type { SavedViewRecord, WorkspaceFilters } from './types';

type Props = {
  filters: WorkspaceFilters;
  onFiltersChange: (next: WorkspaceFilters) => void;
  savedViews: SavedViewRecord[];
  selectedSavedViewId: string;
  onSelectSavedView: (id: string) => void;
  onSaveView: () => void;
  onUpdateView: () => void;
  onExport: (format: 'csv' | 'pdf') => void;
  busy: boolean;
};

const WorkspaceHeader = ({
  filters,
  onFiltersChange,
  savedViews,
  selectedSavedViewId,
  onSelectSavedView,
  onSaveView,
  onUpdateView,
  onExport,
  busy,
}: Props) => {
  return (
    <div className="panel gads-workspace__header" role="region" aria-label="Google Ads workspace filters">
      <div className="gads-workspace__filters-grid">
        <label className="dashboard-field" htmlFor="gads-start-date">
          <span className="dashboard-field__label">Start</span>
          <input
            id="gads-start-date"
            type="date"
            value={filters.startDate}
            onChange={(event) => onFiltersChange({ ...filters, startDate: event.target.value })}
          />
        </label>
        <label className="dashboard-field" htmlFor="gads-end-date">
          <span className="dashboard-field__label">End</span>
          <input
            id="gads-end-date"
            type="date"
            value={filters.endDate}
            onChange={(event) => onFiltersChange({ ...filters, endDate: event.target.value })}
          />
        </label>
        <label className="dashboard-field" htmlFor="gads-compare">
          <span className="dashboard-field__label">Compare</span>
          <select
            id="gads-compare"
            value={filters.compare}
            onChange={(event) =>
              onFiltersChange({
                ...filters,
                compare: event.target.value as WorkspaceFilters['compare'],
              })
            }
          >
            <option value="none">None</option>
            <option value="dod">DoD</option>
            <option value="wow">WoW</option>
            <option value="mom">MoM</option>
            <option value="yoy">YoY</option>
          </select>
        </label>
        <label className="dashboard-field" htmlFor="gads-customer-id">
          <span className="dashboard-field__label">Account ID</span>
          <input
            id="gads-customer-id"
            type="text"
            placeholder="Optional"
            value={filters.customerId}
            onChange={(event) => onFiltersChange({ ...filters, customerId: event.target.value })}
          />
        </label>
        <label className="dashboard-field" htmlFor="gads-campaign-id">
          <span className="dashboard-field__label">Campaign ID</span>
          <input
            id="gads-campaign-id"
            type="text"
            placeholder="Optional"
            value={filters.campaignId}
            onChange={(event) => onFiltersChange({ ...filters, campaignId: event.target.value })}
          />
        </label>
      </div>

      <div className="gads-workspace__header-actions">
        <label className="dashboard-field" htmlFor="gads-saved-view">
          <span className="dashboard-field__label">Saved view</span>
          <select
            id="gads-saved-view"
            value={selectedSavedViewId}
            onChange={(event) => onSelectSavedView(event.target.value)}
          >
            <option value="">Current filters</option>
            {savedViews.map((view) => (
              <option key={view.id} value={view.id}>
                {view.name}
              </option>
            ))}
          </select>
        </label>
        <button className="button secondary" type="button" onClick={onSaveView} disabled={busy}>
          Save view
        </button>
        <button
          className="button secondary"
          type="button"
          onClick={onUpdateView}
          disabled={busy || !selectedSavedViewId}
        >
          Update view
        </button>
        <button className="button secondary" type="button" onClick={() => onExport('csv')} disabled={busy}>
          Export CSV
        </button>
        <button className="button secondary" type="button" onClick={() => onExport('pdf')} disabled={busy}>
          Export PDF
        </button>
      </div>
    </div>
  );
};

export default WorkspaceHeader;
