import {
  test,
  expect,
  mockScanBarcode,
  mockScanBarcodeError,
  makeScanResponse,
  makeIngredient,
  makePersonalizedInsight,
  makeOrangeBiomarkerScan,
  NUTELLA_BARCODE,
} from "../../fixtures";
import type { SemaphoreColor } from "../../../frontend/lib/api/types";

const SEMAPHORE_COLORS: SemaphoreColor[] = ["GRAY", "BLUE", "YELLOW", "ORANGE", "RED"];

test.describe("Feature: Scan result", () => {
  for (const color of SEMAPHORE_COLORS) {
    test(`happy path — ${color} semaphore renders hero with ARIA label`, async ({ mockedPage }) => {
      await mockScanBarcode(mockedPage, makeScanResponse({ semaphore: color }));
      await mockedPage.goto(`/scan/${NUTELLA_BARCODE}`);

      const hero = mockedPage.getByLabel(/Semáforo/i);
      await expect(hero).toBeVisible();
    });
  }

  test("edge — ingredient accordion expands to show CAS number and E-number", async ({ mockedPage }) => {
    await mockScanBarcode(
      mockedPage,
      makeScanResponse({
        ingredients: [
          makeIngredient({
            name: "Lecitina de soja",
            cas_number: "8002-43-5",
            e_number: "E322",
            regulatory_status: "Approved",
          }),
        ],
      }),
    );
    await mockedPage.goto(`/scan/${NUTELLA_BARCODE}`);

    const trigger = mockedPage.getByRole("button", { name: /lecitina de soja/i });
    await trigger.click();

    await expect(mockedPage.getByText("8002-43-5")).toBeVisible();
    await expect(mockedPage.getByText("E322")).toBeVisible();
  });

  test("edge — Para Ti shows Alertas and Vigilar tabs with counts", async ({ mockedPage }) => {
    const alert = makePersonalizedInsight({
      kind: "alert",
      friendly_biomarker_label: "Colesterol LDL",
    });
    const watch = makePersonalizedInsight({
      kind: "watch",
      avatar_variant: "yellow",
      severity: "LOW",
      // Unique label so it's identifiable when the Vigilar tab is active
      friendly_biomarker_label: "Glucosa en ayunas",
    });
    await mockScanBarcode(
      mockedPage,
      makeScanResponse({ personalized_insights: [alert, watch] }),
    );
    await mockedPage.goto(`/scan/${NUTELLA_BARCODE}`);

    await expect(mockedPage.getByRole("button", { name: /alertas \(1\)/i })).toBeVisible();
    await expect(mockedPage.getByRole("button", { name: /vigilar \(1\)/i })).toBeVisible();

    // Switch to Vigilar tab and verify the watch insight's biomarker label renders
    await mockedPage.getByRole("button", { name: /vigilar \(1\)/i }).click();
    await expect(mockedPage.getByText("Glucosa en ayunas")).toBeVisible();
  });

  test("edge — BGE-M3 re-ranking: multiple affecting_ingredients render as pills", async ({ mockedPage }) => {
    await mockScanBarcode(mockedPage, makeOrangeBiomarkerScan());
    await mockedPage.goto(`/scan/${NUTELLA_BARCODE}`);

    await expect(mockedPage.getByLabel(/Semáforo/i)).toBeVisible();
    await expect(mockedPage.getByText("Grasas trans").first()).toBeVisible();
    await expect(mockedPage.getByText("Aceite de palma").first()).toBeVisible();
    await expect(mockedPage.getByText(/tu LDL está/i)).toBeVisible();
  });

  test("edge — BiomarkerEmptyState shows link to /biosync when no biomarkers", async ({ mockedPage }) => {
    await mockScanBarcode(mockedPage, makeScanResponse({ personalized_insights: [] }));
    await mockedPage.goto(`/scan/${NUTELLA_BARCODE}`);

    const biosyncLink = mockedPage.getByRole("link", { name: /ir a biosync/i });
    await expect(biosyncLink).toBeVisible();
    await expect(biosyncLink).toHaveAttribute("href", /\/biosync$/);
  });
});
