import { test, expect, mockAuthLoginSuccess, mockAuthLoginFail, TEST_EMAIL, TEST_PASSWORD } from "../../fixtures";

test.describe("Feature: Login", () => {
  test("happy path — valid credentials redirect to dashboard", async ({ page }) => {
    await mockAuthLoginSuccess(page);
    await page.goto("/login");

    await page.locator('input[autocomplete="email"]').fill(TEST_EMAIL);
    await page.locator('input[autocomplete="current-password"]').fill(TEST_PASSWORD);
    await page.getByRole("button", { name: /entrar/i }).click();

    await expect(page).toHaveURL("/");
  });

  test("edge — 401 invalid credentials shows AuthAlert", async ({ page }) => {
    await mockAuthLoginFail(page, 401);
    await page.goto("/login");

    await page.locator('input[autocomplete="email"]').fill(TEST_EMAIL);
    await page.locator('input[autocomplete="current-password"]').fill("wrong-password");
    await page.getByRole("button", { name: /entrar/i }).click();

    await expect(page.getByText(/credenciales inválidas/i)).toBeVisible();
    await expect(page).toHaveURL("/login");
  });

  test("edge — 429 rate limit shows specific copy", async ({ page }) => {
    await mockAuthLoginFail(page, 429);
    await page.goto("/login");

    await page.locator('input[autocomplete="email"]').fill(TEST_EMAIL);
    await page.locator('input[autocomplete="current-password"]').fill(TEST_PASSWORD);
    await page.getByRole("button", { name: /entrar/i }).click();

    await expect(page.getByText(/demasiados intentos/i)).toBeVisible();
  });

  test("error — network failure shows connection alert", async ({ page }) => {
    await page.route("**/auth/login", (route) => route.abort("failed"));
    await page.goto("/login");

    await page.locator('input[autocomplete="email"]').fill(TEST_EMAIL);
    await page.locator('input[autocomplete="current-password"]').fill(TEST_PASSWORD);
    await page.getByRole("button", { name: /entrar/i }).click();

    await expect(page.getByRole("alert").first()).toBeVisible();
  });
});
