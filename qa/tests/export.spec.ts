import { expect, test } from "./fixtures/base";
import { skipWhenNoLiveApi } from "../utils/live";

test.describe("metrics CSV export", () => {
  skipWhenNoLiveApi(test);

  test("returns a CSV attachment", async ({ page, mockMode }) => {
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

    await page.goto("/");

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

    expect(response.status).toBe(200);
    expect(response.contentType ?? "").toMatch(/text\/csv/i);
    expect(response.contentDisposition ?? "").toMatch(/\.csv/i);

    const [headerLine, dataLine] = response.body.trim().split("\n");
    const headers = headerLine.split(",");
    const data = dataLine.split(",");

    expect(headers).toEqual([
      "date",
      "parish",
      "impressions",
      "clicks",
      "spend",
      "conversions",
      "roas",
    ]);
    expect(data[0]).toMatch(/\d{4}-\d{2}-\d{2}/);
    expect(Number(data[2])).toBeGreaterThan(0);

    if (mockMode) {
      await page.unroute("**/api/metrics/export/**");
    }
  });
});
