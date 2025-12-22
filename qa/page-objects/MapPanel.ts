import { expect, type Locator, type Page } from '@playwright/test';

import BasePage from './BasePage';

class MapPanel extends BasePage {
  constructor(page: Page) {
    super(page);
  }

  private get panel(): Locator {
    return this.page
      .getByRole('heading', { name: /Parish heatmap/i })
      .locator('..')
      .locator('..');
  }

  private get accessibilityTriggers(): Locator {
    return this.panel.locator('button[data-testid^="parish-feature-"]');
  }

  async waitForFeatureCount(expected: number): Promise<void> {
    await expect(this.accessibilityTriggers).toHaveCount(expected, { timeout: 20_000 });
  }

  async selectFeature(name: string): Promise<void> {
    const trigger = this.panel.locator(`button[data-testid="parish-feature-${name}"]`);
    await expect(trigger).toBeAttached();
    await trigger.dispatchEvent('click');
  }
}

export default MapPanel;
