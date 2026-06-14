// Fixture: missing expect import — only test is imported.
import { test } from "@playwright/test";

test("check title", async ({ page }) => {
  await page.goto("https://example.com");
  // expect is used but not imported — this file will fail to compile
  await expect(page).toHaveTitle("Example Domain");
});
