import { createBrowserRouter, Navigate } from 'react-router-dom';

import BudgetDashboard from './routes/BudgetDashboard';
import CampaignDashboard from './routes/CampaignDashboard';
import CampaignDetail from './routes/CampaignDetail';
import CreativeDashboard from './routes/CreativeDashboard';
import CreativeDetail from './routes/CreativeDetail';
import DashboardCreate from './routes/DashboardCreate';
import DashboardLibrary from './routes/DashboardLibrary';
import CsvUpload from './routes/CsvUpload';
import DataSources from './routes/DataSources';
import DashboardLayout from './routes/DashboardLayout';
import Home from './pages/Home';
import InviteAcceptPage from './routes/InviteAcceptPage';
import LoginPage from './routes/LoginPage';
import PasswordResetPage from './routes/PasswordResetPage';
import ParishMapDetail from './routes/ParishMapDetail';
import ProtectedRoute from './routes/ProtectedRoute';

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
