import path from "node:path";
import {
  test,
  expect,
  mockBiosyncExtract,
  mockBiosyncExtractError,
  mockBiosyncUpload,
  mockBiosyncStatus,
  mockBiosyncDelete,
  makeBiomarker,
  makeBiomarkerExtraction,
  makeBiomarkerStatus,
} from "../../fixtures";

const PDF_FIXTURE = path.resolve(__dirname, "../../fixtures/files/biomarkers.pdf");

test.describe("Feature: Biosync PDF flow", () => {
  test("happy path — upload PDF → extract → review → confirm → toast → redirect /", async ({ mockedPage }) => {
    await mockBiosyncStatus(mockedPage, null);
    await mockBiosyncExtract(
      mockedPage,
      makeBiomarkerExtraction({
        biomarkers: [makeBiomarker({ name: "ldl", value: 150, classification: "high" })],
      }),
    );
    await mockBiosyncUpload(mockedPage, makeBiomarkerStatus({ has_data: true }));
    await mockedPage.goto("/biosync");

    await mockedPage.locator('input[type="file"]').setInputFiles(PDF_FIXTURE);

    // Review state
    await expect(
      mockedPage.getByRole("heading", { name: /revisa los valores extraídos/i }),
    ).toBeVisible();

    await mockedPage.getByRole("button", { name: /confirmar y guardar/i }).click();

    await expect(mockedPage.getByText(/biomarcadores guardados/i)).toBeVisible();
    await expect(mockedPage).toHaveURL("/");
  });

  test("edge — edited value in review state is sent in upload request", async ({ mockedPage }) => {
    await mockBiosyncStatus(mockedPage, null);
    await mockBiosyncExtract(
      mockedPage,
      makeBiomarkerExtraction({ biomarkers: [makeBiomarker({ value: 95 })] }),
    );

    let uploadedValue: number | null = null;
    await mockedPage.route("**/biosync/upload", async (route) => {
      const body = JSON.parse((route.request().postData() ?? "{}") as string);
      uploadedValue = (body as { biomarkers: { value: number }[] }).biomarkers[0].value;
      return route.fulfill({
        status: 201,
        contentType: "application/json",
        body: JSON.stringify(makeBiomarkerStatus({ has_data: true })),
      });
    });

    await mockedPage.goto("/biosync");
    await mockedPage.locator('input[type="file"]').setInputFiles(PDF_FIXTURE);
    await expect(
      mockedPage.getByRole("heading", { name: /revisa los valores extraídos/i }),
    ).toBeVisible();

    const numberInput = mockedPage.locator('input[type="number"]').first();
    await numberInput.fill("180");
    await mockedPage.getByRole("button", { name: /confirmar y guardar/i }).click();

    await expect.poll(() => uploadedValue).toBe(180);
  });

  test("edge — active status shows banner with expiry date", async ({ mockedPage }) => {
    await mockBiosyncStatus(
      mockedPage,
      makeBiomarkerStatus({ has_data: true, expires_at: "2026-10-25T12:00:00Z" }),
    );
    await mockedPage.goto("/biosync");

    await expect(mockedPage.getByText(/ya tienes biomarcadores activos/i)).toBeVisible();
    await expect(mockedPage.getByText(/expiran el/i)).toBeVisible();
  });

  test("edge — delete dialog confirms and shows success toast", async ({ mockedPage }) => {
    let deleted = false;
    await mockedPage.route("**/biosync/data", async (route) => {
      deleted = true;
      await route.fulfill({ status: 204 });
    });
    await mockBiosyncStatus(mockedPage, makeBiomarkerStatus({ has_data: true }));
    await mockedPage.goto("/biosync");

    await mockedPage.getByRole("button", { name: /eliminar/i }).first().click();
    await mockedPage.getByRole("button", { name: /^eliminar$/i }).last().click();

    await expect.poll(() => deleted).toBe(true);
    await expect(mockedPage.getByText(/biomarcadores eliminados/i)).toBeVisible();
  });

  test("error — 413 PDF too large shows toast", async ({ mockedPage }) => {
    await mockBiosyncStatus(mockedPage, null);
    await mockBiosyncExtractError(mockedPage, 413);
    await mockedPage.goto("/biosync");

    await mockedPage.locator('input[type="file"]').setInputFiles(PDF_FIXTURE);
    await expect(mockedPage.getByText(/pdf demasiado grande/i)).toBeVisible();
  });

  test("error — 422 invalid PDF shows toast", async ({ mockedPage }) => {
    await mockBiosyncStatus(mockedPage, null);
    await mockBiosyncExtractError(mockedPage, 422);
    await mockedPage.goto("/biosync");

    await mockedPage.locator('input[type="file"]').setInputFiles(PDF_FIXTURE);
    await expect(mockedPage.getByText(/archivo inválido/i)).toBeVisible();
  });
});
