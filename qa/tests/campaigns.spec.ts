import { test, expect } from '@playwright/test';

test.describe('campaigns dashboard layout', () => {
  test('desktop 1440x900', async ({ page }) => {
    await page.goto('/dashboards/campaigns');
    await page.setViewportSize({ width: 1440, height: 900 });
    await expect(page).toHaveScreenshot('campaigns-1440x900.png', { animations: 'disabled' });
  });

  test('mobile 390x844', async ({ page }) => {
    await page.goto('/dashboards/campaigns');
    await page.setViewportSize({ width: 390, height: 844 });
    await expect(page).toHaveScreenshot('campaigns-390x844.png', { animations: 'disabled' });
  });
});
