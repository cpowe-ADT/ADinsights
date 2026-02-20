import { type FormEvent, useState } from 'react';
import { useNavigate } from 'react-router-dom';

import { createReport } from '../lib/phase2Api';
import '../styles/phase2.css';
import '../styles/dashboard.css';

const ReportCreatePage = () => {
  const navigate = useNavigate();
  const [name, setName] = useState('');
  const [description, setDescription] = useState('');
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const submit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (!name.trim()) {
      setError('Report name is required.');
      return;
    }

    setSaving(true);
    setError(null);
    try {
      const created = await createReport({
        name: name.trim(),
        description: description.trim(),
        filters: {},
        layout: {},
      });
      navigate(`/reports/${created.id}`);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Unable to create report.');
    } finally {
      setSaving(false);
    }
  };

  return (
    <section className="phase2-page">
      <header>
        <p className="dashboardEyebrow">Reporting</p>
        <h1 className="dashboardHeading">Create Report</h1>
        <p className="phase2-page__subhead">
          Create a report definition for exports and scheduled delivery.
        </p>
      </header>

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
            rows={5}
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
