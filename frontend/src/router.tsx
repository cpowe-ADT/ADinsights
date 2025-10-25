import { createBrowserRouter, Navigate } from 'react-router-dom';

import BudgetDashboard from './routes/BudgetDashboard';
import CampaignDashboard from './routes/CampaignDashboard';
import CampaignDetail from './routes/CampaignDetail';
import CreativeDashboard from './routes/CreativeDashboard';
import CreativeDetail from './routes/CreativeDetail';
import DashboardLayout from './routes/DashboardLayout';
import Home from './pages/Home';
import LoginPage from './routes/LoginPage';
import ParishMapDetail from './routes/ParishMapDetail';
import ProtectedRoute from './routes/ProtectedRoute';

export const router = createBrowserRouter(
  [
    {
      path: '/login',
      element: <LoginPage />,
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
            { index: true, element: <Navigate to="campaigns" replace /> },
            { path: 'campaigns', element: <CampaignDashboard /> },
            { path: 'campaigns/:campaignId', element: <CampaignDetail /> },
            { path: 'creatives', element: <CreativeDashboard /> },
            { path: 'creatives/:creativeId', element: <CreativeDetail /> },
            { path: 'budget', element: <BudgetDashboard /> },
            { path: 'map', element: <ParishMapDetail /> },
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
      v7_startTransition: true,
    } as any,
  },
);

export default router;
