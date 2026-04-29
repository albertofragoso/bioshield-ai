import path from "node:path";
import {
  test,
  expect,
  mockScanPhoto,
  mockScanPhotoError,
  mockScanResultGet,
  makeScanResponse,
} from "../../fixtures";

const FIXTURE = path.resolve(__dirname, "../../fixtures/files/nutrition-label.png");

test.describe("Feature: Photo scan", () => {
  test("happy path — upload PNG → AI loader → result with product_name", async ({ mockedPage }) => {
    const photoId = "photo-abc123def456";
    const response = makeScanResponse({
      product_barcode: photoId,
      product_name: "Galletas Marca Demo",
      source: "photo",
    });
    await mockScanPhoto(mockedPage, response);
    await mockedPage.goto("/scan");

    await mockedPage.getByRole("tab", { name: /foto de etiqueta/i }).click();
    await mockedPage.locator('input[type="file"]').first().setInputFiles(FIXTURE);

    // AI loader visible during upload (SCAN_PHASES terminal text)
    await expect(
      mockedPage.getByText(/READING_LABEL_OCR|EXTRACTING_INGREDIENTS|BioShield\s+AI/i),
    ).toBeVisible();

    await expect(mockedPage).toHaveURL(new RegExp(`/scan/${photoId}`));
    await expect(mockedPage.getByText("Galletas Marca Demo")).toBeVisible();
  });

  test("edge — photo result persists on direct link (uses GET /scan/result/{id})", async ({ mockedPage }) => {
    const photoId = "photo-persisted00001";
    const response = makeScanResponse({
      product_barcode: photoId,
      product_name: "Producto persistido",
      source: "photo",
    });
    await mockScanResultGet(mockedPage, response);

    await mockedPage.goto(`/scan/${photoId}`);

    await expect(mockedPage.getByText("Producto persistido")).toBeVisible();
    await expect(mockedPage.getByLabel(/Semáforo/i)).toBeVisible();
  });

  test("error — 422 invalid image shows alert", async ({ mockedPage }) => {
    await mockScanPhotoError(mockedPage, 422);
    await mockedPage.goto("/scan");

    await mockedPage.getByRole("tab", { name: /foto de etiqueta/i }).click();
    await mockedPage.locator('input[type="file"]').first().setInputFiles(FIXTURE);

    await expect(mockedPage.getByText(/imagen inválida/i)).toBeVisible();
  });

  test("error — 413 oversized image shows alert", async ({ mockedPage }) => {
    await mockScanPhotoError(mockedPage, 413);
    await mockedPage.goto("/scan");

    await mockedPage.getByRole("tab", { name: /foto de etiqueta/i }).click();
    await mockedPage.locator('input[type="file"]').first().setInputFiles(FIXTURE);

    await expect(mockedPage.getByText(/demasiado grande/i)).toBeVisible();
  });
});
