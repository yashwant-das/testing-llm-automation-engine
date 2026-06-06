import { test, expect } from "@playwright/test";

// Fixture: timeout too short — 5000ms on a slow page that needs 30000ms.
test("load slow page", async ({ page }) => {
  await page.goto("https://example.com/slow", { timeout: 5000 });
  // eslint-disable-next-line playwright/no-wait-for-selector
  await page.waitForSelector("#content", { timeout: 5000 });
  await expect(page.locator("#content")).toBeVisible();
});
