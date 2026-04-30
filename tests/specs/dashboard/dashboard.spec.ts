import {
  test,
  expect,
  mockBiosyncStatus,
  mockScanHistory,
  makeBiomarkerStatus,
  makeScanHistoryEntry,
} from "../../fixtures";

test.describe("Feature: Dashboard", () => {
  test("happy path — populated dashboard shows biomarker card and recent scans", async ({ mockedPage }) => {
    await mockBiosyncStatus(mockedPage, makeBiomarkerStatus({ has_data: true }));
    await mockScanHistory(mockedPage, [
      makeScanHistoryEntry({ id: "s1", product_name: "Producto Alpha", semaphore: "YELLOW" }),
      makeScanHistoryEntry({ id: "s2", product_name: "Producto Beta", semaphore: "RED" }),
    ]);
    await mockedPage.goto("/");

    await expect(mockedPage.getByText(/biomarcadores activos/i)).toBeVisible();
    await expect(mockedPage.getByText("Producto Alpha")).toBeVisible();
    await expect(mockedPage.getByText("Producto Beta")).toBeVisible();
  });

  test("edge — empty dashboard shows welcome CTAs", async ({ mockedPage }) => {
    // applyDefaultMocks already provides 404 biosync + empty history
    await mockedPage.goto("/");

    await expect(mockedPage.getByText(/sin scans aún/i)).toBeVisible();
    await expect(mockedPage.getByRole("link", { name: /escanear producto/i }).first()).toBeVisible();
  });

  test("edge — biomarker expiring in <30 days shows amber warning", async ({ mockedPage }) => {
    const expiresIn14Days = new Date();
    expiresIn14Days.setDate(expiresIn14Days.getDate() + 14);

    await mockBiosyncStatus(
      mockedPage,
      makeBiomarkerStatus({
        has_data: true,
        expires_at: expiresIn14Days.toISOString(),
      }),
    );
    await mockedPage.goto("/");

    await expect(mockedPage.getByText(/caducan en|días/i)).toBeVisible();
  });
});
