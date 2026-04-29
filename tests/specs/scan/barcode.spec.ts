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
  test("happy path — Nutella barcode renders YELLOW semaphore with ingredients", async ({ mockedPage }) => {
    await mockScanBarcode(mockedPage, nutellaResponse());
    await mockedPage.goto("/scan");

    await mockedPage.getByRole("tab", { name: /código de barras/i }).click();
    await mockedPage.getByPlaceholder(/manualmente/i).fill(NUTELLA_BARCODE);
    await mockedPage.getByRole("button", { name: /^ir$/i }).click();

    await expect(mockedPage).toHaveURL(`/scan/${NUTELLA_BARCODE}`);
    await expect(mockedPage.getByLabel(/Semáforo/i)).toBeVisible();
    await expect(mockedPage.getByText("E322")).toBeVisible();
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

  test("edge — cache hit: scanning the same barcode twice triggers only 1 network call", async ({ mockedPage }) => {
    let calls = 0;
    await mockedPage.route("**/scan/barcode", async (route) => {
      calls += 1;
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify(nutellaResponse()),
      });
    });

    const scanBarcode = async () => {
      await mockedPage.goto("/scan");
      await mockedPage.getByRole("tab", { name: /código de barras/i }).click();
      await mockedPage.getByPlaceholder(/manualmente/i).fill(NUTELLA_BARCODE);
      await mockedPage.getByRole("button", { name: /^ir$/i }).click();
      await expect(mockedPage).toHaveURL(`/scan/${NUTELLA_BARCODE}`);
    };

    await scanBarcode();
    await scanBarcode();

    expect(calls).toBe(1);
  });

  test("error — 500 backend error shows ErrorPage", async ({ mockedPage }) => {
    await mockScanBarcodeError(mockedPage, 500);
    await mockedPage.goto("/scan");

    await mockedPage.getByRole("tab", { name: /código de barras/i }).click();
    await mockedPage.getByPlaceholder(/manualmente/i).fill(NUTELLA_BARCODE);
    await mockedPage.getByRole("button", { name: /^ir$/i }).click();

    await expect(mockedPage.getByRole("alert")).toBeVisible();
  });
});
