import {expect, test} from '@playwright/test';

test('Broken Login Example', async ({page}) => {
    // Navigate to the login page
    await page.goto('https://the-internet.herokuapp.com/login');

    // FAILURE CASE: selector does not exist on the page (correct selector is '#username')
    await page.locator('#user-input-field-wrong').fill('tomsmith');

    // Correct password field
    await page.locator('#password').fill('SuperSecretPassword!');

    // FAILURE CASE: button role name is wrong (correct name is 'Login')
    await page.getByRole('button', {name: 'Submit'}).click();

    // Verification
    await expect(page.locator('#flash')).toContainText('You logged into a secure area!');
});
