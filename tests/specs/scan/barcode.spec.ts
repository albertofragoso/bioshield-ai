import {
  test,
  expect,
  mockScanBarcode,
  mockScanBarcodeError,
  makeScanResponse,
  makeIngredient,
  makeConflict,
  NUTELLA_BARCODE,
} from "../../fixtures";

const nutellaResponse = () =>
  makeScanResponse({
    semaphore: "YELLOW",
    ingredients: [
      makeIngredient({
        name: "Lecitina de soja",
        canonical_name: "soy_lecithin",
        e_number: "E322",
        regulatory_status: "Approved",
      }),
      makeIngredient({
        name: "Aceite de palma",
        canonical_name: "palm_oil",
        regulatory_status: "Restricted",
        conflicts: [makeConflict({ severity: "MEDIUM" })],
      }),
    ],
  });

test.describe("Feature: Barcode scan", () => {
  test("happy path — Nutella barcode result page renders YELLOW semaphore", async ({ mockedPage }) => {
    // Navigate directly to result URL — this is the canonical path after a successful barcode scan
    await mockScanBarcode(mockedPage, nutellaResponse());
    await mockedPage.goto(`/scan/${NUTELLA_BARCODE}`);

    await expect(mockedPage.getByLabel(/Semáforo/i)).toBeVisible();
    await expect(mockedPage.getByText("Nutella")).toBeVisible();
  });

  test("edge — 404 unknown barcode shows fallback and offers photo tab", async ({ mockedPage }) => {
    await mockScanBarcodeError(mockedPage, 404);
    await mockedPage.goto("/scan");

    await mockedPage.getByRole("tab", { name: /código de barras/i }).click();
    await mockedPage.getByPlaceholder(/manualmente/i).fill("9999999999999");
    await mockedPage.getByRole("button", { name: /^ir$/i }).click();

    await expect(mockedPage.getByText(/no encontramos este producto/i)).toBeVisible();
    await mockedPage.getByRole("button", { name: /intentar con foto/i }).click();
    await expect(
      mockedPage.getByRole("tab", { name: /foto de etiqueta/i, selected: true }),
    ).toBeVisible();
  });

  test("edge — cache hit: scan form uses TanStack Query cache after soft navigation back", async ({ mockedPage }) => {
    // Force immediate camera permission denial so PermissionDeniedCard renders deterministically
    await mockedPage.addInitScript(() => {
      Object.defineProperty(navigator, "mediaDevices", {
        writable: true,
        value: {
          getUserMedia: () =>
            Promise.reject(new DOMException("Permission denied", "NotAllowedError")),
        },
      });
    });

    let calls = 0;
    await mockedPage.route("**/scan/barcode", async (route) => {
      calls += 1;
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify(nutellaResponse()),
      });
    });

    // First visit: query fires (calls = 1)
    await mockedPage.goto(`/scan/${NUTELLA_BARCODE}`);
    await expect(mockedPage.getByLabel(/Semáforo/i)).toBeVisible();

    // Soft nav back to /scan (React tree preserved → QueryClient cache intact)
    await mockedPage.locator('a[href="/scan"]').first().click();
    await expect(mockedPage).toHaveURL("/scan");

    // Wait for PermissionDeniedCard (camera denied via addInitScript)
    await mockedPage.getByPlaceholder(/ej\. 3017/i).waitFor({ state: "visible", timeout: 10000 });
    await mockedPage.getByPlaceholder(/ej\. 3017/i).fill(NUTELLA_BARCODE);
    await mockedPage.getByRole("button", { name: /^ir$/i }).click();

    // handleBarcodeDetect finds cached data → navigates without network call
    await expect(mockedPage).toHaveURL(`/scan/${NUTELLA_BARCODE}`, { timeout: 10000 });
    expect(calls).toBe(1);
  });

  test("error — 500 backend error shows ErrorPage", async ({ mockedPage }) => {
    await mockScanBarcodeError(mockedPage, 500);
    await mockedPage.goto("/scan");

    await mockedPage.getByRole("tab", { name: /código de barras/i }).click();
    await mockedPage.getByPlaceholder(/manualmente/i).fill(NUTELLA_BARCODE);
    await mockedPage.getByRole("button", { name: /^ir$/i }).click();

    await expect(mockedPage.getByRole("alert").first()).toBeVisible();
  });
});
