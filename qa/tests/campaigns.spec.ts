import { test, expect } from '@playwright/test';

const SKIP_SCREENSHOTS = process.env.QA_SKIP_SCREENSHOTS !== '0';

test.describe('campaigns dashboard layout', () => {
  test('desktop 1440x900', async ({ page }) => {
    await page.goto('/dashboards/campaigns');
    await page.setViewportSize({ width: 1440, height: 900 });
    if (!SKIP_SCREENSHOTS) {
      await expect(page).toHaveScreenshot('campaigns-1440x900.png', { animations: 'disabled' });
    }
  });

  test('mobile 390x844', async ({ page }) => {
    await page.goto('/dashboards/campaigns');
    await page.setViewportSize({ width: 390, height: 844 });
    if (!SKIP_SCREENSHOTS) {
      await expect(page).toHaveScreenshot('campaigns-390x844.png', { animations: 'disabled' });
    }
  });
});
