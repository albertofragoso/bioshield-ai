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
    const alert = makePersonalizedInsight({ kind: "alert", friendly_title: "Alerta de LDL" });
    const watch = makePersonalizedInsight({
      kind: "watch",
      avatar_variant: "yellow",
      severity: "LOW",
      friendly_title: "Vigilancia glucosa",
    });
    await mockScanBarcode(
      mockedPage,
      makeScanResponse({ personalized_insights: [alert, watch] }),
    );
    await mockedPage.goto(`/scan/${NUTELLA_BARCODE}`);

    await expect(mockedPage.getByRole("button", { name: /alertas \(1\)/i })).toBeVisible();
    await expect(mockedPage.getByRole("button", { name: /vigilar \(1\)/i })).toBeVisible();

    await mockedPage.getByRole("button", { name: /vigilar \(1\)/i }).click();
    await expect(mockedPage.getByText("Vigilancia glucosa")).toBeVisible();
  });

  test("edge — BGE-M3 re-ranking: multiple affecting_ingredients render as pills", async ({ mockedPage }) => {
    await mockScanBarcode(mockedPage, makeOrangeBiomarkerScan());
    await mockedPage.goto(`/scan/${NUTELLA_BARCODE}`);

    await expect(mockedPage.getByLabel(/Semáforo/i)).toBeVisible();
    await expect(mockedPage.getByText("Grasas trans")).toBeVisible();
    await expect(mockedPage.getByText("Aceite de palma")).toBeVisible();
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
