import { test } from "./fixtures/base";
import { skipWhenNoLiveApi } from "../utils/live";
import { DashboardPage } from "../page-objects";
import { schemaValidate } from "../utils/schemaValidate";

test.describe("metrics CSV export", () => {
  skipWhenNoLiveApi(test);

  test("returns a CSV attachment", async ({ page, mockMode, liveApi }) => {
    test.skip(!mockMode && !liveApi.ready, "Live API is not configured");

    const csvBody = [
      ["date", "parish", "impressions", "clicks", "spend", "conversions", "roas"],
      ["2024-09-01", "Kingston", "120000", "3400", "540.00", "120", "3.5"],
    ]
      .map((row) => row.join(","))
      .join("\n");

    if (mockMode) {
      await page.route("**/api/metrics/export/**", (route) => {
        void route.fulfill({
          status: 200,
          headers: {
            "Content-Type": "text/csv; charset=utf-8",
            "Content-Disposition": "attachment; filename=tenant-metrics.csv",
          },
          body: csvBody,
        });
      });
    }

    const dashboard = new DashboardPage(page);
    await dashboard.open();

    const response = await page.evaluate(async () => {
      const result = await fetch("/api/metrics/export/?format=csv", {
        headers: { Accept: "text/csv" },
      });
      const text = await result.text();
      return {
        status: result.status,
        contentType: result.headers.get("Content-Type"),
        contentDisposition: result.headers.get("Content-Disposition"),
        body: text,
      };
    });

    const lines = response.body
      .split(/\r?\n/)
      .map((line) => line.trim())
      .filter((line) => line.length > 0);
    const [headerLine, ...dataLines] = lines;
    const headers = headerLine?.split(",") ?? [];
    const rows = dataLines.map((line) => {
      const values = line.split(",");
      return headers.reduce<Record<string, string>>((acc, header, index) => {
        acc[header] = values[index] ?? "";
        return acc;
      }, {});
    });

    await schemaValidate("metrics-export", {
      status: response.status,
      contentType: response.contentType ?? "",
      contentDisposition: response.contentDisposition ?? "",
      headers,
      rows,
    });
    expect(response.status).toBe(200);
    expect(response.contentType ?? "").toMatch(/text\/csv/i);
    expect(response.contentDisposition ?? "").toMatch(/\.csv/i);

    const lines = response.body.trim().split("\n");
    expect(lines.length).toBeGreaterThan(0);

    const headers = lines[0].split(",");
    expect(headers).toEqual([
      "date",
      "parish",
      "impressions",
      "clicks",
      "spend",
      "conversions",
      "roas",
    ]);

    if (mockMode) {
      expect(lines.length).toBeGreaterThan(1);
      const data = lines[1].split(",");
      expect(data).toEqual([
        "2024-09-01",
        "Kingston",
        "120000",
        "3400",
        "540.00",
        "120",
        "3.5",
      ]);
    } else {
      expect(lines.length).toBeGreaterThan(1);
    }

    if (mockMode) {
      await page.unroute("**/api/metrics/export/**");
    }
  });
});
