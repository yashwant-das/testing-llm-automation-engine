import { expect, test } from '@playwright/test';

test('Login with valid credentials', async ({ page }) => {
    await page.goto('https://the-internet.herokuapp.com/login');

    await page.locator('#username-field').fill('tomsmith');
    await page.locator('#password').fill('SuperSecretPassword!');
    await page.getByRole('button', { name: 'Submit' }).click();

    await expect(page.locator('#flash')).toContainText('You logged into a secure area!');
});
