import type { Locator, Page } from "@playwright/test";

import BasePage from "./BasePage";
import MapPanel from "./MapPanel";

type MetricColumn = "parish" | "impressions" | "clicks";

const COLUMN_HEADERS: Record<MetricColumn, RegExp> = {
  parish: /Parish/i,
  impressions: /Impressions/i,
  clicks: /Clicks/i,
};

class DashboardPage extends BasePage {
  readonly mapPanel: MapPanel;

  private columnIndexCache: Partial<Record<MetricColumn, number>> = {};

  constructor(page: Page) {
    super(page);
    this.mapPanel = new MapPanel(page);
  }

  async open(): Promise<void> {
    await this.goto("/");
  }

  private get metricsTable(): Locator {
    return this.page
      .getByRole("heading", { name: /Campaign performance/i })
      .locator("..")
      .locator("..")
      .locator("table");
  }

  private get metricRows(): Locator {
    return this.metricsTable.locator("tbody").getByRole("row");
  }

  private async resolveColumnIndex(column: MetricColumn): Promise<number> {
    const cached = this.columnIndexCache[column];
    if (typeof cached === "number") {
      return cached;
    }

    const headers = this.metricsTable.getByRole("columnheader");
    const headerCount = await headers.count();
    const matcher = COLUMN_HEADERS[column];

    for (let index = 0; index < headerCount; index += 1) {
      const text = (await headers.nth(index).innerText()).trim();
      if (matcher.test(text)) {
        this.columnIndexCache[column] = index;
        return index;
      }
    }

    throw new Error(`Column ${column} was not found in the metrics table.`);
  }

  async waitForMetricsLoaded(expectedRows?: number): Promise<void> {
    await this.metricsTable.waitFor({ state: "visible" });
    await this.waitForNetworkIdle();

    if (typeof expectedRows === "number") {
      const handle = await this.metricsTable.elementHandle();
      if (handle) {
        try {
          await this.page.waitForFunction(
            ({ table, expected }) => table.querySelectorAll("tbody tr").length >= expected,
            { table: handle, expected: expectedRows }
          );
        } finally {
          await handle.dispose();
        }
      }
    }
  }

  async getMetricRowCount(): Promise<number> {
    return this.metricRows.count();
  }

  async getColumnValues(column: MetricColumn): Promise<string[]> {
    const index = await this.resolveColumnIndex(column);
    const rowCount = await this.metricRows.count();
    const values: string[] = [];

    for (let rowIndex = 0; rowIndex < rowCount; rowIndex += 1) {
      const row = this.metricRows.nth(rowIndex);
      const cellText = await row.getByRole("cell").nth(index).innerText();
      values.push(cellText.trim());
    }

    return values;
  }

  async getNumericColumn(column: Exclude<MetricColumn, "parish">): Promise<number[]> {
    const rawValues = await this.getColumnValues(column);
    return rawValues.map((value) => Number(value.replace(/,/g, "")));
  }

  async getFirstRow(): Promise<Record<MetricColumn, string>> {
    const columnEntries = await Promise.all(
      (Object.keys(COLUMN_HEADERS) as MetricColumn[]).map(async (column) => {
        const index = await this.resolveColumnIndex(column);
        const value = await this.metricRows.first().getByRole("cell").nth(index).innerText();
        return [column, value.trim()] as const;
      })
    );

    return Object.fromEntries(columnEntries) as Record<MetricColumn, string>;
  }

  async getSortedStatus(): Promise<string> {
    const announcement = await this.page.getByText(/Sorted by/i).first().innerText();
    return announcement.trim();
  }

  async toggleSortByClicks(): Promise<void> {
    await this.page.getByRole("button", { name: /Sort by Clicks/i }).click();
    await this.waitForNetworkIdle();
  }
}

export default DashboardPage;
