import CreativeTable from "../components/CreativeTable";
import FullPageLoader from "../components/FullPageLoader";
import useDashboardStore from "../state/useDashboardStore";

const CreativeDashboard = () => {
  const { creative, campaign, creativeRows } = useDashboardStore((state) => ({
    creative: state.creative,
    campaign: state.campaign,
    creativeRows: state.getCreativeRowsForSelectedParish(),
  }));

  const currency = campaign.data?.summary.currency ?? "USD";

  if (creative.status === "loading" && !creative.data) {
    return <FullPageLoader message="Loading creative performance…" />;
  }

  if (creative.status === "error" && !creative.data) {
    return <div className="status-message error">{creative.error ?? "Unable to load creative performance."}</div>;
  }

  if (!creative.data) {
    return <div className="status-message muted">Creative insights will appear once ads accrue spend.</div>;
  }

  return (
    <div className="dashboard-grid single-panel">
      <section className="panel full-width">
        <CreativeTable rows={creativeRows} currency={currency} />
      </section>
    </div>
  );
};

export default CreativeDashboard;
