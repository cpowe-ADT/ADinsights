import apiClient from './apiClient';

export type DatasetLiveReason =
  | 'adapter_disabled'
  | 'missing_snapshot'
  | 'stale_snapshot'
  | 'default_snapshot'
  | 'ready';

export interface DatasetStatusResponse {
  live: {
    enabled: boolean;
    reason: DatasetLiveReason;
    snapshot_generated_at?: string | null;
    detail?: string | null;
  };
  demo: {
    enabled: boolean;
    source?: 'demo' | 'fake' | null;
    tenant_count?: number | null;
  };
  warehouse_adapter_enabled: boolean;
}

export function titleForLiveDatasetReason(reason: DatasetLiveReason): string {
  switch (reason) {
    case 'adapter_disabled':
      return 'Live reporting disabled';
    case 'missing_snapshot':
      return 'Waiting for first live snapshot';
    case 'stale_snapshot':
      return 'Live data is refreshing';
    case 'default_snapshot':
      return 'Fallback live snapshot';
    case 'ready':
    default:
      return 'Live reporting ready';
  }
}

export function messageForLiveDatasetReason(
  reason: DatasetLiveReason,
  detail?: string | null,
): string {
  if (typeof detail === 'string' && detail.trim()) {
    return detail.trim();
  }
  switch (reason) {
    case 'adapter_disabled':
      return 'Live reporting is not enabled in this environment.';
    case 'missing_snapshot':
      return 'Meta is connected, but the first live warehouse snapshot has not been generated yet.';
    case 'stale_snapshot':
      return 'Live data is refreshing.';
    case 'default_snapshot':
      return 'Latest live snapshot is fallback data.';
    case 'ready':
    default:
      return 'Live reporting is ready.';
  }
}

export async function loadDatasetStatus(): Promise<DatasetStatusResponse> {
  return apiClient.get<DatasetStatusResponse>('/datasets/status/');
}
