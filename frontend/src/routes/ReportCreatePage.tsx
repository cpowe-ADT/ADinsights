import { type FormEvent, useState } from 'react';
import { useNavigate } from 'react-router-dom';

import { useAuth } from '../auth/AuthContext';
import DashboardState from '../components/DashboardState';
import { createReport } from '../lib/phase2Api';
import { canAccessCreatorUi } from '../lib/rbac';
import '../styles/phase2.css';
import '../styles/dashboard.css';

const ReportCreatePage = () => {
  const { user } = useAuth();
  const navigate = useNavigate();
  const canCreate = canAccessCreatorUi(user);
  const [name, setName] = useState('');
  const [description, setDescription] = useState('');
  const [filtersJson, setFiltersJson] = useState('{\n  "platforms": ["google", "meta"],\n  "lookback_days": 30\n}');
  const [layoutJson, setLayoutJson] = useState('{\n  "sections": ["performance", "creatives"]\n}');
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const applyTemplate = (type: 'full' | 'google' | 'meta') => {
    if (type === 'full') {
      setName('Full platform performance');
      setFiltersJson(JSON.stringify({ platforms: ['google', 'meta'], lookback_days: 30 }, null, 2));
      setLayoutJson(JSON.stringify({ sections: ['performance', 'creatives', 'budget'] }, null, 2));
    } else if (type === 'google') {
      setName('Google Ads summary');
      setFiltersJson(JSON.stringify({ platforms: ['google'], lookback_days: 14 }, null, 2));
      setLayoutJson(JSON.stringify({ sections: ['performance', 'search_terms'] }, null, 2));
    } else if (type === 'meta') {
      setName('Meta Ads deep dive');
      setFiltersJson(JSON.stringify({ platforms: ['meta'], lookback_days: 7 }, null, 2));
      setLayoutJson(JSON.stringify({ sections: ['performance', 'ad_sets', 'creatives'] }, null, 2));
    }
  };

  const formatJson = () => {
    try {
      setFiltersJson(JSON.stringify(JSON.parse(filtersJson), null, 2));
      setLayoutJson(JSON.stringify(JSON.parse(layoutJson), null, 2));
      setError(null);
    } catch {
      setError('Cannot format: Invalid JSON detected.');
    }
  };

  const submit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (!name.trim()) {
      setError('Report name is required.');
      return;
    }

    let filters = {};
    let layout = {};

    try {
      filters = JSON.parse(filtersJson);
    } catch {
      setError('Invalid JSON in Filters field.');
      return;
    }

    try {
      layout = JSON.parse(layoutJson);
    } catch {
      setError('Invalid JSON in Layout field.');
      return;
    }

    setSaving(true);
    setError(null);
    try {
      const created = await createReport({
        name: name.trim(),
        description: description.trim(),
        filters,
        layout,
      });
      navigate(`/reports/${created.id}`);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Unable to create report.');
    } finally {
      setSaving(false);
    }
  };

  if (!canCreate) {
    return (
      <DashboardState
        variant="empty"
        layout="page"
        title="Read-only reporting access"
        message="Viewer access can review reports, but cannot create new report definitions."
        actionLabel="Back to reports"
        onAction={() => navigate('/reports')}
      />
    );
  }

  return (
    <section className="phase2-page">
      <header>
        <p className="dashboardEyebrow">Reporting</p>
        <h1 className="dashboardHeading">Create Report</h1>
        <p className="phase2-page__subhead">
          Create a report definition for exports and scheduled delivery.
        </p>
      </header>

      <div className="phase2-form-helpers">
        <p className="phase2-form-helpers__label">Quick templates:</p>
        <div className="phase2-row-actions">
          <button type="button" className="button tertiary small" onClick={() => applyTemplate('full')}>
            Full platform
          </button>
          <button type="button" className="button tertiary small" onClick={() => applyTemplate('google')}>
            Google Ads
          </button>
          <button type="button" className="button tertiary small" onClick={() => applyTemplate('meta')}>
            Meta Ads
          </button>
          <button type="button" className="button tertiary small" style={{ marginLeft: 'auto' }} onClick={formatJson}>
            Format JSON
          </button>
        </div>
      </div>

      <form className="phase2-form" onSubmit={submit}>
        <label className="phase2-form__field" htmlFor="report-name">
          <span>Name</span>
          <input
            id="report-name"
            value={name}
            onChange={(event) => setName(event.target.value)}
            placeholder="Weekly performance review"
            disabled={saving}
          />
        </label>

        <label className="phase2-form__field" htmlFor="report-description">
          <span>Description</span>
          <textarea
            id="report-description"
            value={description}
            onChange={(event) => setDescription(event.target.value)}
            placeholder="Executive summary across campaigns and budgets"
            rows={3}
            disabled={saving}
          />
        </label>

        <label className="phase2-form__field" htmlFor="report-filters">
          <span>Filters (JSON)</span>
          <textarea
            id="report-filters"
            className="phase2-form__code"
            value={filtersJson}
            onChange={(event) => setFiltersJson(event.target.value)}
            rows={6}
            disabled={saving}
          />
        </label>

        <label className="phase2-form__field" htmlFor="report-layout">
          <span>Layout (JSON)</span>
          <textarea
            id="report-layout"
            className="phase2-form__code"
            value={layoutJson}
            onChange={(event) => setLayoutJson(event.target.value)}
            rows={6}
            disabled={saving}
          />
        </label>

        {error ? <p className="status-message error">{error}</p> : null}

        <div className="phase2-row-actions">
          <button type="button" className="button tertiary" onClick={() => navigate('/reports')}>
            Cancel
          </button>
          <button type="submit" className="button primary" disabled={saving}>
            {saving ? 'Creating…' : 'Create report'}
          </button>
        </div>
      </form>
    </section>
  );
};

export default ReportCreatePage;
