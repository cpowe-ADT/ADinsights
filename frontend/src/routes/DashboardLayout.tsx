import { useEffect, useMemo, useState } from "react";
import { Outlet, useLocation } from "react-router-dom";

import { useAuth } from "../auth/AuthContext";
import Breadcrumbs from "../components/Breadcrumbs";
import Header from "../components/Header";
import useDashboardStore from "../state/useDashboardStore";

const metricOptions = [
  { value: "spend", label: "Spend" },
  { value: "impressions", label: "Impressions" },
  { value: "clicks", label: "Clicks" },
  { value: "conversions", label: "Conversions" },
  { value: "roas", label: "ROAS" },
];

const segmentLabels: Record<string, string> = {
  dashboards: "Dashboards",
  campaigns: "Campaigns",
  creatives: "Creatives",
  budget: "Budget pacing",
};

const DashboardLayout = () => {
  const { tenantId, logout, user } = useAuth();
  const location = useLocation();
  const [isScrolled, setIsScrolled] = useState(false);
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

  useEffect(() => {
    const handleScroll = () => {
      setIsScrolled(window.scrollY > 4);
    };

    handleScroll();
    window.addEventListener("scroll", handleScroll, { passive: true });
    return () => window.removeEventListener("scroll", handleScroll);
  }, []);

  const errors = useMemo(() => {
    return [campaign, creative, budget, parish]
      .filter((slice) => slice.status === "error" && slice.error)
      .map((slice) => slice.error as string);
  }, [budget, campaign, creative, parish]);

  const navLinks = useMemo(
    () => [
      { label: "Campaigns", to: "/dashboards/campaigns", end: true },
      { label: "Creatives", to: "/dashboards/creatives", end: true },
      { label: "Budget pacing", to: "/dashboards/budget", end: true },
    ],
    [],
  );

  const activeNav = useMemo(
    () => navLinks.find((link) => location.pathname.startsWith(link.to)),
    [location.pathname, navLinks],
  );

  const breadcrumbs = useMemo(() => {
    const items: { label: string; to?: string }[] = [{ label: "Home", to: "/" }];
    const segments = location.pathname.split("/").filter(Boolean);
    let pathAccumulator = "";

    segments.forEach((segment, index) => {
      pathAccumulator += `/${segment}`;
      const label = segmentLabels[segment] ?? segment.replace(/-/g, " ");
      items.push({
        label: label.charAt(0).toUpperCase() + label.slice(1),
        to: index === segments.length - 1 ? undefined : pathAccumulator,
      });
    });

    return items;
  }, [location.pathname]);

  const subtitle = (
    <span>
      Tenant <strong>{tenantId ?? "unknown"}</strong>
      {selectedParish ? (
        <span>
          {" • "}Filtering to <strong>{selectedParish}</strong>
        </span>
      ) : null}
    </span>
  );

  return (
    <div className="dashboard-shell">
      <div className={`dashboard-top${isScrolled ? " shadow" : ""}`}>
        <Header
          title={activeNav?.label ?? "Dashboards"}
          subtitle={subtitle}
          navLinks={navLinks}
          metricOptions={metricOptions}
          selectedMetric={selectedMetric}
          onMetricChange={(value) => setSelectedMetric(value as typeof selectedMetric)}
          userEmail={(user as { email?: string } | undefined)?.email}
          onLogout={logout}
        />
        <Breadcrumbs items={breadcrumbs} />
      </div>
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
