import type { ChangeEvent } from 'react';

type DateRangePickerProps = {
  datePreset: string;
  since: string;
  until: string;
  onPresetChange: (value: string) => void;
  onSinceChange: (value: string) => void;
  onUntilChange: (value: string) => void;
};

const DateRangePicker = ({
  datePreset,
  since,
  until,
  onPresetChange,
  onSinceChange,
  onUntilChange,
}: DateRangePickerProps) => {
  const onPresetSelect = (event: ChangeEvent<HTMLSelectElement>) => onPresetChange(event.target.value);
  const onSinceSelect = (event: ChangeEvent<HTMLInputElement>) => onSinceChange(event.target.value);
  const onUntilSelect = (event: ChangeEvent<HTMLInputElement>) => onUntilChange(event.target.value);

  return (
    <div className="meta-controls-row">
      <label className="dashboard-field">
        <span className="dashboard-field__label">Preset</span>
        <select value={datePreset} onChange={onPresetSelect}>
          <option value="today">Today</option>
          <option value="yesterday">Yesterday</option>
          <option value="last_7d">Last 7d</option>
          <option value="last_14d">Last 14d</option>
          <option value="last_28d">Last 28d</option>
          <option value="last_30d">Last 30d</option>
          <option value="last_90d">Last 90d</option>
        </select>
      </label>
      <label className="dashboard-field">
        <span className="dashboard-field__label">Since</span>
        <input type="date" value={since} onChange={onSinceSelect} />
      </label>
      <label className="dashboard-field">
        <span className="dashboard-field__label">Until</span>
        <input type="date" value={until} onChange={onUntilSelect} />
      </label>
    </div>
  );
};

export default DateRangePicker;
