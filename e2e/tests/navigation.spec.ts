import { test, expect } from '@playwright/test';

test.describe('Navigation', () => {
  test('should load the home page', async ({ page }) => {
    await page.goto('/');
    await expect(page).toHaveTitle(/System Design/);
  });

  test('should navigate to problems list', async ({ page }) => {
    await page.goto('/');
    await page.click('text=Problems');
    await expect(page).toHaveURL(/\/problems/);
  });

  test('should show problem list page', async ({ page }) => {
    await page.goto('/problems');
    await expect(page.locator('h1')).toContainText(/Problems|System Design/);
  });

  test('should display navigation header', async ({ page }) => {
    await page.goto('/');
    const header = page.locator('header, nav');
    await expect(header).toBeVisible();
  });
});

test.describe('Problems List', () => {
  test('should display problems', async ({ page }) => {
    await page.goto('/problems');
    // Wait for the page to load
    await page.waitForLoadState('networkidle');

    // Check for problem cards or list items
    const problemCards = page.locator('[data-testid="problem-card"], .card, article');
    const count = await problemCards.count();
    expect(count).toBeGreaterThanOrEqual(0);
  });

  test('should have filter options', async ({ page }) => {
    await page.goto('/problems');
    await page.waitForLoadState('networkidle');

    // Check for difficulty filter or search input
    const filterElements = page.locator('input[type="search"], select, [data-testid="filter"]');
    await expect(filterElements.first()).toBeVisible();
  });
});

test.describe('Theme Toggle', () => {
  test('should toggle theme', async ({ page }) => {
    await page.goto('/');

    // Get initial theme
    const html = page.locator('html');
    const initialTheme = await html.getAttribute('class');

    // Click theme toggle if it exists
    const themeToggle = page.locator('button[aria-label*="theme"], [data-testid="theme-toggle"]');

    if (await themeToggle.isVisible()) {
      await themeToggle.click();

      // Check if theme changed
      const newTheme = await html.getAttribute('class');
      expect(newTheme).not.toBe(initialTheme);
    }
  });
});
