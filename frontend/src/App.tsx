import { BrowserRouter, Navigate, Route, Routes } from 'react-router-dom';

import BudgetDashboard from './routes/BudgetDashboard';
import CampaignDashboard from './routes/CampaignDashboard';
import CampaignDetail from './routes/CampaignDetail';
import CreativeDashboard from './routes/CreativeDashboard';
import CreativeDetail from './routes/CreativeDetail';
import DashboardLayout from './routes/DashboardLayout';
import LoginPage from './routes/LoginPage';
import ProtectedRoute from './routes/ProtectedRoute';
import Home from './pages/Home';
import { ToastProvider } from './components/ToastProvider';
import ParishMapDetail from './routes/ParishMapDetail';

function App() {
  return (
    <ToastProvider>
      <BrowserRouter>
        <Routes>
          <Route path="/login" element={<LoginPage />} />
          <Route element={<ProtectedRoute />}>
            <Route path="/" element={<Home />} />
            <Route path="/dashboards" element={<DashboardLayout />}>
              <Route index element={<Navigate to="campaigns" replace />} />
              <Route path="campaigns" element={<CampaignDashboard />} />
              <Route path="campaigns/:campaignId" element={<CampaignDetail />} />
              <Route path="creatives" element={<CreativeDashboard />} />
              <Route path="creatives/:creativeId" element={<CreativeDetail />} />
              <Route path="budget" element={<BudgetDashboard />} />
              <Route path="map" element={<ParishMapDetail />} />
            </Route>
          </Route>
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </BrowserRouter>
    </ToastProvider>
  );
}

export default App;
