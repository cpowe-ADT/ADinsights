import type { GoogleAdsSavedView, GoogleAdsWorkspaceSummaryResponse } from '../../../lib/googleAdsDashboard';

export type WorkspaceFilters = {
  startDate: string;
  endDate: string;
  compare: 'none' | 'dod' | 'wow' | 'mom' | 'yoy';
  customerId: string;
  campaignId: string;
};

export type WorkspaceTab =
  | 'overview'
  | 'campaigns'
  | 'search'
  | 'pmax'
  | 'assets'
  | 'conversions'
  | 'pacing'
  | 'changes'
  | 'recommendations'
  | 'reports';

export type SearchMode = 'keywords' | 'search_terms' | 'insights';

export type SavedViewRecord = GoogleAdsSavedView;

export type SummaryRecord = GoogleAdsWorkspaceSummaryResponse;
