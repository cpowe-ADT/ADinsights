import { FormEvent, useEffect, useState } from "react";

import MetricsGrid from "./components/MetricsGrid";
import ParishMap from "./components/ParishMap";
import { useAuth } from "./auth/AuthContext";
import useDashboardStore, { MetricKey } from "./state/useDashboardStore";

const metricOptions: { label: string; value: MetricKey }[] = [
  { label: "Impressions", value: "impressions" },
  { label: "Clicks", value: "clicks" },
  { label: "Spend", value: "spend" },
  { label: "Conversions", value: "conversions" },
  { label: "ROAS", value: "roas" },
];

function App() {
  const { login, logout, status: authStatus, isAuthenticated, error: authError, tenantId } = useAuth();
  const { loadMetrics, selectedMetric, setSelectedMetric } = useDashboardStore();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");

  useEffect(() => {
    if (!isAuthenticated) {
      return;
    }

    loadMetrics(tenantId).catch((error) => {
      console.error("Failed to load campaign metrics", error);
    });
  }, [isAuthenticated, loadMetrics, tenantId]);

  const handleSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    try {
      await login(email, password);
    } catch {
      // Errors handled in auth context state
    }
  };

  if (!isAuthenticated) {
    return (
      <div className="app-shell">
        <header className="app-header">
          <div>
            <h1>ADinsights Dashboard</h1>
            <p>Sign in to view tenant-specific campaign performance.</p>
          </div>
        </header>
        <div className="auth-container">
          <form className="auth-form" onSubmit={handleSubmit}>
            <h2>Tenant Login</h2>
            <label htmlFor="email">Email</label>
            <input
              id="email"
              type="email"
              value={email}
              onChange={(event) => setEmail(event.target.value)}
              required
            />
            <label htmlFor="password">Password</label>
            <input
              id="password"
              type="password"
              value={password}
              onChange={(event) => setPassword(event.target.value)}
              required
            />
            {authError ? <p className="auth-error">{authError}</p> : null}
            <button type="submit" disabled={authStatus === "authenticating"}>
              {authStatus === "authenticating" ? "Signing in…" : "Sign In"}
            </button>
          </form>
        </div>
      </div>
    );
  }

  return (
    <div className="app-shell">
      <header className="app-header">
        <div>
          <h1>Jamaica Ads Performance</h1>
          <p>
            Viewing data for tenant <strong>{tenantId ?? "unknown"}</strong>.
          </p>
        </div>
        <div>
          <label htmlFor="metric-select">Metric: </label>
          <select
            id="metric-select"
            value={selectedMetric}
            onChange={(event) => setSelectedMetric(event.target.value as MetricKey)}
          >
            {metricOptions.map((option) => (
              <option key={option.value} value={option.value}>
                {option.label}
              </option>
            ))}
          </select>
          <button type="button" className="logout-button" onClick={logout}>
            Log out
          </button>
        </div>
      </header>
      <div className="app-content">
        <section className="map-pane">
          <ParishMap />
        </section>
        <section className="grid-pane">
          <MetricsGrid />
        </section>
      </div>
    </div>
  );
}

export default App;
