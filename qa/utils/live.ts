import type { TestType } from "@playwright/test";

function wantsLiveApi(): boolean {
  return (process.env.MOCK_MODE ?? "true").toLowerCase() === "false";
}

function hasLiveCredentials(): boolean {
  if (process.env.LIVE_API_AUTHORIZATION) {
    return true;
  }
  if (process.env.LIVE_API_TOKEN) {
    return true;
  }
  if (process.env.LIVE_API_API_KEY) {
    return true;
  }
  if (process.env.LIVE_API_USERNAME && process.env.LIVE_API_PASSWORD) {
    return true;
  }
  return false;
}

export type LiveApiState = {
  requireLiveApi: boolean;
  baseUrl: string | null;
  credentialsPresent: boolean;
  ready: boolean;
};

export function getLiveApiState(): LiveApiState {
  const requireLiveApi = wantsLiveApi();
  const baseUrl = process.env.LIVE_API_BASE_URL ?? null;
  const credentialsPresent = hasLiveCredentials();
  return {
    requireLiveApi,
    baseUrl,
    credentialsPresent,
    ready: Boolean(requireLiveApi && baseUrl && credentialsPresent),
  };
}

export function skipWhenNoLiveApi<TFixtures, TWorkerFixtures>(
  test: TestType<TFixtures, TWorkerFixtures>,
  message?: string
): void {
  const state = getLiveApiState();

  if (!state.requireLiveApi) {
    return;
  }

  const missingParts: string[] = [];
  if (!state.baseUrl) {
    missingParts.push("LIVE_API_BASE_URL");
  }
  if (!state.credentialsPresent) {
    missingParts.push("LIVE_API credentials");
  }

  const shouldSkip = missingParts.length > 0;
  test.skip(
    shouldSkip,
    message ??
      (missingParts.length
        ? `Set ${missingParts.join(", ")} to run live API tests`
        : "Skipping live API tests")
  );
}
