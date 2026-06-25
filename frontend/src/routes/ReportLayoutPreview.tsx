import { useState } from 'react';

import {
  GridCanvas,
  LayoutEditor,
  loadLayout,
  saveLayout,
  slbSampleLayout,
  type DashboardLayoutConfig,
} from '../components/report-layout';

import '../styles/dashboard.css';

/**
 * Config-driven report layout (foundation for customizable views) + a working
 * drag-and-drop editor. The whole report is the {@link DashboardLayoutConfig};
 * the editor only mutates that config, which {@link GridCanvas} renders read-only
 * — so the view and the editor never drift. Edits persist to localStorage today;
 * a tenant/user-scoped backend store is the planned follow-up.
 */
const ReportLayoutPreview = () => {
  const [editing, setEditing] = useState(false);
  const [layout, setLayout] = useState<DashboardLayoutConfig>(
    () => loadLayout(slbSampleLayout.id) ?? slbSampleLayout,
  );
  const [savedNote, setSavedNote] = useState<string | null>(null);

  const handleSave = (next: DashboardLayoutConfig) => {
    saveLayout(next);
    setSavedNote('Saved to this browser');
  };

  return (
    <section className="dashboardPage" aria-label="Report layout preview">
      <header className="dashboardPageHeader">
        <p className="dashboardEyebrow">Report builder · {editing ? 'edit' : 'preview'}</p>
        <h1 className="dashboardHeading">Config-driven layout</h1>
        <p className="muted">
          This entire report is rendered from a saved layout config. Switch to edit mode to drag,
          resize, add, and remove charts — the foundation for fully customizable views. Values shown
          are the real edge-sourced SLB May 2026 figures.
        </p>
        <div className="report-builder-actions" style={{ display: 'flex', gap: '0.75rem', alignItems: 'center', marginTop: '0.5rem' }}>
          <button type="button" className="button" onClick={() => setEditing((v) => !v)}>
            {editing ? 'Done editing' : 'Edit layout'}
          </button>
          {savedNote ? <span className="muted">{savedNote}</span> : null}
        </div>
      </header>

      {editing ? (
        <LayoutEditor layout={layout} onChange={setLayout} onSave={handleSave} />
      ) : (
        <GridCanvas layout={layout} />
      )}
    </section>
  );
};

export default ReportLayoutPreview;
