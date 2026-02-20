import { createBrowserRouter, Navigate, useParams } from 'react-router-dom';

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
import MetaAccountsPage from './routes/MetaAccountsPage';
import MetaCampaignOverviewPage from './routes/MetaCampaignOverviewPage';
import MetaInsightsDashboardPage from './routes/MetaInsightsDashboardPage';
import MetaConnectionStatusPage from './routes/MetaConnectionStatusPage';
import MetaIntegrationPage from './routes/MetaIntegrationPage';
import MetaPagesListPage from './routes/MetaPagesListPage';
import MetaPageOverviewPage from './routes/MetaPageOverviewPage';
import MetaPagePostsPage from './routes/MetaPagePostsPage';
import MetaPostDetailPage from './routes/MetaPostDetailPage';

const MetaPageOverviewAliasRedirect = () => {
  const { pageId = '' } = useParams();
  return <Navigate to={`/dashboards/meta/pages/${pageId}/overview`} replace />;
};

const MetaPagePostsAliasRedirect = () => {
  const { pageId = '' } = useParams();
  return <Navigate to={`/dashboards/meta/pages/${pageId}/posts`} replace />;
};

const MetaPostAliasRedirect = () => {
  const { postId = '' } = useParams();
  return <Navigate to={`/dashboards/meta/posts/${postId}`} replace />;
};

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
          path: '/integrations/meta',
          element: <MetaIntegrationPage />,
        },
        {
          path: '/meta/pages',
          element: <Navigate to="/dashboards/meta/pages" replace />,
        },
        {
          path: '/meta/pages/:pageId/overview',
          element: <MetaPageOverviewAliasRedirect />,
        },
        {
          path: '/meta/pages/:pageId/posts',
          element: <MetaPagePostsAliasRedirect />,
        },
        {
          path: '/meta/posts/:postId',
          element: <MetaPostAliasRedirect />,
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
            { path: 'meta/accounts', element: <MetaAccountsPage /> },
            { path: 'meta/campaigns', element: <MetaCampaignOverviewPage /> },
            { path: 'meta/insights', element: <MetaInsightsDashboardPage /> },
            { path: 'meta/status', element: <MetaConnectionStatusPage /> },
            { path: 'meta/pages', element: <MetaPagesListPage /> },
            { path: 'meta/pages/:pageId', element: <MetaPageOverviewAliasRedirect /> },
            { path: 'meta/pages/:pageId/overview', element: <MetaPageOverviewPage /> },
            { path: 'meta/pages/:pageId/posts', element: <MetaPagePostsPage /> },
            { path: 'meta/posts/:postId', element: <MetaPostDetailPage /> },
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
    future: {
      v7_relativeSplatPath: true,
    },
  },
);

export default router;
