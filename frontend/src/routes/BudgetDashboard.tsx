import BudgetPacingList from "../components/BudgetPacingList";
import FullPageLoader from "../components/FullPageLoader";
import useDashboardStore from "../state/useDashboardStore";

const BudgetDashboard = () => {
  const { budget, campaign, budgetRows } = useDashboardStore((state) => ({
    budget: state.budget,
    campaign: state.campaign,
    budgetRows: state.getBudgetRowsForSelectedParish(),
  }));

  const currency = campaign.data?.summary.currency ?? "USD";

  if (budget.status === "loading" && !budget.data) {
    return <FullPageLoader message="Loading budget pacing…" />;
  }

  if (budget.status === "error" && !budget.data) {
    return <div className="status-message error">{budget.error ?? "Unable to load budget pacing."}</div>;
  }

  if (!budget.data) {
    return <div className="status-message muted">Budget pacing will appear once campaigns have budgets configured.</div>;
  }

  return (
    <div className="dashboard-grid single-panel">
      <section className="panel full-width">
        <header className="panel-header">
          <h2>Monthly pacing</h2>
          <p className="muted">Compare current spend against planned budgets.</p>
        </header>
        <BudgetPacingList rows={budgetRows} currency={currency} />
      </section>
    </div>
  );
};

export default BudgetDashboard;
