import { expect, type Locator, type Page } from "@playwright/test";

import BasePage from "./BasePage";

class MapPanel extends BasePage {
  constructor(page: Page) {
    super(page);
  }

  private get panel(): Locator {
    return this.page
      .getByRole("heading", { name: /Parish heatmap/i })
      .locator("..")
      .locator("..");
  }

  private get shapes(): Locator {
    return this.panel.locator(".leaflet-interactive");
  }

  private get tooltip(): Locator {
    return this.page.locator(".leaflet-tooltip");
  }

  async waitForFeatureCount(expected: number): Promise<void> {
    await expect(this.shapes).toHaveCount(expected);
  }

  async hoverFeature(index: number): Promise<void> {
    await this.shapes.nth(index).hover();
  }

  async hoverEachFeatureUntil(predicate: (text: string) => boolean): Promise<string | null> {
    const count = await this.shapes.count();
    for (let index = 0; index < count; index += 1) {
      await this.hoverFeature(index);
      await expect(this.tooltip).toBeVisible();
      const text = await this.tooltip.innerText();
      if (predicate(text)) {
        return text;
      }
    }
    return null;
  }

  async getTooltipText(): Promise<string> {
    await expect(this.tooltip).toBeVisible();
    return this.tooltip.innerText();
  }
}

export default MapPanel;
