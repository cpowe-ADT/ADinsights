import type { TestType } from "@playwright/test";

function wantsLiveApi(): boolean {
  return (process.env.MOCK_MODE ?? "true").toLowerCase() === "false";
}

export function skipWhenNoLiveApi<TFixtures, TWorkerFixtures>(
  test: TestType<TFixtures, TWorkerFixtures>,
  message = "Set LIVE_API_BASE_URL to run live API tests"
): void {
  const requireLiveApi = wantsLiveApi();
  const hasLiveBaseUrl = Boolean(process.env.LIVE_API_BASE_URL);
  test.skip(requireLiveApi && !hasLiveBaseUrl, message);
}
