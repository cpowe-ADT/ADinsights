import { GridCanvas, slbSampleLayout } from '../components/report-layout';

import '../styles/dashboard.css';

/**
 * Preview of the config-driven report layout (foundation for customizable views
 * + drag-and-drop). The page is just a thin shell — the whole report is the
 * {@link slbSampleLayout} config rendered by {@link GridCanvas}. Swapping the
 * config (or binding live data via `resolveData`) is all it takes to change the
 * report; the future editor will mutate that config interactively.
 */
const ReportLayoutPreview = () => (
  <section className="dashboardPage" aria-label="Report layout preview">
    <header className="dashboardPageHeader">
      <p className="dashboardEyebrow">Report builder · preview</p>
      <h1 className="dashboardHeading">Config-driven layout</h1>
      <p className="muted">
        This entire report is rendered from a saved layout config — the foundation for
        customizable views and drag-and-drop charts. Values shown are the real edge-sourced
        SLB May 2026 figures.
      </p>
    </header>
    <GridCanvas layout={slbSampleLayout} />
  </section>
);

export default ReportLayoutPreview;
