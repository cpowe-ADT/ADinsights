import { useEffect, useMemo } from "react";
import { NavLink, Outlet } from "react-router-dom";

import { useAuth } from "../auth/AuthContext";
import useDashboardStore from "../state/useDashboardStore";

const metricOptions = [
  { value: "spend", label: "Spend" },
  { value: "impressions", label: "Impressions" },
  { value: "clicks", label: "Clicks" },
  { value: "conversions", label: "Conversions" },
  { value: "roas", label: "ROAS" },
];

const DashboardLayout = () => {
  const { tenantId, logout, user } = useAuth();
  const {
    loadAll,
    selectedMetric,
    setSelectedMetric,
    selectedParish,
    campaign,
    creative,
    budget,
    parish,
  } = useDashboardStore((state) => ({
    loadAll: state.loadAll,
    selectedMetric: state.selectedMetric,
    setSelectedMetric: state.setSelectedMetric,
    selectedParish: state.selectedParish,
    campaign: state.campaign,
    creative: state.creative,
    budget: state.budget,
    parish: state.parish,
  }));

  useEffect(() => {
    void loadAll(tenantId);
  }, [loadAll, tenantId]);

  const errors = useMemo(() => {
    return [campaign, creative, budget, parish]
      .filter((slice) => slice.status === "error" && slice.error)
      .map((slice) => slice.error as string);
  }, [budget, campaign, creative, parish]);

  return (
    <div className="dashboard-shell">
      <header className="dashboard-header">
        <div>
          <h1>ADinsights</h1>
          <p className="muted">
            Tenant <strong>{tenantId ?? "unknown"}</strong>
            {selectedParish ? (
              <span>
                {" • "}Filtering to <strong>{selectedParish}</strong>
              </span>
            ) : null}
          </p>
        </div>
        <div className="header-actions">
          <label htmlFor="metric-select" className="muted">
            Map metric
          </label>
          <select
            id="metric-select"
            value={selectedMetric}
            onChange={(event) => setSelectedMetric(event.target.value as typeof selectedMetric)}
          >
            {metricOptions.map((option) => (
              <option key={option.value} value={option.value}>
                {option.label}
              </option>
            ))}
          </select>
          <span className="muted user-pill">{(user as { email?: string } | undefined)?.email ?? "Account"}</span>
          <button type="button" className="button tertiary" onClick={logout}>
            Log out
          </button>
        </div>
      </header>
      <nav className="dashboard-nav">
        <NavLink to="/dashboards/campaigns" className={({ isActive }) => (isActive ? "active" : undefined)}>
          Campaigns
        </NavLink>
        <NavLink to="/dashboards/creatives" className={({ isActive }) => (isActive ? "active" : undefined)}>
          Creatives
        </NavLink>
        <NavLink to="/dashboards/budget" className={({ isActive }) => (isActive ? "active" : undefined)}>
          Budget pacing
        </NavLink>
      </nav>
      {errors.length > 0 ? (
        <div className="status-message error" role="alert">
          {errors.map((message, index) => (
            <span key={`${message}-${index}`}>{message}</span>
          ))}
        </div>
      ) : null}
      <main className="dashboard-content">
        <Outlet />
      </main>
    </div>
  );
};

export default DashboardLayout;
