import { useEffect, useMemo, useState } from 'react';

import { useAuth } from '../auth/AuthContext';
import useDashboardStore from '../state/useDashboardStore';
import {
  GridCanvas,
  LayoutEditor,
  createStoreResolver,
  liveDashboardLayout,
  loadLayout,
  saveLayout,
  type DashboardLayoutConfig,
} from '../components/report-layout';

import '../styles/dashboard.css';

/**
 * Config-driven report layout bound to **live** dashboard-store data, plus the
 * drag-and-drop editor. Widgets carry `dataKey`s ("summary.totalSpend",
 * "parish.spend", …); `createStoreResolver` maps them to the real campaign +
 * parish metrics the store loads. The editor mutates the same config the canvas
 * renders, so view and editor never drift. Layouts persist to localStorage today
 * (tenant/user backend store is the planned follow-up).
 */
const ReportLayoutPreview = () => {
  const { tenantId } = useAuth();
  const loadAll = useDashboardStore((state) => state.loadAll);
  const summary = useDashboardStore((state) => state.campaign.data?.summary ?? null);
  const parish = useDashboardStore((state) => state.parish.data ?? null);

  const [editing, setEditing] = useState(false);
  const [layout, setLayout] = useState<DashboardLayoutConfig>(
    () => loadLayout(liveDashboardLayout.id) ?? liveDashboardLayout,
  );
  const [savedNote, setSavedNote] = useState<string | null>(null);

  useEffect(() => {
    void loadAll(tenantId);
  }, [loadAll, tenantId]);

  const resolveData = useMemo(
    () =>
      createStoreResolver({
        summary: (summary as Record<string, unknown> | null) ?? undefined,
        parish: (parish as ReadonlyArray<Record<string, unknown>> | null) ?? undefined,
      }),
    [summary, parish],
  );

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
          This entire report is rendered from a saved layout config and bound to live dashboard
          data. Switch to edit mode to drag, resize, add, and remove charts — the foundation for
          fully customizable views.
        </p>
        <div
          className="report-builder-actions"
          style={{ display: 'flex', gap: '0.75rem', alignItems: 'center', marginTop: '0.5rem' }}
        >
          <button type="button" className="button" onClick={() => setEditing((v) => !v)}>
            {editing ? 'Done editing' : 'Edit layout'}
          </button>
          {savedNote ? <span className="muted">{savedNote}</span> : null}
        </div>
      </header>

      {editing ? (
        <LayoutEditor
          layout={layout}
          onChange={setLayout}
          onSave={handleSave}
          resolveData={resolveData}
        />
      ) : (
        <GridCanvas layout={layout} resolveData={resolveData} />
      )}
    </section>
  );
};

export default ReportLayoutPreview;
