import {
  test,
  expect,
  mockBiosyncStatus,
  mockScanHistory,
  makeBiomarkerStatus,
  makeScanHistoryEntry,
} from "../../fixtures";

test.describe("Feature: Dashboard", () => {
  test("happy path — orb CTA links to /scan", async ({ mockedPage }) => {
    await mockBiosyncStatus(mockedPage, makeBiomarkerStatus({ has_data: false }));
    await mockScanHistory(mockedPage, []);
    await mockedPage.goto("/home");

    const orbLink = mockedPage.getByRole("link", { name: /escanear producto/i }).first();
    await expect(orbLink).toBeVisible();
    await expect(orbLink).toHaveAttribute("href", "/scan");
  });

  test("happy path — populated dashboard shows biomarker card and recent scans", async ({ mockedPage }) => {
    await mockBiosyncStatus(mockedPage, makeBiomarkerStatus({ has_data: true }));
    await mockScanHistory(mockedPage, [
      makeScanHistoryEntry({ id: "s1", product_name: "Producto Alpha", semaphore: "YELLOW" }),
      makeScanHistoryEntry({ id: "s2", product_name: "Producto Beta", semaphore: "RED" }),
    ]);
    await mockedPage.goto("/home");

    await expect(mockedPage.getByText(/biomarcadores activos/i)).toBeVisible();
    await expect(mockedPage.getByText("Producto Alpha")).toBeVisible();
    await expect(mockedPage.getByText("Producto Beta")).toBeVisible();
  });

  test("edge — empty history shows empty state message", async ({ mockedPage }) => {
    await mockBiosyncStatus(mockedPage, makeBiomarkerStatus({ has_data: false }));
    await mockScanHistory(mockedPage, []);
    await mockedPage.goto("/home");

    await expect(mockedPage.getByText(/escanea tu primer producto/i)).toBeVisible();
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
    await mockScanHistory(mockedPage, []);
    await mockedPage.goto("/home");

    await expect(mockedPage.getByText(/14d/i).first()).toBeVisible();
  });

  test("edge — bottom nav visible on mobile viewport", async ({ mockedPage }) => {
    await mockedPage.setViewportSize({ width: 390, height: 844 });
    await mockBiosyncStatus(mockedPage, makeBiomarkerStatus({ has_data: false }));
    await mockScanHistory(mockedPage, []);
    await mockedPage.goto("/home");

    await expect(mockedPage.getByRole("navigation", { name: /bottom/i })).toBeVisible();
  });

  test("edge — bottom nav hidden on desktop viewport", async ({ mockedPage }) => {
    await mockedPage.setViewportSize({ width: 1280, height: 900 });
    await mockBiosyncStatus(mockedPage, makeBiomarkerStatus({ has_data: false }));
    await mockScanHistory(mockedPage, []);
    await mockedPage.goto("/home");

    await expect(mockedPage.getByRole("navigation", { name: /bottom/i })).toBeHidden();
  });
});
