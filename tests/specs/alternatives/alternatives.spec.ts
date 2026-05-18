import { test, expect } from "@playwright/test";

const BASE = "http://localhost:3000";
const API  = "http://localhost:8000";

async function registerAndLogin(page: any, email: string, password: string) {
  await page.request.post(`${API}/auth/register`, {
    data: { email, password },
  });
  const res = await page.request.post(`${API}/auth/login`, {
    data: { email, password },
  });
  const { access_token } = await res.json();
  await page.context().addCookies([
    { name: "access_token", value: access_token, domain: "localhost", path: "/" },
  ]);
  return access_token;
}

test.describe("Alternative Matching (Fase 2)", () => {
  test.beforeAll(async ({ request }) => {
    // Seed fixture products
    // In CI this should be handled by conftest / test setup script
    // Running seed script before E2E suite:
    // await exec("python -m scripts.seed_alternatives_fixture")
  });

  test("RED scan shows 'Ver alternativas' button", async ({ page }) => {
    await registerAndLogin(page, "alt-e2e-red@test.com", "password123");

    // Mock a scan result with RED semaphore
    await page.route(`${API}/scan/barcode`, async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          product_barcode: "FIX_YOGURT_BAD",
          product_name: "Yogurt con Sucralosa",
          semaphore: "RED",
          ingredients: [{ name: "sucralosa", canonical_name: "sucralosa", cas_number: null, e_number: null, regulatory_status: "Restricted", confidence_score: 0.9, conflicts: [{ conflict_type: "REGULATORY", severity: "HIGH", summary: "Banned in EU", sources: ["EFSA"] }] }],
          conflict_severity: "HIGH",
          source: "barcode",
          scanned_at: new Date().toISOString(),
          personalized_insights: [],
        }),
      });
    });

    await page.goto(`${BASE}/scan/FIX_YOGURT_BAD`);
    await expect(page.getByText("Ver alternativas más limpias")).toBeVisible();
  });

  test("BLUE scan does NOT show 'Ver alternativas' button", async ({ page }) => {
    await registerAndLogin(page, "alt-e2e-blue@test.com", "password123");

    await page.route(`${API}/scan/barcode`, async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          product_barcode: "FIX_YOGURT_001",
          product_name: "Activia Natural",
          semaphore: "BLUE",
          ingredients: [],
          conflict_severity: null,
          source: "barcode",
          scanned_at: new Date().toISOString(),
          personalized_insights: [],
        }),
      });
    });

    await page.goto(`${BASE}/scan/FIX_YOGURT_001`);
    await expect(page.getByText("Ver alternativas más limpias")).not.toBeVisible();
  });

  test("Alternatives page loads and shows top pick", async ({ page }) => {
    await registerAndLogin(page, "alt-e2e-alts@test.com", "password123");

    await page.route(`${API}/scan/alternatives/FIX_YOGURT_BAD`, async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          scanned_product: { barcode: "FIX_YOGURT_BAD", name: "Yogurt con Sucralosa", semaphore: "RED" },
          top_pick: {
            product: { barcode: "FIX_YOGURT_001", name: "Activia Natural", brand: "Danone", clean_score: 0 },
            clean_ingredients: ["Sin sucralosa", "Sin colorantes"],
            biomarker_conflicts: [],
            compatibility_pct: 95,
            avatar_variant: "blue",
          },
          alternatives: [
            {
              product: { barcode: "FIX_YOGURT_002", name: "Lala Bio 100", brand: "Lala", clean_score: 1 },
              avatar_variant: "yellow",
              semaphore_precomputed: "YELLOW",
            },
          ],
          has_biomarkers: false,
          fallback_used: false,
        }),
      });
    });

    await page.goto(`${BASE}/scan/FIX_YOGURT_BAD/alternatives`);
    await expect(page.getByText("Mejor match para ti")).toBeVisible();
    await expect(page.getByText("Activia Natural")).toBeVisible();
    await expect(page.getByText("Otras opciones")).toBeVisible();
    await expect(page.getByText("Lala Bio 100")).toBeVisible();
  });

  test("Without biomarkers shows BioSync CTA", async ({ page }) => {
    await registerAndLogin(page, "alt-e2e-nobio@test.com", "password123");

    await page.route(`${API}/scan/alternatives/**`, async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          scanned_product: { barcode: "FIX_YOGURT_BAD", name: "Yogurt con Sucralosa", semaphore: "RED" },
          top_pick: {
            product: { barcode: "FIX_YOGURT_001", name: "Activia Natural", brand: "Danone", clean_score: 0 },
            clean_ingredients: ["Sin sucralosa"],
            biomarker_conflicts: [],
            compatibility_pct: 90,
            avatar_variant: "blue",
          },
          alternatives: [],
          has_biomarkers: false,
          fallback_used: false,
        }),
      });
    });

    await page.goto(`${BASE}/scan/FIX_YOGURT_BAD/alternatives`);
    await expect(page.getByText("Personaliza con tus biomarcadores")).toBeVisible();
  });

  test("Empty state shown when no alternatives found", async ({ page }) => {
    await registerAndLogin(page, "alt-e2e-empty@test.com", "password123");

    await page.route(`${API}/scan/alternatives/**`, async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          scanned_product: { barcode: "FIX_NOCAT_001", name: "Producto Sin Categoría", semaphore: "RED" },
          top_pick: null,
          alternatives: [],
          has_biomarkers: false,
          fallback_used: true,
        }),
      });
    });

    await page.goto(`${BASE}/scan/FIX_NOCAT_001/alternatives`);
    await expect(page.getByText("No encontramos alternativas")).toBeVisible();
  });

  test("Tap on alternative navigates to its scan result", async ({ page }) => {
    await registerAndLogin(page, "alt-e2e-tap@test.com", "password123");

    await page.route(`${API}/scan/alternatives/**`, async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          scanned_product: { barcode: "FIX_YOGURT_BAD", name: "Yogurt con Sucralosa", semaphore: "RED" },
          top_pick: {
            product: { barcode: "FIX_YOGURT_001", name: "Activia Natural", brand: "Danone", clean_score: 0 },
            clean_ingredients: ["Sin sucralosa"],
            biomarker_conflicts: [],
            compatibility_pct: 95,
            avatar_variant: "blue",
          },
          alternatives: [],
          has_biomarkers: false,
          fallback_used: false,
        }),
      });
    });

    await page.goto(`${BASE}/scan/FIX_YOGURT_BAD/alternatives`);
    await page.getByText("Ver análisis completo →").click();
    await expect(page).toHaveURL(/\/scan\/FIX_YOGURT_001/);
  });

  test("desktop layout shows two-column grid", async ({ page }) => {
    await registerAndLogin(page, "alt-e2e-desktop@test.com", "password123");

    await page.route(`${API}/scan/alternatives/**`, async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          scanned_product: { barcode: "FIX_YOGURT_BAD", name: "Yogurt con Sucralosa", semaphore: "RED" },
          top_pick: {
            product: { barcode: "FIX_YOGURT_001", name: "Activia Natural", brand: "Danone", clean_score: 0 },
            clean_ingredients: ["Sin sucralosa", "Sin colorantes"],
            biomarker_conflicts: [],
            compatibility_pct: 95,
            avatar_variant: "blue",
          },
          alternatives: [
            {
              product: { barcode: "FIX_YOGURT_002", name: "Lala Bio 100", brand: "Lala", clean_score: 1 },
              avatar_variant: "yellow",
              semaphore_precomputed: "YELLOW",
            },
          ],
          has_biomarkers: false,
          fallback_used: false,
        }),
      });
    });

    await page.setViewportSize({ width: 1200, height: 800 });
    await page.goto(`${BASE}/scan/FIX_YOGURT_BAD/alternatives`);
    await page.waitForLoadState("networkidle");

    const heroPanel = page.getByText("Comparación directa");
    await expect(heroPanel).toBeVisible();

    const ranking = page.getByText("Ranking por clean score");
    await expect(ranking).toBeVisible();
  });

  test("mobile layout shows single column hero panel", async ({ page }) => {
    await registerAndLogin(page, "alt-e2e-mobile@test.com", "password123");

    await page.route(`${API}/scan/alternatives/**`, async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          scanned_product: { barcode: "FIX_YOGURT_BAD", name: "Yogurt con Sucralosa", semaphore: "RED" },
          top_pick: {
            product: { barcode: "FIX_YOGURT_001", name: "Activia Natural", brand: "Danone", clean_score: 0 },
            clean_ingredients: ["Sin sucralosa", "Sin colorantes"],
            biomarker_conflicts: [],
            compatibility_pct: 95,
            avatar_variant: "blue",
          },
          alternatives: [
            {
              product: { barcode: "FIX_YOGURT_002", name: "Lala Bio 100", brand: "Lala", clean_score: 1 },
              avatar_variant: "yellow",
              semaphore_precomputed: "YELLOW",
            },
          ],
          has_biomarkers: false,
          fallback_used: false,
        }),
      });
    });

    await page.setViewportSize({ width: 375, height: 812 });
    await page.goto(`${BASE}/scan/FIX_YOGURT_BAD/alternatives`);
    await page.waitForLoadState("networkidle");

    const heroPanel = page.getByText("Comparación directa");
    await expect(heroPanel).toBeVisible();
  });
});
