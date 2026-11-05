import { expect, test } from '@playwright/test';

test('shows a sized map container and remounts it when returning to the tab', async ({ page }) => {
  await page.goto('/');
  const map = page.locator('capacitor-google-map');
  await expect(map).toBeVisible();
  const bounds = await map.boundingBox();
  expect(bounds?.width).toBeGreaterThan(0);
  expect(bounds?.height).toBeGreaterThanOrEqual(300);

  await page.getByRole('tab', { name: 'Tab 2', exact: true }).click();
  await expect(map).toHaveCount(0);

  await page.getByRole('tab', { name: 'Tab 1', exact: true }).click();
  await expect(map).toBeVisible();
});
