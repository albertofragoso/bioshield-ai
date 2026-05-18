import {
  test,
  expect,
  mockAuthRegisterSuccess,
  mockAuthRegisterConflict,
  mockAuthLoginSuccess,
  TEST_EMAIL,
  TEST_PASSWORD,
} from "../../fixtures";

// The terms checkbox uses a sr-only <input> inside a <label>.
// Playwright requires force:true to interact with sr-only inputs.
async function acceptTerms(page: any) {
  await page.locator('input[type="checkbox"]').check({ force: true });
}

test.describe("Feature: Register", () => {
  test("happy path — register triggers auto-login and redirects to dashboard", async ({ page }) => {
    await mockAuthRegisterSuccess(page);
    await mockAuthLoginSuccess(page);
    await page.goto("/register");

    await page.locator('input[autocomplete="email"]').fill(TEST_EMAIL);
    await page.locator('input[autocomplete="new-password"]').fill(TEST_PASSWORD);
    await acceptTerms(page);
    await page.getByRole("button", { name: /crear cuenta/i }).click();

    await expect(page).toHaveURL("/");
  });

  test("edge — 409 email already registered shows AuthAlert", async ({ page }) => {
    await mockAuthRegisterConflict(page);
    await page.goto("/register");

    await page.locator('input[autocomplete="email"]').fill(TEST_EMAIL);
    await page.locator('input[autocomplete="new-password"]').fill(TEST_PASSWORD);
    await acceptTerms(page);
    await page.getByRole("button", { name: /crear cuenta/i }).click();

    await expect(page.getByText(/email ya registrado/i)).toBeVisible();
  });

  test("edge — submit button is disabled until terms are accepted", async ({ page }) => {
    await page.goto("/register");

    await page.locator('input[autocomplete="email"]').fill(TEST_EMAIL);
    await page.locator('input[autocomplete="new-password"]').fill(TEST_PASSWORD);
    // terms NOT accepted — button must be disabled
    await expect(page.getByRole("button", { name: /crear cuenta/i })).toBeDisabled();
  });

  test("edge — submitting a short password shows validation error", async ({ page }) => {
    await page.goto("/register");

    await page.locator('input[autocomplete="email"]').fill(TEST_EMAIL);
    await page.locator('input[autocomplete="new-password"]').fill("abc");
    await acceptTerms(page);
    await page.getByRole("button", { name: /crear cuenta/i }).click();

    await expect(page.getByText(/al menos 8 caracteres/i)).toBeVisible();
  });
});
