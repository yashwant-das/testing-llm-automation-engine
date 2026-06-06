import { test, expect } from "@playwright/test";

// Fixture: selector drifted — #submit-btn was renamed to [data-testid="submit"]
// The same broken selector appears in two places to exercise multi-site replacement.
test("submit form", async ({ page }) => {
  await page.goto("https://example.com/form");
  await page.locator("#submit-btn").waitFor({ state: "visible" });
  await page.locator("#submit-btn").click();
  await expect(page.locator("#result")).toHaveText("Submitted");
});
