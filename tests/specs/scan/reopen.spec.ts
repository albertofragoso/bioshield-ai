import {
  test,
  expect,
  mockScanResultGet,
  makeScanResponse,
  makePersonalizedInsight,
  NUTELLA_BARCODE,
} from "../../fixtures";

test.describe("Feature: Scan reopen", () => {
  test("happy path — direct navigation calls GET not POST", async ({ mockedPage }) => {
    let postCalled = false;
    await mockedPage.route("**/scan/barcode", async (route) => {
      postCalled = true;
      await route.continue();
    });

    const scanResponse = makeScanResponse();
    await mockScanResultGet(mockedPage, scanResponse);

    await mockedPage.goto(`/scan/${NUTELLA_BARCODE}`);
    await expect(mockedPage.getByLabel(/Semáforo/i)).toBeVisible();

    expect(postCalled).toBe(false);
  });

  test("edge — personalized insights render on direct navigation", async ({ mockedPage }) => {
    const alert = makePersonalizedInsight({ kind: "alert" });
    const scanResponse = makeScanResponse({ personalized_insights: [alert] });
    await mockScanResultGet(mockedPage, scanResponse);

    await mockedPage.goto(`/scan/${NUTELLA_BARCODE}`);

    await expect(mockedPage.getByRole("button", { name: /alertas \(1\)/i })).toBeVisible();
  });
});
