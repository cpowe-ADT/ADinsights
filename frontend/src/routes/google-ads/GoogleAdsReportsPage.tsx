import ReportsTabSection from '../../components/google-ads/workspace/tab-sections/ReportsTabSection';

/**
 * Legacy-mode Reports page (Sprint 3, S3c).
 *
 * The workflow form + saved-views table + export-job controls live in
 * `ReportsTabSection` so both modes (unified workspace tab and legacy route)
 * share a single implementation per architect §6.10.
 */
const GoogleAdsReportsPage = () => (
  <section className="dashboardPage">
    <header className="dashboardPageHeader">
      <p className="dashboardEyebrow">Google Ads</p>
      <h1 className="dashboardHeading">Reports & Exports</h1>
      <p className="dashboardSubtitle">
        Create on-demand exports and manage reusable saved views.
      </p>
    </header>

    <ReportsTabSection />
  </section>
);

export default GoogleAdsReportsPage;
