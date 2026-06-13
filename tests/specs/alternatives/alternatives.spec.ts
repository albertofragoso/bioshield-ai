import { test, expect, mockScanBarcode, makeScanResponse } from "../../fixtures";
import { mockAlternatives } from "../../fixtures/api-mocks";
import { makeAlternativesResponse } from "../../fixtures/factories";

test.describe("Alternative Matching", () => {
  test("RED scan shows 'Ver alternativas' button", async ({ mockedPage }) => {
    await mockScanBarcode(
      mockedPage,
      makeScanResponse({
        product_barcode: "FIX_YOGURT_BAD",
        product_name: "Yogurt con Sucralosa",
        semaphore: "RED",
        conflict_severity: "HIGH",
      }),
    );
    await mockedPage.goto("/scan/FIX_YOGURT_BAD");
    await expect(mockedPage.getByText("Ver alternativas más limpias")).toBeVisible();
  });

  test("BLUE scan does NOT show 'Ver alternativas' button", async ({ mockedPage }) => {
    await mockScanBarcode(
      mockedPage,
      makeScanResponse({
        product_barcode: "FIX_YOGURT_001",
        product_name: "Activia Natural",
        semaphore: "BLUE",
        conflict_severity: null,
        ingredients: [],
      }),
    );
    await mockedPage.goto("/scan/FIX_YOGURT_001");
    await expect(mockedPage.getByText("Ver alternativas más limpias")).not.toBeVisible();
  });

  test("Alternatives page loads and shows top pick and ranking", async ({ mockedPage }) => {
    const data = makeAlternativesResponse();
    await mockAlternatives(mockedPage, "FIX_YOGURT_BAD", data);
    await mockedPage.goto("/scan/FIX_YOGURT_BAD/alternatives");
    await expect(mockedPage.getByText("Mejor alternativa")).toBeVisible();
    await expect(mockedPage.getByText("Activia Natural")).toBeVisible();
    await expect(mockedPage.getByText("Ranking por clean score")).toBeVisible();
    await expect(mockedPage.getByText("Lala Bio 100")).toBeVisible();
  });

  test("Without biomarkers shows BioSync CTA in hero panel", async ({ mockedPage }) => {
    const data = makeAlternativesResponse({ has_biomarkers: false });
    await mockAlternatives(mockedPage, "FIX_YOGURT_BAD", data);
    await mockedPage.goto("/scan/FIX_YOGURT_BAD/alternatives");
    await expect(
      mockedPage.getByText("Activa BioSync para ver compatibilidad personalizada"),
    ).toBeVisible();
  });

  test("Empty state shown when no alternatives found", async ({ mockedPage }) => {
    const data = makeAlternativesResponse({
      scanned_product: {
        barcode: "FIX_NOCAT_001",
        name: "Producto Sin Categoría",
        brand: null,
        semaphore: "RED",
        clean_score: 5,
      },
      top_pick: null,
      alternatives: [],
      fallback_used: true,
    });
    await mockAlternatives(mockedPage, "FIX_NOCAT_001", data);
    await mockedPage.goto("/scan/FIX_NOCAT_001/alternatives");
    await expect(mockedPage.getByText("No encontramos alternativas")).toBeVisible();
  });

  test("Back link returns to scan result page", async ({ mockedPage }) => {
    const data = makeAlternativesResponse();
    await mockAlternatives(mockedPage, "FIX_YOGURT_BAD", data);
    await mockScanBarcode(
      mockedPage,
      makeScanResponse({ product_barcode: "FIX_YOGURT_BAD", semaphore: "RED" }),
    );
    await mockedPage.goto("/scan/FIX_YOGURT_BAD/alternatives");
    await mockedPage.getByText("resultado del scan").click();
    await expect(mockedPage).toHaveURL(/\/scan\/FIX_YOGURT_BAD$/);
  });
});
