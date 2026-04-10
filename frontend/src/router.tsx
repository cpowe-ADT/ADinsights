import { lazy, Suspense, type ReactElement } from 'react';
import { createBrowserRouter, Navigate, useParams } from 'react-router-dom';

import FullPageLoader from './components/FullPageLoader';
import ErrorPage from './pages/ErrorPage';
import Home from './pages/Home';
import InviteAcceptPage from './routes/InviteAcceptPage';
import LoginPage from './routes/LoginPage';
import NotFoundPage from './routes/NotFoundPage';
import PasswordResetPage from './routes/PasswordResetPage';
import ProtectedRoute from './routes/ProtectedRoute';
import {
  GoogleAdsCampaignDrawerRedirect,
  GoogleAdsTabRedirect,
} from './routes/google-ads/GoogleAdsLegacyRedirects';

const AlertCreatePage = lazy(() => import('./routes/AlertCreatePage'));
const AlertRunsPage = lazy(() => import('./routes/AlertRunsPage'));
const AlertsPage = lazy(() => import('./routes/AlertsPage'));
const AlertDetailPage = lazy(() => import('./routes/AlertDetailPage'));
const AuditLogPage = lazy(() => import('./routes/AuditLogPage'));
const BudgetDashboard = lazy(() => import('./routes/BudgetDashboard'));
const CampaignDashboard = lazy(() => import('./routes/CampaignDashboard'));
const CampaignDetail = lazy(() => import('./routes/CampaignDetail'));
const CreativeDashboard = lazy(() => import('./routes/CreativeDashboard'));
const CreativeDetail = lazy(() => import('./routes/CreativeDetail'));
const CsvUpload = lazy(() => import('./routes/CsvUpload'));
const CsvUploadDetail = lazy(() => import('./routes/CsvUploadDetail'));
const DashboardCreate = lazy(() => import('./routes/DashboardCreate'));
const DashboardLibrary = lazy(() => import('./routes/DashboardLibrary'));
const DashboardLayout = lazy(() => import('./routes/DashboardLayout'));
const SavedDashboardPage = lazy(() => import('./routes/SavedDashboardPage'));
const DataSources = lazy(() => import('./routes/DataSources'));
const GoogleAnalyticsDashboardPage = lazy(() => import('./routes/GoogleAnalyticsDashboardPage'));
const SearchConsoleDashboardPage = lazy(() => import('./routes/SearchConsoleDashboardPage'));
const GoogleAdsAssetsPage = lazy(() => import('./routes/google-ads/GoogleAdsAssetsPage'));
const GoogleAdsBreakdownsPage = lazy(() => import('./routes/google-ads/GoogleAdsBreakdownsPage'));
const GoogleAdsBudgetPage = lazy(() => import('./routes/google-ads/GoogleAdsBudgetPage'));
const GoogleAdsCampaignDetailPage = lazy(
  () => import('./routes/google-ads/GoogleAdsCampaignDetailPage'),
);
const GoogleAdsCampaignsPage = lazy(() => import('./routes/google-ads/GoogleAdsCampaignsPage'));
const GoogleAdsChangeLogPage = lazy(() => import('./routes/google-ads/GoogleAdsChangeLogPage'));
const GoogleAdsChannelsPage = lazy(() => import('./routes/google-ads/GoogleAdsChannelsPage'));
const GoogleAdsConversionsPage = lazy(
  () => import('./routes/google-ads/GoogleAdsConversionsPage'),
);
const GoogleAdsExecutivePage = lazy(() => import('./routes/google-ads/GoogleAdsExecutivePage'));
const GoogleAdsKeywordsPage = lazy(() => import('./routes/google-ads/GoogleAdsKeywordsPage'));
const GoogleAdsPmaxPage = lazy(() => import('./routes/google-ads/GoogleAdsPmaxPage'));
const GoogleAdsRecommendationsPage = lazy(
  () => import('./routes/google-ads/GoogleAdsRecommendationsPage'),
);
const GoogleAdsReportsPage = lazy(() => import('./routes/google-ads/GoogleAdsReportsPage'));
const GoogleAdsWorkspacePage = lazy(() => import('./routes/google-ads/GoogleAdsWorkspacePage'));
const HealthOverviewPage = lazy(() => import('./routes/HealthOverviewPage'));
const MetaAccountsPage = lazy(() => import('./routes/MetaAccountsPage'));
const MetaCampaignOverviewPage = lazy(() => import('./routes/MetaCampaignOverviewPage'));
const MetaConnectionStatusPage = lazy(() => import('./routes/MetaConnectionStatusPage'));
const MetaInsightsDashboardPage = lazy(() => import('./routes/MetaInsightsDashboardPage'));
const MetaIntegrationPage = lazy(() => import('./routes/MetaIntegrationPage'));
const MetaPagesListPage = lazy(() => import('./routes/MetaPagesListPage'));
const MetaPageOverviewPage = lazy(() => import('./routes/MetaPageOverviewPage'));
const MetaPagePostsPage = lazy(() => import('./routes/MetaPagePostsPage'));
const MetaPostDetailPage = lazy(() => import('./routes/MetaPostDetailPage'));
const ParishMapDetail = lazy(() => import('./routes/ParishMapDetail'));
const ProfilePage = lazy(() => import('./routes/ProfilePage'));
const ReportCreatePage = lazy(() => import('./routes/ReportCreatePage'));
const ReportDetailPage = lazy(() => import('./routes/ReportDetailPage'));
const ReportsPage = lazy(() => import('./routes/ReportsPage'));
const SummariesPage = lazy(() => import('./routes/SummariesPage'));
const SummaryDetailPage = lazy(() => import('./routes/SummaryDetailPage'));
const NotificationChannelsPage = lazy(() => import('./routes/NotificationChannelsPage'));
const SyncConnectionDetailPage = lazy(() => import('./routes/SyncConnectionDetailPage'));
const SyncHealthPage = lazy(() => import('./routes/SyncHealthPage'));

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

function withRouteLoader(element: ReactElement, message = 'Loading page…') {
  return <Suspense fallback={<FullPageLoader message={message} />}>{element}</Suspense>;
}

function resolveBooleanFlag(value: unknown, defaultValue: boolean): boolean {
  if (typeof value !== 'string') {
    return defaultValue;
  }
  const normalized = value.trim().toLowerCase();
  if (['1', 'true', 'yes', 'y', 'on'].includes(normalized)) {
    return true;
  }
  if (['0', 'false', 'no', 'n', 'off'].includes(normalized)) {
    return false;
  }
  return defaultValue;
}

const GOOGLE_ADS_WORKSPACE_UNIFIED = resolveBooleanFlag(
  import.meta.env.VITE_GOOGLE_ADS_WORKSPACE_UNIFIED,
  true,
);

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
      errorElement: <ErrorPage />,
      children: [
        {
          path: '/',
          element: <Home />,
        },
        {
          path: '/ops/sync-health',
          element: withRouteLoader(<SyncHealthPage />, 'Loading sync health…'),
        },
        {
          path: '/ops/sync-health/:connectionId',
          element: withRouteLoader(<SyncConnectionDetailPage />, 'Loading connection detail…'),
        },
        {
          path: '/ops/health',
          element: withRouteLoader(<HealthOverviewPage />, 'Loading health overview…'),
        },
        {
          path: '/ops/audit',
          element: withRouteLoader(<AuditLogPage />, 'Loading audit logs…'),
        },
        {
          path: '/reports',
          element: withRouteLoader(<ReportsPage />, 'Loading reports…'),
        },
        {
          path: '/reports/new',
          element: withRouteLoader(<ReportCreatePage />, 'Loading report builder…'),
        },
        {
          path: '/reports/:reportId',
          element: withRouteLoader(<ReportDetailPage />, 'Loading report…'),
        },
        {
          path: '/alerts',
          element: withRouteLoader(<AlertsPage />, 'Loading alerts…'),
        },
        {
          path: '/alerts/new',
          element: withRouteLoader(<AlertCreatePage />, 'Loading alert builder…'),
        },
        {
          path: '/alerts/history',
          element: withRouteLoader(<AlertRunsPage />, 'Loading alert history…'),
        },
        {
          path: '/alerts/:alertId',
          element: withRouteLoader(<AlertDetailPage />, 'Loading alert detail…'),
        },
        {
          path: '/settings/notifications',
          element: withRouteLoader(<NotificationChannelsPage />, 'Loading notification channels…'),
        },
        {
          path: '/integrations/meta',
          element: withRouteLoader(<MetaIntegrationPage />, 'Loading Meta integration…'),
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
          element: withRouteLoader(<SummariesPage />, 'Loading summaries…'),
        },
        {
          path: '/summaries/:summaryId',
          element: withRouteLoader(<SummaryDetailPage />, 'Loading summary detail…'),
        },
        {
          path: '/me',
          element: withRouteLoader(<ProfilePage />, 'Loading profile…'),
        },
        {
          path: '/dashboards',
          element: withRouteLoader(<DashboardLayout />, 'Loading dashboards…'),
          children: [
            {
              index: true,
              element: withRouteLoader(<DashboardLibrary />, 'Loading dashboards…'),
            },
            {
              path: 'create',
              element: withRouteLoader(<DashboardCreate />, 'Loading dashboard builder…'),
            },
            {
              path: 'saved/:dashboardId',
              element: withRouteLoader(<SavedDashboardPage />, 'Loading saved dashboard…'),
            },
            {
              path: 'campaigns',
              element: withRouteLoader(<CampaignDashboard />, 'Loading campaign dashboard…'),
            },
            {
              path: 'campaigns/:campaignId',
              element: withRouteLoader(<CampaignDetail />, 'Loading campaign detail…'),
            },
            {
              path: 'creatives',
              element: withRouteLoader(<CreativeDashboard />, 'Loading creative dashboard…'),
            },
            {
              path: 'creatives/:creativeId',
              element: withRouteLoader(<CreativeDetail />, 'Loading creative detail…'),
            },
            {
              path: 'budget',
              element: withRouteLoader(<BudgetDashboard />, 'Loading budget dashboard…'),
            },
            {
              path: 'data-sources',
              element: withRouteLoader(<DataSources />, 'Loading data sources…'),
            },
            {
              path: 'web/ga4',
              element: withRouteLoader(<GoogleAnalyticsDashboardPage />, 'Loading GA4 dashboard…'),
            },
            {
              path: 'web/search-console',
              element: withRouteLoader(<SearchConsoleDashboardPage />, 'Loading Search Console…'),
            },
            {
              path: 'meta/accounts',
              element: withRouteLoader(<MetaAccountsPage />, 'Loading Meta accounts…'),
            },
            {
              path: 'meta/campaigns',
              element: withRouteLoader(<MetaCampaignOverviewPage />, 'Loading Meta campaigns…'),
            },
            {
              path: 'meta/insights',
              element: withRouteLoader(<MetaInsightsDashboardPage />, 'Loading Meta insights…'),
            },
            {
              path: 'meta/status',
              element: withRouteLoader(<MetaConnectionStatusPage />, 'Loading Meta status…'),
            },
            {
              path: 'meta/pages',
              element: withRouteLoader(<MetaPagesListPage />, 'Loading Meta pages…'),
            },
            { path: 'meta/pages/:pageId', element: <MetaPageOverviewAliasRedirect /> },
            {
              path: 'meta/pages/:pageId/overview',
              element: withRouteLoader(
                <MetaPageOverviewPage />,
                'Loading Meta page overview…',
              ),
            },
            {
              path: 'meta/pages/:pageId/posts',
              element: withRouteLoader(<MetaPagePostsPage />, 'Loading Meta page posts…'),
            },
            {
              path: 'meta/posts/:postId',
              element: withRouteLoader(<MetaPostDetailPage />, 'Loading Meta post detail…'),
            },
            {
              path: 'google-ads',
              element: GOOGLE_ADS_WORKSPACE_UNIFIED
                ? withRouteLoader(
                    <GoogleAdsWorkspacePage />,
                    'Loading Google Ads workspace…',
                  )
                : <Navigate to="/dashboards/google-ads/executive" replace />,
            },
            {
              path: 'google-ads/executive',
              element: GOOGLE_ADS_WORKSPACE_UNIFIED
                ? <GoogleAdsTabRedirect tab="overview" />
                : withRouteLoader(<GoogleAdsExecutivePage />, 'Loading Google Ads overview…'),
            },
            {
              path: 'google-ads/campaigns',
              element: GOOGLE_ADS_WORKSPACE_UNIFIED
                ? <GoogleAdsTabRedirect tab="campaigns" />
                : withRouteLoader(
                    <GoogleAdsCampaignsPage />,
                    'Loading Google Ads campaigns…',
                  ),
            },
            {
              path: 'google-ads/campaigns/:campaignId',
              element: GOOGLE_ADS_WORKSPACE_UNIFIED
                ? <GoogleAdsCampaignDrawerRedirect />
                : withRouteLoader(
                    <GoogleAdsCampaignDetailPage />,
                    'Loading Google Ads campaign…',
                  ),
            },
            {
              path: 'google-ads/channels',
              element: GOOGLE_ADS_WORKSPACE_UNIFIED
                ? <GoogleAdsTabRedirect tab="campaigns" />
                : withRouteLoader(
                    <GoogleAdsChannelsPage />,
                    'Loading channel performance…',
                  ),
            },
            {
              path: 'google-ads/keywords',
              element: GOOGLE_ADS_WORKSPACE_UNIFIED
                ? <GoogleAdsTabRedirect tab="search" extra={{ search_mode: 'keywords' }} />
                : withRouteLoader(
                    <GoogleAdsKeywordsPage />,
                    'Loading keyword performance…',
                  ),
            },
            {
              path: 'google-ads/assets',
              element: GOOGLE_ADS_WORKSPACE_UNIFIED
                ? <GoogleAdsTabRedirect tab="assets" />
                : withRouteLoader(
                    <GoogleAdsAssetsPage />,
                    'Loading asset performance…',
                  ),
            },
            {
              path: 'google-ads/pmax',
              element: GOOGLE_ADS_WORKSPACE_UNIFIED
                ? <GoogleAdsTabRedirect tab="pmax" />
                : withRouteLoader(<GoogleAdsPmaxPage />, 'Loading Performance Max…'),
            },
            {
              path: 'google-ads/breakdowns',
              element: GOOGLE_ADS_WORKSPACE_UNIFIED
                ? <GoogleAdsTabRedirect tab="campaigns" />
                : withRouteLoader(<GoogleAdsBreakdownsPage />, 'Loading breakdowns…'),
            },
            {
              path: 'google-ads/conversions',
              element: GOOGLE_ADS_WORKSPACE_UNIFIED
                ? <GoogleAdsTabRedirect tab="conversions" />
                : withRouteLoader(<GoogleAdsConversionsPage />, 'Loading conversions…'),
            },
            {
              path: 'google-ads/budget',
              element: GOOGLE_ADS_WORKSPACE_UNIFIED
                ? <GoogleAdsTabRedirect tab="pacing" />
                : withRouteLoader(<GoogleAdsBudgetPage />, 'Loading budget pacing…'),
            },
            {
              path: 'google-ads/change-log',
              element: GOOGLE_ADS_WORKSPACE_UNIFIED
                ? <GoogleAdsTabRedirect tab="changes" />
                : withRouteLoader(<GoogleAdsChangeLogPage />, 'Loading change log…'),
            },
            {
              path: 'google-ads/recommendations',
              element: GOOGLE_ADS_WORKSPACE_UNIFIED
                ? <GoogleAdsTabRedirect tab="recommendations" />
                : withRouteLoader(
                    <GoogleAdsRecommendationsPage />,
                    'Loading recommendations…',
                  ),
            },
            {
              path: 'google-ads/reports',
              element: GOOGLE_ADS_WORKSPACE_UNIFIED
                ? <GoogleAdsTabRedirect tab="reports" />
                : withRouteLoader(<GoogleAdsReportsPage />, 'Loading saved views…'),
            },
            {
              path: 'map',
              element: withRouteLoader(<ParishMapDetail />, 'Loading parish map…'),
            },
            {
              path: 'uploads',
              element: withRouteLoader(<CsvUpload />, 'Loading CSV uploads…'),
            },
            {
              path: 'uploads/:uploadId',
              element: withRouteLoader(<CsvUploadDetail />, 'Loading upload detail…'),
            },
          ],
        },
      ],
    },
    {
      path: '*',
      element: <NotFoundPage />,
    },
  ],
  {
    future: {
      v7_relativeSplatPath: true,
    },
  },
);

export default router;
