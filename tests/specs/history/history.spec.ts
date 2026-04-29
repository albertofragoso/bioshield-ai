import {
  test,
  expect,
  mockScanHistory,
  makeScanHistoryEntry,
} from "../../fixtures";

test.describe("Feature: History", () => {
  test("happy path — entries grouped by day (Hoy and Ayer)", async ({ mockedPage }) => {
    const todayISO = new Date().toISOString();
    const yesterdayISO = new Date(Date.now() - 86_400_000).toISOString();

    await mockScanHistory(mockedPage, [
      makeScanHistoryEntry({
        id: "h1",
        product_name: "Hoy producto",
        semaphore: "YELLOW",
        scanned_at: todayISO,
      }),
      makeScanHistoryEntry({
        id: "h2",
        product_name: "Ayer producto",
        semaphore: "ORANGE",
        scanned_at: yesterdayISO,
      }),
    ]);
    await mockedPage.goto("/history");

    await expect(mockedPage.getByText(/^Hoy$/i)).toBeVisible();
    await expect(mockedPage.getByText(/^Ayer$/i)).toBeVisible();
    await expect(mockedPage.getByText("Hoy producto")).toBeVisible();
    await expect(mockedPage.getByText("Ayer producto")).toBeVisible();
  });

  test("edge — clicking RED filter pill narrows results to red entries only", async ({ mockedPage }) => {
    await mockScanHistory(mockedPage, [
      makeScanHistoryEntry({ id: "r1", product_name: "Rojo peligroso", semaphore: "RED" }),
      makeScanHistoryEntry({ id: "y1", product_name: "Amarillo ok", semaphore: "YELLOW" }),
    ]);
    await mockedPage.goto("/history");

    await mockedPage.getByRole("button", { name: /RED/i }).click();

    await expect(mockedPage.getByText("Rojo peligroso")).toBeVisible();
    await expect(mockedPage.getByText("Amarillo ok")).not.toBeVisible();
  });

  test("edge — search input filters entries by product_name", async ({ mockedPage }) => {
    await mockScanHistory(mockedPage, [
      makeScanHistoryEntry({ id: "n1", product_name: "Nutella" }),
      makeScanHistoryEntry({ id: "c1", product_name: "Coca-Cola" }),
    ]);
    await mockedPage.goto("/history");

    await mockedPage.getByPlaceholder(/buscar por producto/i).fill("nut");

    await expect(mockedPage.getByText("Nutella")).toBeVisible();
    await expect(mockedPage.getByText("Coca-Cola")).not.toBeVisible();
  });

  test("edge — empty history shows welcome empty state", async ({ mockedPage }) => {
    await mockScanHistory(mockedPage, []);
    await mockedPage.goto("/history");

    await expect(mockedPage.getByText(/sin escaneos aún/i)).toBeVisible();
  });

  test("edge — active filter with no matching entries shows filtered empty state", async ({ mockedPage }) => {
    await mockScanHistory(mockedPage, [
      makeScanHistoryEntry({ id: "y1", semaphore: "YELLOW" }),
    ]);
    await mockedPage.goto("/history");

    await mockedPage.getByRole("button", { name: /RED/i }).click();

    await expect(mockedPage.getByText(/sin resultados para este filtro/i)).toBeVisible();
  });
});
