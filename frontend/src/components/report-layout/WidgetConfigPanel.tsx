import type { KpiFormat } from '../viz';
import type { DashboardWidget, WidgetOptions, WidgetType } from './layoutSchema';

const TYPES: readonly WidgetType[] = ['kpi', 'bar', 'pie', 'gauge', 'table', 'note'];
const FORMATS: readonly KpiFormat[] = ['number', 'currency', 'percent', 'rate'];

export interface WidgetConfigPanelProps {
  widget: DashboardWidget;
  onChange: (patch: Partial<DashboardWidget>) => void;
  onClose: () => void;
}

/**
 * Side panel for editing a selected widget: title, type, the `dataKey` that binds
 * it to live data, and type-specific options (KPI format/currency, gauge unit,
 * note text). Emits a patch the editor merges into the layout config.
 */
const WidgetConfigPanel = ({ widget, onChange, onClose }: WidgetConfigPanelProps) => {
  const opts = widget.options ?? {};
  const setOption = (patch: Partial<WidgetOptions>) =>
    onChange({ options: { ...opts, ...patch } });

  return (
    <aside className="report-config" aria-label={`Configure ${widget.title ?? widget.type}`}>
      <div className="report-config__head">
        <h3 className="report-config__title">Widget settings</h3>
        <button
          type="button"
          className="report-config__close"
          onClick={onClose}
          aria-label="Close settings"
        >
          ×
        </button>
      </div>

      <div className="report-config__grid">
        <label className="report-config__field">
          <span>Title</span>
          <input
            type="text"
            value={widget.title ?? ''}
            onChange={(e) => onChange({ title: e.target.value })}
          />
        </label>

        <label className="report-config__field">
          <span>Type</span>
          <select
            value={widget.type}
            onChange={(e) => onChange({ type: e.target.value as WidgetType })}
          >
            {TYPES.map((t) => (
              <option key={t} value={t}>
                {t}
              </option>
            ))}
          </select>
        </label>

        <label className="report-config__field">
          <span>Data key</span>
          <input
            type="text"
            placeholder="summary.totalSpend"
            value={widget.dataKey ?? ''}
            onChange={(e) => onChange({ dataKey: e.target.value || undefined })}
          />
        </label>

        {widget.type === 'kpi' ? (
          <label className="report-config__field">
            <span>Format</span>
            <select
              value={opts.format ?? 'number'}
              onChange={(e) => setOption({ format: e.target.value as KpiFormat })}
            >
              {FORMATS.map((f) => (
                <option key={f} value={f}>
                  {f}
                </option>
              ))}
            </select>
          </label>
        ) : null}

        {widget.type === 'kpi' && opts.format === 'currency' ? (
          <label className="report-config__field">
            <span>Currency</span>
            <input
              type="text"
              placeholder="JMD"
              value={opts.currency ?? ''}
              onChange={(e) => setOption({ currency: e.target.value || undefined })}
            />
          </label>
        ) : null}

        {widget.type === 'gauge' ? (
          <label className="report-config__field">
            <span>Unit</span>
            <input
              type="text"
              placeholder="%"
              value={opts.unit ?? ''}
              onChange={(e) => setOption({ unit: e.target.value || undefined })}
            />
          </label>
        ) : null}

        {widget.type === 'note' ? (
          <label className="report-config__field report-config__field--wide">
            <span>Text</span>
            <textarea
              rows={3}
              value={opts.text ?? ''}
              onChange={(e) => setOption({ text: e.target.value })}
            />
          </label>
        ) : null}
      </div>
    </aside>
  );
};

export default WidgetConfigPanel;
