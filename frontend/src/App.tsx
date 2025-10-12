import { useEffect } from "react";

import MetricsGrid from "./components/MetricsGrid";
import ParishMap from "./components/ParishMap";
import useDashboardStore, { MetricKey } from "./state/useDashboardStore";

const metricOptions: { label: string; value: MetricKey }[] = [
  { label: "Impressions", value: "impressions" },
  { label: "Clicks", value: "clicks" },
  { label: "Spend", value: "spend" },
  { label: "Conversions", value: "conversions" },
  { label: "ROAS", value: "roas" },
];

function App() {
  const { loadSampleData, selectedMetric, setSelectedMetric } = useDashboardStore();

  useEffect(() => {
    loadSampleData().catch((error) => {
      console.error("Failed to load sample data", error);
    });
  }, [loadSampleData]);

  return (
    <div className="app-shell">
      <header className="app-header">
        <div>
          <h1>Jamaica Ads Performance</h1>
          <p>Mock data to validate the multi-tenant dashboard experience.</p>
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
