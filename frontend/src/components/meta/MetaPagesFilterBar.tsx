import { useMemo } from 'react';

import type { MetaPageRecord } from '../../lib/metaPageInsights';
import {
  createMetaPageDefaultCustomRange,
  normalizeMetaPageDatePreset,
  type MetaPageDatePreset,
} from '../../lib/metaPageDateRange';

type MetaPagesFilterBarProps = {
  pages: MetaPageRecord[];
  selectedPageId: string;
  datePreset: string;
  since: string;
  until: string;
  onChangePage: (pageId: string) => void;
  onChangeDatePreset: (preset: MetaPageDatePreset) => void;
  onChangeSince: (value: string) => void;
  onChangeUntil: (value: string) => void;
};

const MetaPagesFilterBar = ({
  pages,
  selectedPageId,
  datePreset,
  since,
  until,
  onChangePage,
  onChangeDatePreset,
  onChangeSince,
  onChangeUntil,
}: MetaPagesFilterBarProps) => {
  const presets: { label: string; value: MetaPageDatePreset }[] = useMemo(
    () => [
      { label: 'Last 7 days', value: 'last_7d' },
      { label: 'Last 28 days', value: 'last_28d' },
      { label: 'Last 90 days', value: 'last_90d' },
      { label: 'Custom', value: 'custom' },
    ],
    [],
  );

  const presetValue = normalizeMetaPageDatePreset(datePreset);

  const onPresetChange = (value: MetaPageDatePreset) => {
    if (value !== 'custom') {
      onChangeDatePreset(value);
      return;
    }
    const defaults = createMetaPageDefaultCustomRange();
    onChangeDatePreset('custom');
    onChangeSince(since || defaults.since);
    onChangeUntil(until || defaults.until);
  };

  const normalizedPages = pages.slice().sort((a, b) => a.name.localeCompare(b.name));

  return (
    <div className="panel meta-controls-row" style={{ marginBottom: '1rem' }}>
      <label className="dashboard-field">
        <span className="dashboard-field__label">Page</span>
        <select
          value={selectedPageId}
          onChange={(event) => onChangePage(event.target.value)}
          disabled={normalizedPages.length === 0}
        >
          {normalizedPages.length === 0 ? <option value="">No pages</option> : null}
          {normalizedPages.map((page) => (
            <option key={page.page_id} value={page.page_id}>
              {page.name}
              {page.can_analyze ? '' : ' (no ANALYZE)'}
            </option>
          ))}
        </select>
      </label>

      <label className="dashboard-field">
        <span className="dashboard-field__label">Date range</span>
        <select value={presetValue} onChange={(event) => onPresetChange(event.target.value as MetaPageDatePreset)}>
          {presets.map((preset) => (
            <option key={preset.value} value={preset.value}>
              {preset.label}
            </option>
          ))}
        </select>
      </label>

      {presetValue === 'custom' ? (
        <>
          <label className="dashboard-field">
            <span className="dashboard-field__label">Since</span>
            <input type="date" value={since} onChange={(event) => onChangeSince(event.target.value)} />
          </label>
          <label className="dashboard-field">
            <span className="dashboard-field__label">Until</span>
            <input type="date" value={until} onChange={(event) => onChangeUntil(event.target.value)} />
          </label>
        </>
      ) : null}

      <p className="meta-note" style={{ margin: 0, alignSelf: 'flex-end' }}>
        Insights typically update daily; latest complete day is yesterday (America/Jamaica).
      </p>
    </div>
  );
};

export default MetaPagesFilterBar;
