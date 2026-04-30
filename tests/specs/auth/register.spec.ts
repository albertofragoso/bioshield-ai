import {
  test,
  expect,
  mockAuthRegisterSuccess,
  mockAuthRegisterConflict,
  mockAuthLoginSuccess,
  TEST_EMAIL,
  TEST_PASSWORD,
} from "../../fixtures";

test.describe("Feature: Register", () => {
  test("happy path — register triggers auto-login and redirects to dashboard", async ({ page }) => {
    await mockAuthRegisterSuccess(page);
    await mockAuthLoginSuccess(page);
    await page.goto("/register");

    await page.locator('input[autocomplete="email"]').fill(TEST_EMAIL);
    await page.locator('input[autocomplete="new-password"]').fill(TEST_PASSWORD);
    await page.getByText(/acepto los términos/i).click();
    await page.getByRole("button", { name: /crear cuenta/i }).click();

    await expect(page).toHaveURL("/");
  });

  test("edge — 409 email already registered shows AuthAlert", async ({ page }) => {
    await mockAuthRegisterConflict(page);
    await page.goto("/register");

    await page.locator('input[autocomplete="email"]').fill(TEST_EMAIL);
    await page.locator('input[autocomplete="new-password"]').fill(TEST_PASSWORD);
    await page.getByText(/acepto los términos/i).click();
    await page.getByRole("button", { name: /crear cuenta/i }).click();

    await expect(page.getByText(/email ya registrado/i)).toBeVisible();
  });

  test("edge — submitting without accepting terms shows validation error", async ({ page }) => {
    await page.goto("/register");

    await page.locator('input[autocomplete="email"]').fill(TEST_EMAIL);
    await page.locator('input[autocomplete="new-password"]').fill(TEST_PASSWORD);
    // Do NOT click terms checkbox
    await page.getByRole("button", { name: /crear cuenta/i }).click();

    await expect(page.getByText(/debes aceptar los términos/i)).toBeVisible();
  });

  test("edge — submitting a short password shows validation error", async ({ page }) => {
    await page.goto("/register");

    await page.locator('input[autocomplete="email"]').fill(TEST_EMAIL);
    await page.locator('input[autocomplete="new-password"]').fill("abc");
    await page.getByText(/acepto los términos/i).click();
    await page.getByRole("button", { name: /crear cuenta/i }).click();

    await expect(page.getByText(/al menos 8 caracteres/i)).toBeVisible();
  });
});
