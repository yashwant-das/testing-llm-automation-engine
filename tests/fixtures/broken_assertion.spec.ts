import { test, expect } from "@playwright/test";

// Fixture: wrong assertion — toBe used where toHaveText is required for a locator.
test("check heading text", async ({ page }) => {
  await page.goto("https://example.com");
  const heading = page.locator("h1");
  expect(heading).toBe("Example Domain");
});
