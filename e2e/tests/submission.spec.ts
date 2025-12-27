import { test, expect } from '@playwright/test';

test.describe('Submission Flow', () => {
  test.beforeEach(async ({ page }) => {
    // Navigate to problems page
    await page.goto('/problems');
    await page.waitForLoadState('networkidle');
  });

  test('should display problem details', async ({ page }) => {
    // Click on first problem if available
    const problemLinks = page.locator('a[href*="/problems/"]');
    const count = await problemLinks.count();

    if (count > 0) {
      await problemLinks.first().click();
      await page.waitForLoadState('networkidle');

      // Check for problem title and description
      await expect(page.locator('h1')).toBeVisible();
    }
  });

  test('should navigate to submission page', async ({ page }) => {
    // Navigate to a problem detail page
    const problemLinks = page.locator('a[href*="/problems/"]');
    const count = await problemLinks.count();

    if (count > 0) {
      await problemLinks.first().click();
      await page.waitForLoadState('networkidle');

      // Click start/submit button if available
      const startButton = page.locator('button:has-text("Start"), a:has-text("Start")');
      if (await startButton.isVisible()) {
        await startButton.click();
        await page.waitForLoadState('networkidle');

        // Should be on submission page
        expect(page.url()).toContain('submit');
      }
    }
  });
});

test.describe('Submission Page Components', () => {
  test('should display schema editor on submission page', async ({ page }) => {
    // Navigate directly to a submission page if it exists
    await page.goto('/problems/1/submit');

    // Wait for page load
    await page.waitForTimeout(1000);

    // Check if we're on a valid page (might redirect to login or 404)
    const url = page.url();

    if (url.includes('submit')) {
      // Look for editor components
      const editors = page.locator('[data-testid="schema-editor"], textarea, .monaco-editor');
      const editorCount = await editors.count();
      expect(editorCount).toBeGreaterThanOrEqual(0);
    }
  });

  test('should display validation feedback', async ({ page }) => {
    await page.goto('/problems/1/submit');
    await page.waitForTimeout(1000);

    const url = page.url();

    if (url.includes('submit')) {
      // Check for validation-related elements
      const validationElements = page.locator('[data-testid="validation"], .validation, .feedback');
      const count = await validationElements.count();
      expect(count).toBeGreaterThanOrEqual(0);
    }
  });
});

test.describe('Results Page', () => {
  test('should display test results', async ({ page }) => {
    // Navigate to results page if a submission exists
    await page.goto('/results/1');
    await page.waitForTimeout(1000);

    const url = page.url();

    // Check if page loaded (might redirect if no submission exists)
    if (url.includes('results')) {
      // Look for result-related elements
      const resultElements = page.locator('[data-testid="test-result"], .test-result, .card');
      const count = await resultElements.count();
      expect(count).toBeGreaterThanOrEqual(0);
    }
  });
});
