import { createBrowserRouter, Navigate } from 'react-router-dom';

import BudgetDashboard from './routes/BudgetDashboard';
import CampaignDashboard from './routes/CampaignDashboard';
import CampaignDetail from './routes/CampaignDetail';
import CreativeDashboard from './routes/CreativeDashboard';
import CreativeDetail from './routes/CreativeDetail';
import AlertsPage from './routes/AlertsPage';
import AlertDetailPage from './routes/AlertDetailPage';
import AuditLogPage from './routes/AuditLogPage';
import DashboardCreate from './routes/DashboardCreate';
import DashboardLibrary from './routes/DashboardLibrary';
import CsvUpload from './routes/CsvUpload';
import DataSources from './routes/DataSources';
import DashboardLayout from './routes/DashboardLayout';
import HealthOverviewPage from './routes/HealthOverviewPage';
import Home from './pages/Home';
import InviteAcceptPage from './routes/InviteAcceptPage';
import LoginPage from './routes/LoginPage';
import PasswordResetPage from './routes/PasswordResetPage';
import ParishMapDetail from './routes/ParishMapDetail';
import ProtectedRoute from './routes/ProtectedRoute';
import ReportCreatePage from './routes/ReportCreatePage';
import ReportDetailPage from './routes/ReportDetailPage';
import ReportsPage from './routes/ReportsPage';
import SummariesPage from './routes/SummariesPage';
import SummaryDetailPage from './routes/SummaryDetailPage';
import SyncHealthPage from './routes/SyncHealthPage';

export const router = createBrowserRouter(
  [
    {
      path: '/login',
      element: <LoginPage />,
    },
    {
      path: '/invite',
      element: <InviteAcceptPage />,
    },
    {
      path: '/password-reset',
      element: <PasswordResetPage />,
    },
    {
      element: <ProtectedRoute />,
      children: [
        {
          path: '/',
          element: <Home />,
        },
        {
          path: '/ops/sync-health',
          element: <SyncHealthPage />,
        },
        {
          path: '/ops/health',
          element: <HealthOverviewPage />,
        },
        {
          path: '/ops/audit',
          element: <AuditLogPage />,
        },
        {
          path: '/reports',
          element: <ReportsPage />,
        },
        {
          path: '/reports/new',
          element: <ReportCreatePage />,
        },
        {
          path: '/reports/:reportId',
          element: <ReportDetailPage />,
        },
        {
          path: '/alerts',
          element: <AlertsPage />,
        },
        {
          path: '/alerts/:alertId',
          element: <AlertDetailPage />,
        },
        {
          path: '/summaries',
          element: <SummariesPage />,
        },
        {
          path: '/summaries/:summaryId',
          element: <SummaryDetailPage />,
        },
        {
          path: '/dashboards',
          element: <DashboardLayout />,
          children: [
            { index: true, element: <DashboardLibrary /> },
            { path: 'create', element: <DashboardCreate /> },
            { path: 'campaigns', element: <CampaignDashboard /> },
            { path: 'campaigns/:campaignId', element: <CampaignDetail /> },
            { path: 'creatives', element: <CreativeDashboard /> },
            { path: 'creatives/:creativeId', element: <CreativeDetail /> },
            { path: 'budget', element: <BudgetDashboard /> },
            { path: 'data-sources', element: <DataSources /> },
            { path: 'map', element: <ParishMapDetail /> },
            { path: 'uploads', element: <CsvUpload /> },
          ],
        },
      ],
    },
    {
      path: '*',
      element: <Navigate to="/" replace />,
    },
  ],
  {
    future: undefined,
  },
);

export default router;
