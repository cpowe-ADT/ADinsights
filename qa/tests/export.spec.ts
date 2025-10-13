import { test } from "./fixtures/base";
import { skipWhenNoLiveApi } from "../utils/live";
import { schemaValidate } from "../utils/schemaValidate";

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

    if (mockMode) {
      await page.unroute("**/api/metrics/export/**");
    }
  });
});
