import { expect, test } from '@playwright/test';
import { existsSync } from 'fs';
import { resolve } from 'path';

/**
 * Infrastructure smoke tests.
 *
 * Verify that the Playwright test runner, imports, and project fixture files
 * are in the expected state — without requiring a network connection or browser.
 * These run as part of `npm run test` to confirm the test infrastructure is healthy.
 */

test('Playwright test API imports resolve correctly', async () => {
  expect(typeof test).toBe('function');
  expect(typeof expect).toBe('function');
});

test('broken_example.spec.ts demo fixture is present', async () => {
  const fixturePath = resolve(__dirname, 'broken_example.spec.ts');
  expect(existsSync(fixturePath)).toBe(true);
});

test('healing benchmark fixture file is present', async () => {
  const fixturePath = resolve(__dirname, '../../benchmarks/healing/fixtures/repair_scenarios.json');
  expect(existsSync(fixturePath)).toBe(true);
});

test('generation benchmark fixture file is present', async () => {
  const fixturePath = resolve(__dirname, '../../benchmarks/generation/fixtures/web_scenarios.json');
  expect(existsSync(fixturePath)).toBe(true);
});
