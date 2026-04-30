import {
  test,
  expect,
  mockAuthLogout,
  mockAuthRefreshSuccess,
  mockAuthRefreshFail,
  mockScanBarcode,
  makeScanResponse,
  NUTELLA_BARCODE,
} from "../../fixtures";

test.describe("Feature: Session lifecycle", () => {
  test("happy path — logout clears cookies and redirects to /login", async ({ mockedPage, context }) => {
    await mockAuthLogout(mockedPage);
    await mockedPage.goto("/");
    await mockedPage.getByRole("button", { name: /salir/i }).click();

    await expect(mockedPage).toHaveURL("/login");
    const cookies = await context.cookies();
    const accessCookie = cookies.find((c) => c.name === "access_token");
    expect(accessCookie).toBeUndefined();
  });

  test("edge — 401 in apiFetch triggers /auth/refresh and retries successfully", async ({ mockedPage }) => {
    let scanCalls = 0;
    await mockedPage.route("**/scan/barcode", async (route) => {
      scanCalls += 1;
      if (scanCalls === 1) {
        return route.fulfill({
          status: 401,
          contentType: "application/json",
          body: JSON.stringify({ detail: "Token expirado" }),
        });
      }
      return route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify(makeScanResponse()),
      });
    });
    await mockAuthRefreshSuccess(mockedPage);

    await mockedPage.goto("/scan");
    await mockedPage.getByRole("tab", { name: /código de barras/i }).click();
    await mockedPage.getByPlaceholder(/manualmente/i).fill(NUTELLA_BARCODE);
    await mockedPage.getByRole("button", { name: /^ir$/i }).click();

    await expect(mockedPage).toHaveURL(`/scan/${NUTELLA_BARCODE}`, { timeout: 10000 });
    expect(scanCalls).toBe(2);
  });

  test("edge — refresh fails → SessionExpiredDialog appears", async ({ mockedPage }) => {
    await mockedPage.route("**/scan/barcode", (route) =>
      route.fulfill({
        status: 401,
        contentType: "application/json",
        body: JSON.stringify({ detail: "Token expirado" }),
      }),
    );
    await mockAuthRefreshFail(mockedPage);

    await mockedPage.goto("/scan");
    await mockedPage.getByRole("tab", { name: /código de barras/i }).click();
    await mockedPage.getByPlaceholder(/manualmente/i).fill(NUTELLA_BARCODE);
    await mockedPage.getByRole("button", { name: /^ir$/i }).click();

    await expect(mockedPage.getByText(/sesión expirada/i)).toBeVisible();
    await expect(mockedPage.getByRole("button", { name: /entrar de nuevo/i })).toBeVisible();
  });

  test("error — protected route without cookie redirects to /login", async ({ page }) => {
    await page.goto("/scan");
    await expect(page).toHaveURL("/login");
  });

  test("edge — visiting /login while already authenticated redirects to /", async ({ mockedPage }) => {
    await mockedPage.goto("/login");
    await expect(mockedPage).toHaveURL("/");
  });
});
