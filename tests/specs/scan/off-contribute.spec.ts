// tests/specs/scan/off-contribute.spec.ts
import {
  test,
  expect,
  mockScanBarcode,
  mockScanResultGet,
  mockContributeOff,
  mockContributeOffError,
  makeScanResponse,
  makeIngredient,
} from "../../fixtures";

const PHOTO_ID = "photo-off-test-00001";

const photoScan = makeScanResponse({
  product_barcode: PHOTO_ID,
  product_name: "Galletas Demo",
  source: "photo",
  ingredients: [
    makeIngredient({ name: "Harina de trigo" }),
    makeIngredient({ name: "Azúcar" }),
  ],
});

test.describe("Feature: OFF contribute toggle", () => {
  test("default — toggle is off and ENVIAR button is absent", async ({ mockedPage }) => {
    await mockScanResultGet(mockedPage, photoScan);
    await mockedPage.goto(`/scan/${PHOTO_ID}`);

    const toggle = mockedPage.getByRole("switch", { name: /contribuir a open food facts/i });
    await expect(toggle).toBeVisible();
    await expect(toggle).toHaveAttribute("aria-checked", "false");
    await expect(mockedPage.getByRole("button", { name: /enviar/i })).not.toBeVisible();
  });

  test("happy path — activate toggle → ENVIAR → success banner", async ({ mockedPage }) => {
    await mockScanResultGet(mockedPage, photoScan);
    await mockContributeOff(mockedPage);
    await mockedPage.goto(`/scan/${PHOTO_ID}`);

    const toggle = mockedPage.getByRole("switch", { name: /contribuir a open food facts/i });
    await toggle.click();
    await expect(toggle).toHaveAttribute("aria-checked", "true");

    const enviarBtn = mockedPage.getByRole("button", { name: /enviar/i });
    await expect(enviarBtn).toBeVisible();
    await enviarBtn.click();

    await expect(mockedPage.getByText(/contribución enviada/i)).toBeVisible();
    await expect(toggle).not.toBeVisible();
  });

  test("error — failed POST shows error banner with Reintentar button", async ({ mockedPage }) => {
    await mockScanResultGet(mockedPage, photoScan);
    await mockContributeOffError(mockedPage);
    await mockedPage.goto(`/scan/${PHOTO_ID}`);

    await mockedPage.getByRole("switch", { name: /contribuir a open food facts/i }).click();
    await mockedPage.getByRole("button", { name: /enviar/i }).click();

    await expect(mockedPage.getByText(/error al enviar/i)).toBeVisible();
    await expect(mockedPage.getByRole("button", { name: /reintentar/i })).toBeVisible();
  });

  test("not rendered for barcode scan", async ({ mockedPage }) => {
    const barcodeScan = makeScanResponse({ source: "barcode" });
    await mockScanBarcode(mockedPage, barcodeScan);
    await mockedPage.goto(`/scan/${barcodeScan.product_barcode}`);

    await expect(
      mockedPage.getByRole("switch", { name: /contribuir a open food facts/i }),
    ).not.toBeVisible();
  });
});
