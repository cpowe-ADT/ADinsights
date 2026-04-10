import { type FormEvent, useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';

import { createAlert } from '../lib/phase2Api';
import '../styles/phase2.css';
import '../styles/dashboard.css';

const METRIC_OPTIONS = [
  'spend',
  'impressions',
  'clicks',
  'conversions',
  'roas',
  'ctr',
  'cpc',
  'cpm',
  'cpa',
] as const;

const OPERATOR_OPTIONS = ['>', '<', '>=', '<=', '=='] as const;

const SEVERITY_OPTIONS = ['info', 'warning', 'critical'] as const;

const AlertCreatePage = () => {
  const navigate = useNavigate();
  const [name, setName] = useState('');
  const [metric, setMetric] = useState<string>(METRIC_OPTIONS[0]);
  const [comparisonOperator, setComparisonOperator] = useState<string>(OPERATOR_OPTIONS[0]);
  const [threshold, setThreshold] = useState('');
  const [lookbackHours, setLookbackHours] = useState('24');
  const [severity, setSeverity] = useState<string>(SEVERITY_OPTIONS[0]);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const submit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (!name.trim()) {
      setError('Alert name is required.');
      return;
    }
    const thresholdNum = Number(threshold);
    if (!Number.isFinite(thresholdNum) || thresholdNum < 0) {
      setError('Threshold must be a positive number.');
      return;
    }
    const lookbackNum = Number(lookbackHours);
    if (!Number.isInteger(lookbackNum) || lookbackNum <= 0) {
      setError('Lookback hours must be a positive integer.');
      return;
    }

    setSaving(true);
    setError(null);
    try {
      await createAlert({
        name: name.trim(),
        metric,
        comparison_operator: comparisonOperator,
        threshold: String(thresholdNum),
        lookback_hours: lookbackNum,
        severity,
      });
      navigate('/alerts');
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Unable to create alert.');
    } finally {
      setSaving(false);
    }
  };

  return (
    <section className="phase2-page">
      <header className="phase2-page__header">
        <div>
          <p className="dashboardEyebrow">Alerts</p>
          <h1 className="dashboardHeading">Create Alert Rule</h1>
          <p className="phase2-page__subhead">
            Define a threshold-based alert rule for automated monitoring.
          </p>
        </div>
      </header>

      <form className="phase2-form" onSubmit={submit}>
        <label className="phase2-form__field" htmlFor="alert-name">
          <span>Name</span>
          <input
            id="alert-name"
            value={name}
            onChange={(event) => setName(event.target.value)}
            placeholder="High spend alert"
            disabled={saving}
          />
        </label>

        <label className="phase2-form__field" htmlFor="alert-metric">
          <span>Metric</span>
          <select
            id="alert-metric"
            value={metric}
            onChange={(event) => setMetric(event.target.value)}
            disabled={saving}
          >
            {METRIC_OPTIONS.map((m) => (
              <option key={m} value={m}>
                {m}
              </option>
            ))}
          </select>
        </label>

        <label className="phase2-form__field" htmlFor="alert-operator">
          <span>Comparison operator</span>
          <select
            id="alert-operator"
            value={comparisonOperator}
            onChange={(event) => setComparisonOperator(event.target.value)}
            disabled={saving}
          >
            {OPERATOR_OPTIONS.map((op) => (
              <option key={op} value={op}>
                {op}
              </option>
            ))}
          </select>
        </label>

        <label className="phase2-form__field" htmlFor="alert-threshold">
          <span>Threshold</span>
          <input
            id="alert-threshold"
            type="number"
            value={threshold}
            onChange={(event) => setThreshold(event.target.value)}
            placeholder="100"
            min="0"
            step="any"
            disabled={saving}
          />
        </label>

        <label className="phase2-form__field" htmlFor="alert-lookback">
          <span>Lookback hours</span>
          <input
            id="alert-lookback"
            type="number"
            value={lookbackHours}
            onChange={(event) => setLookbackHours(event.target.value)}
            placeholder="24"
            min="1"
            step="1"
            disabled={saving}
          />
        </label>

        <label className="phase2-form__field" htmlFor="alert-severity">
          <span>Severity</span>
          <select
            id="alert-severity"
            value={severity}
            onChange={(event) => setSeverity(event.target.value)}
            disabled={saving}
          >
            {SEVERITY_OPTIONS.map((s) => (
              <option key={s} value={s}>
                {s}
              </option>
            ))}
          </select>
        </label>

        {error ? <p className="status-message error">{error}</p> : null}

        <div className="phase2-row-actions">
          <Link to="/alerts" className="button tertiary">
            Cancel
          </Link>
          <button type="submit" className="button primary" disabled={saving}>
            {saving ? 'Creating...' : 'Create alert'}
          </button>
        </div>
      </form>
    </section>
  );
};

export default AlertCreatePage;
