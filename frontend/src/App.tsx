import { BrowserRouter, Navigate, Route, Routes } from "react-router-dom";

import BudgetDashboard from "./routes/BudgetDashboard";
import CampaignDashboard from "./routes/CampaignDashboard";
import CreativeDashboard from "./routes/CreativeDashboard";
import DashboardLayout from "./routes/DashboardLayout";
import AppShell from "./routes/AppShell";
import ParishMapDetail from "./routes/ParishMapDetail";
import LoginPage from "./routes/LoginPage";
import ProtectedRoute from "./routes/ProtectedRoute";
import Home from "./pages/Home";

function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/login" element={<LoginPage />} />
        <Route element={<ProtectedRoute />}>
          <Route path="/" element={<AppShell />}>
            <Route index element={<Home />} />
            <Route path="dashboards" element={<DashboardLayout />}>
              <Route index element={<Navigate to="campaigns" replace />} />
              <Route path="campaigns" element={<CampaignDashboard />} />
              <Route path="creatives" element={<CreativeDashboard />} />
              <Route path="budget" element={<BudgetDashboard />} />
            </Route>
          <Route path="/" element={<Home />} />
          <Route path="/dashboards" element={<DashboardLayout />}>
            <Route index element={<Navigate to="campaigns" replace />} />
            <Route path="campaigns" element={<CampaignDashboard />} />
            <Route path="creatives" element={<CreativeDashboard />} />
            <Route path="budget" element={<BudgetDashboard />} />
            <Route path="map" element={<ParishMapDetail />} />
          </Route>
        </Route>
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </BrowserRouter>
  );
}

export default App;
